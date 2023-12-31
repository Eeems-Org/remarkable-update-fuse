import os
import sys

from ext4 import Volume
from hashlib import md5
from remarkable_update_fuse import UpdateImage
from remarkable_update_fuse import UpdateImageSignatureException

failed = False


def to_hex(data):
    return "0x" + "".join([f"{x:02X}" for x in data])


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


def assert_hash(expected_hash, *path):
    global failed
    print(f"checking {os.path.join(*path)} md5sum is {expected_hash}: ", end="")
    inode = volume.root.get_inode(*path)
    actual_hash = md5(inode.open_read().read()).hexdigest()
    if actual_hash != expected_hash:
        print("fail")
        print(f"  Error: Hash returned is {actual_hash}")
        failed = True
        return

    print("pass")


image = UpdateImage(".venv/2.15.1.1189_reMarkable2-wVbHkgKisg-.signed")
volume = Volume(image)
print("checking image signature: ", end="")
try:
    image.verify(
        volume.root.get_inode(
            "usr", "share", "update_engine", "update-payload-key.pub.pem"
        )
        .open_read()
        .read()
    )
    print("pass")
except VerificationError:
    print("fail")

inode = volume.root.get_inode("bin", "bash.bash")
reader = inode.open_read()

# Make sure that we aren't reading zeros where there should be a larger block of data
assert_byte(0x00020000, b"\x0c")
assert_byte(0x00020001, b"\x60")
assert_byte(0x00020002, b"\x9d")


def fn():
    with open(".venv/2.15.1.1189_reMarkable2-wVbHkgKisg-.ext4", "rb") as f:
        volume = Volume(f)
        inode = volume.root.get_inode("bin", "bash.bash")
        reader = inode.open_read()
        reader.seek(0x000BBFFF)
        block_index = reader.cursor // volume.block_size
        block_offset = reader.get_block_mapping(block_index) * volume.block_size
        offset = block_offset + (reader.cursor % volume.block_size)
        f.seek(volume.offset + offset)
        print(f"  Info: Direct read: {to_hex(f.read(1))}")
        print(f"  Info: Volume read: {to_hex(volume.read(offset, 1))}")


# Make sure we return a non-zero where a kernel loopback would return data
assert_byte(0x000BBFFF, b"\xe5")
fn()
assert_byte(0x000BC000, b"\x54")

assert_hash("68f0a9db4c3cfce9e96c82250587fe1b", "bin", "bash.bash")


if failed:
    sys.exit(1)
