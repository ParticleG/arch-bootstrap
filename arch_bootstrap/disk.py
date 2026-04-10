from __future__ import annotations

from pathlib import Path

from archinstall.lib.models.device import (
    BDevice,
    BtrfsMountOption,
    BtrfsOptions,
    DeviceModification,
    DiskLayoutConfiguration,
    DiskLayoutType,
    FilesystemType,
    ModificationStatus,
    PartitionFlag,
    PartitionModification,
    PartitionType,
    Size,
    SnapshotConfig,
    SnapshotType,
    SubvolumeModification,
    Unit,
)


# =============================================================================
# Partition geometry constants (MiB)
# =============================================================================

ALIGNMENT_MIB = 1       # GPT protective / alignment gap at start
EFI_PARTITION_MIB = 1025  # ALIGNMENT_MIB + 1 GiB (1024 MiB) for EFI
GPT_BACKUP_MIB = 1       # Reserved for GPT backup header at end
MIN_DISK_SIZE_MIB = 8 * 1024  # 8 GiB minimum usable disk size


# =============================================================================
# Disk layout builder
# =============================================================================

def build_disk_layout(device: BDevice) -> DiskLayoutConfiguration:
    """Build opinionated disk layout: 1 GiB EFI + Btrfs remainder with subvolumes."""
    sector_size = device.device_info.sector_size
    total_bytes = device.device_info.total_size.convert(Unit.B, None).value
    total_mib = total_bytes // (1024 * 1024)

    if total_mib < MIN_DISK_SIZE_MIB:
        raise ValueError(
            f'Disk too small: {total_mib} MiB '
            f'(minimum {MIN_DISK_SIZE_MIB} MiB / {MIN_DISK_SIZE_MIB // 1024} GiB)'
        )

    # Partition geometry (MiB-aligned)
    efi_start = Size(ALIGNMENT_MIB, Unit.MiB, sector_size)
    efi_length = Size(1, Unit.GiB, sector_size)
    root_start = Size(EFI_PARTITION_MIB, Unit.MiB, sector_size)

    # Root partition: remaining space minus EFI area and GPT backup header
    root_length_mib = total_mib - EFI_PARTITION_MIB - GPT_BACKUP_MIB
    root_length = Size(max(root_length_mib, 1), Unit.MiB, sector_size)

    efi_partition = PartitionModification(
        status=ModificationStatus.Create,
        type=PartitionType.Primary,
        start=efi_start,
        length=efi_length,
        fs_type=FilesystemType.Fat32,
        mountpoint=Path('/boot'),
        flags=[PartitionFlag.BOOT, PartitionFlag.ESP],
    )

    root_partition = PartitionModification(
        status=ModificationStatus.Create,
        type=PartitionType.Primary,
        start=root_start,
        length=root_length,
        fs_type=FilesystemType.Btrfs,
        mountpoint=None,  # mountpoint handled by subvolumes
        mount_options=[BtrfsMountOption.compress.value],
        btrfs_subvols=[
            SubvolumeModification(Path('@'), Path('/')),
            SubvolumeModification(Path('@home'), Path('/home')),
            SubvolumeModification(Path('@log'), Path('/var/log')),
            SubvolumeModification(Path('@pkg'), Path('/var/cache/pacman/pkg')),
        ],
    )

    device_mod = DeviceModification(device=device, wipe=True)
    device_mod.add_partition(efi_partition)
    device_mod.add_partition(root_partition)

    return DiskLayoutConfiguration(
        config_type=DiskLayoutType.Default,
        device_modifications=[device_mod],
        btrfs_options=BtrfsOptions(
            snapshot_config=SnapshotConfig(snapshot_type=SnapshotType.Snapper),
        ),
    )
