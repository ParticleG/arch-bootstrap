#!/usr/bin/env python3
"""arch-bootstrap: Opinionated Arch Linux installer powered by archinstall.

Usage (on Arch ISO):
    curl -LO https://raw.githubusercontent.com/.../arch_bootstrap.py
    python arch_bootstrap.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: upgrade archinstall BEFORE importing it.
#
# The Arch ISO ships archinstall 3.x, but this script requires 4.1.
# If we detect the ISO environment and archinstall is outdated, upgrade it
# via pacman and re-exec ourselves so the new package is picked up by the
# Python import machinery.
# ---------------------------------------------------------------------------

_ARCHINSTALL_BOOTSTRAP_ENV = '_ARCH_BOOTSTRAP_UPGRADED'


def _needs_archinstall_upgrade() -> bool:
    """Return True if running on ISO and archinstall is not 4.x+."""
    if not Path('/run/archiso').exists():
        return False
    # Already upgraded in this process tree — don't loop
    if os.environ.get(_ARCHINSTALL_BOOTSTRAP_ENV) == '1':
        return False
    try:
        import archinstall  # noqa: F811
        version = getattr(archinstall, '__version__', '0.0.0')
        major = int(version.split('.')[0])
        return major < 4
    except (ImportError, ValueError, AttributeError):
        # archinstall missing entirely or version unparseable — upgrade
        return True


def _upgrade_and_reexec() -> None:
    """Upgrade archinstall via pacman, then re-exec this script."""
    print('arch-bootstrap: ISO detected with archinstall < 4.x — upgrading...')
    result = subprocess.run(
        ['pacman', '-Sy', '--noconfirm', 'archinstall'],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    if result.returncode != 0:
        print(
            f'WARNING: Failed to upgrade archinstall: {result.stderr.strip()}',
            file=sys.stderr,
        )
        print('Attempting to continue with existing version...', file=sys.stderr)
        return  # fall through — imports will either work or fail with a clear error

    # Mark that we've already upgraded to prevent infinite re-exec loop
    os.environ[_ARCHINSTALL_BOOTSTRAP_ENV] = '1'
    # Re-exec: replaces current process with a fresh Python interpreter that
    # will pick up the newly installed archinstall package.
    os.execv(sys.executable, [sys.executable] + sys.argv)


# Perform bootstrap check before ANY archinstall import
if __name__ == '__main__' and _needs_archinstall_upgrade():
    if os.geteuid() != 0:
        print('Error: This script must be run as root.', file=sys.stderr)
        sys.exit(1)
    _upgrade_and_reexec()

# ---------------------------------------------------------------------------
# archinstall imports (safe now — we are on 4.x+)
# ---------------------------------------------------------------------------

from archinstall.lib.applications.application_handler import ApplicationHandler
from archinstall.lib.args import ArchConfig, ArchConfigHandler
from archinstall.lib.authentication.authentication_handler import AuthenticationHandler
from archinstall.lib.configuration import ConfigurationOutput
from archinstall.lib.disk.device_handler import device_handler
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.disk.utils import disk_layouts
from archinstall.lib.general.general_menu import PostInstallationAction, select_post_installation
from archinstall.lib.global_menu import GlobalMenu
from archinstall.lib.installer import Installer, run_custom_user_commands
from archinstall.lib.menu.helpers import Confirmation, Input, Selection
from archinstall.lib.menu.util import delayed_warning, get_password
from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.models.application import (
    ApplicationConfiguration,
    Audio,
    AudioConfiguration,
    BluetoothConfiguration,
    PowerManagement,
    PowerManagementConfiguration,
    ZramAlgorithm,
    ZramConfiguration,
)
from archinstall.lib.models.authentication import AuthenticationConfiguration
from archinstall.lib.models.bootloader import Bootloader, BootloaderConfiguration
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
    SectorSize,
    Size,
    SnapshotConfig,
    SnapshotType,
    SubvolumeModification,
    Unit,
)
from archinstall.lib.models.locale import LocaleConfiguration
from archinstall.lib.models.mirrors import (
    CustomRepository,
    MirrorConfiguration,
    MirrorRegion,
    SignCheck,
    SignOption,
)
from archinstall.lib.models.network import NetworkConfiguration, NicType
from archinstall.lib.models.packages import Repository
from archinstall.lib.models.profile import ProfileConfiguration
from archinstall.lib.models.users import Password, User
from archinstall.lib.network.network_handler import install_network_config
from archinstall.lib.output import debug, error, info, warn
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.tui.ui.components import tui
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType

# =============================================================================
# Constants
# =============================================================================

BASE_PACKAGES: list[str] = ['neovim', 'git', '7zip', 'base-devel', 'zsh']

# GPU driver configuration
GPU_VENDORS: list[str] = ['amd', 'intel', 'nvidia_open', 'nouveau']

GPU_DETECT_PATTERNS: dict[str, str] = {
    'amd': r'VGA.*AMD|VGA.*ATI|Display.*AMD',
    'intel': r'VGA.*Intel|Display.*Intel',
    'nvidia_open': r'VGA.*NVIDIA|3D.*NVIDIA|Display.*NVIDIA',
    'nouveau': r'VGA.*NVIDIA|3D.*NVIDIA|Display.*NVIDIA',
}

GPU_LABELS: dict[str, str] = {
    'amd': 'AMD (Radeon)',
    'intel': 'Intel (HD/UHD/Arc)',
    'nvidia_open': 'NVIDIA Proprietary (Turing+)',
    'nouveau': 'NVIDIA Nouveau (Open Source)',
}

GPU_PACKAGES: dict[str, list[str]] = {
    'common': ['mesa'],
    'amd': ['vulkan-radeon', 'xf86-video-amdgpu', 'xf86-video-ati'],
    'intel': ['intel-media-driver', 'libva-intel-driver', 'vulkan-intel'],
    'nvidia_open': ['nvidia-open-dkms', 'dkms', 'libva-nvidia-driver'],
    'nouveau': ['xf86-video-nouveau', 'vulkan-nouveau'],
}

# Language options
LANGUAGES: dict[str, str] = {
    'zh_CN.UTF-8': '简体中文',
    'en_US.UTF-8': 'English',
    'ja_JP.UTF-8': '日本語',
}

# Country/region metadata
COUNTRY_NAMES: dict[str, str] = {
    'CN': 'China',
    'US': 'United States',
    'JP': 'Japan',
    'DE': 'Germany',
    'GB': 'United Kingdom',
    'FR': 'France',
    'KR': 'South Korea',
    'AU': 'Australia',
    'CA': 'Canada',
    'SG': 'Singapore',
    'TW': 'Taiwan',
    'HK': 'Hong Kong',
    'SE': 'Sweden',
    'NL': 'Netherlands',
    'IN': 'India',
    'BR': 'Brazil',
    'RU': 'Russia',
}

COUNTRY_TIMEZONES: dict[str, str] = {
    'CN': 'Asia/Shanghai',
    'US': 'America/New_York',
    'JP': 'Asia/Tokyo',
    'DE': 'Europe/Berlin',
    'GB': 'Europe/London',
    'FR': 'Europe/Paris',
    'KR': 'Asia/Seoul',
    'AU': 'Australia/Sydney',
    'CA': 'America/Toronto',
    'SG': 'Asia/Singapore',
    'TW': 'Asia/Taipei',
    'HK': 'Asia/Hong_Kong',
    'SE': 'Europe/Stockholm',
    'NL': 'Europe/Amsterdam',
    'IN': 'Asia/Kolkata',
    'BR': 'America/Sao_Paulo',
    'RU': 'Europe/Moscow',
}

# Countries shown in the region selection menu (display order)
REGION_MENU_COUNTRIES: list[str] = [
    'CN', 'US', 'JP', 'DE', 'GB', 'FR', 'KR', 'AU', 'CA', 'SG', 'TW', 'HK',
]

ARCHLINUXCN_URL = 'https://repo.archlinuxcn.org/$arch'

# Fallback mirror pools (used when MirrorListHandler has no data for a region)
FALLBACK_MIRRORS: dict[str, list[str]] = {
    'CN': [
        'https://mirrors.ustc.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.bfsu.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.aliyun.com/archlinux/$repo/os/$arch',
        'https://mirrors.hit.edu.cn/archlinux/$repo/os/$arch',
        'https://mirror.nju.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.hust.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.cqu.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.xjtu.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.jlu.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.jcut.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.qlu.edu.cn/archlinux/$repo/os/$arch',
    ],
    'US': [
        'https://mirrors.kernel.org/archlinux/$repo/os/$arch',
        'https://mirror.rackspace.com/archlinux/$repo/os/$arch',
        'https://mirrors.rit.edu/archlinux/$repo/os/$arch',
        'https://mirror.mtu.edu/archlinux/$repo/os/$arch',
        'https://mirrors.mit.edu/archlinux/$repo/os/$arch',
    ],
    'JP': [
        'https://ftp.jaist.ac.jp/pub/Linux/ArchLinux/$repo/os/$arch',
        'https://mirrors.cat.net/archlinux/$repo/os/$arch',
        'https://ftp.tsukuba.wide.ad.jp/Linux/archlinux/$repo/os/$arch',
    ],
    'DE': [
        'https://mirror.f4st.host/archlinux/$repo/os/$arch',
        'https://ftp.fau.de/archlinux/$repo/os/$arch',
        'https://mirror.netcologne.de/archlinux/$repo/os/$arch',
    ],
    'Worldwide': [
        'https://geo.mirror.pkgbuild.com/$repo/os/$arch',
        'https://mirror.rackspace.com/archlinux/$repo/os/$arch',
    ],
}

# Network backend options
NETWORK_BACKENDS: dict[str, str] = {
    'nm_iwd': 'NetworkManager (iwd backend)',
    'nm': 'NetworkManager (default backend)',
}

# Geolocation endpoints (tried in order, 2s timeout each)
GEO_ENDPOINTS: list[str] = [
    'https://ifconfig.co/country-iso',
    'https://ipinfo.io/country',
    'https://api.country.is/',
]

# NVIDIA Turing+ threshold (PCI Device ID >= 0x1e00)
NVIDIA_TURING_THRESHOLD = 0x1E00


# =============================================================================
# Detection helpers
# =============================================================================

def detect_country() -> str | None:
    """Detect country via IP geolocation. Returns ISO 3166-1 alpha-2 code or None."""
    import json
    import urllib.request

    for url in GEO_ENDPOINTS:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'curl/8.0'})
            with urllib.request.urlopen(req, timeout=2) as resp:
                body = resp.read().decode().strip()

                # Try JSON response first (e.g. api.country.is returns {"country":"US",...})
                try:
                    data = json.loads(body)
                    code = str(data.get('country', '')).strip().upper()
                except (json.JSONDecodeError, AttributeError):
                    code = body.upper()

                if re.match(r'^[A-Z]{2}$', code):
                    return code
        except Exception:
            continue

    return None


def detect_gpu() -> list[str]:
    """Detect GPUs via lspci. Returns list of pre-selected vendor keys.

    For NVIDIA, checks PCI Device ID to decide between nvidia_open (Turing+)
    and nouveau (older).
    """
    try:
        lspci_output = subprocess.check_output(
            ['lspci', '-nn'], text=True, stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    detected: list[str] = []

    # Check AMD and Intel
    for vendor in ('amd', 'intel'):
        if re.search(GPU_DETECT_PATTERNS[vendor], lspci_output):
            detected.append(vendor)

    # Check NVIDIA with Turing+ logic
    if re.search(GPU_DETECT_PATTERNS['nvidia_open'], lspci_output):
        # Extract NVIDIA PCI Device IDs: [10de:XXXX]
        nvidia_ids = re.findall(r'\[10de:([0-9a-fA-F]{4})\]', lspci_output)
        has_turing = any(int(did, 16) >= NVIDIA_TURING_THRESHOLD for did in nvidia_ids)
        detected.append('nvidia_open' if has_turing else 'nouveau')

    return detected


def detect_preferred_disk() -> Path | None:
    """Select preferred disk: first with no partitions, else first NVMe, else None."""
    try:
        devices = device_handler.devices
    except Exception:
        # Device enumeration can fail on exotic hardware or broken udev state
        return None

    # Filter out read-only, loop, and tiny disks (< 8 GiB)
    candidates = [
        d for d in devices
        if not d.device_info.read_only
        and d.device_info.type != 'loop'
        and d.device_info.total_size.convert(Unit.GiB, None).value >= 8
    ]

    if not candidates:
        return None

    # Prefer first disk with no partitions
    for dev in candidates:
        if not dev.partition_infos:
            return dev.device_info.path

    # Prefer first NVMe disk
    for dev in candidates:
        if 'nvme' in str(dev.device_info.path):
            return dev.device_info.path

    # No preference
    return None


def needs_kmscon(locale: str) -> bool:
    """Check if kmscon is needed for non-English locales (CJK console rendering)."""
    return locale != 'en_US.UTF-8'


def is_iso_environment() -> bool:
    """Check if running on the Arch ISO."""
    return Path('/run/archiso').exists()


def is_raw_tty() -> bool:
    """Check if running on a raw Linux TTY (no X/Wayland).

    Raw TTY cannot render CJK characters properly without kmscon.
    Returns True if TERM is 'linux' or stdin is /dev/tty[0-9]+.
    """
    if os.environ.get('TERM') == 'linux':
        return True
    try:
        tty_name = os.ttyname(0)
        if re.match(r'/dev/tty\d+', tty_name):
            return True
    except (OSError, AttributeError):
        pass
    return False


def cleanup_disk_locks() -> None:
    """Release disk locks: swap, LVM volume groups, LUKS containers.

    Must be called before filesystem operations to avoid 'Device busy' errors.
    """
    # Deactivate swap on all devices
    subprocess.run(['swapoff', '--all'], stderr=subprocess.DEVNULL, check=False)

    # Deactivate LVM volume groups (if lvm2 is available)
    try:
        subprocess.run(
            ['vgchange', '-an'], stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, check=False,
        )
    except FileNotFoundError:
        pass

    # Close LUKS containers
    try:
        dm_path = Path('/dev/mapper')
        if dm_path.exists():
            for dev in dm_path.iterdir():
                if dev.name == 'control':
                    continue
                subprocess.run(
                    ['cryptsetup', 'close', str(dev)],
                    stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, check=False,
                )
    except FileNotFoundError:
        pass


# =============================================================================
# Mirror resolution helper
# =============================================================================

def resolve_mirror_regions(
    country: str | None,
    mirror_list_handler: MirrorListHandler,
) -> list[MirrorRegion]:
    """Resolve mirror regions for a country, with fallback to hardcoded pools.

    1. Try MirrorListHandler's online data (reflector-backed).
    2. Fall back to FALLBACK_MIRRORS for the country.
    3. Fall back to FALLBACK_MIRRORS['Worldwide'].
    """
    if country and country in COUNTRY_NAMES:
        region_name = COUNTRY_NAMES[country]
        regions = mirror_list_handler.get_mirror_regions()
        matching = [r for r in regions if r.name == region_name]
        if matching:
            return matching

    # Fallback to hardcoded mirrors
    country_key = country if country and country in FALLBACK_MIRRORS else 'Worldwide'
    urls = FALLBACK_MIRRORS.get(country_key, FALLBACK_MIRRORS['Worldwide'])
    region_name = COUNTRY_NAMES.get(country, 'Worldwide') if country else 'Worldwide'
    return [MirrorRegion(name=region_name, urls=urls)]


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


# =============================================================================
# Config builder
# =============================================================================

def build_default_config(
    country: str | None,
    locale: str,
    mirror_list_handler: MirrorListHandler,
) -> ArchConfig:
    """Build ArchConfig with all opinionated defaults pre-filled."""
    config = ArchConfig()

    # Locale
    config.locale_config = LocaleConfiguration(
        kb_layout='',  # intentionally empty, set via vconsole.conf post-install
        sys_lang=locale,
        sys_enc='UTF-8',
    )

    # Bootloader: EFISTUB + UKI
    config.bootloader_config = BootloaderConfiguration(
        bootloader=Bootloader.Efistub,
        uki=True,
        removable=False,
    )

    # Applications: PipeWire + Bluetooth + tuned
    config.app_config = ApplicationConfiguration(
        audio_config=AudioConfiguration(audio=Audio.PIPEWIRE),
        bluetooth_config=BluetoothConfiguration(enabled=True),
        power_management_config=PowerManagementConfiguration(
            power_management=PowerManagement.TUNED,
        ),
    )

    # Swap: zram with lzo-rle
    config.swap = ZramConfiguration(enabled=True, algorithm=ZramAlgorithm.LZO_RLE)

    # Profile: Minimal
    minimal_profile = profile_handler.get_profile_by_name('Minimal')
    if minimal_profile:
        config.profile_config = ProfileConfiguration(profile=minimal_profile)

    # Network: default to NM+iwd
    config.network_config = NetworkConfiguration(type=NicType.NM_IWD)

    # Timezone (from detected country)
    if country and country in COUNTRY_TIMEZONES:
        config.timezone = COUNTRY_TIMEZONES[country]

    # Mirror configuration (with fallback pools)
    mirror_regions = resolve_mirror_regions(country, mirror_list_handler)
    config.mirror_config = MirrorConfiguration(mirror_regions=mirror_regions)

    # archlinuxcn repository for CN users
    if country == 'CN':
        config.mirror_config.custom_repositories.append(
            CustomRepository(
                name='archlinuxcn',
                url=ARCHLINUXCN_URL,
                sign_check=SignCheck.Optional,
                sign_option=SignOption.TrustAll,
            ),
        )

    # Hostname, kernel, NTP, packages, downloads
    config.hostname = 'archlinux'
    config.kernels = ['linux']
    config.ntp = True
    config.packages = list(BASE_PACKAGES)
    config.parallel_downloads = 0  # 0 = pacman default (5), matches Bash version

    return config


# =============================================================================
# Wizard steps
# =============================================================================

# Each wizard step is an async function that modifies a WizardState.
# Returns 'next', 'back', or 'abort'.

class WizardState:
    """Mutable state accumulated during the wizard."""

    def __init__(self) -> None:
        self.country: str | None = None
        self.locale: str = 'en_US.UTF-8'
        self.disk_device: BDevice | None = None
        self.network_type: NicType = NicType.NM_IWD
        self.multilib: bool = True
        self.gpu_vendors: list[str] = []
        self.username: str = ''
        self.user_password: Password | None = None
        self.root_password: Password | None = None
        self.detected_country: str | None = None
        self.detected_gpu: list[str] = []
        self.preferred_disk: Path | None = None


async def step_language(state: WizardState) -> str:
    """Step 1: Select system language."""
    raw_tty = is_raw_tty()

    items = [
        MenuItem(f'{label} ({code})', value=code)
        for code, label in LANGUAGES.items()
    ]
    group = MenuItemGroup(items)

    # On raw TTY, default to English to avoid CJK rendering issues
    if raw_tty and state.locale != 'en_US.UTF-8':
        header = (
            'Select system language\n'
            'NOTE: Raw TTY detected — CJK languages will install kmscon\n'
            'for proper console rendering after reboot.'
        )
    else:
        header = 'Select system language / 选择系统语言 / システム言語を選択'

    group.set_default_by_value(state.locale)
    group.set_focus_by_value(state.locale)

    result = await Selection[str](
        group,
        header=header,
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.locale = result.get_value()
            return 'next'
        case _:
            return 'back'


async def step_region(state: WizardState) -> str:
    """Step 2: Select country/region."""
    items = [
        MenuItem(f'{COUNTRY_NAMES[code]} ({code})', value=code)
        for code in REGION_MENU_COUNTRIES
    ]
    group = MenuItemGroup(items)

    preset = state.country or state.detected_country
    if preset and preset in REGION_MENU_COUNTRIES:
        group.set_default_by_value(preset)
        group.set_focus_by_value(preset)

    result = await Selection[str](
        group,
        header='Select your country/region',
        allow_skip=True,
        enable_filter=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.country = result.get_value()
            return 'next'
        case _:
            return 'back'


async def step_disk(state: WizardState) -> str:
    """Step 3: Select target disk."""
    try:
        devices = [
            d for d in device_handler.devices
            if not d.device_info.read_only
            and d.device_info.type != 'loop'
        ]
    except Exception:
        devices = []

    if not devices:
        # No suitable disks found
        await Confirmation(
            header='No suitable disks found. Cannot proceed.',
            allow_skip=False,
            preset=True,
        ).show()
        return 'abort'

    items = []
    for dev in devices:
        di = dev.device_info
        size_str = di.total_size.format_highest()
        part_count = len(dev.partition_infos)
        label = f'{di.path}  {di.model}  {size_str}  ({part_count} partitions)'
        items.append(MenuItem(label, value=dev))

    group = MenuItemGroup(items)

    # Try to preselect preferred disk
    if state.preferred_disk:
        for dev in devices:
            if dev.device_info.path == state.preferred_disk:
                group.set_default_by_value(dev)
                group.set_focus_by_value(dev)
                break

    result = await Selection[BDevice](
        group,
        header='Select target disk (ALL DATA WILL BE ERASED)',
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.disk_device = result.get_value()
            return 'next'
        case _:
            return 'back'


async def step_network(state: WizardState) -> str:
    """Step 4: Select network backend."""
    items = [
        MenuItem(label, value=key)
        for key, label in NETWORK_BACKENDS.items()
    ]
    group = MenuItemGroup(items)

    current = state.network_type.value
    group.set_default_by_value(current)
    group.set_focus_by_value(current)

    result = await Selection[str](
        group,
        header='Select network backend',
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            value = result.get_value()
            state.network_type = NicType(value)
            return 'next'
        case _:
            return 'back'


async def step_repos(state: WizardState) -> str:
    """Step 5: Enable multilib repository."""
    result = await Confirmation(
        header='Enable multilib repository? (32-bit library support)',
        allow_skip=True,
        preset=state.multilib,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.multilib = result.item() == MenuItem.yes()
            return 'next'
        case _:
            return 'back'


async def step_gpu_drivers(state: WizardState) -> str:
    """Step 6: Select GPU drivers."""
    items = [
        MenuItem(GPU_LABELS[vendor], value=vendor)
        for vendor in GPU_VENDORS
    ]
    group = MenuItemGroup(items)

    # Pre-select detected GPUs
    preselect = state.gpu_vendors if state.gpu_vendors else state.detected_gpu
    if preselect:
        group.set_selected_by_value(preselect)

    result = await Selection[str](
        group,
        header='Select GPU drivers (Space to toggle, Enter to confirm)',
        multi=True,
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.gpu_vendors = result.get_values()
            return 'next'
        case _:
            return 'back'


async def step_username(state: WizardState) -> str:
    """Step 7: Enter username."""
    default = state.username or os.environ.get('SUDO_USER', '') or os.environ.get('USER', '')
    # Filter out 'root' — not a useful default
    if default == 'root':
        default = ''

    def validate(value: str) -> str | None:
        if not value:
            return 'Username cannot be empty'
        if not re.match(r'^[a-z_][a-z0-9_-]*$', value):
            return 'Must start with a-z or _, followed by a-z 0-9 _ -'
        if len(value) > 32:
            return 'Username must be 32 characters or fewer'
        return None

    result = await Input(
        header='Enter username',
        default_value=default if default else None,
        allow_skip=True,
        validator_callback=validate,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            value = result.get_value()
            if value:
                state.username = value
                return 'next'
            return 'back'
        case _:
            return 'back'


async def step_user_password(state: WizardState) -> str:
    """Step 8: Enter user password."""
    password = await get_password(
        header=f'Enter password for {state.username}',
        allow_skip=True,
    )

    if password is None:
        return 'back'

    state.user_password = password
    return 'next'


async def step_root_password(state: WizardState) -> str:
    """Step 9: Enter root password (optional)."""
    result = await Confirmation(
        header='Set a root password? (skip for no root login)',
        allow_skip=True,
        preset=False,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            if result.item() == MenuItem.yes():
                password = await get_password(
                    header='Enter root password',
                    allow_skip=True,
                )
                if password is None:
                    return 'back'
                state.root_password = password
            else:
                state.root_password = None
            return 'next'
        case _:
            return 'back'


# =============================================================================
# Confirmation panel
# =============================================================================

async def step_confirm(
    state: WizardState,
    config: ArchConfig,
) -> str:
    """Confirmation panel: Install / Advanced Modify / Cancel."""
    # Build summary text
    kmscon_needed = needs_kmscon(state.locale)
    lines = [
        f'Language:     {state.locale}',
        f'Region:       {COUNTRY_NAMES.get(state.country, "Unknown") if state.country else "Not set"}',
        f'Timezone:     {config.timezone}',
        f'Disk:         {state.disk_device.device_info.path if state.disk_device else "Not set"}'
        f'  ({state.disk_device.device_info.total_size.format_highest() if state.disk_device else ""})',
        f'Network:      {state.network_type.display_msg()}',
        f'Multilib:     {"Enabled" if state.multilib else "Disabled"}',
        f'GPU Drivers:  {", ".join(GPU_LABELS.get(v, v) for v in state.gpu_vendors) or "None"}',
        f'Username:     {state.username}',
        f'Root login:   {"Enabled" if state.root_password else "Disabled"}',
        f'kmscon:       {"Added (CJK console)" if kmscon_needed else "Not needed"}',
        '',
        '── Fixed defaults ──',
        'Bootloader:   EFISTUB (UKI)',
        'Filesystem:   Btrfs + zstd + Snapper',
        'Audio:        PipeWire',
        'Bluetooth:    Enabled',
        'Power:        tuned',
        'Swap:         zram (lzo-rle)',
        'Profile:      Minimal',
    ]
    summary = '\n'.join(lines)

    items = [
        MenuItem('Install', value='install'),
        MenuItem('Advanced Modify (archinstall menu)', value='advanced'),
        MenuItem('Cancel', value='cancel'),
    ]
    group = MenuItemGroup(items)
    group.set_focus_by_value('install')

    result = await Selection[str](
        group,
        header=summary,
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            return result.get_value()
        case _:
            return 'back'


# =============================================================================
# Wizard runner
# =============================================================================

def apply_wizard_state_to_config(
    state: WizardState,
    config: ArchConfig,
    mirror_list_handler: MirrorListHandler,
) -> None:
    """Apply wizard selections to ArchConfig."""
    # Locale
    config.locale_config = LocaleConfiguration(
        kb_layout='',
        sys_lang=state.locale,
        sys_enc='UTF-8',
    )

    # Timezone
    if state.country and state.country in COUNTRY_TIMEZONES:
        config.timezone = COUNTRY_TIMEZONES[state.country]

    # Mirror regions (with fallback pools)
    mirror_regions = resolve_mirror_regions(state.country, mirror_list_handler)
    if config.mirror_config is None:
        config.mirror_config = MirrorConfiguration()
    config.mirror_config.mirror_regions = mirror_regions

    # archlinuxcn
    # Remove existing archlinuxcn if any
    config.mirror_config.custom_repositories = [
        r for r in config.mirror_config.custom_repositories
        if r.name != 'archlinuxcn'
    ]
    if state.country == 'CN':
        config.mirror_config.custom_repositories.append(
            CustomRepository(
                name='archlinuxcn',
                url=ARCHLINUXCN_URL,
                sign_check=SignCheck.Optional,
                sign_option=SignOption.TrustAll,
            ),
        )

    # Multilib
    if state.multilib:
        if Repository.Multilib not in config.mirror_config.optional_repositories:
            config.mirror_config.optional_repositories.append(Repository.Multilib)
    else:
        config.mirror_config.optional_repositories = [
            r for r in config.mirror_config.optional_repositories
            if r != Repository.Multilib
        ]

    # Disk layout
    if state.disk_device:
        config.disk_config = build_disk_layout(state.disk_device)

    # Network
    config.network_config = NetworkConfiguration(type=state.network_type)

    # GPU packages
    gpu_packages = list(GPU_PACKAGES['common'])  # always include mesa
    for vendor in state.gpu_vendors:
        gpu_packages.extend(GPU_PACKAGES.get(vendor, []))
    # Merge with base packages (avoid duplicates)
    all_packages = list(BASE_PACKAGES)
    for pkg in gpu_packages:
        if pkg not in all_packages:
            all_packages.append(pkg)
    # kmscon for non-English locales
    if needs_kmscon(state.locale) and 'kmscon' not in all_packages:
        all_packages.append('kmscon')
    config.packages = all_packages

    # Authentication
    users = []
    if state.username and state.user_password:
        users.append(User(
            username=state.username,
            password=state.user_password,
            sudo=True,
        ))
    config.auth_config = AuthenticationConfiguration(
        root_enc_password=state.root_password,
        users=users,
    )

    # Custom commands for kmscon setup
    if needs_kmscon(state.locale):
        config.custom_commands = [
            'systemctl disable getty@tty1',
            'systemctl enable kmsconvt@tty1',
        ]
    else:
        config.custom_commands = []

    # Services (empty — handled by app_config and profile)
    config.services = []


async def run_wizard(
    state: WizardState,
    config: ArchConfig,
    mirror_list_handler: MirrorListHandler,
) -> str:
    """Run the complete wizard. Returns 'install', 'advanced', or 'abort'."""
    steps = [
        step_language,
        step_region,
        step_disk,
        step_network,
        step_repos,
        step_gpu_drivers,
        step_username,
        step_user_password,
        step_root_password,
    ]

    current = 0
    while current < len(steps):
        result = await steps[current](state)
        if result == 'next':
            current += 1
        elif result == 'back':
            if current > 0:
                current -= 1
            # If at first step, stay there (can't go further back)
        elif result == 'abort':
            return 'abort'

    # Apply wizard state to config before showing confirmation
    apply_wizard_state_to_config(state, config, mirror_list_handler)

    # Confirmation loop (can return to wizard or open GlobalMenu)
    while True:
        action = await step_confirm(state, config)
        if action == 'install':
            return 'install'
        elif action == 'cancel' or action == 'back':
            # Go back to the last wizard step
            current = len(steps) - 1
            while current >= 0:
                result = await steps[current](state)
                if result == 'next':
                    current += 1
                    if current >= len(steps):
                        apply_wizard_state_to_config(state, config, mirror_list_handler)
                        break
                elif result == 'back':
                    current = max(0, current - 1)
                elif result == 'abort':
                    return 'abort'
        elif action == 'advanced':
            return 'advanced'

    return 'abort'


# =============================================================================
# Advanced menu (GlobalMenu escape hatch)
# =============================================================================

def run_global_menu(
    config: ArchConfig,
    mirror_list_handler: MirrorListHandler,
) -> ArchConfig | None:
    """Open archinstall's native GlobalMenu for advanced configuration."""
    global_menu = GlobalMenu(
        config,
        mirror_list_handler,
        skip_boot=False,
        title='arch-bootstrap — Advanced Configuration',
    )

    return tui.run(global_menu)


