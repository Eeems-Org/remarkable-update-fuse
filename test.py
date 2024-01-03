import os
import sys

from hashlib import md5
from remarkable_update_fuse import UpdateImage
from remarkable_update_fuse import UpdateImageSignatureException
from remarkable_update_fuse.ext4.struct import to_hex
from remarkable_update_fuse import ext4
from remarkable_update_fuse.ext4 import ChecksumError
from remarkable_update_fuse.ext4 import SymbolicLink

failed = False


def assert_byte(offset, byte):
    global failed
    reader.seek(offset)
    data = reader.read(1)
    print(f"checking offset {offset:08X} is {to_hex(byte)}: ", end="")
    if len(data) != 1:
        print("fail")
        failed = True
        print(f"  Error: {len(data)} bytes returned, only 1 expected: {to_hex(data)}")
        return

    if data != byte:
        print("fail")
        failed = True
        print(f"  Error: Data returned is {to_hex(data)}")
        return

    print("pass")


def assert_exists(path):
    global volume
    print(f"checking that {path} exists: ", end="")
    try:
        volume.inode_at(path)
        print("pass")
    except FileNotFoundError:
        print("fail")
        failed = True


def assert_hash(expected_hash, path):
    global failed
    print(f"checking {path} md5sum is {expected_hash}: ", end="")
    inode = volume.inode_at(path)
    actual_hash = md5(inode.open().read()).hexdigest()
    if actual_hash != expected_hash:
        print("fail")
        print(f"  Error: Hash returned is {actual_hash}")
        failed = True
        return

    print("pass")


def assert_symlink_to(path, symlink):
    assert isinstance(symlink, bytes)
    global failed
    print(f"checking {path} is symlink to {symlink}: ", end="")
    inode = volume.inode_at(path)
    if not isinstance(inode, SymbolicLink):
        print("fail")
        failed = True
        print(f"  Error: Inode is not symlink: {inode}")
        return

    data = inode.readlink()
    if data != symlink:
        print("fail")
        print(f"  Error: symlink is actually to {data}")
        failed = True
        return

    print("pass")


image = UpdateImage(".venv/2.15.1.1189_reMarkable2-wVbHkgKisg-.signed")
volume = ext4.Volume(image)
print(f"validating {volume.uuid}: ", end="")
try:
    volume.root.validate()
    print("pass")

except ChecksumError:
    print("fail")
    failed = True

print("checking image signature: ", end="")
try:
    image.verify(
        volume.inode_at("/usr/share/update_engine/update-payload-key.pub.pem")
        .open()
        .read()
    )
    print("pass")
except UpdateImageSignatureException:
    print("fail")

inode = volume.inode_at("/bin/bash.bash")
reader = inode.open()

# Make sure that we aren't reading zeros where there should be a larger block of data
assert_byte(0x00020000, b"\x0c")
assert_byte(0x00020001, b"\x60")
assert_byte(0x00020002, b"\x9d")

# Make sure we return a non-zero where a kernel loopback would return data
assert_byte(0x000BBFFF, b"\xe5")
assert_byte(0x000BC000, b"\x54")

assert_exists("/bin/bash.bash")
assert_exists("/uboot-version")
assert_exists("/home/root")
assert_hash("f33ff883cb5c36aa7ec7f5f4c1e24133", "/uboot-version")
assert_hash("68f0a9db4c3cfce9e96c82250587fe1b", "/bin/bash.bash")
assert_hash(
    "6a67b9873c57fbb8589ef4a4f744beb3",
    "/usr/share/update_engine/update-payload-key.pub.pem",
)
print("checking / contents: ", end="")
print(
    "pass"
    if [
        ".",
        "..",
        "lost+found",
        "bin",
        "boot",
        "dev",
        "etc",
        "home",
        "lib",
        "media",
        "mnt",
        "postinst",
        "proc",
        "run",
        "sbin",
        "sys",
        "tmp",
        "uboot-postinst",
        "uboot-version",
        "usr",
        "var",
    ]
    == [d.name_str for d, _ in volume.root.opendir()]
    else "fail"
)
assert_symlink_to("/bin/ash", b"/bin/busybox.nosuid")

if failed:
    sys.exit(1)
