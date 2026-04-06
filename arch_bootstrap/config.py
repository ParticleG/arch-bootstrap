from __future__ import annotations

from typing import TYPE_CHECKING

from archinstall.lib.args import ArchConfig
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
from archinstall.lib.models.locale import LocaleConfiguration
from archinstall.lib.models.mirrors import (
    CustomRepository,
    MirrorConfiguration,
    SignCheck,
    SignOption,
)
from archinstall.lib.models.network import NetworkConfiguration, NicType
from archinstall.lib.models.packages import Repository
from archinstall.lib.models.profile import ProfileConfiguration
from archinstall.lib.models.users import Password, User
from archinstall.lib.profile.profiles_handler import profile_handler

from .constants import (
    ARCHLINUXCN_URL,
    BASE_PACKAGES,
    COUNTRY_TIMEZONES,
    GPU_PACKAGES,
)
from .detection import needs_kmscon
from .disk import build_disk_layout
from .mirrors import resolve_mirror_regions

if TYPE_CHECKING:
    from .wizard import WizardState


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
# Wizard state → config application
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
