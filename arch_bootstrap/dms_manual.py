"""DMS Manual installer - installs DankMaterialShell without dankinstall binary."""

from __future__ import annotations

import subprocess
from pathlib import Path

from archinstall.lib.output import Font, debug, info

from .constants import (
    DMS_MANUAL_AUR_PACKAGES,
    DMS_MANUAL_COMPOSITOR_PACKAGES,
    DMS_MANUAL_PREREQ_PACKAGES,
    DMS_MANUAL_SYSTEM_PACKAGES,
    DMS_MANUAL_TERMINAL_PACKAGES,
)
from .i18n import t
from .nvidia import install_niri_drm_wait
from .utils import run_with_retry


_PREFIX = '[dms-manual]'


def _info(msg: str) -> None:
    """Log an info message with a colored [dms-manual] prefix."""
    info(f'{_PREFIX} {msg}', fg='green', font=[Font.bold])


def _debug(msg: str) -> None:
    """Log a debug message with a colored [dms-manual] prefix."""
    debug(f'{_PREFIX} {msg}', fg='green')


_GREETD_CONFIG_TEMPLATE = """\
[terminal]
vt = 1

[default_session]
command = "dms-greeter --command {compositor} -p /usr/share/quickshell/dms"
user = "greeter"
"""

_SUDOERS_FILE = '99-dms-manual-temp'

# Maps compositor/terminal wizard values to dms setup stdin prompt choices
_DMS_SETUP_COMPOSITOR_MAP: dict[str, str] = {'niri': '1', 'hyprland': '2'}
_DMS_SETUP_TERMINAL_MAP: dict[str, str] = {'ghostty': '1', 'kitty': '2', 'alacritty': '3'}


# ---------------------------------------------------------------------------
# Installation steps
# ---------------------------------------------------------------------------

def _install_prereq_packages(chroot_dir: Path, username: str) -> bool:
    """Install prerequisite packages that must precede the main batch.

    Returns True on success (or if the list is empty), False on failure.
    """
    if not DMS_MANUAL_PREREQ_PACKAGES:
        return True

    _info(t('dms_manual.installing_prereqs'))
    _debug(f'Packages: {", ".join(DMS_MANUAL_PREREQ_PACKAGES)}')

    cmd = (
        'GIT_CONFIG_SYSTEM=/etc/gitconfig '
        'MAKEPKG_GIT_CONFIG=/etc/gitconfig '
        'LANG=C.UTF-8 paru -S --noconfirm --needed --skipreview '
        + ' '.join(DMS_MANUAL_PREREQ_PACKAGES)
    )

    result = run_with_retry(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c', cmd],
        description=t('dms_manual.installing_prereqs'),
    )

    if result.returncode != 0:
        _info(t('dms_manual.failed') % result.returncode)
        return False

    return True


def _install_packages(
    chroot_dir: Path,
    username: str,
    compositor: str,
    terminal: str,
) -> bool:
    """Install all remaining DMS packages via paru.

    Returns True on success, False on failure.
    """
    _info(t('dms_manual.installing_deps'))

    # Build the full package list
    compositor_pkgs = DMS_MANUAL_COMPOSITOR_PACKAGES.get(compositor, [])
    terminal_pkg = DMS_MANUAL_TERMINAL_PACKAGES.get(terminal, '')
    all_packages = (
        DMS_MANUAL_AUR_PACKAGES
        + DMS_MANUAL_SYSTEM_PACKAGES
        + list(compositor_pkgs)
        + ([terminal_pkg] if terminal_pkg else [])
    )
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
        description=t('dms_manual.installing_deps'),
    )

    if result.returncode != 0:
        _info(t('dms_manual.failed') % result.returncode)
        return False

    return True


