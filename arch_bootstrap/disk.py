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
# Disk layout builder
# =============================================================================

def build_disk_layout(device: BDevice) -> DiskLayoutConfiguration:
    """Build opinionated disk layout: 1 GiB EFI + Btrfs remainder with subvolumes."""
    sector_size = device.device_info.sector_size
    total_bytes = device.device_info.total_size.convert(Unit.B, None).value

    # Partition geometry (MiB-aligned)
    efi_start = Size(1, Unit.MiB, sector_size)
    efi_length = Size(1, Unit.GiB, sector_size)
    root_start = Size(1 + 1024, Unit.MiB, sector_size)  # 1 MiB + 1 GiB = 1025 MiB

    # Root partition: remaining space minus 1 MiB for GPT backup header
    total_mib = total_bytes // (1024 * 1024)
    root_length_mib = total_mib - 1025 - 1  # subtract EFI start+size and GPT backup
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
