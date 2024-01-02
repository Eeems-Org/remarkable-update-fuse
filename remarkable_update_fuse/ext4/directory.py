from ctypes import c_uint32
from ctypes import c_uint16
from ctypes import c_uint8
from ctypes import c_char
from ctypes import memmove
from ctypes import addressof

from .struct import Ext4Struct
from .enum import EXT4_FT

EXT4_NAME_LEN = 255
EXT4_DIR_PAD = 4
EXT4_DIR_ROUND = EXT4_DIR_PAD - 1
EXT4_MAX_REC_LEN = (1 << 16) - 1


class DirectoryEntryStruct(Ext4Struct):
    def __init__(self, directory, offset):
        self.directory = directory
        super().__init__(directory.volume, offset)

    def read_from_volume(self):
        data = self.directory._open().read()[self.offset : self.offset + self.size]
        memmove(addressof(self), data, self.size)


class DirectoryEntryBase(DirectoryEntryStruct):
    @property
    def name_bytes(self):
        return bytes(self.name)[: self.name_len]

    @property
    def name_str(self):
        return self.name_bytes.decode("utf-8")

    @property
    def is_fake_entry(self):
        return 0 < self.name_len <= 2 and self.name_bytes in (b".", b"..")


class DirectoryEntry(DirectoryEntryBase):
    _pack_ = 1
    # _anonymous_ = ("l_i_reserved",)
    _fields_ = [
        ("inode", c_uint32),
        ("rec_len", c_uint16),
        ("name_len", c_uint16),
        ("name", c_char * EXT4_NAME_LEN),
    ]


class DirectoryEntry2(DirectoryEntryBase):
    _pack_ = 1
    # _anonymous_ = ("l_i_reserved",)
    _fields_ = [
        ("inode", c_uint32),
        ("rec_len", c_uint16),
        ("name_len", c_uint8),
        ("file_type", EXT4_FT),
        ("name", c_char * EXT4_NAME_LEN),
    ]

    @property
    def is_fake_entry(self):
        return super().is_fake_entry or self.file_type == EXT4_FT.DIR_CSUM


class DirectoryEntryTail(DirectoryEntryStruct):
    _pack_ = 1
    # _anonymous_ = ("det_reserved_zero1", "det_reserved_zero2",)
    _fields_ = [
        ("det_reserved_zero1", c_uint32),
        ("det_rec_len", c_uint16),
        ("det_reserved_zero2", c_uint8),
        ("det_reserved_ft", c_uint8),  # EXT4_FT.DIR_CSUM
        ("det_checksum", c_uint32),
    ]

    @property
    def magic(self):
        return self.det_reserved_ft

    @property
    def expected_magic(self):
        return EXT4_FT.DIR_CSUM


class DirectoryEntryHash(DirectoryEntryStruct):
    _pack_ = 1
    # _anonymous_ = ("det_reserved_zero1", "det_reserved_zero2",)
    _fields_ = [
        ("hash", c_uint32),
        ("minor_hash", c_uint32),
    ]
