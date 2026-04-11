"""Exo desktop shell installation for Niri.

Exo is a Material Design 3 desktop shell for the Niri compositor, built
with Ignis (Python/GTK4 widget framework).  This module clones the Exo
repository, installs its AUR dependencies via paru, copies configuration
files into the user's home directory, configures greetd for autologin
into the Niri session, and enables the required systemd services.

Source: https://github.com/debuggyo/Exo
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path

from archinstall.lib.output import Font, debug, info

from .constants import (
    EXO_AUR_PACKAGES,
    EXO_REPO_URL,
    EXO_SYSTEM_PACKAGES,
)
from .i18n import t
from .nvidia import install_niri_drm_wait
from .utils import get_clone_url, run_with_retry

_PREFIX = '[Exo]'

# greetd configuration template (autologin, no greeter)
_GREETD_CONFIG = """\
[terminal]
vt = 1

[default_session]
command = "niri-session"
user = "{username}"
"""


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _info(msg: str) -> None:
    """Log an info message with a colored [Exo] prefix."""
    info(f'{_PREFIX} {msg}', fg='green', font=[Font.bold])


def _debug(msg: str) -> None:
    """Log a debug message with a colored [Exo] prefix."""
    debug(f'{_PREFIX} {msg}', fg='green')


# ---------------------------------------------------------------------------
# Installation steps
# ---------------------------------------------------------------------------

def _install_aur_packages(chroot_dir: Path, username: str) -> bool:
    """Install Exo's AUR dependencies via paru.

    Returns True on success, False on failure.
    """
    _info(t('exo.installing_deps'))
    all_packages = EXO_AUR_PACKAGES + EXO_SYSTEM_PACKAGES
    _debug(f'Packages: {", ".join(all_packages)}')

    cmd = (
        'GIT_CONFIG_SYSTEM=/etc/gitconfig '
        'MAKEPKG_GIT_CONFIG=/etc/gitconfig '
        'LANG=C.UTF-8 paru -S --noconfirm --needed --skipreview '
        + ' '.join(all_packages)
    )

    result = run_with_retry(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c', cmd],
        description=t('exo.installing_deps'),
    )

    if result.returncode != 0:
        _info(t('exo.failed') % (result.returncode or -1))
        return False

    return True


def _clone_and_copy_configs(
    chroot_dir: Path,
    username: str,
    country: str | None,
) -> bool:
    """Clone the Exo repo and copy configuration files.

    Returns True on success, False on failure.
    """
    _info(t('exo.cloning_repo'))

    clone_url = get_clone_url(EXO_REPO_URL, is_cn=(country == 'CN'))
    repo_path = '/var/tmp/exo-shell'

    # Clone into chroot /var/tmp
    result = run_with_retry(
        ['arch-chroot', str(chroot_dir),
         'git', 'clone', '--depth', '1', clone_url, repo_path],
        description=t('exo.cloning_repo'),
    )

    if result.returncode != 0:
        _info(f'Failed to clone Exo repo (exit {result.returncode})')
        return False

    # Copy configs as user
    _info(t('exo.copying_configs'))

    quoted_home = shlex.quote(f'/home/{username}')
    copy_cmds = ' && '.join([
        # Create target directories
        f'mkdir -p {quoted_home}/.config/ignis',
        f'mkdir -p {quoted_home}/.config/matugen',
        f'mkdir -p {quoted_home}/.config/niri',
        f'mkdir -p {quoted_home}/Pictures/Wallpapers',
        # Copy config trees
        f'cp -r {repo_path}/ignis/. {quoted_home}/.config/ignis/',
        f'cp -r {repo_path}/matugen/. {quoted_home}/.config/matugen/',
        # Copy individual files
        f'cp {repo_path}/exodefaults/config.kdl {quoted_home}/.config/niri/config.kdl',
        f'cp {repo_path}/exodefaults/default_wallpaper.png {quoted_home}/Pictures/Wallpapers/default.png',
        f'cp {repo_path}/exodefaults/preview-colors.scss {quoted_home}/.config/ignis/styles/preview-colors.scss',
        # Create empty user settings
        f'echo \'{{}}\' > {quoted_home}/.config/ignis/user_settings.json',
    ])

    result = subprocess.run(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c', copy_cmds],
        check=False,
    )

    if result.returncode != 0:
        _info(f'Failed to copy Exo configs (exit {result.returncode})')
        return False

    return True


def _run_matugen(chroot_dir: Path, username: str) -> None:
    """Run matugen for initial Material You color generation."""
    _info(t('exo.running_matugen'))

    quoted_home = shlex.quote(f'/home/{username}')
    result = subprocess.run(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c',
         f'matugen image {quoted_home}/Pictures/Wallpapers/default.png'],
        check=False,
    )

    if result.returncode != 0:
        _info(f'matugen failed (exit {result.returncode}), colors can be generated on first login')


def _set_gtk_theme(chroot_dir: Path, username: str) -> None:
    """Set the GTK theme to adw-gtk3 via gsettings.

    This may fail inside chroot due to missing dbus session, which is
    expected — the theme will be applied on first login.
    """
    result = subprocess.run(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c',
         'gsettings set org.gnome.desktop.interface gtk-theme "adw-gtk3"'],
        check=False,
    )

    if result.returncode != 0:
        _debug('gsettings failed (expected in chroot, theme will apply on login)')
    else:
        _debug('GTK theme set to adw-gtk3')


def _configure_greetd(chroot_dir: Path, username: str) -> None:
    """Write greetd configuration for autologin into Niri."""
    _info(t('exo.configuring_greetd'))

    config_dir = chroot_dir / 'etc' / 'greetd'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'config.toml'
    # Escape TOML special characters in username by wrapping in quotes
    safe_username = username.replace('\\', '\\\\').replace('"', '\\"')
    config_path.write_text(_GREETD_CONFIG.format(username=safe_username))
    _debug(f'Wrote {config_path}')


def _enable_services(chroot_dir: Path) -> None:
    """Enable greetd and set graphical.target via manual symlinks.

    systemctl commands do not work inside arch-chroot (no running
    systemd), so we create the symlinks directly.
    """
    _info(t('exo.enabling_services'))

    # Enable greetd (display-manager.service)
    dm_link = chroot_dir / 'etc' / 'systemd' / 'system' / 'display-manager.service'
    dm_link.parent.mkdir(parents=True, exist_ok=True)
    greetd_unit = Path('/usr/lib/systemd/system/greetd.service')
    if not dm_link.exists():
        dm_link.symlink_to(greetd_unit)
        _debug(f'Symlinked display-manager.service -> {greetd_unit}')
    else:
        _debug('display-manager.service already exists, skipping')

    # Set graphical.target as default
    default_link = chroot_dir / 'etc' / 'systemd' / 'system' / 'default.target'
    default_link.parent.mkdir(parents=True, exist_ok=True)
    graphical_unit = Path('/usr/lib/systemd/system/graphical.target')
    if default_link.is_symlink() or default_link.exists():
        default_link.unlink()
    default_link.symlink_to(graphical_unit)
    _debug(f'Symlinked default.target -> {graphical_unit}')


def _install_exoupdate(chroot_dir: Path) -> None:
    """Install the exoupdate command from the cloned repo.

    Copies exoinstall.py to /usr/local/bin/exoupdate and makes it
    executable.
    """
    src = chroot_dir / 'var' / 'tmp' / 'exo-shell' / 'exoinstall.py'
    dst = chroot_dir / 'usr' / 'local' / 'bin' / 'exoupdate'
    dst.parent.mkdir(parents=True, exist_ok=True)

    if src.exists():
        dst.write_bytes(src.read_bytes())
        dst.chmod(0o755)
        _debug(f'Installed exoupdate to {dst}')
    else:
        _debug(f'exoinstall.py not found at {src}, skipping exoupdate')


def _cleanup_repo(chroot_dir: Path) -> None:
    """Remove the cloned Exo repository from /var/tmp."""
    repo_path = chroot_dir / 'var' / 'tmp' / 'exo-shell'
    if repo_path.exists():
        shutil.rmtree(repo_path)
        _debug('Removed /var/tmp/exo-shell')


def _fix_ownership(chroot_dir: Path, username: str) -> None:
    """Fix file ownership for all Exo config directories."""
    home = f'/home/{username}'
    dirs = [
        f'{home}/.config/ignis',
        f'{home}/.config/matugen',
        f'{home}/.config/niri',
        f'{home}/Pictures',
    ]

    subprocess.run(
        ['arch-chroot', str(chroot_dir), 'chown', '-R',
         f'{username}:{username}', *dirs],
        check=False,
    )
    _debug(f'Fixed ownership of Exo config directories for {username}')


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def install_exo(
    chroot_dir: Path,
    username: str,
    country: str | None = None,
    gpu_vendors: list[str] | None = None,
) -> None:
    """Install the Exo desktop shell for Niri.

    Installs Exo's AUR dependencies via paru, clones the Exo repository,
    copies configuration files, runs matugen for initial color generation,
    configures greetd for autologin into the Niri session, and enables
    systemd services.

    The CN GitHub proxy (if applicable) should already be configured in
    /etc/gitconfig by the caller before this function is invoked, so
    paru's internal git operations (AUR clones) are also proxied.

    Args:
        chroot_dir: Path to the mounted chroot (e.g. /mnt).
        username: Non-root user account.
        country: User's country code (for CN proxy resolution).
        gpu_vendors: List of GPU vendor identifiers (e.g. ['nvidia_open', 'amd']).
    """
    # Set up temporary NOPASSWD sudoers (paru needs sudo for pacman/makepkg)
    sudoers_file = chroot_dir / 'etc' / 'sudoers.d' / f'99-{username}-temp'
    sudoers_file.write_text(
        f'{username} ALL=(ALL) NOPASSWD: ALL\n',
    )
    sudoers_file.chmod(0o440)
    _debug('Temporary NOPASSWD sudoers rule created')

    try:
        # 1. Install AUR dependencies via paru
        if not _install_aur_packages(chroot_dir, username):
            return

        # 2. Clone Exo repo and copy config files
        if not _clone_and_copy_configs(chroot_dir, username, country):
            _cleanup_repo(chroot_dir)
            return

        # 3. Run matugen for initial color generation
        _run_matugen(chroot_dir, username)

        # 4. Set GTK theme
        _set_gtk_theme(chroot_dir, username)

        # 5. Install exoupdate command
        _install_exoupdate(chroot_dir)

        # 6. Cleanup cloned repo
        _cleanup_repo(chroot_dir)
    finally:
        sudoers_file.unlink(missing_ok=True)
        _debug('Removed temporary NOPASSWD sudoers rule')

    # 7. Configure greetd for Niri autologin
    _configure_greetd(chroot_dir, username)

    # 8. Enable systemd services (manual symlinks)
    _enable_services(chroot_dir)

    # 9. NVIDIA DRM wait workaround
    if gpu_vendors:
        has_nvidia = any(v == 'nvidia_open' for v in gpu_vendors)
        if has_nvidia:
            install_niri_drm_wait(chroot_dir)

    # 10. Fix file ownership
    _fix_ownership(chroot_dir, username)

    _info(t('exo.complete'))
