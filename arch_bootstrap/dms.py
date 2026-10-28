"""Dux Shell (DMS) desktop installation and chroot integration.

The native path installs Dux 2 packages from the official repositories and
AUR, deploys compositor and terminal configuration with
``dms setup headless``, and then performs deterministic chroot integration:
keybinds, environment, XDG autostart ordering, greeter sync, Dux Search
service links, and service activation that cannot rely on a running systemd.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from .archinstall_compat import Font, debug, info

from .constants import (
    DUX_AUR_PACKAGES,
    DUX_COMPOSITOR_PACKAGES,
    DUX_SYSTEM_PACKAGES,
    DUX_TERMINAL_PACKAGES,
    FILE_MANAGER_OPTIONS,
)
from .i18n import t
from .utils import build_paru_aur_install_command, run_with_retry

_PREFIX = '[DMS]'


def _info(msg: str) -> None:
    """Log an info message with a colored [DMS] prefix."""
    info(f'{_PREFIX} {msg}', fg='green', font=[Font.bold])


def _debug(msg: str) -> None:
    """Log a debug message with a colored [DMS] prefix."""
    debug(f'{_PREFIX} {msg}', fg='green')


# ---------------------------------------------------------------------------
# Dux greeter configuration
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
    """Prepare the greeter account and synchronize Dux state inside a chroot.

    The greeter package owns the account and tmpfiles rules.  A minimal
    embedded-UI command is written first so greetd remains usable even when
    theme synchronization fails.  The target user joins the greeter group
    before ``runuser`` starts, so that new process inherits the group and can
    read greeter memory during auto-login sync.
    """
    _info(t('dms.greeter_configuring'))
    config_path = _write_greetd_bootstrap_config(chroot_dir, compositor)
    _debug(t('dms.greeter_bootstrap_written', config_path))

    account = subprocess.run(
        ['arch-chroot', str(chroot_dir), 'id', '-u', 'greeter'],
        check=False,
    )
    if account.returncode != 0:
        _info(t('dms.greeter_user_missing'))
        return False

    tmpfiles = subprocess.run(
        [
            'arch-chroot', str(chroot_dir),
            'systemd-tmpfiles', '--create',
            '/usr/lib/tmpfiles.d/dms-greeter.conf',
        ],
        check=False,
    )
    if tmpfiles.returncode != 0:
        _info(t('dms.greeter_tmpfiles_failed', tmpfiles.returncode))
        return False

    group_result = subprocess.run(
        ['arch-chroot', str(chroot_dir), 'usermod', '-aG', 'greeter', username],
        check=False,
    )
    if group_result.returncode != 0:
        _info(t('dms.greeter_group_failed', group_result.returncode))
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
# Service enablement
# ---------------------------------------------------------------------------

def _user_wants_dir_name(compositor: str) -> str:
    """Return the compositor session unit that should want dms.service."""
    if compositor == 'niri':
        return 'niri.service.wants'
    if compositor == 'hyprland':
        return 'hyprland-session.target.wants'
    raise ValueError(f'Unsupported DMS compositor: {compositor}')


def _enable_dms_services(
    chroot_dir: Path,
    username: str,
    compositor: str,
) -> bool:
    """Enable packaged services after configuration succeeds.

    User-manager operations are unavailable in the installation chroot.
    Enable only the target user's compositor session, not other desktops.
    """
    _info(t('dms.enabling_services'))

    user_dir = chroot_dir / 'home' / username / '.config/systemd/user'
    session_unit = _user_wants_dir_name(compositor).removesuffix('.wants')
    required = (
        'usr/lib/systemd/system/greetd.service',
        'usr/lib/systemd/system/graphical.target',
        'usr/lib/systemd/user/dms.service',
        'usr/lib/systemd/user/dsearch.service',
    )
    if not all((chroot_dir / path).is_file() for path in required):
        _info(t('dms.packages_missing'))
        return False
    if not (
        (user_dir / session_unit).is_file()
        or (chroot_dir / 'usr/lib/systemd/user' / session_unit).is_file()
    ):
        _info(t('dms.packages_missing'))
        return False

    wants_dir = user_dir / f'{session_unit}.wants'
    wants_dir.mkdir(parents=True, exist_ok=True)
    ownership = subprocess.run(
        ['arch-chroot', str(chroot_dir), 'chown', '-R',
         f'{username}:{username}', f'/home/{username}/.config/systemd'],
        check=False,
    )
    if ownership.returncode != 0:
        _info(t('dms.ownership_failed', ownership.returncode))
        return False

    system_dir = chroot_dir / 'etc/systemd/system'
    system_dir.mkdir(parents=True, exist_ok=True)
    for link, target in (
        (system_dir / 'display-manager.service', '/usr/lib/systemd/system/greetd.service'),
        (system_dir / 'default.target', '/usr/lib/systemd/system/graphical.target'),
        (wants_dir / 'dms.service', '/usr/lib/systemd/user/dms.service'),
        (wants_dir / 'dsearch.service', '/usr/lib/systemd/user/dsearch.service'),
    ):
        if link.is_symlink():
            link.unlink()
        link.symlink_to(target)
    _info(t('dms.complete'))
    return True


# ---------------------------------------------------------------------------
# Package installation
# ---------------------------------------------------------------------------

def install_chroot_packages(
    chroot_dir: Path,
    username: str,
    repo_packages: list[str],
    aur_packages: list[str],
    description: str,
    *,
    failure_key: str = 'dms.native_packages_failed',
) -> bool:
    """Install exact repository and AUR package sets inside the chroot."""
    repo_packages = list(dict.fromkeys(repo_packages))
    aur_packages = list(dict.fromkeys(aur_packages))

    if repo_packages:
        _debug(f'Repository packages: {", ".join(repo_packages)}')
        result = run_with_retry(
            ['arch-chroot', str(chroot_dir),
             'env', 'LANG=C.UTF-8',
             'pacman', '-S', '--noconfirm', '--needed', *repo_packages],
            description=description,
            check=False,
        )
        if result.returncode != 0:
            _info(t(failure_key, result.returncode))
            return False

    if aur_packages:
        _debug(f'AUR packages: {", ".join(aur_packages)}')
        command = (
            'GIT_CONFIG_SYSTEM=/etc/gitconfig '
            'MAKEPKG_GIT_CONFIG=/etc/gitconfig '
            + build_paru_aur_install_command(aur_packages)
        )
        result = run_with_retry(
            ['arch-chroot', str(chroot_dir),
             'runuser', '-l', username, '-c', command],
            description=description,
            check=False,
        )
        if result.returncode != 0:
            _info(t(failure_key, result.returncode))
            return False

    return True


def verify_dms_installation(chroot_dir: Path) -> bool:
    """Verify binaries and user units needed before any service is enabled."""
    required = [
        'usr/bin/dms',
        'usr/bin/dms-greeter',
        'usr/bin/dsearch',
        'usr/lib/systemd/user/dms.service',
        'usr/lib/systemd/user/dsearch.service',
    ]
    missing = [path for path in required if not (chroot_dir / path).exists()]
    if missing:
        _info(t('dms.packages_missing'))
        _debug(f'Missing: {", ".join(missing)}')
        return False
    return True


def _configure_session_startup(chroot_dir: Path, username: str, compositor: str) -> None:
    """Replace setup's no-user-manager fallback with session service startup.

    Dux 2.0 falls back to launching ``dms run`` directly when systemctl cannot
    contact a user manager. The installer enables the session wants links only
    after greeter synchronization, so that fallback must not launch a second
    shell. Hyprland's marked block is restored to Dux 2.0's systemd form.
    """
    config_dir = chroot_dir / 'home' / username / '.config'
    if compositor == 'niri':
        path = config_dir / 'niri/config.kdl'
        content = path.read_text()
        content = '\n'.join(
            line for line in content.splitlines()
            if line.strip() != 'spawn-at-startup "dms" "run"'
        ) + '\n'
    else:
        path = config_dir / 'hypr/hyprland.lua'
        content = path.read_text()
        begin = '-- DMS_STARTUP_BEGIN'
        end = '-- DMS_STARTUP_END'
        start = content.index(begin)
        stop = content.index(end, start) + len(end)
        startup = (
            begin + '\n'
            'hl.on("hyprland.start", function()\n'
            '\thl.exec_cmd("dbus-update-activation-environment --systemd --all")\n'
            '\thl.exec_cmd("systemctl --user start hyprland-session.target")\n'
            'end)\n' + end
        )
        content = content[:start] + startup + content[stop:]
    path.write_text(content)


def run_dms_setup(
    chroot_dir: Path,
    username: str,
    compositor: str,
    terminal: str,
) -> bool:
    """Use upstream setup, deferring service enablement until greeter sync."""
    _info(t('dms.setup_running'))
    command = (
        'env LANG=C.UTF-8 dms setup headless '
        f'--compositor {shlex.quote(compositor)} '
        f'--terminal {shlex.quote(terminal)} --force'
    )
    try:
        result = subprocess.run(
            ['arch-chroot', str(chroot_dir),
             'runuser', '-l', username, '-c', command],
            check=False,
        )
    finally:
        # Some systemctl versions write a link before daemon-reload fails.
        # Do not leave DMS enabled if any later configuration step fails.
        link = (
            chroot_dir / 'home' / username / '.config/systemd/user'
            / _user_wants_dir_name(compositor) / 'dms.service'
        )
        if link.is_symlink():
            link.unlink()

    if result.returncode != 0:
        _info(t('dms.setup_failed', result.returncode))
        return False
    _configure_session_startup(chroot_dir, username, compositor)
    return True


def _file_manager_shortcut(
    terminal: str,
    file_managers: list[str],
) -> tuple[str, list[str]] | None:
    """Prefer a selected GUI manager; use the terminal only for TUI-only choices."""
    for manager in file_managers:
        option = FILE_MANAGER_OPTIONS.get(manager)
        if option and not option.get('tui'):
            return option['label'], ['sh', '-c', 'exec xdg-open "$HOME"']
    if 'yazi' in file_managers:
        command = [terminal]
        if terminal != 'kitty':
            command.append('-e')
        command.append('yazi')
        return FILE_MANAGER_OPTIONS['yazi']['label'], [
            'sh', '-c', f'exec {shlex.join(command)} "$HOME"',
        ]
    return None


def _keybind_action(compositor: str, command: list[str]) -> str:
    """Build the provider-native action string for an application command."""
    if compositor == 'niri':
        return 'spawn ' + ' '.join(json.dumps(argument) for argument in command)
    return 'exec ' + shlex.join(command)


def configure_dms_shortcuts(
    chroot_dir: Path,
    username: str,
    compositor: str,
    terminal: str,
    file_managers: list[str],
) -> bool:
    """Add browser and selected file-manager shortcuts through ``dms keybinds``.

    DMS owns the generated keybind files.  ``dms keybinds set`` writes through
    the supported provider override path, preserving stock binds instead of
    editing generated files directly.
    """
    key_prefix = 'Mod' if compositor == 'niri' else 'SUPER'
    bindings = [
        ('B', 'Browser', ['xdg-open', 'https://']),
    ]
    file_manager = _file_manager_shortcut(terminal, file_managers)
    if file_manager is not None:
        bindings.append(('E', file_manager[0], file_manager[1]))

    for key, description, command in bindings:
        result = subprocess.run(
            [
                'arch-chroot', str(chroot_dir),
                'runuser', '-l', username, '-c',
                'env LANG=C.UTF-8 dms keybinds set '
                f'{shlex.quote(compositor)} {shlex.quote(f"{key_prefix}+{key}")} '
                f'{shlex.quote(_keybind_action(compositor, command))} '
                f'--desc {shlex.quote(description)}',
            ],
            check=False,
        )
        if result.returncode != 0:
            _info(t('dms.file_manager_binds_failed', result.returncode))
            return False
    return True


def normalize_dms_ownership(chroot_dir: Path, username: str) -> bool:
    """Normalize user configuration ownership before greeter group sync."""
    result = subprocess.run(
        ['arch-chroot', str(chroot_dir), 'chown', '-R',
         f'{username}:{username}', f'/home/{username}/.config'],
        check=False,
    )
    if result.returncode != 0:
        _info(t('dms.ownership_failed', result.returncode))
        return False
    _debug(f'Fixed ownership of /home/{username}/.config')
    return True


def configure_dms_environment(chroot_dir: Path) -> None:
    """Write environment variables required by Dux Shell into /etc/environment.

    Sets ``QT_QPA_PLATFORMTHEME=qt6ct`` and ``QS_ICON_THEME=Adwaita``.
    The icon theme directory name is case-sensitive.
    """
    _info('Configuring Dux environment variables...')

    env_file = chroot_dir / 'etc' / 'environment'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    lines = env_file.read_text().splitlines() if env_file.exists() else []
    entries = {
        'QT_QPA_PLATFORMTHEME': 'qt6ct',
        'QS_ICON_THEME': 'Adwaita',
    }
    replaced: set[str] = set()
    updated: list[str] = []
    for line in lines:
        key = line.split('=', 1)[0] if '=' in line else ''
        if key in entries:
            if key not in replaced:
                updated.append(f'{key}={entries[key]}')
                replaced.add(key)
            continue
        updated.append(line)

    for key, value in entries.items():
        if key not in replaced:
            updated.append(f'{key}={value}')

    env_file.write_text('\n'.join(updated) + '\n')
    _debug('Ensured Dux environment entries in /etc/environment')
    _info('Dux environment variables configured')


def configure_dms_autostart(chroot_dir: Path, username: str) -> bool:
    """Make XDG autostart applications start after dms.service."""
    dropin = (
        chroot_dir / 'home' / username / '.config' / 'systemd' / 'user'
        / 'app-@autostart.service.d' / 'override.conf'
    )
    dropin.parent.mkdir(parents=True, exist_ok=True)
    dropin.write_text('[Unit]\nAfter=dms.service\n')
    ownership = subprocess.run(
        ['arch-chroot', str(chroot_dir), 'chown', '-R',
         f'{username}:{username}', f'/home/{username}/.config/systemd'],
        check=False,
    )
    if ownership.returncode != 0:
        _info(t('dms.ownership_failed', ownership.returncode))
        return False
    _info(t('dms.autostart_configured'))
    return True


def _configure_i2c(chroot_dir: Path, username: str) -> None:
    """Add user to the i2c group and load i2c-dev at boot for DDC brightness."""
    _info(t('dms.configuring_i2c'))
    modules_load_dir = chroot_dir / 'etc' / 'modules-load.d'
    modules_load_dir.mkdir(parents=True, exist_ok=True)
    (modules_load_dir / 'i2c-dev.conf').write_text('i2c-dev\n')
    run_with_retry(
        ['arch-chroot', str(chroot_dir), 'usermod', '-a', '-G', 'i2c', username],
        description='add user to i2c group',
    )
    _info(t('dms.i2c_configured'))


def _prepare_dsearch(
    chroot_dir: Path,
    username: str,
) -> bool:
    """Check Dux Search and build its initial index before service activation."""
    _info(t('dms.dsearch_enabling'))
    if not (
        (chroot_dir / 'usr' / 'bin' / 'dsearch').exists()
        and (chroot_dir / 'usr' / 'lib' / 'systemd' / 'user' / 'dsearch.service').exists()
    ):
        _info(t('dms.search_missing'))
        return False

    _info(t('dms.dsearch_indexing'))
    result = subprocess.run(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c', 'dsearch index generate'],
        check=False,
    )
    if result.returncode == 0:
        _info(t('dms.dsearch_complete'))
    else:
        _debug(
            f'dsearch index generate failed (exit {result.returncode}), '
            'index will be built on first login',
        )
    return True


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def validate_dms_selection(compositor: str, terminal: str) -> None:
    """Reject compositor or terminal values the upstream tools do not support."""
    if compositor not in DUX_COMPOSITOR_PACKAGES:
        raise ValueError(f'Unsupported Dux compositor: {compositor}')
    if terminal not in DUX_TERMINAL_PACKAGES:
        raise ValueError(f'Unsupported Dux terminal: {terminal}')


def install_dms(
    chroot_dir: Path,
    username: str,
    compositor: str,
    terminal: str,
    file_managers: list[str] | None = None,
) -> bool:
    """Install Dux Shell from the official repositories and AUR.

    Installs the native Dux 2 packages, deploys compositor and terminal
    configuration with ``dms setup headless``, then configures shortcuts,
    greeter, Dux Search, autostart ordering, and service links.  Every required
    step must succeed before services are enabled.

    The CN GitHub proxy (if applicable) should already be configured in
    /etc/gitconfig by the caller before this function is invoked, so paru's
    internal git operations are also proxied.
    """
    validate_dms_selection(compositor, terminal)
    file_managers = file_managers or []
    repo_packages = [
        *DUX_SYSTEM_PACKAGES,
        *DUX_COMPOSITOR_PACKAGES[compositor],
        DUX_TERMINAL_PACKAGES[terminal],
    ]

    sudoers_tmp = chroot_dir / 'etc' / 'sudoers.d' / '99-dms-temp'
    sudoers_tmp.parent.mkdir(parents=True, exist_ok=True)
    sudoers_tmp.write_text(f'{username} ALL=(ALL) NOPASSWD: ALL\n')
    sudoers_tmp.chmod(0o440)
    _debug('Temporary NOPASSWD sudoers rule created')

    try:
        _info(t('dms.setting_up_sudoers'))
        _info(t('dms.native_packages_installing'))
        if not install_chroot_packages(
            chroot_dir,
            username,
            repo_packages,
            DUX_AUR_PACKAGES,
            t('dms.native_packages_installing'),
        ):
            return False
        if not verify_dms_installation(chroot_dir):
            return False

        if not run_dms_setup(chroot_dir, username, compositor, terminal):
            return False
        if not configure_dms_shortcuts(
            chroot_dir, username, compositor, terminal, file_managers,
        ):
            return False
        if not normalize_dms_ownership(chroot_dir, username):
            return False

        if not configure_dms_greeter(chroot_dir, username, compositor):
            _debug(t('dms.greeter_fallback'))
            return False
    finally:
        if sudoers_tmp.exists():
            sudoers_tmp.unlink()
            _debug('Removed temporary sudoers rule')

    configure_dms_environment(chroot_dir)
    _configure_i2c(chroot_dir, username)
    if not configure_dms_autostart(chroot_dir, username):
        return False
    if not _prepare_dsearch(chroot_dir, username):
        return False

    # Enable display and user services only after every required step succeeds.
    if not _enable_dms_services(chroot_dir, username, compositor):
        return False

    _info(t('dms.complete'))
    return True