def _run_dms_setup(
    chroot_dir: Path,
    username: str,
    compositor: str,
    terminal: str,
) -> None:
    """Run ``dms setup`` with automated stdin input."""
    _info(t('dms_manual.running_setup'))

    comp_choice = _DMS_SETUP_COMPOSITOR_MAP.get(compositor, '1')
    term_choice = _DMS_SETUP_TERMINAL_MAP.get(terminal, '1')
    stdin_input = f'{comp_choice}\n{term_choice}\n1\ny\n'  # compositor, terminal, systemd=Yes, confirm=y

    result = subprocess.run(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c', 'dms setup'],
        input=stdin_input,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        _debug(f'dms setup exited with code {result.returncode}')


def _configure_greetd(chroot_dir: Path, compositor: str) -> None:
    """Write greetd configuration for dms-greeter."""
    _info(t('dms_manual.configuring_greetd'))

    config_dir = chroot_dir / 'etc' / 'greetd'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'config.toml'
    config_path.write_text(_GREETD_CONFIG_TEMPLATE.format(compositor=compositor))
    _debug(f'Wrote {config_path}')


def _enable_services(
    chroot_dir: Path,
    username: str,
    compositor: str,
) -> None:
    """Enable greetd, graphical.target, and compositor-specific DMS service.

    systemctl commands do not work inside arch-chroot (no running
    systemd), so we create the symlinks directly.
    """
    _info(t('dms_manual.enabling_services'))

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

    # Enable DMS user service for the chosen compositor
    if compositor == 'niri':
        wants_dir = (
            chroot_dir / 'home' / username / '.config'
            / 'systemd' / 'user' / 'niri.service.wants'
        )
    elif compositor == 'hyprland':
        wants_dir = (
            chroot_dir / 'home' / username / '.config'
            / 'systemd' / 'user' / 'hyprland-session.target.wants'
        )
    else:
        _debug(f'Unknown compositor {compositor!r}, skipping DMS service symlink')
        return

    wants_dir.mkdir(parents=True, exist_ok=True)
    dms_link = wants_dir / 'dms.service'
    dms_unit = Path('/usr/lib/systemd/user/dms.service')
    if not dms_link.exists():
        dms_link.symlink_to(dms_unit)
        _debug(f'Symlinked {dms_link.name} -> {dms_unit}')
    else:
        _debug(f'{dms_link.name} already exists, skipping')


def _configure_environment(chroot_dir: Path) -> None:
    """Write environment variables to /etc/environment."""
    env_file = chroot_dir / 'etc' / 'environment'

    entries = {
        'QT_QPA_PLATFORMTHEME': 'qt6ct',
        'QS_ICON_THEME': 'adwaita',
    }

    existing = env_file.read_text() if env_file.exists() else ''

    for key, value in entries.items():
        if f'{key}=' not in existing:
            existing += f'{key}={value}\n'

    env_file.write_text(existing)


def _fix_ownership(chroot_dir: Path, username: str) -> None:
    """Fix file ownership for DMS config directories."""
    home = f'/home/{username}'
    dirs = [f'{home}/.config']

    subprocess.run(
        ['arch-chroot', str(chroot_dir), 'chown', '-R',
         f'{username}:{username}', *dirs],
        check=False,
    )
    _debug(f'Fixed ownership of ~/.config for {username}')


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def install_dms_manual(
    chroot_dir: Path,
    username: str,
    compositor: str = 'niri',
    terminal: str = 'ghostty',
    country: str | None = None,
    gpu_vendors: list[str] | None = None,
) -> None:
    """Install DMS desktop environment manually (without dankinstall).

    Installs DMS packages via paru in two phases (prerequisite packages
    first if any, then everything else), runs ``dms setup``
    with stdin piping for automation, configures greetd with dms-greeter,
    and enables systemd services via manual symlinks.

    The CN GitHub proxy (if applicable) should already be configured in
    /etc/gitconfig by the caller before this function is invoked, so
    paru's internal git operations (AUR clones) are also proxied.

    Args:
        chroot_dir: Path to the mounted chroot (e.g. /mnt).
        username: Non-root user account.
        compositor: Compositor to install ('niri' or 'hyprland').
        terminal: Terminal emulator to install ('ghostty', 'kitty', or 'alacritty').
        country: User's country code (for CN proxy resolution).
        gpu_vendors: List of GPU vendor identifiers (e.g. ['nvidia_open', 'amd']).
    """
    gpu_vendors = gpu_vendors or []
    sudoers_path = chroot_dir / 'etc' / 'sudoers.d' / _SUDOERS_FILE

    try:
        # 1. Temporary NOPASSWD sudoers
        _info(t('dms_manual.setting_up_sudoers'))
        sudoers_path.parent.mkdir(parents=True, exist_ok=True)
        sudoers_path.write_text(f'{username} ALL=(ALL) NOPASSWD: ALL\n')
        sudoers_path.chmod(0o440)

        # 2. Install prerequisite packages (if any)
        if not _install_prereq_packages(chroot_dir, username):
            return

        # 3. Install all remaining packages
        if not _install_packages(chroot_dir, username, compositor, terminal):
            return

        # 4. Run dms setup for initial configuration
        _run_dms_setup(chroot_dir, username, compositor, terminal)

    finally:
        # Always remove temporary sudoers
        if sudoers_path.exists():
            sudoers_path.unlink()
            _debug('Removed temporary sudoers rule')

    # 5. Configure greetd
    _configure_greetd(chroot_dir, compositor)

    # 6. Enable systemd services
    _enable_services(chroot_dir, username, compositor)

    # 7. NVIDIA DRM wait workaround (Optimus laptops with niri)
    if compositor == 'niri' and gpu_vendors:
        has_nvidia = any(v == 'nvidia_open' for v in gpu_vendors)
        if has_nvidia:
            install_niri_drm_wait(chroot_dir)

    # 8. Configure environment variables
    _configure_environment(chroot_dir)

    # 9. Fix file ownership
    _fix_ownership(chroot_dir, username)

    _info(t('dms_manual.complete'))
