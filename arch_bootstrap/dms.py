"""DMS (DankMaterialShell) desktop environment installation via dankinstall.

Downloads the dankinstall binary from GitHub releases and runs it in
headless mode inside the chroot to install DMS with the user's selected
compositor and terminal emulator.

Dankinstall owns the base package and configuration generation.  This module
then applies deterministic chroot fixups for greeter synchronization, required
runtime packages, and service enablement that cannot rely on a running systemd.
"""

from __future__ import annotations

import gzip
import http.client
import platform
import shlex
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from .archinstall_compat import Font, debug, error, info

from .constants import (
    DANKINSTALL_RELEASE_BASE,
    DESKTOP_PORTAL_PACKAGES,
    DMS_RUNTIME_PACKAGES,
)
from .i18n import t
from .utils import resolve_github_proxy, retry_on_failure, run_with_retry

_PREFIX = '[DMS]'


def _info(msg: str) -> None:
    """Log an info message with a colored [DMS] prefix."""
    info(f'{_PREFIX} {msg}', fg='green', font=[Font.bold])


def _debug(msg: str) -> None:
    """Log a debug message with a colored [DMS] prefix."""
    debug(f'{_PREFIX} {msg}', fg='green')


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
    is_cn = country == 'CN'
    if is_cn:
        _info('China detected, resolving GitHub proxy...')
        proxy = resolve_github_proxy(is_cn)
        if proxy:
            _info(f'Using proxy: {proxy}')
            url = f'{proxy}/{url}'

    _info(f'Downloading dankinstall ({arch})...')
    _debug(f'URL: {url}')

    # Download compressed binary (with retry)
    def _do_download() -> bytes:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            error(f'{_PREFIX} Failed to download dankinstall: {e}')
            raise RuntimeError(f'Failed to download dankinstall: {e}') from e

    compressed = retry_on_failure(_do_download, description='dankinstall download')

    # Decompress and write to chroot /var/tmp (NOT /tmp — arch-chroot
    # mounts a fresh tmpfs over /tmp, hiding files written from outside)
    binary_data = gzip.decompress(compressed)
    target = chroot_dir / 'var' / 'tmp' / 'dankinstall'
    target.write_bytes(binary_data)
    target.chmod(0o755)

    size_mb = len(binary_data) / 1024 / 1024
    _info(f'Downloaded dankinstall ({size_mb:.1f} MB)')
    return target


# ---------------------------------------------------------------------------
# DMS greeter configuration
# ---------------------------------------------------------------------------

_GREETD_CONFIG_TEMPLATE = """\
[terminal]
vt = 1

[default_session]
command = "/usr/bin/dms-greeter --command {compositor}"
user = "greeter"
"""


def _write_greetd_bootstrap_config(chroot_dir: Path, compositor: str) -> Path:
    """Write a valid embedded-UI greeter config before running the sync CLI."""
    if compositor not in {'niri', 'hyprland'}:
        raise ValueError(f'Unsupported DMS compositor: {compositor}')

    config_path = chroot_dir / 'etc' / 'greetd' / 'config.toml'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_GREETD_CONFIG_TEMPLATE.format(compositor=compositor))
    return config_path


def configure_dms_greeter(
    chroot_dir: Path,
    username: str,
    compositor: str,
) -> bool:
    """Prepare the greeter account and synchronize DMS state inside a chroot.

    A minimal embedded-UI command is written first, so greetd remains usable
    even when the optional theme synchronization fails.  The target user is
    added to the greeter group before ``runuser`` starts; that new process then
    inherits the group and can read greeter memory during auto-login sync.
    """
    _info(t('dms.greeter_configuring'))
    config_path = _write_greetd_bootstrap_config(chroot_dir, compositor)
    _debug(t('dms.greeter_bootstrap_written', config_path))

    account_commands = [
        (
            ['arch-chroot', str(chroot_dir), 'usermod', '-d', '/var/lib/greeter', 'greeter'],
            'dms.greeter_home_failed',
        ),
        (
            [
                'arch-chroot', str(chroot_dir),
                'install', '-d', '-m', '0755',
                '-o', 'greeter', '-g', 'greeter',
                '/var/lib/greeter',
            ],
            'dms.greeter_home_create_failed',
        ),
        (
            [
                'arch-chroot', str(chroot_dir),
                'install', '-d', '-m', '2770',
                '-o', 'greeter', '-g', 'greeter',
                '/var/cache/dms-greeter',
            ],
            'dms.greeter_cache_failed',
        ),
        (
            ['arch-chroot', str(chroot_dir), 'usermod', '-aG', 'greeter', username],
            'dms.greeter_group_failed',
        ),
    ]

    for command, failure_key in account_commands:
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            _info(t(failure_key, result.returncode))
            return False

    sync_result = subprocess.run(
        [
            'arch-chroot', str(chroot_dir),
            'runuser', '-l', username, '-c',
            'env LANG=C.UTF-8 DMS_PRIVESC=sudo dms-greeter sync -y',
        ],
        check=False,
    )
    if sync_result.returncode != 0:
        _info(t('dms.greeter_sync_failed', sync_result.returncode))
        return False

    _info(t('dms.greeter_complete'))
    return True


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
    'wtype',            # clipboard paste text support
    'i2c-tools',       # I2C/DDC monitor brightness control
    *DMS_RUNTIME_PACKAGES,
    *DESKTOP_PORTAL_PACKAGES,
]