# =============================================================================
# Installation
# =============================================================================

def perform_installation(
    config: ArchConfig,
    mirror_list_handler: MirrorListHandler,
) -> None:
    """Execute the installation using archinstall's Installer."""
    start_time = time.monotonic()
    info('Starting installation...')

    auth_handler = AuthenticationHandler()
    application_handler = ApplicationHandler()

    if not config.disk_config:
        error('No disk configuration provided')
        return

    disk_config = config.disk_config
    run_mkinitcpio = not config.bootloader_config or not config.bootloader_config.uki
    locale_config = config.locale_config
    optional_repos = config.mirror_config.optional_repositories if config.mirror_config else []
    mountpoint = disk_config.mountpoint if disk_config.mountpoint else Path('/mnt')

    with Installer(
        mountpoint,
        disk_config,
        kernels=config.kernels,
        silent=False,
    ) as installation:
        if disk_config.config_type != DiskLayoutType.Pre_mount:
            installation.mount_ordered_layout()

        installation.sanity_check(offline=False, skip_ntp=False, skip_wkd=False)

        if mirror_config := config.mirror_config:
            installation.set_mirrors(mirror_list_handler, mirror_config, on_target=False)

        installation.minimal_installation(
            optional_repositories=optional_repos,
            mkinitcpio=run_mkinitcpio,
            hostname=config.hostname,
            locale_config=locale_config,
        )

        if mirror_config := config.mirror_config:
            installation.set_mirrors(mirror_list_handler, mirror_config, on_target=True)

        if config.swap and config.swap.enabled:
            installation.setup_swap(algo=config.swap.algorithm)

        if config.bootloader_config and config.bootloader_config.bootloader != Bootloader.NO_BOOTLOADER:
            installation.add_bootloader(
                config.bootloader_config.bootloader,
                config.bootloader_config.uki,
                config.bootloader_config.removable,
            )

        if config.network_config:
            install_network_config(config.network_config, installation, config.profile_config)

        users = None
        if config.auth_config:
            if config.auth_config.users:
                users = config.auth_config.users
                installation.create_users(config.auth_config.users)
                auth_handler.setup_auth(installation, config.auth_config, config.hostname)

        if app_config := config.app_config:
            application_handler.install_applications(installation, app_config)

        if profile_config := config.profile_config:
            profile_handler.install_profile_config(installation, profile_config)

        if config.packages and config.packages[0] != '':
            installation.add_additional_packages(config.packages)

        if timezone := config.timezone:
            installation.set_timezone(timezone)

        if config.ntp:
            installation.activate_time_synchronization()

        if config.auth_config and config.auth_config.root_enc_password:
            root_user = User('root', config.auth_config.root_enc_password, False)
            installation.set_user_password(root_user)

        if (profile_config := config.profile_config) and profile_config.profile:
            profile_config.profile.post_install(installation)
            if users:
                profile_config.profile.provision(installation, users)

        if services := config.services:
            installation.enable_service(services)

        if disk_config.has_default_btrfs_vols():
            btrfs_options = disk_config.btrfs_options
            snapshot_config = btrfs_options.snapshot_config if btrfs_options else None
            snapshot_type = snapshot_config.snapshot_type if snapshot_config else None
            if snapshot_type:
                bootloader = config.bootloader_config.bootloader if config.bootloader_config else None
                installation.setup_btrfs_snapshot(snapshot_type, bootloader)

        if cc := config.custom_commands:
            run_custom_user_commands(cc, installation)

        installation.genfstab()

        debug(f'Disk states after installing:\n{disk_layouts()}')

    # Post-install: write keyboard layout to vconsole.conf
    chroot_dir = mountpoint
    if not (chroot_dir / 'etc').exists():
        chroot_dir = Path('/mnt')

    vconsole = chroot_dir / 'etc' / 'vconsole.conf'
    vconsole.write_text('KEYMAP=us\n')

    elapsed_time = time.monotonic() - start_time
    info(f'Installation completed in {elapsed_time:.0f} seconds.')

    # Post-installation action
    action: PostInstallationAction = tui.run(lambda: select_post_installation(elapsed_time))
    match action:
        case PostInstallationAction.EXIT:
            pass
        case PostInstallationAction.REBOOT:
            os.system('reboot')
        case PostInstallationAction.CHROOT:
            os.system(f'arch-chroot {chroot_dir}')


