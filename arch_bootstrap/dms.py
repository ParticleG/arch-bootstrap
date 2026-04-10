"""DMS (DankMaterialShell) desktop environment installation via dankinstall.

Downloads the dankinstall binary from GitHub releases and runs it in
headless mode inside the chroot to install DMS with the user's selected
compositor and terminal emulator.

This replaces the previous approach of manually replicating dankinstall's
package lists, config templates, systemd setup, and greetd configuration —
delegating all of that to dankinstall itself ensures accuracy and avoids
drift from upstream.
"""

from __future__ import annotations

import gzip
import platform
import re
import stat
import subprocess
import urllib.request
from pathlib import Path

from archinstall.lib.output import Font, debug, info

from .constants import (
    DANKINSTALL_RELEASE_BASE,
    GHPROXY_CHUNK_URL,
    GHPROXY_FALLBACK,
)
from .i18n import t
from .nvidia import install_niri_drm_wait

_PREFIX = '[DMS]'


def _info(msg: str) -> None:
    """Log an info message with a colored [DMS] prefix."""
    info(f'{_PREFIX} {msg}', fg='green', font=[Font.bold])


def _debug(msg: str) -> None:
    """Log a debug message with a colored [DMS] prefix."""
    debug(f'{_PREFIX} {msg}', fg='green')


# ---------------------------------------------------------------------------
# GitHub proxy resolution (for CN users)
# ---------------------------------------------------------------------------

def _resolve_ghproxy() -> str | None:
    """Resolve a working GitHub proxy URL from ghproxy.link.

    ghproxy.link is a Vue SPA; the available proxy domains are embedded in
    a webpack JS chunk as href="https://gh<word>.<tld>" links.  We fetch
    the chunk and extract the first available domain.

    Returns proxy base URL (e.g. 'https://ghfast.top') or None.
    """
    try:
        req = urllib.request.Request(GHPROXY_CHUNK_URL)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return None

    matches = re.findall(r'href=.{0,5}(https://gh[a-z0-9]+\.[a-z]+)', content)
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# dankinstall binary download
# ---------------------------------------------------------------------------

def _download_dankinstall(chroot_dir: Path, country: str | None) -> Path:
    """Download and extract the dankinstall binary into the chroot.

    Downloads the gzipped binary from GitHub releases (with proxy for CN),
    decompresses it, and places it at /tmp/dankinstall inside the chroot.

    Returns the path to the binary on the host filesystem.
    """
    arch = 'arm64' if platform.machine() == 'aarch64' else 'amd64'
    filename = f'dankinstall-{arch}.gz'
    url = f'{DANKINSTALL_RELEASE_BASE}/{filename}'

    # Apply GitHub proxy for CN users
    if country == 'CN':
        _info('China detected, resolving GitHub proxy...')
        proxy = _resolve_ghproxy()
        if proxy:
            _info(f'Using proxy: {proxy}')
            url = f'{proxy}/{url}'
        else:
            _info(f'Using fallback proxy: {GHPROXY_FALLBACK}')
            url = f'{GHPROXY_FALLBACK}/{url}'

    _info(f'Downloading dankinstall ({arch})...')
    _debug(f'URL: {url}')

    # Download compressed binary
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        compressed = resp.read()

    # Decompress and write to chroot /var/tmp (NOT /tmp — arch-chroot
    # mounts a fresh tmpfs over /tmp, hiding files written from outside)
    binary_data = gzip.decompress(compressed)
    target = chroot_dir / 'var' / 'tmp' / 'dankinstall'
    target.write_bytes(binary_data)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    size_mb = len(binary_data) / 1024 / 1024
    _info(f'Downloaded dankinstall ({size_mb:.1f} MB)')
    return target


# ---------------------------------------------------------------------------
# Post-dankinstall service enablement
# ---------------------------------------------------------------------------