def _install_dms_extras(chroot_dir: Path) -> bool:
    """Install packages omitted by dankinstall but required by this profile."""
    _info(t('dms.extras_installing'))
    _debug(f'Packages: {", ".join(_DMS_EXTRA_PACKAGES)}')

    result = run_with_retry(
        ['arch-chroot', str(chroot_dir),
         'env', 'LANG=C.UTF-8', 'pacman', '-S', '--noconfirm', '--needed', *_DMS_EXTRA_PACKAGES],
        description=t('dms.extras_installing'),
        check=False,
    )

    if result.returncode != 0:
        _info(t('dms.extras_failed', result.returncode))
        return False

    _info(t('dms.extras_complete'))
    return True


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


def _configure_i2c(chroot_dir: Path, username: str) -> None:
    """Add user to the i2c group and load i2c-dev module at boot for DDC monitor brightness control."""
    _info(t('dms.configuring_i2c'))
    modules_load_dir = chroot_dir / 'etc' / 'modules-load.d'
    modules_load_dir.mkdir(parents=True, exist_ok=True)
    (modules_load_dir / 'i2c-dev.conf').write_text('i2c-dev\n')
    run_with_retry(
        ['arch-chroot', str(chroot_dir), 'usermod', '-a', '-G', 'i2c', username],
        description='add user to i2c group',
    )
    _info(t('dms.i2c_configured'))


def _enable_dsearch(
    chroot_dir: Path,
    username: str,
    compositor: str,
) -> None:
    """Enable the DankSearch user service and generate the initial index.

    Creates a symlink so dsearch starts with the compositor session,
    writes a default config if none exists, and runs ``dsearch index
    generate`` to build the initial search index.
    """
    _info(t('dms.dsearch_enabling'))

    # Enable dsearch.service under the compositor's wants directory
    if compositor == 'niri':
        wants_dir_name = 'niri.service.wants'
    elif compositor == 'hyprland':
        wants_dir_name = 'hyprland-session.target.wants'
    else:
        _debug(f'Unknown compositor {compositor!r}, skipping dsearch service')
        return

    user_wants_dir = (
        chroot_dir / 'home' / username / '.config' / 'systemd' / 'user'
        / wants_dir_name
    )
    user_wants_dir.mkdir(parents=True, exist_ok=True)
    dsearch_link = user_wants_dir / 'dsearch.service'
    dsearch_unit = Path('/usr/lib/systemd/user/dsearch.service')
    if not dsearch_link.exists():
        dsearch_link.symlink_to(dsearch_unit)
        _debug(f'Symlinked {wants_dir_name}/dsearch.service -> {dsearch_unit}')
    else:
        _debug(f'{wants_dir_name}/dsearch.service already exists, skipping')

    # Fix ownership
    subprocess.run(
        ['arch-chroot', str(chroot_dir), 'chown', '-R',
         f'{username}:{username}', f'/home/{username}/.config/systemd'],
        check=False,
    )

    # Generate initial index
    _info(t('dms.dsearch_indexing'))
    result = subprocess.run(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c', 'dsearch index generate'],
        check=False,
    )
    if result.returncode == 0:
        _info(t('dms.dsearch_complete'))
    else:
        _debug(f'dsearch index generate failed (exit {result.returncode}), index will be built on first login')


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
) -> bool:
    """Install DMS via dankinstall in headless mode.

    Downloads the dankinstall binary from ParticleG/DankMaterialShell releases,
    sets up temporary passwordless sudo for the user, and runs dankinstall with
    the selected compositor and terminal emulator.

    The CN GitHub proxy (if applicable) should already be configured in
    /etc/gitconfig by the caller before this function is invoked, so paru's
    internal git operations are also proxied.

    Returns ``True`` only after the shell, greeter, runtime dependencies, and
    service links are all configured successfully.
    """
    binary_path = _download_dankinstall(chroot_dir, country)

    sudoers_tmp = chroot_dir / 'etc' / 'sudoers.d' / 'dankinstall-tmp'
    sudoers_tmp.write_text(f'{username} ALL=(ALL) NOPASSWD: ALL\n')
    sudoers_tmp.chmod(0o440)
    _debug('Temporary NOPASSWD sudoers rule created')

    try:
        _info(t('dms.running_dankinstall'))
        cmd = (
            f'DANKINSTALL_LOG_DIR=/var/tmp '
            f'GIT_CONFIG_SYSTEM=/etc/gitconfig '
            f'MAKEPKG_GIT_CONFIG=/etc/gitconfig '
            f'LANG=C.UTF-8 /var/tmp/dankinstall '
            f'-c {shlex.quote(compositor)} -t {shlex.quote(terminal)} '
            f'--include-deps dms-greeter '
            f'--replace-configs-all -y'
        )

        result = subprocess.run(
            ['arch-chroot', str(chroot_dir),
             'runuser', '-l', username, '-c', cmd],
            check=False,
        )
        if result.returncode != 0:
            _info(t('dms.failed', result.returncode or -1))
            _debug('Check /var/tmp/dankinstall-*.log for details')
            return False

        if not configure_dms_greeter(chroot_dir, username, compositor):
            _debug(t('dms.greeter_fallback'))
            return False
    finally:
        if sudoers_tmp.exists():
            sudoers_tmp.unlink()
            _debug('Removed temporary sudoers rule')
        if binary_path.exists():
            binary_path.unlink()
            _debug('Removed dankinstall binary')

    if not _install_dms_extras(chroot_dir):
        return False

    _configure_dms_environment(chroot_dir)
    _configure_i2c(chroot_dir, username)
    _enable_dsearch(chroot_dir, username, compositor)

    # Enable display and user services only after every required step succeeds.
    _enable_dms_services(chroot_dir, username, compositor)

    _info(t('dms.complete'))
    return True
