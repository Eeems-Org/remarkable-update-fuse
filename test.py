from remarkable_update_fuse import UpdateImage
from ext4 import Volume

volume = Volume(UpdateImage(".venv/2.15.1.1189_reMarkable2-wVbHkgKisg-.signed"))
inode = volume.root.get_inode("bin", "bash.bash")
reader = inode.open_read()


def to_hex(data):
    return "".join([f"{x:X}" for x in data])


def Assert(byte):
    data = reader.read(1)
    if len(data) != 1:
        raise Exception(
            f"{len(data)} bytes returned, only 1 expected: 0x{to_hex(data)}"
        )

    if data != byte:
        raise Exception(f"0x{to_hex(data)} != 0x{to_hex(byte)}")


# Make sure that we aren't reading zeros where there should be a larger block of data
reader.seek(0x00020000)
Assert(b"\x0c")
Assert(b"\x60")
Assert(b"\x9d")

# Make sure we return a non-zero where a kernel loopback would return data
reader.seek(0x000BBFFF)
Assert(b"\xe5")
