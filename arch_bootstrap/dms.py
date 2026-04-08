"""DMS (DankMaterialShell) desktop environment installation and configuration.

Handles package installation (pacman + AUR), configuration template deployment,
systemd user service setup, and greetd display manager configuration.
All operations target the chroot environment during installation.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

from archinstall.lib.output import Font, info, debug

from .constants import (
    DMS_AUR_PACKAGES,
    DMS_GREETD_CONFIG,
    DMS_PLACEHOLDER_FILES,
    DMS_SYSTEMD_TARGETS,
    DMS_TEMPLATE_BASE_URL,
    DMS_TEMPLATES,
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

    Returns proxy base URL (e.g. 'https://xxx.example.com') or None.
    """
    try:
        req = urllib.request.Request(GHPROXY_CHUNK_URL, method='GET')
        with urllib.request.urlopen(req, timeout=5) as resp:
            final_url = resp.url
            from urllib.parse import urlparse
            parsed = urlparse(final_url)
            proxy = f'{parsed.scheme}://{parsed.netloc}'
            if proxy != 'https://ghproxy.link':
                return proxy
    except Exception:
        pass
    return None


def _resolve_download_base_url(country: str | None) -> str:
    """Determine the base URL for downloading DMS templates.

    For non-CN users: direct GitHub raw URL.
    For CN users: try ghproxy.link -> fallback proxy -> direct (best effort).
    """
    if country != 'CN':
        return DMS_TEMPLATE_BASE_URL

    _info('China detected, resolving GitHub proxy for templates...')

    # Try ghproxy.link
    proxy = _resolve_ghproxy()
    if proxy:
        _info(f'Found proxy: {proxy}')
        return f'{proxy}/{DMS_TEMPLATE_BASE_URL}'

    # Try fallback
    _info(f'Trying fallback proxy: {GHPROXY_FALLBACK}')
    try:
        test_url = f'{GHPROXY_FALLBACK}/{DMS_TEMPLATE_BASE_URL}/niri.kdl'
        req = urllib.request.Request(test_url, method='HEAD')
        urllib.request.urlopen(req, timeout=10)
        return f'{GHPROXY_FALLBACK}/{DMS_TEMPLATE_BASE_URL}'
    except Exception:
        pass

    # Fall through to direct URL (may be slow but might work)
    _info('No proxy available, using direct GitHub URL')
    return DMS_TEMPLATE_BASE_URL


# ---------------------------------------------------------------------------
# AUR package building
# ---------------------------------------------------------------------------


def build_dms_aur_packages(
    chroot_dir: Path,
    username: str,
) -> None:
    """Build and install DMS AUR packages via makepkg in the chroot.

    Uses `runuser -l <username>` to run makepkg as non-root, following the
    same pattern as oh-my-zsh installation in installation.py.

    Args:
        chroot_dir: Path to the mounted chroot.
        username: Non-root user to run makepkg as.
    """
    aur_packages = list(DMS_AUR_PACKAGES['common'])
    aur_packages.extend(DMS_AUR_PACKAGES.get('greeter', []))

    for pkg in aur_packages:
        _info(t('dms.building_aur') % pkg)

        safe_pkg = shlex.quote(pkg)
        build_script = (
            f'set -e; '
            f'cd /tmp; '
            f'rm -rf {safe_pkg}; '
            f'git clone https://aur.archlinux.org/{safe_pkg}.git; '
            f'cd {safe_pkg}; '
            f'makepkg -si --noconfirm --needed'
        )

        result = subprocess.run(
            ['arch-chroot', str(chroot_dir),
             'runuser', '-l', username, '-c', build_script],
        )

        if result.returncode != 0:
            _info(t('dms.aur_failed') % (pkg, result.returncode))
            raise RuntimeError(
                f'AUR package {pkg} failed to build (exit {result.returncode}). '
                f'DMS installation cannot continue without this package.'
            )


# ---------------------------------------------------------------------------
# Configuration template deployment
# ---------------------------------------------------------------------------

