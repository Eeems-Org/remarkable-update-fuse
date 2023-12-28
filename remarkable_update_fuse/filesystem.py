import bz2
import errno
import fuse
import os
import stat
import struct
import sys

from optparse import OptionParser
from .update_metadata_pb2 import DeltaArchiveManifest

fuse.fuse_python_api = (0, 2)

BLOCK_SIZE = 4096
IMAGE_PATH = "/image.ext4"


class ImageException(Exception):
    pass


class FuseArgs(fuse.FuseArgs):
    def __init__(self):
        fuse.FuseArgs.__init__(self)
        self.update_file = None

    def __str__(self):
        return (
            "\n".join(
                [
                    f"< {self.update_file} on {self.mountpoint}:",
                    f"  {self.modifiers}",
                    "  -o ",
                ]
            )
            + ",\n     ".join(self._str_core())
            + " >"
        )


class FuseOptParse(fuse.FuseOptParse):
    def __init__(self, *args, **kw):
        fuse.FuseOptParse.__init__(self, *args, **kw)

    def parse_args(self, args=None, values=None):
        _opts, _args = fuse.FuseOptParse.parse_args(self, args, values)
        if _args:
            self.fuse_args.update_file = os.path.realpath(_args.pop())
        return _opts, _args


class Stat(fuse.Stat):
    def __init__(self):
        self.st_mode = 0
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 0
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 0
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0


class UpdateFS(fuse.Fuse):
    version = "%prog " + fuse.__version__
    fusage = "%prog update_file mountpoint [options]"
    dash_s_do = "setsingle"
    update_size = -1
    manifest = None
    start_pos = -1
    image_size = 0

    def __init__(self, *args, **kw):
        fuse.Fuse.__init__(
            self,
            *args,
            fuse_args=FuseArgs(),
            parser_class=FuseOptParse,
            **kw,
        )

    def _read_image(self):
        with open(self.update_file, "rb") as f:
            magic = f.read(4)
            if magic != b"CrAU":
                self.fuse_error("Wrong header")

            major = struct.unpack(">Q", f.read(8))[0]
            if major != 1:
                self.fuse_error("Unsupported version")

            self.update_size = struct.unpack(">Q", f.read(8))[0]
            data = f.read(self.update_size)
            self.manifest = DeltaArchiveManifest.FromString(data)
            self.start_pos = f.tell()

        for chunk, offset, length, f in self.chunks:
            self.image_size += length

    @property
    def chunks(self):
        with open(self.update_file, "rb") as f:
            for chunk in self.manifest.install_operations:
                f.seek(self.start_pos + chunk.data_offset)
                dst_offset = chunk.dst_extents[0].start_block * BLOCK_SIZE
                dst_length = chunk.dst_extents[0].num_blocks * BLOCK_SIZE
                if chunk.type not in (0, 1):
                    self.fuse_error(f"Unsupported type {chunk.type}")

                yield chunk, dst_offset, dst_length, f

    @property
    def update_file(self):
        return self.fuse_args.update_file

    def fuse_error(self, msg):
        print(msg, file=sys.stderr)
        self.parser.print_help()
        sys.exit(1)

    def main(self, args=None):
        if self.update_file is None:
            self.fuse_error("fuse: missing update_file parameter")

        if not os.path.exists(self.update_file):
            self.fuse_error(f"fuse: File does not exist {self.update_file}")

        self._read_image()
        fuse.Fuse.main(self, args)

    def getattr(self, path):
        if path == "/":
            _stat = Stat()
            _stat.st_mode = stat.S_IFDIR | 0o755
            _stat.st_nlink = 2
            return _stat

        if path == IMAGE_PATH:
            _stat = Stat()
            _stat.st_mode = stat.S_IFREG | 0o444
            _stat.st_nlink = 1
            _stat.st_size = self.image_size
            return _stat

        return -errno.ENOENT

    def readdir(self, path, offset):
        for entry in (".", "..", IMAGE_PATH[1:]):
            yield fuse.Direntry(entry)

    def open(self, path, flags):
        if path != IMAGE_PATH:
            return -errno.ENOENT

        mode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & mode) != os.O_RDONLY:
            return -errno.EACCES

    def read(self, path, size, offset):
        if path != IMAGE_PATH:
            return -errno.ENOENT

        if offset >= self.image_size:
            return b""

        if offset + size > self.image_size:
            size = self.image_size - offset

        res = bytearray(size)
        d = f"{IMAGE_PATH}[{offset}:{offset + size}]"
        print(f"{d} read", file=sys.stderr)
        for chunk, chunk_offset, chunk_length, f in self.chunks:
            if offset < chunk_offset:
                continue
            if offset >= chunk_offset + chunk_length:
                continue

            chunk_data = f.read(chunk.data_length)
            if chunk.type == 1:
                try:
                    chunk_data = bz2.decompress(chunk_data)

                except ValueError as e:
                    print(f"{d} Error: {e}", file=sys.stderr)
                    return -errno.EIO

                if chunk_length - len(chunk_data) < 0:
                    print(
                        f"{d} Error: Compressed data was the wrong length {len(chunk_data)}",
                        file=sys.stderr,
                    )
                    return -errno.EIO

            chunk_start_offset = max(offset - chunk_offset, 0)
            chunk_end_offset = min(offset - chunk_offset + size, chunk_length - 1)
            data = chunk_data[chunk_start_offset:chunk_end_offset]
            print(
                f"{d} chunk [{chunk_start_offset}:{chunk_end_offset}]", file=sys.stderr
            )

            assert chunk_start_offset >= 0
            assert chunk_end_offset < chunk_length
            assert chunk_end_offset - chunk_start_offset == len(data)

            start_offset = chunk_offset + chunk_start_offset - offset
            end_offset = chunk_offset + chunk_end_offset - offset
            res[start_offset:end_offset] = data

            assert start_offset >= 0
            assert start_offset < len(res)
            assert end_offset < chunk_offset + chunk_length
            assert end_offset - start_offset == len(data)
            assert end_offset <= len(res)
            assert res[start_offset:end_offset] == data

        return bytes(res)
