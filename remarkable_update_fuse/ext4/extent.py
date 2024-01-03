from ctypes import c_uint32
from ctypes import c_uint16
from ctypes import sizeof

from .struct import Ext4Struct
from .struct import crc32c


class ExtentBlocks(object):
    def __init__(self, extent):
        self.extent = extent

    @property
    def block_size(self):
        return self.extent.block_size

    @property
    def volume(self):
        return self.extent.volume

    @property
    def ee_start(self):
        return self.extent.ee_start

    @property
    def ee_block(self):
        return self.extent.ee_block

    @property
    def ee_len(self):
        # Don't use ee_len as we want to know the value for
        # uninitialized blocks as well
        return self.extent.len

    @property
    def is_initialized(self):
        return self.extent.is_initialized

    def __contains__(self, ee_block):
        return self.ee_block <= ee_block < self.ee_block + self.ee_len

    def __getitem__(self, ee_block):
        block_size = self.block_size
        if not self.is_initialized or ee_block not in self:
            # Uninitialized
            return bytearray(block_size)

        disk_block = self.ee_start + (ee_block - self.ee_block)
        self.volume.seek(disk_block * block_size)
        return self.volume.read(block_size)

    def __iter__(self):
        return iter(range(self.ee_block, self.ee_len))

    def __len__(self):
        return self.ee_len


class ExtentHeader(Ext4Struct):
    _pack_ = 1
    # _anonymous_ = ()
    _fields_ = [
        ("eh_magic", c_uint16),
        ("eh_entries", c_uint16),
        ("eh_max", c_uint16),
        ("eh_depth", c_uint16),
        ("eh_generation", c_uint32),
    ]

    def __init__(self, tree, offset):
        self.tree = tree
        super().__init__(self.inode.volume, offset)

        self.indices = []
        self.extents = []

        offset = self.offset + self.size
        for i in range(0, self.eh_entries):
            if self.eh_depth == 0:
                self.extents.append(Extent(self, offset, i))
                offset += sizeof(Extent)

            else:
                self.indices.append(ExtentIndex(self, offset, i))
                offset += sizeof(ExtentIndex)

        self.indices.sort(key=lambda entry: entry.ei_no)
        self.extents.sort(key=lambda entry: entry.ee_no)
        i_block = type(self.inode).i_block
        i_block_offset = self.inode.offset + i_block.offset
        self.tail = (
            ExtentTail(self, offset)
            if offset in range(i_block_offset, i_block_offset + i_block.size)
            else None
        )

    @property
    def inode(self):
        return self.tree.inode

    @property
    def expected_magic(self):
        return 0xF30A

    @property
    def magic(self):
        return self.eh_magic

    @property
    def expected_checksum(self):
        if self.tail is None or not self.tail.et_checksum:
            return None

        return self.tail.et_checksum

    @property
    def seed(self):
        return self.inode.seed

    @property
    def checksum(self):
        if self.expected_checksum is None:
            return None

        self.volume.seek(self.offset)
        data = self.volume.read(self.tail.offset - self.offset)
        return crc32c(data, self.seed)


class ExtentIndex(Ext4Struct):
    _pack_ = 1
    # _anonymous_ = ("ei_unused",)
    _fields_ = [
        ("ei_block", c_uint32),
        ("ei_leaf_lo", c_uint32),
        ("ei_leaf_hi", c_uint16),
        ("ei_unused", c_uint16),
    ]

    def __init__(self, header, offset, ei_no):
        self.ei_no = ei_no
        self.header = header
        super().__init__(self.inode.volume, offset)

    @property
    def ei_leaf(self):
        return self.ei_leaf_hi << 32 | self.ei_leaf_lo

    @property
    def tree(self):
        return self.header.tree

    @property
    def inode(self):
        return self.tree.inode


class Extent(Ext4Struct):
    _pack_ = 1
    # _anonymous_ = ("ei_unused",)
    _fields_ = [
        ("ee_block", c_uint32),
        ("ee_len", c_uint16),
        ("ee_start_hi", c_uint16),
        ("ee_start_lo", c_uint32),
    ]

    def __init__(self, header, offset, ee_no):
        super().__init__(header.inode.volume, offset)
        self.ee_no = ee_no
        self.header = header
        self.blocks = ExtentBlocks(self)

    @property
    def ee_start(self):
        return self.ee_start_hi << 32 | self.ee_start_lo

    @property
    def tree(self):
        return self.header.tree

    @property
    def is_initialized(self):
        return self.ee_len < 32768

    @property
    def len(self):
        return self.ee_len if self.is_initialized else self.ee_len - 32768

    @property
    def inode(self):
        return self.tree.inode

    @property
    def block_size(self):
        return self.volume.block_size

    def read(self):
        return b"".join(b.read() for b in self.blocks)


class ExtentTail(Ext4Struct):
    _pack_ = 1
    _fields_ = [
        ("et_checksum", c_uint32),
    ]

    def __init__(self, header, offset):
        self.header = header
        super().__init__(self.inode.volume, offset)

    @property
    def tree(self):
        return self.header.tree

    @property
    def inode(self):
        return self.tree.inode


class ExtentTree(object):
    def __init__(self, inode):
        self.inode = inode
        if not self.has_extents:
            return

        self.headers = []
        to_process = [self.offset]
        while to_process:
            header_offset = to_process.pop(0)
            header = ExtentHeader(self, header_offset)
            self.headers.append(header)
            for index in header.indices:
                to_process.append(index.ei_leaf * self.volume.block_size)

    @property
    def volume(self):
        return self.inode.volume

    @property
    def offset(self):
        return self.inode.offset + type(self.inode).i_block.offset

    @property
    def has_extents(self):
        return not self.inode.is_inline

    def verify(self):
        pass

    def validate(self):
        for header in self.headers:
            header.validate()

    @property
    def extents(self):
        extents = []
        for header in self.headers:
            extents += header.extents

        return extents

    @property
    def indices(self):
        indices = []
        for header in self.headers:
            indices += header.indices

        return indices
