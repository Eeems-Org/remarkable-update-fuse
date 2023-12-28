import errno
import fuse
import os
import stat
import sys
import ext4

from optparse import OptionParser
from .image import UpdateImage

# from .ext4 import Ext4Filesystem

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
    image = None
    volume = None

    def __init__(self, *args, **kw):
        fuse.Fuse.__init__(
            self,
            *args,
            fuse_args=FuseArgs(),
            parser_class=FuseOptParse,
            **kw,
        )

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

        self.image = UpdateImage(self.update_file)
        self.volume = ext4.Volume(self.image, offset=0)
        fuse.Fuse.main(self, args)

    def get_inode(self, path):
        path = os.path.normpath(path)
        if path == "/":
            return self.volume.root

        paths = []
        while True:
            split = os.path.split(path)
            path = split[0]
            if not split[1]:
                break

            paths.insert(0, split[1])

        return self.volume.root.get_inode(*paths)

    def getattr(self, path):
        try:
            inode = self.get_inode(path)
            _stat = Stat()
            _stat.st_mode = inode.inode.i_mode
            _stat.st_ino = inode.inode.i_uid_lo
            _stat.st_nlink = inode.inode.i_links_count
            _stat.st_uid = inode.inode.i_uid_lo
            _stat.st_gid = inode.inode.i_gid_lo
            _stat.st_size = inode.inode.i_size_lo
            _stat.st_atime = inode.inode.i_atime
            _stat.st_mtime = inode.inode.i_mtime
            _stat.st_ctime = inode.inode.i_ctime
            return _stat
        except FileNotFoundError:
            return -errno.ENOENT

    def readdir(self, path, offset):
        try:
            inode = self.get_inode(path)
            for file_name, inode_idx, file_type in inode.open_dir():
                yield fuse.Direntry(file_name)

        except FileNotFoundError:
            print(f"{path} not found")
            return -errno.ENOENT

    def open(self, path, flags):
        try:
            inode = self.get_inode(path)
            if inode.is_dir:
                return -errno.EACCES

            mode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
            if (flags & mode) != os.O_RDONLY:
                return -errno.EACCES

        except FileNotFoundError:
            print(f"{path} not found")
            return -errno.ENOENT

    def read(self, path, size, offset):
        try:
            inode = self.get_inode(path)
            reader = inode.open_read()
            reader.seek(offset, os.SEEK_SET)
            return reader.read(size)

        except FileNotFoundError:
            print(f"{path} not found")
            return -errno.ENOENT
