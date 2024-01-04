import io
import warnings

from ctypes import LittleEndianStructure
from ctypes import Union
from ctypes import c_uint32
from ctypes import c_uint16
from ctypes import sizeof

from .struct import Ext4Struct
from .struct import crc32c
from .struct import MagicError

from .enum import EXT4_OS
from .enum import EXT4_FL
from .enum import EXT4_FEATURE_INCOMPAT
from .enum import MODE
from .enum import EXT4_FT

from .extent import ExtentTree

from .block import BlockIO

from .directory import DirectoryEntry
from .directory import DirectoryEntry2
from .directory import DirectoryEntryTail
from .directory import DirectoryEntryHash
from .directory import EXT4_DIR_ROUND

from .htree import DXRoot

from .xattr import ExtendedAttributeIBodyHeader


class OpenDirectoryError(Exception):
    pass


class InodeError(Exception):
    pass


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

    def __new__(cls, volume, offset, i_no):
        if cls is not Inode:
            return super().__new__(cls)

        volume.seek(offset + Inode.i_mode.offset)
        file_type = (
            Inode.field_type("i_mode").from_buffer_copy(volume.read(Inode.i_mode.size))
            & 0xF000
        )
        if file_type == MODE.IFIFO:
            return Fifo(volume, offset, i_no)

        if file_type == MODE.IFDIR:
            return Directory(volume, offset, i_no)

        if file_type == MODE.IFREG:
            return File(volume, offset, i_no)

        if file_type == MODE.IFLNK:
            return SymbolicLink(volume, offset, i_no)

        if file_type == MODE.IFCHR:
            return CharacterDevice(volume, offset, i_no)

        if file_type == MODE.IFBLK:
            return BlockDevice(volume, offset, i_no)

        if file_type == MODE.IFSOCK:
            return Socket(volume, offset, i_no)

        raise InodeError(f"Unknown file type 0x{file_type:X}")

    def __init__(self, volume, offset, i_no):
        self.i_no = i_no
        super().__init__(volume, offset)
        self.tree = ExtentTree(self)

    @property
    def superblock(self):
        return self.volume.superblock

    @property
    def i_size(self):
        return self.i_size_high << 32 | self.i_size_lo

    @property
    def i_file_acl(self):
        return self.osd2.linux2.l_i_file_acl_high << 32 | self.i_file_acl_lo

    @property
    def has_hi(self):
        return self.superblock.s_inode_size > self.EXT2_GOOD_OLD_INODE_SIZE

    @property
    def fits_in_hi(self):
        return (
            self.has_hi
            and self.i_checksum_hi.offset + self.i_checksum_hi.size
            <= self.EXT2_GOOD_OLD_INODE_SIZE + self.i_extra_isize
        )

    @property
    def seed(self):
        seed = crc32c(self.i_no.to_bytes(4, "little"), self.volume.seed)
        return crc32c(
            self.i_generation.to_bytes(Inode.i_generation.size, "little"),
            seed,
        )

    @property
    def checksum(self):
        if self.superblock.s_creator_os != EXT4_OS.LINUX:
            return None

        data = bytes(self)
        checksum_offset = (
            Inode.osd2.offset + Osd2.linux2.offset + Linux2.l_i_checksum_lo.offset
        )
        checksum_size = Linux2.l_i_checksum_lo.size
        csum = crc32c(data[:checksum_offset], self.seed)
        csum = crc32c(b"\0" * checksum_size, csum)
        csum = crc32c(
            data[checksum_offset + checksum_size : self.EXT2_GOOD_OLD_INODE_SIZE],
            csum,
        )
        if self.has_hi:
            offset = Inode.i_checksum_hi.offset
            csum = crc32c(data[self.EXT2_GOOD_OLD_INODE_SIZE : offset], csum)
            if self.fits_in_hi:
                csum = crc32c(b"\0" * Inode.i_checksum_hi.size, csum)
                offset += Inode.i_checksum_hi.size

            csum = crc32c(data[offset:], csum)

        if not self.has_hi:
            csum &= 0xFFFF

        return csum

    @property
    def expected_checksum(self):
        if self.superblock.s_creator_os != EXT4_OS.LINUX:
            return None

        provided_csum = 0
        provided_csum |= self.osd2.linux2.l_i_checksum_lo
        if self.has_hi:
            provided_csum |= self.i_checksum_hi << 16

        return provided_csum

    def validate(self):
        super().validate()
        if self.tree is not None:
            self.tree.validate()

    @property
    def is_inline(self):
        return (self.i_flags & EXT4_FL.EXTENTS) == 0

    @property
    def extents(self):
        return self.tree.extents

    @property
    def headers(self):
        return self.tree.headers

    @property
    def indices(self):
        return self.tree.indices

    def _open(self, mode="rb", encoding=None, newline=None):
        if mode != "rb" or encoding is not None or newline is not None:
            raise NotImplementedError()

        if self.is_inline:
            self.volume.seek(self.offset + Inode.i_block.offset)
            data = self.volume.read(self.i_size)
            return io.BytesIO(data)

        return BlockIO(self)

    def open(self, mode="rb", encoding=None, newline=None):
        raise NotImplementedError()

    @property
    def xattrs(self):
        inline_offset = self.offset + self.EXT2_GOOD_OLD_INODE_SIZE + self.i_extra_isize
        inline_size = self.superblock.s_inode_size - inline_offset
        if inline_size > sizeof(ExtendedAttributeIBodyHeader):
            try:
                header = ExtendedAttributeIBodyHeader(self, inline_offset, inline_size)
                header.verify()
                for name, value in header:
                    yield name, value

            except MagicError:
                pass

        if self.i_file_acl != 0:
            block_offset = self.i_file_acl * self.block_size
            try:
                header = ExtendedAttributeIBodyHeader(
                    self, block_offset, self.volume.block_size
                )
                header.verify()
                for name, value in header:
                    yield name, value

            except MagicError:
                if not self.superblock.ignore_magic:
                    raise


