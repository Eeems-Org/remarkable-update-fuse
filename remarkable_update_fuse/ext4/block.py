import io
import errno

from .extent import Extent


class BlockIOBlocks(object):
    def __init__(self, blockio):
        self.blockio = blockio

    @property
    def block_size(self):
        return self.blockio.block_size

    @property
    def volume(self):
        return self.blockio.inode.volume

    @property
    def ee_start(self):
        return self.blockio.ee_start

    @property
    def ee_block(self):
        return self.blockio.ee_block

    @property
    def ee_len(self):
        return self.blockio.ee_len

    def __contains__(self, ee_block):
        for extent in self.blockio.extents:
            if ee_block in extent.blocks:
                return True

        return False

    def __getitem__(self, ee_block):
        for extent in self.blockio.extents:
            if ee_block in extent.blocks:
                return extent.blocks[ee_block]

        return bytearray(self.block_size)


class BlockIO(io.RawIOBase):
    def __init__(self, inode):
        super().__init__()
        self.inode = inode
        self.cursor = 0
        self.blocks = BlockIOBlocks(self)

    def __len__(self):
        return self.inode.i_size

    @property
    def extents(self):
        return self.inode.extents

    @property
    def block_size(self):
        return self.inode.volume.block_size

    def seek(self, offset, mode=io.SEEK_SET):
        if mode == io.SEEK_CUR:
            offset += self.cursor

        elif mode == io.SEEK_END:
            offset += len(self)

        elif mode != io.SEEK_SET:
            raise NotImplementedError()

        if offset < 0:
            raise OSError(errno.EINVAL, "Invalid argument")

        self.cursor = offset

    def tell(self):
        return self.cursor

    def read(self, size=-1):
        if size < 0:
            size = len(self) - self.cursor

        data = self.peek(size)
        self.cursor += len(data)
        if size < len(data):
            raise OSError(errno.EIO, "Unexpected EOF")

        return data

    def peek(self, size=0):
        if self.cursor >= len(self):
            return b""

        start_index = self.cursor // self.block_size
        end_index = (self.cursor + size - 1) // self.block_size
        start_offset = self.cursor % self.block_size
        data = b""
        for i in range(start_index, end_index + 1):
            block = self.blocks[i]
            if block is None:
                block = bytearray(self.block_size)

            if i == start_index:
                block = block[start_offset:]

            data += block

        data = data[:size]
        return data
