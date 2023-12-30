import bz2
import io
import os
import struct
import sys
import time

from cachetools import TTLCache
from .update_metadata_pb2 import DeltaArchiveManifest

BLOCK_SIZE = 4096


def sizeof_fmt(num, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


class BlockCache(TTLCache):
    def __init__(self, maxsize, ttl, timer=time.monotonic, getsizeof=sys.getsizeof):
        super().__init__(maxsize, ttl, timer, getsizeof)

    @property
    def usage_str(self):
        return f"{self.curr_size_str}/{self.max_size_str}"

    @property
    def curr_size_str(self):
        return sizeof_fmt(self.currsize)

    @property
    def max_size_str(self):
        return sizeof_fmt(self.maxsize)


class UpdateImageException(Exception):
    pass


class UpdateImage(io.RawIOBase):
    _manifest = None
    _offset = -1
    _size = 0
    _pos = 0

    def __init__(self, update_file, cache_size=500, cache_ttl=60):
        self.update_file = update_file
        self.cache_size = cache_size
        self._cache = BlockCache(
            maxsize=cache_size * 1024 * 1024,
            ttl=cache_ttl,
        )
        with open(self.update_file, "rb") as f:
            magic = f.read(4)
            if magic != b"CrAU":
                raise UpdateImageException("Wrong header")

            major = struct.unpack(">Q", f.read(8))[0]
            if major != 1:
                raise UpdateImageException("Unsupported version")

            size = struct.unpack(">Q", f.read(8))[0]
            data = f.read(size)
            self._manifest = DeltaArchiveManifest.FromString(data)
            self._offset = f.tell()

        for chunk, offset, length, f in self._chunks:
            self._size += length

    @property
    def _chunks(self):
        with open(self.update_file, "rb") as f:
            for chunk in self._manifest.install_operations:
                f.seek(self._offset + chunk.data_offset)
                dst_offset = chunk.dst_extents[0].start_block * BLOCK_SIZE
                dst_length = chunk.dst_extents[0].num_blocks * BLOCK_SIZE
                if chunk.type not in (0, 1):
                    raise UpdateImageException(f"Unsupported type {chunk.type}")

                yield chunk, dst_offset, dst_length, f

        self.expire()

    def _read_chunk(self, chunk, chunk_offset, chunk_length, f):
        if chunk_offset in self._cache:
            return self._cache[chunk_offset]

        chunk_data = f.read(chunk.data_length)
        if chunk.type == 1:
            try:
                chunk_data = bz2.decompress(chunk_data)

            except ValueError as err:
                raise UpdateImageException(f"Error: {err}") from err

            if chunk_length - len(chunk_data) < 0:
                raise UpdateImageException(
                    f"Error: Compressed data was the wrong length {len(chunk_data)}"
                )
        try:
            self._cache[chunk_offset] = chunk_data
        except ValueError as err:
            if str(err) != "value too large":
                raise err

        return chunk_data

    @property
    def cache(self):
        return self._cache

    @property
    def size(self):
        return self._size

    def expire(self):
        self._cache.expire()

    def writable(self):
        return False

    def seekable(self):
        return False

    def readable(self):
        return True

    def seek(self, offset, whence=os.SEEK_SET):
        if whence not in (os.SEEK_SET, os.SEEK_CUR, os.SEEK_END):
            raise OSError("Not supported whence")
        if whence == os.SEEK_SET and offset < 0:
            raise ValueError("offset can't be negative")
        if whence == os.SEEK_END and offset > 0:
            raise ValueError("offset can't be positive")

        if whence == os.SEEK_SET:
            self._pos = min(max(offset, 0), self._size)
        elif whence == os.SEEK_CUR:
            self._pos = min(max(self._pos + offset, 0), self._size)
        elif whence == os.SEEK_END:
            self._pos = min(max(self._pos + offset + self._size, 0), self._size)
        return self._pos

    def tell(self):
        return self._pos

    def read(self, size=-1):
        res = self.peek(size)
        self.seek(len(res), whence=os.SEEK_CUR)
        return res

    def peek(self, size=0):
        offset = self._pos
        if offset >= self._size:
            return b""

        if size <= 0 or offset + size > self._size:
            size = self._size - offset

        res = bytearray(size)
        for chunk, chunk_offset, chunk_length, f in self._chunks:
            if offset < chunk_offset:
                continue
            if offset >= chunk_offset + chunk_length:
                continue

            chunk_data = self._read_chunk(chunk, chunk_offset, chunk_length, f)
            chunk_start_offset = max(offset - chunk_offset, 0)
            chunk_end_offset = min(offset - chunk_offset + size, chunk_length - 1)
            data = chunk_data[chunk_start_offset:chunk_end_offset]

            assert chunk_start_offset >= 0
            assert chunk_end_offset < chunk_length
            assert chunk_end_offset - chunk_start_offset == len(data)

            start_offset = chunk_offset + chunk_start_offset - offset
            end_offset = chunk_offset + chunk_end_offset - offset
            res[start_offset:end_offset] = data

            assert start_offset >= 0
            assert start_offset < len(res)
            assert end_offset < chunk_offset + chunk_length
            assert end_offset - start_offset == len(data)
            assert end_offset <= len(res)
            assert res[start_offset:end_offset] == data

        return bytes(res)
