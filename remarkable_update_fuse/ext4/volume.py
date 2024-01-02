import io
import os
import errno

from uuid import UUID

from cachetools import cached
from cachetools import LRUCache

from .enum import EXT4_INO
from .enum import MODE
from .superblock import Superblock
from .inode import Inode
from .inode import Fifo
from .inode import CharacterDevice
from .inode import Directory
from .inode import BlockDevice
from .inode import File
from .inode import SymbolicLink
from .inode import Socket
from .blockdescriptor import BlockDescriptor


class InvalidStreamException(Exception):
    pass


class Inodes(object):
    def __init__(self, volume):
        self.volume = volume

    @property
    def superblock(self):
        return self.volume.superblock

    @property
    def block_size(self):
        return self.volume.block_size

    @cached(cache={})
    def group(self, index):
        group_index = (index - 1) // self.superblock.s_inodes_per_group
        table_entry_index = (index - 1) % self.superblock.s_inodes_per_group
        return group_index, table_entry_index

    @cached(cache=LRUCache(maxsize=32))
    def offset(self, index):
        group_index, table_entry_index = self.group(index)
        table_offset = (
            self.volume.group_descriptors[group_index].bg_inode_table * self.block_size
        )
        return table_offset + table_entry_index * self.superblock.s_inode_size

    @cached(cache=LRUCache(maxsize=32))
    def __getitem__(self, index):
        offset = self.offset(index)
        self.volume.seek(offset + Inode.i_mode.offset)
        i_mode = Inode.field_type("i_mode").from_buffer_copy(
            self.volume.read(Inode.i_mode.size)
        )
        if i_mode & MODE.IFIFO != 0:
            return Fifo(self.volume, offset, index)

        if i_mode & MODE.IFCHR != 0:
            return CharacterDevice(self.volume, offset, index)

        if i_mode & MODE.IFDIR != 0:
            return Directory(self.volume, offset, index)

        if i_mode & MODE.IFBLK != 0:
            return BlockDevice(self.volume, offset, index)

        if i_mode & MODE.IFREG != 0:
            return File(self.volume, offset, index)

        if i_mode & MODE.IFLNK != 0:
            return SymbolicLink(self.volume, offset, index)

        if i_mode & MODE.IFSOCK != 0:
            return Socket(self.volume, offset, index)

        return Inode(self.volume, offset, index)


class Volume(object):
    def __init__(
        self,
        stream,
        offset=0,
        ignore_flags=False,
        ignore_magic=False,
        ignore_checksum=False,
    ):
        if not isinstance(stream, io.RawIOBase) and not isinstance(
            stream, io.BufferedIOBase
        ):
            raise InvalidStreamException()

        self.stream = stream
        self.offset = offset
        self.cursor = 0
        self.ignore_flags = ignore_flags
        self.ignore_magic = ignore_magic
        self.ignore_checksum = ignore_checksum
        self.superblock = Superblock(self)
        self.group_descriptors = []
        block_size = self.block_size
        table_offset = (self.superblock.offset // block_size + 1) * block_size
        for index in range(
            0, self.superblock.s_inodes_count // self.superblock.s_inodes_per_group
        ):
            descriptor = BlockDescriptor(
                self,
                table_offset + (index * self.superblock.s_desc_size),
            )
            self.group_descriptors.insert(index, descriptor)

        self.inodes = Inodes(self)

    def __len__(self):
        self.stream.seek(0, io.SEEK_END)
        return self.stream.tell() - self.offset

    @property
    def bad_blocks(self):
        return self.inodes[EXT4_INO.BAD]

    @property
    def root(self):
        return self.inodes[EXT4_INO.ROOT]

    @property
    def user_quota(self):
        return self.inodes[EXT4_INO.USR_QUOTA]

    @property
    def group_quota(self):
        return self.inodes[EXT4_INO.GRP_QUOTA]

    @property
    def boot_loader(self):
        return self.inodes[EXT4_INO.BOOT_LOADER]

    @property
    def undelete_directory(self):
        return self.inodes[EXT4_INO.UNDEL_DIR]

    @property
    def journal(self):
        return self.inodes[EXT4_INO.JOURNAL]

    @property
    def has_hi(self):
        return self.superblock.has_hi

    @property
    def uuid(self):
        return UUID(bytes=bytes(self.superblock.s_uuid))

    @property
    def seed(self):
        return self.superblock.seed

    @property
    def block_size(self):
        return 2 ** (10 + self.superblock.s_log_block_size)

    def seek(self, offset, mode=io.SEEK_SET):
        if mode == io.SEEK_SET:
            seek = offset

        elif mode == io.SEEK_CUR:
            seek = self.cursor + offset

        elif mode == io.SEEK_END:
            seek = len(self) - offset

        if seek < 0:
            raise OSError()

        self.cursor = seek
        return self.cursor

    def read(self, size):
        self.stream.seek(self.offset + self.cursor)
        return self.stream.read(size)

    def peek(self, size):
        self.stream.seek(self.offset + self.cursor)
        return self.stream.peek(size)

    def tell(self):
        return self.cursor

    def block_read(self, index, count=1):
        assert index >= 0
        assert count > 0
        block_size = self.block_size  # Only calculate once
        self.seek(index * block_size)
        return self.read(count * block_size)

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

            paths = (split[1].encode("utf-8"),) + paths

        return paths

    @cached(cache=LRUCache(maxsize=32))
    def inode_at(self, path):
        paths = list(self.path_tuple(path))
        cwd = self.root
        if not paths:
            return cwd

        while paths:
            name = paths.pop(0)
            inode = None
            for dirent, file_type in cwd.opendir():
                if dirent.name_bytes == name:
                    inode = self.inodes[dirent.inode]
                    break

            if inode is None:
                raise FileNotFoundError(path)

            while isinstance(inode, SymbolicLink):
                inode = inode.readlink()

            if paths and not isinstance(inode, Directory):
                raise OSError(errno.ENOTDIR)

            cwd = inode

        return inode
