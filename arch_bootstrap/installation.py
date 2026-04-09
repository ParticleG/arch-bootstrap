from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from archinstall.lib.applications.application_handler import ApplicationHandler
from archinstall.lib.args import ArchConfig
from archinstall.lib.authentication.authentication_handler import AuthenticationHandler
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.disk.utils import disk_layouts
from archinstall.lib.general.general_menu import PostInstallationAction, select_post_installation
from archinstall.lib.global_menu import GlobalMenu
from archinstall.lib.installer import Installer, run_custom_user_commands
from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.models.bootloader import Bootloader
from archinstall.lib.models.device import DiskLayoutType
from archinstall.lib.models.users import User
from archinstall.lib.network.network_handler import install_network_config
from archinstall.lib.output import Font, debug, error, info
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.tui.ui.components import tui

from .config import generate_fontconfig, generate_kmscon_config
from .constants import (
    BROWSER_OPTIONS,
    GHPROXY_CHUNK_URL,
    GHPROXY_FALLBACK,
    OMZ_INSTALL_URL,
    OMZ_REMOTE_GITHUB,
)
from .detection import calculate_kmscon_font_size, needs_kmscon
from .i18n import t


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
# Prefixed logging helpers
# =============================================================================

_PREFIX = '[arch-bootstrap]'


def _info(msg: str) -> None:
    """Log an info message with a colored [arch-bootstrap] prefix."""
    info(f'{_PREFIX} {msg}', fg='cyan', font=[Font.bold])


def _debug(msg: str) -> None:
    """Log a debug message with a colored [arch-bootstrap] prefix."""
    debug(f'{_PREFIX} {msg}', fg='cyan')


# =============================================================================
# GitHub proxy resolution (for CN oh-my-zsh)
# =============================================================================

def _resolve_omz_remote(country: str | None) -> str | None:
    """Resolve the oh-my-zsh REMOTE git URL for CN users.

    For non-CN: returns None (use default upstream).
    For CN: resolves GitHub proxy and returns proxied git URL.

    ghproxy.link is a Vue SPA; available proxy domains are embedded in a
    webpack JS chunk as href="https://gh<word>.<tld>".  We parse the chunk
    to extract the first available domain, then wrap the git URL with it.
    """
    if country != 'CN':
        return None

    _info('China detected, resolving GitHub proxy for oh-my-zsh...')

    # Try ghproxy.link — parse JS chunk for available proxy domain
    try:
        req = urllib.request.Request(GHPROXY_CHUNK_URL)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
        matches = re.findall(r'href=.{0,5}(https://gh[a-z0-9]+\.[a-z]+)', content)
        if matches:
            proxy = matches[0]
            _info(f'Found proxy: {proxy}')
            return f'{proxy}/{OMZ_REMOTE_GITHUB}'
    except Exception:
        pass

    # Use fallback proxy directly (don't test with HEAD — many proxies reject it,
    # which caused the previous code to silently fall through to direct GitHub)
    _info(f'Using fallback proxy: {GHPROXY_FALLBACK}')
    return f'{GHPROXY_FALLBACK}/{OMZ_REMOTE_GITHUB}'


# =============================================================================
# WiFi connection transfer
# =============================================================================

def _copy_wifi_connections(chroot_dir: Path) -> None:
    """Copy WiFi connection configs from the live ISO to the new system.

    Transfers both iwd network profiles (/var/lib/iwd/*.psk etc.) and
    NetworkManager connection files (/etc/NetworkManager/system-connections/)
    so the installed system automatically connects to known WiFi networks.
    """
    _info(t('wifi.copying'))
    count = 0

    # Copy iwd network configs (*.psk, *.open, *.8021x)
    iwd_src = Path('/var/lib/iwd')
    if iwd_src.exists():
        iwd_dst = chroot_dir / 'var' / 'lib' / 'iwd'
        iwd_dst.mkdir(parents=True, exist_ok=True)
        for f in iwd_src.iterdir():
            if f.is_file() and f.suffix in ('.psk', '.open', '.8021x'):
                shutil.copy2(f, iwd_dst / f.name)
                _debug(f'Copied iwd config: {f.name}')
                count += 1

    # Copy NetworkManager connection files
    nm_src = Path('/etc/NetworkManager/system-connections')
    if nm_src.exists():
        nm_dst = chroot_dir / 'etc' / 'NetworkManager' / 'system-connections'
        nm_dst.mkdir(parents=True, exist_ok=True)
        for f in nm_src.iterdir():
            if f.is_file():
                shutil.copy2(f, nm_dst / f.name)
                _debug(f'Copied NM connection: {f.name}')
                count += 1

    if count > 0:
        _info(t('wifi.copied') % count)


