import errno
import os
import queue
import sys
import threading
import time
import warnings

import ext4
import fuse

from .image import UpdateImage
from .image import UpdateImageSignatureException
from .threads import KillableThread

# from .ext4 import Ext4Filesystem

fuse.fuse_python_api = (0, 2)


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
    disable_path_cache = False
    cache_debug = False
    cache_size = 500
    cache_ttl = 60

    image = None
    volume = None
    inode_cache = {}
    queue = None
    exit_threads = False

    def __init__(self, *args, **kw):
        fuse.Fuse.__init__(
            self,
            *args,
            fuse_args=FuseArgs(),
            parser_class=FuseOptParse,
            **kw,
        )
        self.parser.add_option(
            mountopt="disable_path_cache",
            action="store_true",
            help="Disable path caching",
        )
        self.parser.add_option(
            mountopt="cache_debug",
            action="store_true",
            help="Debug output for path caching",
        )
        self.parser.add_option(
            mountopt="cache_size",
            default=500,
            type="int",
            help="Size in MB of memory cache for speeding up filesytem access [default: %default]",
        )
        self.parser.add_option(
            mountopt="cache_ttl",
            default=60,
            type="int",
            help="Seconds before the memory cache will evict unused chunks [default: %default]",
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

        self.image = UpdateImage(
            self.update_file,
            cache_size=self.cache_size,
            cache_ttl=self.cache_ttl,
        )
        self.volume = ext4.Volume(self.image, offset=0)
        print("Verifying signature...")
        try:
            self.image.verify(
                self.get_inode("/usr/share/update_engine/update-payload-key.pub.pem")
                .open_read()
                .read()
            )
        except UpdateImageSignatureException:
            warnings.warn("Signature doesn't match contents", RuntimeWarning)

        threads = self.start_cache_threads()
        fuse.Fuse.main(self, args)
        self.exit_threads = True
        _ = [t.kill() for t in threads]
        _ = [t.join() for t in threads]

    def start_cache_threads(self):
        thread = KillableThread(
            target=self.expire_thread,
            args=(self,),
            name="cache-ttl",
        )
        thread.start()
        return [thread]

    @staticmethod
    def path_tuple(path):
        path = os.path.normpath(path)
        paths = tuple()
        if path == "/":
            return paths

        while True:
            split = os.path.split(path)
            path = split[0]
            if not split[1]:
                break

            paths = (split[1],) + paths

        return paths

    # Static as it's being started by threading.Thread
    @staticmethod
    def expire_thread(self):
        prev_usage = ""
        image = self.image
        while not self.exit_threads:
            if self.cache_debug:
                usage = image.cache.usage_str

            time.sleep(1)
            image.expire()
            if not self.cache_debug:
                continue

            if prev_usage == usage:
                continue

            prev_usage = usage
            print(f"[cache-ttl] {usage}")

    def get_inode(self, path):
        paths = UpdateFS.path_tuple(path)
        if not paths:
            return self.volume.root

        if self.disable_path_cache:
            inode = self.volume.root.get_inode(*paths)
            if inode is None:
                raise FileNotFoundError()

            return inode

        if paths not in self.inode_cache:
            inode = self.volume.root.get_inode(*paths)
            self.inode_cache[paths] = inode
            inode.verify()

        inode = self.inode_cache[paths]
        if inode is None:
            raise FileNotFoundError()

        return inode

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

    def readlink(self, path):
        try:
            inode = self.get_inode(path)
            if not inode.is_symlink:
                return path

            return inode.open_read().read().decode("utf-8")

        except FileNotFoundError:
            print(f"{path} not found")
            return -errno.ENOENT
