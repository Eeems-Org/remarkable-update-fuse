import warnings

from ctypes import c_uint32
from ctypes import c_uint16
from ctypes import c_uint8
from ctypes import sizeof

from .struct import Ext4Struct
from .struct import crc32c
from .enum import EXT4_FL


class ExtendedAttributeError(Exception):
    pass


class ExtendedAttributeBase(Ext4Struct):
    def __init__(self, inode, offset, size):
        self.inode = inode
        self.data_size = size
        super().__init__(inode.volume, offset)


class ExtendedAttributeIBodyHeader(ExtendedAttributeBase):
    _pack_ = 1
    # _anonymous_ = ()
    _fields_ = [
        ("h_magic", c_uint32),  # 0xEA020000
    ]

    @property
    def ignore_magic(self):
        return False

    @property
    def magic(self):
        return self.h_magic

    @property
    def expected_magic(self):
        return 0xEA020000

    def __iter__(self):
        offset = self.offset + (4 * ((sizeof(self) + 3) // 4))
        i = 0
        while i < self.data_size:
            entry = ExtendedAttributeEntry(offset + i)
            if (
                entry.e_name_len
                | entry.e_name_index
                | entry.e_value_offs
                | entry.e_value_inum
            ) == 0:
                break

            if entry.e_value_inum != 0:
                inode = self.volue.inodes[entry.e_value_inum]
                if (inode.i_flags & EXT4_FL.EA_INODE) != 0:
                    message = f"Inode {inode.i_no:d} is not marked as large extended attribute value"
                    if not self.volume.ignore_flags:
                        raise ExtendedAttributeError(message)
                    warnings.warn(message, RuntimeWarning)

                # TODO determine if e_value_size or i_size are required to limit results?
                value = inode.open().read()

            else:
                self.volume.seek(offset + i + entry.e_value_offs)
                self.volume.read(entry.e_value_size)

            yield entry.name_str, value
            i += (entry.size + 3) // 4


class ExtendedAttributeHeader(ExtendedAttributeIBodyHeader):
    _pack_ = 1
    # _anonymous_ = ("h_reserved)
    _fields_ = [
        ("h_refcount", c_uint32),
        ("h_blocks", c_uint32),
        ("h_hash", c_uint32),
        ("h_checksum", c_uint32),
        ("h_reserved", c_uint32 * 2),
    ]

    def verify(self):
        super().verify()
        if self.h_blocks != 1:
            raise ExtendedAttributeError(
                f"Invalid number of xattr blocks at offset 0x{self.offset:X} of inode "
                f"{self.inode.i_no:d}: {self.h_blocks:d} (expected 1)"
            )

    @property
    def expected_checksum(self):
        if not self.h_checksum:
            return None

        return self.h_checksum

    @property
    def checksum(self):
        if not self.h_checksum:
            return None

        csum = crc32c(
            bytes(self)[: ExtendedAttributeHeader.h_checksum.offset], self.volume.seed
        )
        csum = crc32c(b"\0" * ExtendedAttributeHeader.h_checksum.size, csum)
        return crc32c(bytes(self)[: ExtendedAttributeHeader.h_reserved.offset], csum)


class ExtendedAttributeEntry(ExtendedAttributeBase):
    NAME_INDICES = [
        "",
        "user.",
        "system.posix_acl_access",
        "system.posix_acl_default",
        "trusted.",
        "security.",
        "system.",
        "system.richacl",
    ]
    _pack_ = 1
    # _anonymous_ = ("h_reserved)
    _fields_ = [
        ("e_name_len", c_uint8),
        ("e_name_index", c_uint8),
        ("e_value_offs", c_uint16),
        ("e_value_inum", c_uint32),
        ("e_value_size", c_uint32),
        ("e_hash", c_uint32),
        # ("e_name", c_char * self.e_name_len),
    ]

    def read_from_volume(self):
        super().read_from_volume()
        self.e_name = self.volume.stream.read(self.e_name_len)

    @property
    def size(self):
        return sizeof(self) + self.e_name_len

    @property
    def name_str(self):
        if 0 > self.e_name_index or self.e_name_index > len(
            ExtendedAttributeEntry.NAME_INDICES
        ):
            raise ExtendedAttributeError(
                f"Unknown attribute prefix {self.e_name_index:d}"
            )

        return ExtendedAttributeEntry.NAME_INDICES[
            self.e_name_index
        ] + self.e_name.decode("iso-8859-2")
