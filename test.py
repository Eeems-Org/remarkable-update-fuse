import os
import sys
import ext4
import errno

from tempfile import TemporaryFile
from ext4 import ChecksumError
from ext4 import SymbolicLink
from ext4.struct import to_hex
from hashlib import md5
from hashlib import sha256
from remarkable_update_fuse import UpdateImage
from remarkable_update_fuse import UpdateImageSignatureException

FAILED = False


def assert_byte(offset, byte):
    global FAILED
    reader.seek(offset)
    data = reader.read(1)
    print(f"checking offset {offset:08X} is {to_hex(byte)}: ", end="")
    if len(data) != 1:
        print("fail")
        FAILED = True
        print(f"  Error: {len(data)} bytes returned, only 1 expected: {to_hex(data)}")
        return

    if data != byte:
        print("fail")
        FAILED = True
        print(f"  Error: Data returned is {to_hex(data)}")
        return

    print("pass")


def assert_raw_byte(offset, byte):
    global FAILED
    image.seek(offset)
    data = image.read(1)
    print(f"checking raw offset {offset:08X} is {to_hex(byte)}: ", end="")
    if len(data) != 1:
        print("fail")
        FAILED = True
        print(f"  Error: {len(data)} bytes returned, only 1 expected: {to_hex(data)}")
        return

    if data != byte:
        print("fail")
        FAILED = True
        print(f"  Error: Data returned is {to_hex(data)}")
        return

    print("pass")


def assert_exists(path):
    global FAILED
    print(f"checking that {path} exists: ", end="")
    try:
        volume.inode_at(path)
        print("pass")
    except FileNotFoundError:
        print("fail")
        FAILED = True


def assert_hash(expected_hash, path):
    global FAILED
    print(f"checking {path} md5sum is {expected_hash}: ", end="")
    inode = volume.inode_at(path)
    actual_hash = md5(inode.open().read()).hexdigest()
    if actual_hash != expected_hash:
        print("fail")
        print(f"  Error: Hash returned is {actual_hash}")
        FAILED = True
        return

    print("pass")


def assert_symlink_to(path, symlink):
    assert isinstance(symlink, bytes)
    global FAILED
    print(f"checking {path} is symlink to {symlink}: ", end="")
    inode = volume.inode_at(path)
    if not isinstance(inode, SymbolicLink):
        print("fail")
        FAILED = True
        print(f"  Error: Inode is not symlink: {inode}")
        return

    data = inode.readlink()
    if data != symlink:
        print("fail")
        print(f"  Error: symlink is actually to {data}")
        FAILED = True
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
    FAILED = True

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

print("checking block count is 278272: ", end="")
# If you remove the actual overhead it should actually be 276480
if volume.superblock.s_blocks_count != 278272:
    print("fail")
    print(f"  Error: {volume.superblock.s_blocks_count}")
    FAILED = True

else:
    print("pass")

print("checking free block count is 54420: ", end="")
if volume.superblock.s_free_blocks_count != 54420:
    print("fail")
    print(f"  Error: {volume.superblock.s_free_blocks_count}")
    FAILED = True

else:
    print("pass")

print("checking inode count is 34816: ", end="")
if volume.superblock.s_inodes_count != 34816:
    print("fail")
    print(f"  Error: {volume.superblock.s_inodes_count}")
    FAILED = True

else:
    print("pass")

print("checking free inode count is 26136: ", end="")
if volume.superblock.s_free_inodes_count != 26136:
    print("fail")
    print(f"  Error: {volume.superblock.s_free_inodes_count}")
    FAILED = True

else:
    print("pass")

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

print("checking path that contains file raises ENOTDIR: ", end="")
try:
    volume.inode_at("/uboot-version/test")
    print("fail")
    print("  No error raised")
    FAILED = True

except OSError as e:
    if e.errno == errno.ENOTDIR:
        print("pass")

    else:
        print("fail")
        FAILED = True
        print(f"  Unexpected error: {os.strerror(e)}")


print("checking writing full image to file: ", end="")
try:
    image.seek(0, os.SEEK_SET)
    with TemporaryFile(mode="wb") as f:
        digest = sha256(image.peek()).hexdigest()
        if "fc7d145e18f14a1a3f435f2fd5ca5924fe8dfe59bf45605dc540deed59551ae4" != digest:
            raise Exception(f"Incorrect digest: {digest}")

        f.write(image.peek())

    print("pass")

except Exception as e:
    FAILED = True
    print("fail")
    print("  ", end="")
    print(e)

# Make sure we aren't reading zeros in the raw image where there should be data
assert_raw_byte(0x00100000, b"\xa4")
assert_raw_byte(0x00100001, b"\x81")
assert_raw_byte(0x00100002, b"\x00")

if FAILED:
    sys.exit(1)