def _enable_dms_services(
    chroot_dir: Path,
    username: str,
    compositor: str,
) -> None:
    """Enable DMS-related systemd services via manual symlinks.

    dankinstall runs inside arch-chroot where there is no running systemd,
    so its ``systemctl enable`` / ``systemctl set-default`` / ``systemctl
    --user add-wants`` calls fail silently.  We recreate the symlinks that
    those commands *would* have created.
    """
    _info('Enabling DMS services (post-dankinstall fixup)...')

    # -- 1. Enable greetd (display-manager.service) -----------------------
    dm_link = chroot_dir / 'etc' / 'systemd' / 'system' / 'display-manager.service'
    dm_link.parent.mkdir(parents=True, exist_ok=True)
    greetd_unit = Path('/usr/lib/systemd/system/greetd.service')
    if not dm_link.exists():
        dm_link.symlink_to(greetd_unit)
        _debug(f'Symlinked display-manager.service -> {greetd_unit}')
    else:
        _debug('display-manager.service already exists, skipping')

    # -- 2. Set graphical.target as default --------------------------------
    default_link = chroot_dir / 'etc' / 'systemd' / 'system' / 'default.target'
    default_link.parent.mkdir(parents=True, exist_ok=True)
    graphical_unit = Path('/usr/lib/systemd/system/graphical.target')
    # Remove existing symlink if present (might point to multi-user.target)
    if default_link.is_symlink() or default_link.exists():
        default_link.unlink()
    default_link.symlink_to(graphical_unit)
    _debug(f'Symlinked default.target -> {graphical_unit}')

    # -- 3. Enable dms user service ----------------------------------------
    if compositor == 'niri':
        wants_dir_name = 'niri.service.wants'
    elif compositor == 'hyprland':
        wants_dir_name = 'hyprland-session.target.wants'
    else:
        _debug(f'Unknown compositor {compositor!r}, skipping user service')
        return

    user_wants_dir = (
        chroot_dir / 'home' / username / '.config' / 'systemd' / 'user'
        / wants_dir_name
    )
    user_wants_dir.mkdir(parents=True, exist_ok=True)
    dms_link = user_wants_dir / 'dms.service'
    dms_unit = Path('/usr/lib/systemd/user/dms.service')
    if not dms_link.exists():
        dms_link.symlink_to(dms_unit)
        _debug(f'Symlinked {wants_dir_name}/dms.service -> {dms_unit}')
    else:
        _debug(f'{wants_dir_name}/dms.service already exists, skipping')

    # Fix ownership: .config/systemd tree should be owned by the user
    subprocess.run(
        ['arch-chroot', str(chroot_dir), 'chown', '-R',
         f'{username}:{username}', f'/home/{username}/.config/systemd'],
        check=False,
    )
    _debug(f'Fixed ownership of /home/{username}/.config/systemd')

    _info('DMS services enabled successfully')


# ---------------------------------------------------------------------------
# NVIDIA DRM wait workaround for niri
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Post-install extras (packages & environment)
# ---------------------------------------------------------------------------

_DMS_EXTRA_PACKAGES = [
    'cups-pk-helper',   # printer management
    'kimageformats',    # KDE image format plugins
    'libavif',          # AVIF support for kimageformats
    'libheif',          # HEIF support for kimageformats
    'libjxl',           # JPEG XL support for kimageformats
    'cava',             # audio visualizer
    'qt6ct',            # Qt6 platform theme configuration
]


def _install_dms_extras(chroot_dir: Path) -> None:
    """Install extra packages that dankinstall does not include.

    These satisfy the warnings reported by ``dms doctor`` after a
    headless dankinstall run (cups-pk-helper, kimageformats optional
    deps, cava, qt6ct).
    """
    _info('Installing DMS extra packages...')
    _debug(f'Packages: {", ".join(_DMS_EXTRA_PACKAGES)}')

    result = subprocess.run(
        ['arch-chroot', str(chroot_dir),
         'pacman', '-S', '--noconfirm', '--needed', *_DMS_EXTRA_PACKAGES],
        check=False,
    )

    if result.returncode == 0:
        _info('DMS extra packages installed')
    else:
        _info(f'DMS extra packages installation failed (exit {result.returncode}), some dms-doctor warnings may persist')