# =============================================================================
# Main entry point
# =============================================================================

def main() -> None:
    # Root check (also checked in bootstrap, but needed when imported as library)
    if os.geteuid() != 0:
        print('Error: This script must be run as root.', file=sys.stderr)
        sys.exit(1)

    info('arch-bootstrap: Opinionated Arch Linux installer')
    info('Detecting environment...')

    # Phase 1: Auto-detection (silent)
    detected_country = detect_country()
    if detected_country:
        info(f'  Detected country: {detected_country} ({COUNTRY_NAMES.get(detected_country, "Unknown")})')

    detected_gpu = detect_gpu()
    if detected_gpu:
        info(f'  Detected GPU: {", ".join(GPU_LABELS.get(v, v) for v in detected_gpu)}')

    preferred_disk = detect_preferred_disk()
    if preferred_disk:
        info(f'  Preferred disk: {preferred_disk}')

    # Initialize mirror list handler
    mirror_list_handler = MirrorListHandler(offline=False, verbose=False)

    # Build initial config with defaults
    initial_locale = 'zh_CN.UTF-8' if detected_country == 'CN' else 'en_US.UTF-8'
    config = build_default_config(detected_country, initial_locale, mirror_list_handler)

    # Initialize wizard state with detection results
    state = WizardState()
    state.detected_country = detected_country
    state.country = detected_country
    state.locale = initial_locale
    state.detected_gpu = detected_gpu
    state.gpu_vendors = list(detected_gpu)
    state.preferred_disk = preferred_disk

    # Phase 2: Interactive wizard
    while True:
        action = tui.run(lambda: run_wizard(state, config, mirror_list_handler))

        if action == 'abort':
            info('Installation aborted.')
            sys.exit(0)

        if action == 'advanced':
            # Open GlobalMenu for advanced modification
            result = run_global_menu(config, mirror_list_handler)
            if result is None:
                # User cancelled GlobalMenu, return to confirmation
                continue
            # Config was modified in-place by GlobalMenu
            continue

        if action == 'install':
            break

    # Phase 3: Disk formatting warning
    if config.disk_config:
        info('Preparing disk operations...')

        # Release disk locks (swap, LVM, LUKS) to avoid 'Device busy'
        cleanup_disk_locks()

        fs_handler = FilesystemHandler(config.disk_config)

        # Countdown warning before destructive operation
        delayed_warning('\nWARNING: All data on the selected disk will be destroyed!')

        fs_handler.perform_filesystem_operations()

    # Apply mirrors to live ISO before installation (speeds up pacstrap)
    if is_iso_environment() and config.mirror_config:
        mirrorlist_path = Path('/etc/pacman.d/mirrorlist')
        mirror_content = config.mirror_config.regions_config(
            mirror_list_handler, speed_sort=True,
        )
        if mirror_content.strip():
            mirrorlist_path.write_text(mirror_content)
            info('Applied fast mirrors to live ISO.')

    # Phase 4: Execute installation
    perform_installation(config, mirror_list_handler)


if __name__ == '__main__':
    main()
