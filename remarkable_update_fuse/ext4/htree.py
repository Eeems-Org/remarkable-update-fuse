from ctypes import c_uint32
from ctypes import c_uint16
from ctypes import c_uint8
from ctypes import c_char

from .struct import Ext4Struct


class DXDot(Ext4Struct):
    _pack_ = 1
    # _anonymous_ = ()
    _fields_ = [
        ("inode", c_uint32),
        ("rec_len", c_uint16),
        ("name_len", c_uint8),
        ("file_type", c_uint8),
        ("name", c_char * 4),  # b".\0\0\0"
    ]


class DXDotDot(Ext4Struct):
    _pack_ = 1
    # _anonymous_ = ()
    _fields_ = [
        ("inode", c_uint32),
        ("rec_len", c_uint16),
        ("name_len", c_uint8),
        ("file_type", c_uint8),
        ("name", c_char * 4),  # b"..\0\0"
    ]


class DXRootInfo(Ext4Struct):
    _pack_ = 1
    # _anonymous_ = ("reserved_zero")
    _fields_ = [
        ("reserved_zero", c_uint32),
        ("hash_version", c_uint8),
        ("info_length", c_uint8),
        ("indirect_levels", c_uint8),
        ("unused_flags", c_uint8),
    ]


class DXEntry(Ext4Struct):
    _pack_ = 1
    # _anonymous_ = ("")
    _fields_ = [
        ("hash", c_uint32),
        ("block", c_uint32),
    ]


class DXEntriesBase(Ext4Struct):
    def read_from_volume(self):
        super().read_from_volume()
        self.entries = [DXEntry(self) for i in range(0, self.count)]


class DXRoot(DXEntriesBase):
    _pack_ = 1
    # _anonymous_ = ("")
    _fields_ = [
        ("dot", DXDot),
        ("dot", DXDotDot),
        ("dx_root_info", DXRootInfo),
        ("limit", c_uint16),
        ("count", c_uint16),
        ("block", c_uint32),
        # ("entries", DXEntry * self.count),
    ]


class DXFake(Ext4Struct):
    _pack_ = 1
    # _anonymous_ = ("")
    _fields_ = [
        ("inode", c_uint32),
        ("rec_len", c_uint16),
    ]


class DXNode(DXEntriesBase):
    _pack_ = 1
    # _anonymous_ = ("")
    _fields_ = [
        ("fake", DXFake),
        ("name_len", c_uint8),
        ("file_type", c_uint8),
        ("limit", c_uint16),
        ("count", c_uint16),
        ("block", c_uint32),
        # ("entries", DXEntry * self.count),
    ]


class DXTail(Ext4Struct):
    _pack_ = 1
    # _anonymous_ = ("dt_reserved")
    _fields_ = [
        ("dt_reserved", c_uint32),
        ("dt_checksum", c_uint16),
    ]
