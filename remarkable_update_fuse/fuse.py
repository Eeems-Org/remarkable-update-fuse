import errno
import os
import queue
import sys
import threading
import time
import warnings

import fuse

from pathlib import PurePosixPath

from . import ext4

from .image import UpdateImage
from .image import UpdateImageSignatureException
from .threads import KillableThread


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

    @property
    def mountpoint(self):
        return self.fuse_args.mountpoint

    def fuse_error(self, msg):
        print(msg, file=sys.stderr)
        self.fuse_args.setmod("showhelp")
        fuse.Fuse.main(self, self.args)
        sys.exit(1)

    def main(self, args=None):
        self.args = args
        if self.fuse_args.getmod("showhelp"):
            fuse.Fuse.main(self, args)
            return

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
                .open()
                .read()
            )
            print("Signature verified")
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
        if self.disable_path_cache:
            inode = self.volume.inode_at(path)
            if inode is None:
                raise FileNotFoundError()

            return inode

        if path not in self.inode_cache:
            inode = self.volume.inode_at(path)
            self.inode_cache[path] = inode
            inode.verify()

        inode = self.inode_cache[path]
        if inode is None:
            raise FileNotFoundError()

        return inode

    def statfs(self):
        superblock = self.volume.superblock
        struct = fuse.StatVfs()
        struct.f_bsize = self.volume.block_size
        struct.f_frsize = self.volume.block_size
        struct.f_blocks = superblock.s_blocks_count
        struct.f_bfree = superblock.s_free_blocks_count
        struct.f_bavail = superblock.s_free_blocks_count - superblock.s_r_blocks_count
        struct.f_files = superblock.s_inodes_count
        struct.f_ffree = superblock.s_free_inodes_count
        struct.f_favail = superblock.s_free_inodes_count
        struct.f_flag = superblock.s_flags.value
        struct.f_namemax = ext4.EXT4_NAME_LEN
        return struct

    def getattr(self, path, inode=None):
        if inode is None:
            try:
                inode = self.get_inode(path)

            except FileNotFoundError:
                print(f"{path} not found")
                return -errno.ENOENT

        _stat = Stat()
        _stat.st_mode = inode.i_mode.value
        _stat.st_ino = inode.i_uid
        _stat.st_nlink = inode.i_links_count
        _stat.st_uid = inode.i_uid
        _stat.st_gid = inode.i_gid
        _stat.st_size = inode.i_size
        _stat.st_atime = inode.i_atime
        _stat.st_mtime = inode.i_mtime
        _stat.st_ctime = inode.i_ctime
        return _stat

    def open(self, path, flags):
        try:
            inode = self.get_inode(path)
            if isinstance(inode, ext4.Directory):
                return -errno.EACCES

            mode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
            if (flags & mode) != os.O_RDONLY:
                return -errno.EACCES

            return inode

        except FileNotFoundError:
            print(f"{path} not found")
            return -errno.ENOENT

    def release(self, _, __=None):
        return

    def read(self, path, size, offset, inode=None):
        if inode is None:
            try:
                inode = self.get_inode(path)

            except FileNotFoundError:
                print(f"{path} not found")
                return -errno.ENOENT

        reader = inode.open()
        reader.seek(offset, os.SEEK_SET)
        return reader.read(size)

    def readlink(self, path, inode=None):
        if inode is None:
            try:
                inode = self.get_inode(path)

            except FileNotFoundError:
                print(f"{path} not found")
                return -errno.ENOENT

        if not isinstance(inode, ext4.SymbolicLink):
            return path

        return inode.readlink().decode("utf-8")

    def getxattr(self, path, name, _):
        try:
            inode = self.get_inode(path)
            for _name, value in inode.xattrs:
                if _name == name:
                    return value

            return None

        except FileNotFoundError:
            print(f"{path} not found")
            return -errno.ENOENT

    def listxattr(self, path, _):
        try:
            inode = self.get_inode(path)
            for name, _ in inode.xattrs:
                yield name

            return None

        except FileNotFoundError:
            print(f"{path} not found")
            return -errno.ENOENT

    def opendir(self, path):
        try:
            inode = self.get_inode(path)
            if not isinstance(inode, ext4.Directory):
                return -errno.EACCES

            return inode

        except FileNotFoundError:
            print(f"{path} not found")
            return -errno.ENOENT

    def releasedir(self, _, __=None):
        return

    def readdir(self, path, _, inode=None):
        if inode is None:
            try:
                inode = self.get_inode(path)

            except FileNotFoundError:
                print(f"{path} not found")
                return -errno.ENOENT

        for dirent, _ in inode.opendir():
            yield fuse.Direntry(dirent.name_str)
