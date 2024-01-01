from ctypes import LittleEndianStructure
from ctypes import Union
from ctypes import c_uint64
from ctypes import c_uint32
from ctypes import c_uint16
from crcmod import mkCrcFun

from .enum import TypedCEnumeration
from .struct import Ext4Struct
from .enum import EXT4_OS
from .enum import EXT4_FL
from .enum import MODE
from .enum import EXT4_FEATURE_INCOMPAT

crc32c = mkCrcFun(0x11EDC6F41)


class Linux1(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("l_i_version", c_uint32),
    ]


class Hurd1(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("h_i_translator", c_uint32),
    ]


class Masix1(LittleEndianStructure):
    _pack_ = 1
    # _anonymous_ = ("m_i_reserved1",)
    _fields_ = [
        ("m_i_reserved1", c_uint32),
    ]


class Osd1(Union):
    _pack_ = 1
    _fields_ = [
        ("linux1", Linux1),
        ("hurd1", Hurd1),
        ("masix1", Masix1),
    ]


class Linux2(LittleEndianStructure):
    _pack_ = 1
    # _anonymous_ = ("l_i_reserved",)
    _fields_ = [
        ("l_i_blocks_high", c_uint16),
        ("l_i_file_acl_high", c_uint16),
        ("l_i_uid_high", c_uint16),
        ("l_i_gid_high", c_uint16),
        ("l_i_checksum_lo", c_uint16),
        ("l_i_reserved", c_uint16),
    ]


class Hurd2(LittleEndianStructure):
    _pack_ = 1
    # _anonymous_ = ("h_i_reserved1",)
    _fields_ = [
        ("h_i_reserved1", c_uint16),
        ("h_i_mode_high", c_uint16),
        ("h_i_uid_high", c_uint16),
        ("h_i_gid_high", c_uint16),
        ("h_i_author", c_uint32),
    ]


class Masix2(LittleEndianStructure):
    _pack_ = 1
    # _anonymous_ = ("h_i_reserved1", "m_i_reserved2")
    _fields_ = [
        ("h_i_reserved1", c_uint16),
        ("m_i_file_acl_high", c_uint16),
        ("m_i_reserved2", c_uint32 * 2),
    ]


class Osd2(Union):
    _pack_ = 1
    _fields_ = [
        ("linux2", Linux2),
        ("hurd2", Hurd2),
        ("masix2", Masix2),
    ]


class Inode(Ext4Struct):
    EXT4_GOOD_OLD_INODE_SIZE = EXT2_GOOD_OLD_INODE_SIZE = 128
    _pack_ = 1
    _fields_ = [
        ("i_mode", MODE),
        ("i_uid", c_uint16),
        ("i_size_lo", c_uint32),
        ("i_atime", c_uint32),
        ("i_ctime", c_uint32),
        ("i_mtime", c_uint32),
        ("i_dtime", c_uint32),
        ("i_gid", c_uint16),
        ("i_links_count", c_uint16),
        ("i_blocks_lo", c_uint32),
        ("i_flags", EXT4_FL),
        ("osd1", Osd1),
        ("i_block", c_uint32 * 15),
        ("i_generation", c_uint32),
        ("i_file_acl_lo", c_uint32),
        ("i_size_high", c_uint32),
        ("i_obso_faddr", c_uint32),
        ("osd2", Osd2),
        ("i_extra_isize", c_uint16),
        ("i_checksum_hi", c_uint16),
        ("i_ctime_extra", c_uint32),
        ("i_mtime_extra", c_uint32),
        ("i_atime_extra", c_uint32),
        ("i_crtime", c_uint32),
        ("i_crtime_extra", c_uint32),
        ("i_version_hi", c_uint32),
        ("i_projid", c_uint32),
    ]

    def __init__(self, volume, offset, i_no):
        super().__init__(volume, offset)
        self.i_no = i_no

    @property
    def has_hi(self):
        return self.volume.superblock.s_inode_size > self.EXT2_GOOD_OLD_INODE_SIZE

    @property
    def fits_in_hi(self):
        return (
            self.has_hi
            and self.i_checksum_hi.offset + self.i_checksum_hi.size
            <= self.EXT2_GOOD_OLD_INODE_SIZE + self.i_extra_isize
        )

    @property
    def seed(self):
        superblock = self.volume.superblock
        if superblock.s_feature_incompat & EXT4_FEATURE_INCOMPAT.CSUM_SEED != 0:
            return superblock.s_checksum_seed

        return crc32c(bytes(superblock.s_uuid))

    @property
    def checksum(self):
        superblock = self.volume.superblock
        if superblock.s_creator_os != EXT4_OS.LINUX:
            return None

        csum = crc32c(self.i_no.to_bytes(4, "little"), self.seed)
        csum = crc32c(
            self.i_generation.to_bytes(Inode.i_generation.size, "little"),
            csum,
        )
        data = bytes(self)
        checksum_offset = (
            Inode.osd2.offset + Osd2.linux2.offset + Linux2.l_i_checksum_lo.offset
        )
        checksum_size = Linux2.l_i_checksum_lo.size
        csum = crc32c(data[:checksum_offset], csum)
        csum = crc32c(b"\0" * checksum_size, csum)
        csum = crc32c(
            data[checksum_offset + checksum_size : self.EXT2_GOOD_OLD_INODE_SIZE],
            csum,
        )
        if self.has_hi:
            offset = Inode.i_checksum_hi.offset
            csum = crc32c(
                data[self.EXT2_GOOD_OLD_INODE_SIZE : offset],
                csum,
            )
            if self.fits_in_hi:
                csum = crc32c(b"\0" * Inode.i_checksum_hi.size, csum)
                offset += Inode.i_checksum_hi.size

            csum = crc32c(
                data[offset:],
                csum,
            )

        if not self.has_hi:
            csum &= 0xFFFF

        return csum

    @property
    def expected_checksum(self):
        superblock = self.volume.superblock
        if superblock.s_creator_os != EXT4_OS.LINUX:
            return None

        provided_csum = 0
        provided_csum |= self.osd2.linux2.l_i_checksum_lo
        if self.has_hi:
            provided_csum |= self.i_checksum_hi << 16

        return provided_csum
