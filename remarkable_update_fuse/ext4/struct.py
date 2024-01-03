import warnings

from ctypes import LittleEndianStructure
from ctypes import memmove
from ctypes import addressof
from ctypes import sizeof
from crcmod import mkCrcFun

crc32c = mkCrcFun(0x11EDC6F41)


class MagicError(Exception):
    pass


class ChecksumError(Exception):
    pass


def to_hex(data):
    if isinstance(data, int):
        return f"0x{data:02X}"

    return "0x" + "".join([f"{x:02X}" for x in data])


class Ext4Struct(LittleEndianStructure):
    def __init__(self, volume, offset):
        super().__init__()
        self.volume = volume
        self.offset = offset
        self.read_from_volume()
        self.verify()

    @classmethod
    def field_type(cls, name):
        for _name, _type in cls._fields_:
            if name == name:
                return _type

        return None

    def read_from_volume(self):
        self.volume.stream.seek(self.offset)
        data = self.volume.stream.read(sizeof(self))
        memmove(addressof(self), data, sizeof(self))

    @property
    def size(self):
        return sizeof(self)

    @property
    def magic(self):
        return None

    @property
    def expected_magic(self):
        return None

    @property
    def checksum(self):
        return None

    @property
    def expected_checksum(self):
        return None

    @property
    def ignore_magic(self):
        return self.volume.ignore_magic

    def verify(self):
        """
        Verify magic numbers
        """
        if self.magic == self.expected_magic:
            return

        message = (
            f"{self} magic bytes do not match! "
            f"expected={to_hex(self.expected_magic)}, "
            f"actual={to_hex(self.magic)}"
        )
        if not self.ignore_magic:
            raise MagicError(message)

        warnings.warn(message, RuntimeWarning)

    def validate(self):
        """
        Validate data checksums
        """
        if self.checksum == self.expected_checksum:
            return

        message = (
            f"{self} checksum does not match! "
            f"expected={self.expected_checksum}, "
            f"actual={self.checksum}"
        )
        if not self.volume.ignore_checksum:
            raise ChecksumError(message)

        warnings.warn(message, RuntimeWarning)
