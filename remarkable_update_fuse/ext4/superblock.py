from ctypes import c_uint64
from ctypes import c_uint32
from ctypes import c_uint16
from ctypes import c_uint8
from ctypes import c_ubyte

from .enum import EXT4_FS
from .enum import EXT4_ERRORS
from .enum import EXT4_OS
from .enum import EXT4_REV
from .enum import EXT4_FEATURE_COMPAT
from .enum import EXT4_FEATURE_INCOMPAT
from .enum import EXT4_FEATURE_RO_COMPAT
from .enum import DX_HASH
from .enum import EXT4_DEFM
from .enum import EXT2_FLAGS
from .enum import EXT4_CHKSUM
from .enum import EXT4_MOUNT
from .enum import FS_ENCRYPTION_MODE
from .struct import Ext4Struct
from .struct import crc32c


class Superblock(Ext4Struct):
    _pack_ = 1
    # _anonymous_ = (
    #     "s_reserved_pad",
    #     "s_reserved",
    # )
    _fields_ = [
        ("s_inodes_count", c_uint32),
        ("s_blocks_count_lo", c_uint32),
        ("s_r_blocks_count_lo", c_uint32),
        ("s_free_blocks_count_lo", c_uint32),
        ("s_free_inodes_count", c_uint32),
        ("s_first_data_block", c_uint32),
        ("s_log_block_size", c_uint32),
        ("s_log_cluster_size", c_uint32),
        ("s_blocks_per_group", c_uint32),
        ("s_clusters_per_group", c_uint32),
        ("s_inodes_per_group", c_uint32),
        ("s_mtime", c_uint32),
        ("s_wtime", c_uint32),
        ("s_mnt_count", c_uint16),
        ("s_max_mnt_count", c_uint16),
        ("s_magic", c_uint16),  # 0xEF53
        ("s_state", EXT4_FS),
        ("s_errors", EXT4_ERRORS),
        ("s_minor_rev_level", c_uint16),
        ("s_lastcheck", c_uint32),
        ("s_checkinterval", c_uint32),
        ("s_creator_os", EXT4_OS),
        ("s_rev_level", EXT4_REV),
        ("s_def_resuid", c_uint16),
        ("s_def_resgid", c_uint16),
        ("s_first_ino", c_uint32),
        ("s_inode_size", c_uint16),
        ("s_block_group_nr", c_uint16),
        ("s_feature_compat", EXT4_FEATURE_COMPAT),
        ("s_feature_incompat", EXT4_FEATURE_INCOMPAT),
        ("s_feature_ro_compat", EXT4_FEATURE_RO_COMPAT),
        ("s_uuid", c_uint8 * 16),
        ("s_volume_name", c_ubyte * 16),
        ("s_last_mounted", c_ubyte * 64),
        ("s_algorithm_usage_bitmap", c_uint32),
        ("s_prealloc_blocks", c_uint8),
        ("s_prealloc_dir_blocks", c_uint8),
        ("s_reserved_gdt_blocks", c_uint16),
        ("s_journal_uuid", c_uint8 * 16),
        ("s_journal_inum", c_uint32),
        ("s_journal_dev", c_uint32),
        ("s_last_orphan", c_uint32),
        ("s_hash_seed", c_uint32 * 4),
        ("s_def_hash_version", DX_HASH),
        ("s_jnl_backup_type", c_uint8),
        ("s_desc_size", c_uint16),
        ("s_default_mount_opts", EXT4_DEFM),
        ("s_first_meta_bg", c_uint32),
        ("s_jnl_blocks", c_uint32 * 17),
        ("s_blocks_count_hi", c_uint32),
        ("s_r_blocks_count_hi", c_uint32),
        ("s_free_blocks_count_hi", c_uint32),
        ("s_min_extra_isize", c_uint16),
        ("s_want_extra_isize", c_uint16),
        ("s_flags", EXT2_FLAGS),
        ("s_raid_stride", c_uint16),
        ("s_mmp_interval", c_uint16),
        ("s_mmp_block", c_uint64),
        ("s_raid_stripe_width", c_uint32),
        ("s_log_groups_per_flex", c_uint8),
        ("s_checksum_type", EXT4_CHKSUM),
        ("s_reserved_pad", c_uint16),
        ("s_kbytes_written", c_uint64),
        ("s_snapshot_inum", c_uint32),
        ("s_snapshot_id", c_uint32),
        ("s_snapshot_r_blocks_count", c_uint64),
        ("s_snapshot_list", c_uint32),
        ("s_error_count", c_uint32),
        ("s_first_error_time", c_uint32),
        ("s_first_error_ino", c_uint32),
        ("s_first_error_block", c_uint64),
        ("s_first_error_func", c_uint8 * 32),
        ("s_first_error_line", c_uint32),
        ("s_last_error_time", c_uint32),
        ("s_last_error_ino", c_uint32),
        ("s_last_error_line", c_uint32),
        ("s_last_error_block", c_uint64),
        ("s_last_error_func", c_uint8 * 32),
        ("s_mount_opts", EXT4_MOUNT * 64),
        ("s_usr_quota_inum", c_uint32),
        ("s_grp_quota_inum", c_uint32),
        ("s_overhead_blocks", c_uint32),
        ("s_backup_bgs", c_uint32),
        ("s_encrypt_algos", FS_ENCRYPTION_MODE * 4),
        ("s_encrypt_pw_salt", c_uint8 * 16),
        ("s_lpf_ino", c_uint32),
        ("s_prj_quota_inum", c_uint32),
        ("s_checksum_seed", c_uint32),
        ("s_reserved", c_uint32 * 98),
        ("s_checksum", c_uint32),
    ]

    def __init__(self, volume, _=None):
        super().__init__(volume, 0x400)

    @property
    def has_hi(self):
        return (self.s_feature_incompat & EXT4_FEATURE_INCOMPAT.IS64BIT) != 0

    @property
    def s_blocks_count(self):
        return (
            (self.s_blocks_per_group) * len(self.volume.group_descriptors)
            - self.s_reserved_gdt_blocks
            - self.s_overhead_blocks
        )
        # if self.has_hi:
        #     return self.s_blocks_count_hi << 32 | self.s_blocks_count_lo

        # return self.s_blocks_count_lo

    @property
    def s_r_blocks_count(self):
        if self.has_hi:
            return self.s_r_blocks_count_hi << 32 | self.s_r_blocks_count_lo

        return self.s_r_blocks_count_lo

    @property
    def s_free_blocks_count(self):
        if self.has_hi:
            return self.s_free_blocks_count_hi << 32 | self.s_free_blocks_count_lo

        return self.s_free_blocks_count_lo

    @property
    def expected_magic(self):
        return 0xEF53

    @property
    def magic(self):
        return self.s_magic

    @property
    def expected_checksum(self):
        if self.s_feature_ro_compat & EXT4_FEATURE_RO_COMPAT.METADATA_CSUM == 0:
            return None

        return self.s_checksum

    @property
    def checksum(self):
        if self.s_feature_ro_compat & EXT4_FEATURE_RO_COMPAT.METADATA_CSUM == 0:
            return None

        return crc32c(bytes(self)[: Superblock.s_checksum.offset])

    @property
    def seed(self):
        if self.s_feature_incompat & EXT4_FEATURE_INCOMPAT.CSUM_SEED != 0:
            return self.s_checksum_seed

        return crc32c(bytes(self.s_uuid))