# =============================================================================
# paru AUR helper installation
# =============================================================================

def _install_paru(
    chroot_dir: Path,
    username: str,
    country: str | None = None,
) -> bool:
    """Install paru AUR helper in the chroot.

    For CN users: paru is available in the archlinuxcn repository and can
    be installed directly via pacman.
    For other users: paru-bin is built from the AUR via makepkg (pre-built
    binary, no Rust compilation needed).

    Returns True if paru was installed successfully.
    """
    _info(t('paru.installing'))

    if country == 'CN':
        # archlinuxcn repo should be configured — install via pacman
        result = subprocess.run(
            ['arch-chroot', str(chroot_dir),
             'pacman', '-S', '--noconfirm', '--needed', 'paru'],
            check=False,
        )
        if result.returncode == 0:
            _info(t('paru.installed_pacman'))
            return True
        _info('pacman install failed, falling back to AUR build...')

    # Build paru-bin from AUR (binary package, no compilation needed)
    build_script = (
        'export LANG=C.UTF-8; '
        'set -e; '
        'cd /tmp; '
        'rm -rf paru-bin; '
        'git clone https://aur.archlinux.org/paru-bin.git; '
        'cd paru-bin; '
        'makepkg -si --noconfirm --needed'
    )
    result = subprocess.run(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c', build_script],
        check=False,
    )
    if result.returncode == 0:
        _info(t('paru.installed_aur'))
        return True

    _info(t('paru.failed') % result.returncode)
    return False


# =============================================================================
# CN GitHub proxy for git in chroot
# =============================================================================

def _setup_cn_git_proxy(chroot_dir: Path) -> None:
    """Write GitHub URL rewrite to /etc/gitconfig for CN users.

    This enables git operations (including makepkg and paru source fetches)
    to use a GitHub proxy.  Written to /etc/gitconfig (system-level git
    config) which is read by all git invocations, including those from
    makepkg (which nullifies GIT_CONFIG_GLOBAL but NOT GIT_CONFIG_SYSTEM).
    """
    # Resolve proxy URL (reuse logic from dms.py)
    proxy = None
    try:
        req = urllib.request.Request(GHPROXY_CHUNK_URL)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
        matches = re.findall(r'href=.{0,5}(https://gh[a-z0-9]+\.[a-z]+)', content)
        if matches:
            proxy = matches[0]
    except Exception:
        pass

    if not proxy:
        proxy = GHPROXY_FALLBACK

    _info(f'CN: GitHub proxy for git → {proxy}')
    gitconfig = chroot_dir / 'etc' / 'gitconfig'
    gitconfig.write_text(
        f'[url "{proxy}/https://github.com/"]\n'
        f'\tinsteadOf = https://github.com/\n'
    )


# =============================================================================
# AUR browser installation
# =============================================================================

def _install_aur_browsers(
    chroot_dir: Path,
    username: str,
    browsers: list[str],
) -> None:
    """Install AUR-only browser packages via paru.

    Only called when paru is available and there are AUR browsers selected.
    """
    aur_packages = []
    for key in browsers:
        info = BROWSER_OPTIONS.get(key, {})
        if info.get('aur', False):
            aur_packages.append(info['package'])

    if not aur_packages:
        return

    pkg_str = ' '.join(shlex.quote(p) for p in aur_packages)
    _info(f'Installing AUR browsers: {", ".join(aur_packages)}')

    result = subprocess.run(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c',
         f'LANG=C.UTF-8 paru -S --noconfirm --needed --skipreview {pkg_str}'],
        check=False,
    )
    if result.returncode != 0:
        _info(f'AUR browser installation failed (exit {result.returncode}), skipping')


# =============================================================================
# Installation
# =============================================================================