def _download_template(url: str) -> str | None:
    """Download a template file and return its content, or None on failure."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode('utf-8')
    except Exception:
        return None


def deploy_dms_configs(
    chroot_dir: Path,
    username: str,
    compositor: str,
    terminal: str,
    country: str | None = None,
) -> None:
    """Download and deploy DMS configuration templates.

    Downloads templates from GitHub (with proxy for CN), replaces
    {{TERMINAL_COMMAND}} placeholder, and writes to the user's home directory.

    Args:
        chroot_dir: Path to the mounted chroot.
        username: Target user.
        compositor: 'niri' or 'hyprland'.
        terminal: 'ghostty', 'kitty', or 'alacritty'.
        country: User's country code (for CN proxy).
    """
    _info(t('dms.downloading_templates'))

    base_url = _resolve_download_base_url(country)
    user_home = chroot_dir / 'home' / username

    # Collect templates to deploy: compositor + terminal
    templates_to_deploy: list[tuple[str, str]] = []
    templates_to_deploy.extend(DMS_TEMPLATES.get(compositor, []))
    templates_to_deploy.extend(DMS_TEMPLATES.get(terminal, []))

    for remote_name, local_rel_path in templates_to_deploy:
        url = f'{base_url}/{remote_name}'
        content = _download_template(url)

        if content is None:
            _info(t('dms.download_failed') % remote_name)
            continue

        # Replace template placeholder
        content = content.replace('{{TERMINAL_COMMAND}}', terminal)

        # Write to target path
        target = user_home / local_rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        _debug(f'Deployed: {local_rel_path}')

    # Create placeholder files for user customization
    _info(t('dms.deploying_config') % compositor)
    for rel_path in DMS_PLACEHOLDER_FILES.get(compositor, []):
        target = user_home / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text('')
            _debug(f'Created placeholder: {rel_path}')


# ---------------------------------------------------------------------------
# systemd user service setup
# ---------------------------------------------------------------------------

def setup_dms_systemd(
    chroot_dir: Path,
    username: str,
    compositor: str,
) -> None:
    """Create systemd user service symlink for DMS auto-start.

    Creates: ~/.config/systemd/user/<compositor>.wants/dms.service
           -> /usr/lib/systemd/user/dms.service

    Args:
        chroot_dir: Path to the mounted chroot.
        username: Target user.
        compositor: 'niri' or 'hyprland'.
    """
    _info(t('dms.setup_systemd'))

    target = DMS_SYSTEMD_TARGETS.get(compositor)
    if not target:
        return

    wants_rel, service_path = target
    user_home = chroot_dir / 'home' / username
    wants_dir = user_home / wants_rel
    wants_dir.mkdir(parents=True, exist_ok=True)

    symlink = wants_dir / 'dms.service'
    if not symlink.exists():
        # Absolute target path is correct: systemd reads this symlink at runtime
        # inside the installed system, where /usr/lib/systemd/user/ is the real path.
        symlink.symlink_to(service_path)
        _debug(f'Symlink: {symlink} -> {service_path}')


# ---------------------------------------------------------------------------
# greetd display manager setup
# ---------------------------------------------------------------------------

def setup_greetd(
    chroot_dir: Path,
    username: str,
    compositor: str,
) -> None:
    """Configure greetd to start the DMS compositor on boot.

    Writes /etc/greetd/config.toml and enables greetd.service.

    Args:
        chroot_dir: Path to the mounted chroot.
        username: Target user.
        compositor: 'niri' or 'hyprland'.
    """
    _info(t('dms.setup_greetd'))

    # Write greetd config
    greetd_dir = chroot_dir / 'etc' / 'greetd'
    greetd_dir.mkdir(parents=True, exist_ok=True)
    config_file = greetd_dir / 'config.toml'
    config_file.write_text(
        DMS_GREETD_CONFIG
        .replace('{compositor}', compositor)
        .replace('{username}', username)
    )
    _debug(f'Written greetd config: {config_file}')

    # Enable greetd.service
    subprocess.run(
        ['arch-chroot', str(chroot_dir),
         'systemctl', 'enable', 'greetd.service'],
        check=True,
    )
    _debug('Enabled greetd.service')


# ---------------------------------------------------------------------------
# Ownership fix
# ---------------------------------------------------------------------------

def _fix_ownership(chroot_dir: Path, username: str) -> None:
    """Fix ownership of all DMS config files under the user's home directory.

    Reads UID/GID from the chroot's /etc/passwd (same pattern as
    installation.py fontconfig ownership fix).
    """
    user_home = chroot_dir / 'home' / username

    # Resolve UID/GID from chroot passwd
    uid = gid = 1000  # fallback
    passwd_file = chroot_dir / 'etc' / 'passwd'
    if passwd_file.exists():
        for line in passwd_file.read_text().splitlines():
            fields = line.split(':')
            if len(fields) >= 4 and fields[0] == username:
                uid, gid = int(fields[2]), int(fields[3])
                break

    # lchown the .config tree recursively (lchown to avoid following symlinks)
    config_dir = user_home / '.config'
    if config_dir.exists():
        for dirpath, _dirnames, filenames in os.walk(config_dir):
            p = Path(dirpath)
            try:
                os.lchown(str(p), uid, gid)
            except OSError:
                pass
            for fname in filenames:
                try:
                    os.lchown(str(p / fname), uid, gid)
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def install_dms(
    chroot_dir: Path,
    username: str,
    compositor: str,
    terminal: str,
    country: str | None = None,
) -> None:
    """Full DMS installation: AUR packages + config + systemd + greetd.

    System packages (pacman) are already installed via config.packages in
    apply_wizard_state_to_config(). This function handles everything else.

    This is the single entry point called from installation.py.

    Args:
        chroot_dir: Path to the mounted chroot (e.g. /mnt).
        username: Non-root user account.
        compositor: 'niri' or 'hyprland'.
        terminal: 'ghostty', 'kitty', or 'alacritty'.
        country: User's country code (for CN proxy resolution).
    """
    # 1. Build and install AUR packages
    build_dms_aur_packages(chroot_dir, username)

    # 2. Deploy configuration templates
    deploy_dms_configs(chroot_dir, username, compositor, terminal, country)

    # 3. Set up systemd user service
    setup_dms_systemd(chroot_dir, username, compositor)

    # 4. Configure greetd
    setup_greetd(chroot_dir, username, compositor)

    # 5. Fix ownership of all deployed config files
    _fix_ownership(chroot_dir, username)

    _info(t('dms.complete'))
