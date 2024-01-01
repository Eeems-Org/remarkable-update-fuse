from ctypes import c_uint32
from ctypes import c_uint16

from .enum import EXT4_BG
from .struct import Ext4Struct


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

    @property
    def bg_inode_table(self):
        if self.volume.has_hi:
            return (self.bg_inode_table_hi << 32) + self.bg_inode_table_lo

        return self.bg_inode_table_lo
