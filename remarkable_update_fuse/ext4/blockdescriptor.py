from ctypes import c_uint32
from ctypes import c_uint16

from .enum import EXT4_BG
from .struct import Ext4Struct
from .struct import crc32c


class BlockDescriptor(Ext4Struct):
    _pack_ = 1
    # _anonymous_ = ("bg_reserved",)
    _fields_ = [
        ("bg_block_bitmap_lo", c_uint32),
        ("bg_inode_bitmap_lo", c_uint32),
        ("bg_inode_table_lo", c_uint32),
        ("bg_free_blocks_count_lo", c_uint16),
        ("bg_free_inodes_count_lo", c_uint16),
        ("bg_used_dirs_count_lo", c_uint16),
        ("bg_flags", EXT4_BG),
        ("bg_exclude_bitmap_lo", c_uint32),
        ("bg_block_bitmap_csum_lo", c_uint16),
        ("bg_inode_bitmap_csum_lo", c_uint16),
        ("bg_itable_unused_lo", c_uint16),
        ("bg_checksum", c_uint16),
        ("bg_block_bitmap_hi", c_uint32),
        ("bg_inode_bitmap_hi", c_uint32),
        ("bg_inode_table_hi", c_uint32),
        ("bg_free_blocks_count_hi", c_uint16),
        ("bg_free_inodes_count_hi", c_uint16),
        ("bg_used_dirs_count_hi", c_uint16),
        ("bg_itable_unused_hi", c_uint16),
        ("bg_exclude_bitmap_hi", c_uint32),
        ("bg_block_bitmap_csum_hi", c_uint16),
        ("bg_inode_bitmap_csum_hi", c_uint16),
        ("bg_reserved", c_uint32),
    ]

    def __init__(self, volume, offset, bg_no):
        super().__init__(volume, offset)
        self.bg_no = bg_no

    @property
    def bg_block_bitmap(self):
        if self.volume.has_hi:
            return self.bg_block_bitmap_hi << 32 | self.bg_block_bitmap_lo

        return self.bg_block_bitmap_lo

    @property
    def bg_inode_bitmap(self):
        if self.volume.has_hi:
            return self.bg_inode_bitmap_hi << 32 | self.bg_inode_bitmap_lo

        return self.bg_inode_bitmap_lo

    @property
    def bg_free_blocks_count(self):
        if self.volume.has_hi:
            return self.bg_free_blocks_count_hi << 32 | self.bg_free_blocks_count_lo

        return self.bg_free_blocks_count_lo

    @property
    def bg_free_inodes_count(self):
        if self.volume.has_hi:
            return self.bg_free_inodes_count_hi << 32 | self.bg_free_inodes_count_lo

        return self.bg_free_inodes_count_lo

    @property
    def bg_exclude_bitmap(self):
        if self.volume.has_hi:
            return self.bg_exclude_bitmap_hi << 32 | self.bg_exclude_bitmap_lo

        return self.bg_exclude_bitmap_lo

    @property
    def bg_used_dirs_count(self):
        if self.volume.has_hi:
            return self.bg_used_dirs_count_hi << 32 | self.bg_used_dirs_count_lo

        return self.bg_used_dirs_count_lo

    @property
    def bg_block_bitmap_csum(self):
        if self.volume.has_hi:
            return self.bg_block_bitmap_csum_hi << 32 | self.bg_block_bitmap_csum_lo

        return self.bg_block_bitmap_csum_lo

    @property
    def bg_inode_bitmap_csum(self):
        if self.volume.has_hi:
            return self.bg_inode_bitmap_csum_hi << 32 | self.bg_inode_bitmap_csum_lo

        return self.bg_inode_bitmap_csum_lo

    @property
    def bg_itable_unused(self):
        if self.volume.has_hi:
            return self.bg_itable_unused_hi << 32 | self.bg_itable_unused_lo

        return self.bg_itable_unused_lo

    @property
    def bg_inode_table(self):
        if self.volume.has_hi:
            return (self.bg_inode_table_hi << 32) + self.bg_inode_table_lo

        return self.bg_inode_table_lo

    @property
    def superblock(self):
        return self.volume.superblock

    @property
    def checksum(self):
        csum = crc32c(self.bg_no.to_bytes(4, "little"), self.volume.seed)
        csum = crc32c(bytes(self)[: BlockDescriptor.bg_checksum.offset], csum)
        if self.volume.has_hi:
            csum = crc32c(b"\x00\x00", csum)
            csum = crc32c(
                bytes(self)[BlockDescriptor.bg_block_bitmap_hi.offset :], csum
            )
        return csum & 0xFFFF

    @property
    def expected_checksum(self):
        return self.bg_checksum