def perform_installation(
    config: ArchConfig,
    mirror_list_handler: MirrorListHandler,
    kmscon_font_name: str = '',
    screen_resolution: tuple[int, int] | None = None,
    gpu_vendors: list[str] | None = None,
    username: str = '',
    country: str | None = None,
    desktop_env: str = 'minimal',
    dms_compositor: str = 'niri',
    dms_terminal: str = 'ghostty',
    browsers: list[str] | None = None,
) -> None:
    """Execute the installation using archinstall's Installer."""
    start_time = time.monotonic()
    _info('Starting installation...')

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

        _debug(f'Disk states after installing:\n{disk_layouts()}')

    # Post-install: write keyboard layout to vconsole.conf
    chroot_dir = mountpoint
    if not (chroot_dir / 'etc').exists():
        chroot_dir = Path('/mnt')

    vconsole = chroot_dir / 'etc' / 'vconsole.conf'
    vconsole.write_text('KEYMAP=us\n')

    # Post-install: write kmscon configuration if needed
    locale = config.locale_config.sys_lang if config.locale_config else 'en_US.UTF-8'
    if needs_kmscon(locale) and kmscon_font_name:
        font_size = calculate_kmscon_font_size(screen_resolution)
        has_gpu = bool(gpu_vendors)
        kmscon_conf_content = generate_kmscon_config(kmscon_font_name, font_size, has_gpu)

        kmscon_dir = chroot_dir / 'etc' / 'kmscon'
        kmscon_dir.mkdir(parents=True, exist_ok=True)
        kmscon_conf = kmscon_dir / 'kmscon.conf'
        kmscon_conf.write_text(kmscon_conf_content)
        _info(f'Written kmscon.conf (font: {kmscon_font_name}, size: {font_size})')

    # Post-install: write user fontconfig for CJK locales
    if needs_kmscon(locale) and kmscon_font_name and username:
        fontconfig_content = generate_fontconfig(kmscon_font_name, locale)
        user_home = chroot_dir / 'home' / username
        fontconfig_dir = user_home / '.config' / 'fontconfig'
        fontconfig_dir.mkdir(parents=True, exist_ok=True)
        fontconfig_file = fontconfig_dir / 'fonts.conf'
        fontconfig_file.write_text(fontconfig_content)

        # Fix ownership: look up the user's UID/GID from the chroot's /etc/passwd
        try:
            # Read passwd from the installed system, not the live ISO
            passwd_file = chroot_dir / 'etc' / 'passwd'
            uid = gid = 1000  # fallback for first non-root user
            if passwd_file.exists():
                for line in passwd_file.read_text().splitlines():
                    fields = line.split(':')
                    if len(fields) >= 4 and fields[0] == username:
                        uid, gid = int(fields[2]), int(fields[3])
                        break

            # chown the entire .config/fontconfig tree
            for path in [user_home / '.config', fontconfig_dir, fontconfig_file]:
                if path.exists():
                    os.chown(path, uid, gid)
        except (ValueError, OSError):
            pass  # best-effort ownership fix

        _info(f'Written fontconfig for user {username}')

    # Post-install: copy WiFi connections from live ISO
    _copy_wifi_connections(chroot_dir)

    # Post-install: CN git proxy (must be set before any AUR operations)
    if country == 'CN':
        _setup_cn_git_proxy(chroot_dir)

    # Post-install: install paru AUR helper
    has_paru = False
    if username:
        has_paru = _install_paru(chroot_dir, username, country)

    # Post-install: set default shell to zsh and install oh-my-zsh
    if username:
        subprocess.run(
            ['arch-chroot', str(chroot_dir), 'chsh', '-s', '/bin/zsh', username],
            check=False,
        )

        omz_remote = _resolve_omz_remote(country)
        if omz_remote:
            omz_cmd = (
                f'REMOTE={shlex.quote(omz_remote)} '
                f'sh -c "$(curl -fsSL {OMZ_INSTALL_URL})" "" --unattended'
            )
        else:
            omz_cmd = f'sh -c "$(curl -fsSL {OMZ_INSTALL_URL})" "" --unattended'

        result = subprocess.run(
            ['arch-chroot', str(chroot_dir),
             'runuser', '-l', username, '-c', omz_cmd],
            check=False,
            timeout=120,
        )
        if result.returncode == 0:
            _info(f'Installed oh-my-zsh for user {username}')
        else:
            _info(f'oh-my-zsh installation failed (exit {result.returncode}), skipping')

    # Post-install: DMS desktop environment
    if desktop_env == 'dms' and username:
        from .dms import install_dms
        _info('Setting up DMS desktop environment...')
        install_dms(
            chroot_dir=chroot_dir,
            username=username,
            compositor=dms_compositor,
            terminal=dms_terminal,
            country=country,
        )

    # Post-install: AUR browsers (requires paru)
    if has_paru and browsers:
        _install_aur_browsers(chroot_dir, username, browsers)

    elapsed_time = time.monotonic() - start_time
    _info(f'Installation completed in {elapsed_time:.0f} seconds.')

    # Post-installation action
    action: PostInstallationAction = tui.run(lambda: select_post_installation(elapsed_time))
    match action:
        case PostInstallationAction.EXIT:
            pass
        case PostInstallationAction.REBOOT:
            os.system('reboot')
        case PostInstallationAction.CHROOT:
            os.system(f'arch-chroot {chroot_dir}')