class Fifo(Inode):
    pass


class CharacterDevice(Inode):
    pass


class BlockDevice(Inode):
    pass


class Socket(Inode):
    pass


class File(Inode):
    def open(self, mode="rb", encoding=None, newline=None):
        return self._open(mode, encoding, newline)


class SymbolicLink(Inode):
    def readlink(self):
        return self._open().read()


class Directory(Inode):
    def __init__(self, volume, offset, i_no):
        super().__init__(volume, offset, i_no)
        self._dirents = None
        if self.is_htree:
            self.htree = DXRoot(self)

    def verify(self):
        super().verify()
        # TODO verify DirectoryEntryHash? Or should this be in validate?

    def validate(self):
        super().validate()
        # TODO validate each directory entry block with DirectoryEntryTail

    @property
    def superblock(self):
        return self.volume.superblock

    @property
    def block_size(self):
        return self.volume.block_size

    @property
    def has_filetype(self):
        return self.superblock.s_feature_incompat & EXT4_FEATURE_INCOMPAT.FILETYPE != 0

    @property
    def is_htree(self):
        return self.i_flags & EXT4_FL.INDEX != 0

    @property
    def is_casefolded(self):
        return self.i_flags & EXT4_FL.CASEFOLD != 0

    @property
    def is_encrypted(self):
        return self.i_flags & EXT4_FL.ENCRYPTED != 0

    @property
    def hash_in_dirent(self):
        return self.is_casefolded and self.is_encrypted

    def _opendir(self):
        if self._dirents is not None:
            for dirent in self._dirents:
                yield dirent

            return

        _type = DirectoryEntry2 if self.has_filetype else DirectoryEntry
        dirents = []
        offset = 0
        data = self._open().read()
        while offset < len(data):
            dirent = _type(self, offset)
            if not dirent.rec_len:
                # How did this happen?
                offset += _type.name.offset  # + EXT4_DIR_ROUND
                continue

            if not dirent.inode or not dirent.name_len:
                offset += dirent.rec_len
                continue

            expected_rec_len = _type.name.offset + dirent.name_len + EXT4_DIR_ROUND
            if not dirent.is_fake_entry and self.hash_in_dirent:
                expected_rec_len += sizeof(DirectoryEntryHash)

            expected_rec_len &= ~EXT4_DIR_ROUND

            if dirent.rec_len < expected_rec_len:
                warnings.warn(
                    "Directory entry is too small for name length"
                    f", expected={expected_rec_len}"
                    f", actual={dirent.rec_len}",
                    RuntimeWarning,
                )
                break

            offset += dirent.rec_len
            if not self.has_filetype or dirent.file_type != EXT4_FT.UNKNOWN:
                dirents.append(dirent)
                yield dirent

        self._dirents = dirents

    def _get_file_type(self, dirent):
        offset = self.volume.inodes.offset(dirent.inode)
        self.volume.seek(offset + Inode.i_mode.offset)
        i_mode = Inode.field_type("i_mode").from_buffer_copy(
            self.volume.read(Inode.i_mode.size)
        )
        self.volume.seek(offset + Inode.i_mode.offset)
        i_mode = Inode.field_type("i_mode").from_buffer_copy(
            self.volume.read(Inode.i_mode.size)
        )
        if i_mode & MODE.IFIFO != 0:
            return EXT4_FT.FIFO

        if i_mode & MODE.IFCHR != 0:
            return EXT4_FT.CHRDEV

        if i_mode & MODE.IFDIR != 0:
            return EXT4_FT.DIR

        if i_mode & MODE.IFBLK != 0:
            return EXT4_FT.BLKDEV

        if i_mode & MODE.IFREG != 0:
            return EXT4_FT.REG_FILE

        if i_mode & MODE.IFLNK != 0:
            return EXT4_FT.SYMLINK

        if i_mode & MODE.IFSOCK != 0:
            return EXT4_FT.SOCK

        raise OpenDirectoryError(
            f"Unexpected file type {i_mode} for inode {dirent.inode}"
        )

    def opendir(self):
        for dirent in self._opendir():
            if isinstance(dirent, DirectoryEntry2):
                file_type = dirent.file_type
                if file_type == EXT4_FT.DIR_CSUM:
                    continue

                if file_type == EXT4_FT.UNKNOWN or file_type > EXT4_FT.MAX:
                    raise OpenDirectoryError(f"Unexpected file type: {file_type}")

            else:
                file_type = self._get_file_type(dirent)

            yield dirent, file_type
