import io

from uuid import UUID

from cachetools import cached
from cachetools import LRUCache

from .enum import EXT4_INO
from .superblock import Superblock
from .inode import Inode
from .blockdescriptor import BlockDescriptor


class InvalidStreamException(Exception):
    pass


class Volume(object):
    def __init__(
        self,
        stream,
        offset=0,
        ignore_flags=False,
        ignore_magic=False,
        ignore_checksum=False,
    ):
        if not isinstance(stream, io.RawIOBase):
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

    def __len__(self):
        self.stream.seek(0, io.SEEK_END)
        return self.stream.tell() - self.offset

    @property
    def bad_blocks(self):
        return self.get_inode(EXT4_INO.BAD)

    @property
    def root(self):
        return self.get_inode(EXT4_INO.ROOT)

    @property
    def user_quota(self):
        return self.get_inode(EXT4_INO.USR_QUOTA)

    @property
    def group_quota(self):
        return self.get_inode(EXT4_INO.GRP_QUOTA)

    @property
    def boot_loader(self):
        return self.get_inode(EXT4_INO.BOOT_LOADER)

    @property
    def undelete_directory(self):
        return self.get_inode(EXT4_INO.UNDEL_DIR)

    @property
    def journal(self):
        return self.get_inode(EXT4_INO.JOURNAL)

    @property
    def has_hi(self):
        return self.superblock.has_hi

    @property
    def uuid(self):
        return UUID(bytes=bytes(self.superblock.s_uuid))

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

    @cached(cache={})
    def get_inode_group(self, index):
        group_index = (index - 1) // self.superblock.s_inodes_per_group
        table_entry_index = (index - 1) % self.superblock.s_inodes_per_group
        return group_index, table_entry_index

    @cached(cache=LRUCache(maxsize=32))
    def get_inode(self, index):
        group_index, table_entry_index = self.get_inode_group(index)
        table_offset = (
            self.group_descriptors[group_index].bg_inode_table * self.block_size
        )
        offset = table_offset + table_entry_index * self.superblock.s_inode_size
        return Inode(self, offset, index)