def _configure_dms_environment(chroot_dir: Path) -> None:
    """Write environment variables required by DMS into /etc/environment.

    Sets ``QT_QPA_PLATFORMTHEME=qt6ct`` and ``QS_ICON_THEME=adwaita``
    so that ``dms doctor`` no longer reports them as missing.
    """
    _info('Configuring DMS environment variables...')

    env_file = chroot_dir / 'etc' / 'environment'

    existing = env_file.read_text() if env_file.exists() else ''

    lines_to_add: list[str] = []

    if 'QT_QPA_PLATFORMTHEME=' not in existing:
        lines_to_add.append('QT_QPA_PLATFORMTHEME=qt6ct')
    if 'QS_ICON_THEME=' not in existing:
        lines_to_add.append('QS_ICON_THEME=adwaita')

    if lines_to_add:
        # Ensure existing content ends with a newline before appending
        if existing and not existing.endswith('\n'):
            existing += '\n'
        env_file.write_text(existing + '\n'.join(lines_to_add) + '\n')
        for line in lines_to_add:
            _debug(f'Added to /etc/environment: {line}')
    else:
        _debug('Environment variables already set, skipping')

    _info('DMS environment variables configured')


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def install_dms(
    chroot_dir: Path,
    username: str,
    compositor: str,
    terminal: str,
    country: str | None = None,
    gpu_vendors: list[str] | None = None,
) -> None:
    """Install DMS via dankinstall in headless mode.

    Downloads dankinstall from ParticleG/DankMaterialShell releases,
    sets up temporary passwordless sudo for the user, and runs
    dankinstall with the selected compositor and terminal.

    The CN GitHub proxy (if applicable) should already be configured in
    /etc/gitconfig by the caller before this function is invoked, so
    dankinstall's internal git operations (AUR clones) are also proxied.

    Args:
        chroot_dir: Path to the mounted chroot (e.g. /mnt).
        username: Non-root user account.
        compositor: 'niri' or 'hyprland'.
        terminal: 'ghostty', 'kitty', or 'alacritty'.
        country: User's country code (for CN proxy resolution).
        gpu_vendors: List of GPU vendor identifiers (e.g. ['nvidia_open', 'amd']).
    """
    # 1. Download dankinstall binary
    binary_path = _download_dankinstall(chroot_dir, country)

    # 2. Set up temporary NOPASSWD sudo (dankinstall needs sudo for pacman/makepkg)
    sudoers_tmp = chroot_dir / 'etc' / 'sudoers.d' / 'dankinstall-tmp'
    sudoers_tmp.write_text(f'{username} ALL=(ALL) NOPASSWD: ALL\n')
    sudoers_tmp.chmod(0o440)
    _debug('Temporary NOPASSWD sudoers rule created')

    try:
        # 3. Run dankinstall in headless mode
        _info(t('dms.running_dankinstall'))
        cmd = (
            f'LANG=C.UTF-8 /var/tmp/dankinstall '
            f'-c {compositor} -t {terminal} '
            f'--include-deps dms-greeter '
            f'--replace-configs-all -y'
        )

        result = subprocess.run(
            ['arch-chroot', str(chroot_dir),
             'runuser', '-l', username, '-c', cmd],
            check=False,
        )

        if result.returncode == 0:
            _info(t('dms.complete'))
        else:
            _info(t('dms.failed') % result.returncode)
    finally:
        # 4. Clean up: remove temporary sudoers rule and binary
        if sudoers_tmp.exists():
            sudoers_tmp.unlink()
            _debug('Removed temporary sudoers rule')
        if binary_path.exists():
            binary_path.unlink()
            _debug('Removed dankinstall binary')

    # 5. Enable DMS services (systemctl commands fail silently inside chroot)
    _enable_dms_services(chroot_dir, username, compositor)

    # 6. NVIDIA DRM wait workaround (Optimus laptops with niri)
    if compositor == 'niri' and gpu_vendors:
        has_nvidia = any(v in ('nvidia_open', 'nouveau') for v in gpu_vendors)
        if has_nvidia:
            install_niri_drm_wait(chroot_dir)

    # 7. Install DMS extras (cups-pk-helper, kimageformats, cava, qt6ct)
    _install_dms_extras(chroot_dir)

    # 8. Configure environment variables for DMS
    _configure_dms_environment(chroot_dir)
