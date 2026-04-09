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

    # Decompress and write to chroot /tmp
    binary_data = gzip.decompress(compressed)
    target = chroot_dir / 'tmp' / 'dankinstall'
    target.write_bytes(binary_data)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    size_mb = len(binary_data) / 1024 / 1024
    _info(f'Downloaded dankinstall ({size_mb:.1f} MB)')
    return target


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def install_dms(
    chroot_dir: Path,
    username: str,
    compositor: str,
    terminal: str,
    country: str | None = None,
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
            f'LANG=C.UTF-8 /tmp/dankinstall '
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
