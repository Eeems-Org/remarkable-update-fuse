from ctypes import c_uint32
from ctypes import c_uint16
from ctypes import c_uint8
from ctypes import c_char
from ctypes import sizeof
from ctypes import addressof
from ctypes import memmove
from ctypes import LittleEndianStructure

from .struct import Ext4Struct
from .struct import MagicError
from .enum import DX_HASH


class DotDirectoryEntry2(LittleEndianStructure):
    _pack_ = 1
    # _anonymous_ = ()
    _fields_ = [
        ("inode", c_uint32),
        ("rec_len", c_uint16),
        ("name_len", c_uint8),
        ("file_type", c_uint8),
        ("name", c_char * 4),  # b".\0\0\0" or b"..\0\0"
    ]

    def verify(self):
        if self.name in (b".\0\0\0", b".\0\0\0"):
            return

        message = f"{self} dot or dotdot entry name invalid! " f"actual={self.name}"
        if not self.ignore_magic:
            raise MagicError(message)


class DXRootInfo(LittleEndianStructure):
    _pack_ = 1
    # _anonymous_ = ("reserved_zero")
    _fields_ = [
        ("reserved_zero", c_uint32),
        ("hash_version", DX_HASH),
        ("info_length", c_uint8),
        ("indirect_levels", c_uint8),
        ("unused_flags", c_uint8),
    ]


class DXBase(Ext4Struct):
    def __init__(self, directory, offset):
        self.directory = directory
        super().__init__(directory.volume, offset)

    def read_from_volume(self):
        reader = self.directory._open()
        reader.seek(self.offset)
        data = reader.read(sizeof(self))
        memmove(addressof(self), data, sizeof(self))


class DXEntry(DXBase):
    _pack_ = 1
    # _anonymous_ = ("")
    _fields_ = [
        ("hash", c_uint32),
        ("block", c_uint32),
    ]

    def __init__(self, parent, index):
        self.index = index
        self.parent = parent
        super().__init__(
            parent.directory,
            parent.offset + parent.size + index * parent.dx_root_info.info_length,
        )


class DXEntriesBase(DXBase):
    def read_from_volume(self):
        super().read_from_volume()

    @property
    def entries(self):
        for i in range(0, self.count - 1):
            yield DXEntry(self, i)


class DXRoot(DXEntriesBase):
    _pack_ = 1
    # _anonymous_ = ("")
    _fields_ = [
        ("dot", DotDirectoryEntry2),
        ("dotdot", DotDirectoryEntry2),
        ("dx_root_info", DXRootInfo),
        ("limit", c_uint16),
        ("count", c_uint16),
        ("block", c_uint32),
        # ("entries", DXEntry * self.count),
    ]

    def __init__(self, inode):
        super().__init__(inode, 0)


class DXFake(LittleEndianStructure):
    _pack_ = 1
    # _anonymous_ = ("")
    _fields_ = [
        ("inode", c_uint32),  # 0
        ("rec_len", c_uint16),
    ]

    @property
    def expected_magic(self):
        return 0

    @property
    def magic(self):
        return self.inode


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


class DXTail(DXBase):
    _pack_ = 1
    # _anonymous_ = ("dt_reserved")
    _fields_ = [
        ("dt_reserved", c_uint32),
        ("dt_checksum", c_uint16),
    ]

    def __init__(self, parent):
        self.parent = parent
        super().__init__(
            parent.directory,
            parent.offset
            + parent.size
            + (parent.count + 1) * parent.dx_root_info.info_length,
        )
