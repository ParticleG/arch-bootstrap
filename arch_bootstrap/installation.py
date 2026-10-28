from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import textwrap
import time
from configparser import ConfigParser
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from archinstall.lib.applications.application_handler import ApplicationHandler
from archinstall.lib.args import ArchConfig
from archinstall.lib.authentication.authentication_handler import AuthenticationHandler
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.disk.utils import disk_layouts
from archinstall.lib.general.general_menu import PostInstallationAction, select_post_installation
from archinstall.lib.menu.helpers import Confirmation
from .archinstall_compat import MenuItem, ResultType
from archinstall.lib.global_menu import GlobalMenu
from archinstall.lib.installer import Installer, run_custom_user_commands
from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.models.bootloader import Bootloader
from archinstall.lib.models.device import DiskLayoutType
from archinstall.lib.models.users import User
from archinstall.lib.network.network_handler import install_network_config
from .archinstall_compat import Font, debug, error, info, tui
from archinstall.lib.profile.profiles_handler import profile_handler

from .config import generate_fontconfig, generate_kmscon_config, get_kmscon_greetd_warning
from .constants import (
    ARCHLINUXCN_URL,
    BROWSER_OPTIONS,
    DESKTOP_APPLICATION_IDS,
    DEV_ENVIRONMENT_OPTIONS,
    EDGE_FLAGS,
    ELECTRON_WAYLAND_FLAGS,
    FCITX5_ENVIRONMENT,
    FILE_MANAGER_OPTIONS,
    INPUT_METHOD_PACKAGES,
    OMZ_INSTALL_URL,
    OMZ_REMOTE_GITHUB,
    KEYRING_OPTIONS,
    NERD_FONT_OPTIONS,
    PROXY_TOOL_OPTIONS,
    REFLECTOR_CONF,
    VSCODE_ARGV_JSON,
    VM_OPTIONS,
)
from .detection import calculate_kmscon_font_size, needs_kmscon
from .i18n import get_lang, t
from .log import copy_log_to_target
from .mirrors import format_cn_mirrorlist
from .packages import collect_optional_packages
from .utils import build_paru_aur_install_command, get_clone_url, install_github_proxy_dl, resolve_github_proxy, run_with_retry


# =============================================================================
# Installation tracker
# =============================================================================

class StepStatus(Enum):
    SUCCESS = 'success'
    FAILED = 'failed'
    SKIPPED = 'skipped'


@dataclass
class StepResult:
    name: str          # i18n key
    status: StepStatus
    reason: str = ''   # failure/skip reason


@dataclass
class InstallationTracker:
    steps: list[StepResult] = field(default_factory=list)

    def record(self, name: str, status: StepStatus, reason: str = '') -> None:
        self.steps.append(StepResult(name, status, reason))

    @property
    def has_failures(self) -> bool:
        return any(s.status == StepStatus.FAILED for s in self.steps)


def _print_summary(tracker: InstallationTracker) -> None:
    """Print a bordered installation summary with step statuses."""
    # ANSI color codes
    GREEN = '\033[32m'
    RED = '\033[31m'
    YELLOW = '\033[33m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    # Translate step names and compute column width
    translated_steps: list[tuple[str, StepResult]] = [
        (t(step.name), step) for step in tracker.steps
    ]
    max_name_len = max((len(name) for name, _ in translated_steps), default=20)
    # Ensure minimum width for title and totals line
    title = t('summary.title')
    log_label = t('summary.log_path')
    log_path = '/var/log/arch-bootstrap/install.log'
    log_line_len = len(log_label) + 2 + len(log_path)  # "label: path"
    min_content_width = max(len(title), log_line_len, max_name_len + 6)
    box_width = min_content_width + 4  # 2 for "║ " + 2 for " ║"

    def pad(text: str, width: int) -> str:
        """Pad text to width accounting for ANSI escape sequences."""
        # Strip ANSI codes to get visible length
        import re
        visible = re.sub(r'\033\[[0-9;]*m', '', text)
        return text + ' ' * (width - len(visible))

    content_width = box_width - 4  # inner content width

    print()
    print(f'╔{"═" * (box_width - 2)}╗')
    print(f'║ {BOLD}{pad(title, content_width)}{RESET} ║')
    print(f'╠{"═" * (box_width - 2)}╣')

    for name, step in translated_steps:
        if step.status == StepStatus.SUCCESS:
            indicator = f'{GREEN}✓{RESET}'
        elif step.status == StepStatus.FAILED:
            indicator = f'{RED}✗{RESET}'
        else:
            indicator = f'{YELLOW}-{RESET}'

        line = f'{indicator} {name}'
        print(f'║ {pad(line, content_width)} ║')

        if step.status == StepStatus.FAILED and step.reason:
            reason_line = f'  {RED}→ {step.reason}{RESET}'
            print(f'║ {pad(reason_line, content_width)} ║')

    print(f'╠{"═" * (box_width - 2)}╣')

    # Totals
    total = len(tracker.steps)
    succeeded = sum(1 for s in tracker.steps if s.status == StepStatus.SUCCESS)
    failed = sum(1 for s in tracker.steps if s.status == StepStatus.FAILED)
    skipped = sum(1 for s in tracker.steps if s.status == StepStatus.SKIPPED)

    totals_line = (
        f'{t("summary.total")}: {total} | '
        f'{GREEN}✓{RESET} {succeeded} | '
        f'{RED}✗{RESET} {failed} | '
        f'{YELLOW}-{RESET} {skipped}'
    )
    print(f'║ {pad(totals_line, content_width)} ║')

    # Log file path
    log_line = f'{log_label}: {log_path}'
    print(f'║ {pad(log_line, content_width)} ║')

    print(f'╚{"═" * (box_width - 2)}╝')
    print()


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


def _write_cn_mirrorlist(path: Path) -> None:
    """Write hardcoded CN official mirrors to the given mirrorlist path.

    Bypasses archinstall's mirror speed-testing entirely for CN region.
    USTC is listed first, followed by TUNA and CERNET as fallbacks.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_cn_mirrorlist())
    _info(f'CN mirrorlist written to {path}')


# =============================================================================
# GitHub proxy resolution (for CN oh-my-zsh)
# =============================================================================

def _resolve_omz_remote(country: str | None) -> str | None:
    """Resolve the oh-my-zsh REMOTE git URL for CN users.

    For non-CN: returns None (use default upstream).
    For CN: resolves GitHub proxy and returns proxied git URL.
    """
    if country != 'CN':
        return None

    _info('China detected, resolving GitHub proxy for oh-my-zsh...')

    proxy = resolve_github_proxy(is_cn=True)
    if proxy:
        _info(f'Using proxy: {proxy}')
        return f'{proxy}/{OMZ_REMOTE_GITHUB}'

    return None


# =============================================================================
# Zsh plugin activation
# =============================================================================

_ZSH_AUTOSUGGESTIONS_SOURCE = (
    '\n# zsh-autosuggestions installed by pacman (outside Oh My Zsh search path)\n'
    '[[ -r /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh ]]'
    ' && source /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh\n'
)


def _patch_zshrc_plugins(zshrc_path: str) -> None:
    """Patch the default oh-my-zsh .zshrc to enable installed plugins.

    - Adds fast-syntax-highlighting to the plugins=() array.
    - Appends a source line for zsh-autosuggestions (pacman installs it to
      /usr/share/zsh/plugins/ which Oh My Zsh does not search).
    """
    path = Path(zshrc_path)
    if not path.exists():
        _debug(f'.zshrc not found at {zshrc_path}, skipping plugin patch')
        return

    content = path.read_text()
    import re

    # Match the active assignment, not Oh My Zsh's commented example.
    plugin_assignment = re.compile(r'^([ \t]*plugins=\()([^)]*)(\))', re.MULTILINE)
    match = plugin_assignment.search(content)
    if match and 'fast-syntax-highlighting' not in match.group(2).split():
        content = plugin_assignment.sub(
            lambda m: f'{m.group(1)}{m.group(2).rstrip()} fast-syntax-highlighting{m.group(3)}',
            content,
            count=1,
        )

    # Append zsh-autosuggestions source after "source $ZSH/oh-my-zsh.sh"
    if 'zsh-autosuggestions' not in content:
        content = content.replace(
            'source $ZSH/oh-my-zsh.sh',
            'source $ZSH/oh-my-zsh.sh' + _ZSH_AUTOSUGGESTIONS_SOURCE,
            1,
        )

    path.write_text(content)
    _debug('Patched .zshrc with zsh plugin configuration')


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
        result = run_with_retry(
            ['arch-chroot', str(chroot_dir),
             'env', 'LANG=C.UTF-8', 'pacman', '-S', '--noconfirm', '--needed', 'paru'],
            description=t('paru.installing'),
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
        'curl -fsSL "https://aur.archlinux.org/cgit/aur.git/snapshot/paru-bin.tar.gz" | tar xz; '
        'cd paru-bin; '
        'makepkg -si --noconfirm --needed'
    )
    result = run_with_retry(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c', build_script],
        description=t('paru.installing'),
        check=False,
    )
    if result.returncode == 0:
        _info(t('paru.installed_aur'))
        return True

    _info(t('paru.failed') % result.returncode)
    return False


# =============================================================================
# archlinuxcn repository setup (post-install, CN only)
# =============================================================================

def _setup_archlinuxcn(chroot_dir: Path) -> None:
    """Configure archlinuxcn repository and install keyring in the chroot.

    Uses USTC mirror for archlinuxcn.  A temporary ``SigLevel = Never`` is used to
    bootstrap ``archlinuxcn-keyring`` and then removed.
    """
    _info('Configuring archlinuxcn repository...')
    pacman_conf = chroot_dir / 'etc' / 'pacman.conf'

    # Add [archlinuxcn] with SigLevel = Never so the keyring can be installed
    with open(pacman_conf, 'a') as f:
        f.write(
            f'\n[archlinuxcn]\n'
            f'SigLevel = Never\n'
            f'Server = {ARCHLINUXCN_URL}\n\n'
        )

    # Install keyring
    _info('Installing archlinuxcn-keyring...')
    result = run_with_retry(
        ['arch-chroot', str(chroot_dir),
         'env', 'LANG=C.UTF-8', 'pacman', '-Syu', '--noconfirm', '--needed',
         'archlinuxcn-keyring'],
        description='archlinuxcn-keyring',
        check=False,
    )
    if result.returncode != 0:
        _info(f'archlinuxcn-keyring installation failed (exit {result.returncode})')
        _info('Leaving bootstrap configuration intact. '
              'Please manually install archlinuxcn-keyring later.')
        return

    # Remove temporary SigLevel override only from the [archlinuxcn] section
    content = pacman_conf.read_text()
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []
    in_archlinuxcn = False
    for line in lines:
        stripped = line.strip()
        # Detect section headers
        if stripped.startswith('[') and stripped.endswith(']'):
            in_archlinuxcn = stripped == '[archlinuxcn]'
        # Skip SigLevel only inside [archlinuxcn]
        if in_archlinuxcn and stripped == 'SigLevel = Never':
            continue
        new_lines.append(line)
    pacman_conf.write_text(''.join(new_lines))


# =============================================================================
# CN GitHub proxy for git in chroot
# =============================================================================

def _setup_cn_git_proxy(chroot_dir: Path) -> None:
    """Write GitHub URL rewrite to /etc/gitconfig for CN users.

    This enables git operations (including makepkg and paru source fetches)
    to use a GitHub proxy.  Written to both /etc/gitconfig (system-level
    git config) and /etc/makepkg.d/gitconfig, because makepkg's source/git.sh
    overrides GIT_CONFIG_SYSTEM to /etc/makepkg.d/gitconfig, bypassing the
    system-level config during AUR builds.
    """
    proxy = resolve_github_proxy(is_cn=True)
    if not proxy:
        _info('CN: no GitHub proxy resolved, skipping git proxy setup')
        return

    _info(f'CN: GitHub proxy for git → {proxy}')
    gitconfig = chroot_dir / 'etc' / 'gitconfig'
    gitconfig.write_text(
        f'[url "{proxy}/https://github.com/"]\n'
        f'\tinsteadOf = https://github.com/\n'
    )

    # Also write to makepkg's git config, since makepkg overrides
    # GIT_CONFIG_SYSTEM to /etc/makepkg.d/gitconfig (see git.sh).
    makepkg_gitconfig = chroot_dir / 'etc' / 'makepkg.d' / 'gitconfig'
    makepkg_gitconfig.parent.mkdir(parents=True, exist_ok=True)
    makepkg_gitconfig.write_text(
        f'[url "{proxy}/https://github.com/"]\n'
        f'\tinsteadOf = https://github.com/\n'
    )

    # Also install the download agent for makepkg's DLAGENTS (non-git sources)
    install_github_proxy_dl(chroot_dir, proxy)


def _remove_cn_git_proxy(chroot_dir: Path) -> None:
    """Remove GitHub proxy URL rewrite from the new system's git configs.

    This undoes what :func:`_setup_cn_git_proxy` wrote, so that git
    operations go directly to GitHub (useful when a local proxy/VPN
    like FlClash is available).
    """
    removed = False
    for path in (
        chroot_dir / 'etc' / 'gitconfig',
        chroot_dir / 'etc' / 'makepkg.d' / 'gitconfig',
    ):
        if path.exists():
            path.unlink()
            _debug(f'Removed git proxy config: {path}')
            removed = True
    if removed:
        _info(t('post.git_proxy_removed'))


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
        browser_info = BROWSER_OPTIONS.get(key, {})
        if 'aur_package' in browser_info:
            aur_packages.append(browser_info['aur_package'])

    if not aur_packages:
        return

    _info(f'Installing AUR browsers: {", ".join(aur_packages)}')
    aur_cmd = build_paru_aur_install_command(aur_packages)

    result = run_with_retry(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c', aur_cmd],
        description=f'AUR browsers: {", ".join(aur_packages)}',
        check=False,
    )
    if result.returncode != 0:
        _info(f'AUR browser installation failed (exit {result.returncode}), skipping')


def _install_prebuilt_input_dictionaries(
    chroot_dir: Path,
    username: str,
    input_methods: list[str],
    country: str | None,
) -> None:
    """Best-effort install for prebuilt input method dictionaries."""
    dictionaries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for im_key in input_methods:
        option = INPUT_METHOD_PACKAGES.get(im_key, {})
        for dictionary in option.get('prebuilt_dictionaries', []):
            url = dictionary.get('url')
            target = dictionary.get('target')
            if not url or not target:
                continue
            key = (url, target)
            if key in seen:
                continue
            seen.add(key)
            dictionaries.append({'url': url, 'target': target})

    if not dictionaries:
        return

    _info(t('post.input_method_dicts'))
    proxy = resolve_github_proxy(country == 'CN')

    for dictionary in dictionaries:
        original_url = dictionary['url']
        download_urls = [original_url]
        if proxy and original_url.startswith('https://github.com/'):
            download_urls.insert(0, f'{proxy}/{original_url}')
        url_args = ' '.join(shlex.quote(url) for url in download_urls)

        target_rel = dictionary['target'].lstrip('/')
        if '..' in Path(target_rel).parts:
            _debug(f'Skipping unsafe input method dictionary path: {target_rel}')
            continue

        target_path = f'/home/{username}/{target_rel}'
        target_dir = target_path.rsplit('/', 1)[0]
        cmd = (
            f'target={shlex.quote(target_path)}; '
            f'dir={shlex.quote(target_dir)}; '
            'mkdir -p "$dir"; '
            'tmp="$(mktemp "$target.tmp.XXXXXX")"; '
            'status=1; '
            f'for url in {url_args}; do '
            'if curl -fsSL --retry 3 --retry-delay 5 --connect-timeout 15 --max-time 900 -o "$tmp" "$url"; then '
            'status=0; break; fi; '
            'status=$?; rm -f "$tmp"; tmp="$(mktemp "$target.tmp.XXXXXX")"; '
            'done; '
            'if [ "$status" -eq 0 ]; then mv "$tmp" "$target"; '
            'else rm -f "$tmp"; exit "$status"; fi'
        )

        result = subprocess.run(
            ['arch-chroot', str(chroot_dir), 'runuser', '-l', username, '-c', cmd],
            check=False,
        )
        if result.returncode == 0:
            _info(t('post.input_method_dict_installed', target_rel))
        else:
            _info(t('post.input_method_dict_failed', target_rel, result.returncode))


def _collect_dev_environment_groups(dev_environments: list[str]) -> list[str]:
    """Return user groups required by selected development tools."""
    groups: list[str] = []
    for de_key in dev_environments:
        option = DEV_ENVIRONMENT_OPTIONS.get(de_key)
        if not option:
            continue
        for group in option.get('groups', []):
            if group not in groups:
                groups.append(group)
    return groups


def _ensure_user_in_groups(chroot_dir: Path, username: str, groups: list[str]) -> bool:
    """Ensure user groups exist and add the target user to them."""
    for group in groups:
        result = run_with_retry(
            ['arch-chroot', str(chroot_dir), 'groupadd', '-f', group],
            max_retries=1, retry_delay=0,
            description=f'ensure {group} group',
        )
        if result.returncode != 0:
            return False

    result = run_with_retry(
        ['arch-chroot', str(chroot_dir),
         'usermod', '-aG', ','.join(groups), username],
        max_retries=1, retry_delay=0,
        description=f'add {username} to {", ".join(groups)} groups',
    )
    return result.returncode == 0


def _gpu_passthrough_parameters(cpuinfo: str) -> list[str]:
    """Return the host CPU's IOMMU requirements without device-specific quirks."""
    if 'GenuineIntel' in cpuinfo:
        return ['intel_iommu=on', 'iommu=pt']
    if 'AuthenticAMD' in cpuinfo:
        return ['iommu=pt']
    raise ValueError(t('post.gpu_iommu_unsupported'))


def _configure_desktop_defaults(chroot_dir: Path, username: str, file_managers: list[str]) -> bool:
    """Merge installed applications' supported MIME types into user defaults."""
    applications = chroot_dir / 'usr/share/applications'
    associations: dict[str, str] = {}
    for desktop_id in DESKTOP_APPLICATION_IDS:
        desktop_path = applications / desktop_id
        if not desktop_path.is_file():
            _debug(f'Desktop application missing: {desktop_id}')
            return False
        entry = ConfigParser(interpolation=None)
        entry.read(desktop_path)
        for mime in entry.get('Desktop Entry', 'MimeType', fallback='').split(';'):
            if mime and not mime.startswith('x-scheme-handler/'):
                associations[mime] = desktop_id + ';'

    for manager in file_managers:
        desktop_id = FILE_MANAGER_OPTIONS.get(manager, {}).get('desktop_id')
        if desktop_id:
            if not (applications / desktop_id).is_file():
                _debug(f'File manager desktop entry missing: {desktop_id}')
                return False
            associations['inode/directory'] = desktop_id + ';'
            break

    config_dir = chroot_dir / 'home' / username / '.config'
    config_dir.mkdir(parents=True, exist_ok=True)
    mimeapps = config_dir / 'mimeapps.list'
    defaults = ConfigParser(interpolation=None)
    defaults.optionxform = str
    defaults.read(mimeapps)
    if not defaults.has_section('Default Applications'):
        defaults.add_section('Default Applications')
    for mime, desktop_id in associations.items():
        if not defaults.has_option('Default Applications', mime):
            defaults.set('Default Applications', mime, desktop_id)
    with mimeapps.open('w') as stream:
        defaults.write(stream, space_around_delimiters=False)
    result = run_with_retry(
        ['arch-chroot', str(chroot_dir), 'chown', f'{username}:{username}',
         f'/home/{username}/.config', f'/home/{username}/.config/mimeapps.list'],
        max_retries=1, retry_delay=0, check=False,
        description='desktop application defaults ownership',
    )
    return result.returncode == 0


def _configure_application_flags(
    chroot_dir: Path,
    username: str,
    browsers: list[str],
    editors: list[str],
    cn_apps: list[str],
) -> bool:
    """Keep Edge's GPU workaround separate from generic Wayland flags."""
    contents = {'.config/electron-flags.conf': ELECTRON_WAYLAND_FLAGS}
    directories = ['.config']
    if 'vscode' in editors:
        contents['.config/code-flags.conf'] = ELECTRON_WAYLAND_FLAGS
        contents['.vscode/argv.json'] = VSCODE_ARGV_JSON
        directories.append('.vscode')
    if 'linuxqq-nt-bwrap' in cn_apps:
        contents['.config/qq-electron-flags.conf'] = ELECTRON_WAYLAND_FLAGS
    if 'edge' in browsers:
        contents['.config/microsoft-edge-stable-flags.conf'] = EDGE_FLAGS
    for relative_path, content in contents.items():
        path = chroot_dir / 'home' / username / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    result = run_with_retry(
        ['arch-chroot', str(chroot_dir), 'chown', f'{username}:{username}',
         *[f'/home/{username}/{path}' for path in [*directories, *contents]]],
        max_retries=1, retry_delay=0, check=False,
        description='application flags ownership',
    )
    return result.returncode == 0


def _configure_gtk_input_method(chroot_dir: Path, username: str) -> bool:
    """Add Fcitx settings without duplicating Dux-generated GTK sections."""
    home = chroot_dir / 'home' / username
    gtk2 = home / '.gtkrc-2.0'
    lines = gtk2.read_text().splitlines() if gtk2.exists() else []
    lines = [line for line in lines if not line.lstrip().startswith('gtk-im-module')]
    gtk2.write_text('\n'.join([*lines, 'gtk-im-module="fcitx"']) + '\n')
    owned = [f'/home/{username}/.gtkrc-2.0']
    for version in ('gtk-3.0', 'gtk-4.0'):
        directory = home / '.config' / version
        directory.mkdir(parents=True, exist_ok=True)
        settings = ConfigParser(interpolation=None, strict=False)
        settings.optionxform = str
        path = directory / 'settings.ini'
        settings.read(path)
        if not settings.has_section('Settings'):
            settings.add_section('Settings')
        settings.set('Settings', 'gtk-im-module', 'fcitx')
        with path.open('w') as stream:
            settings.write(stream, space_around_delimiters=False)
        owned.extend([
            f'/home/{username}/.config/{version}',
            f'/home/{username}/.config/{version}/settings.ini',
        ])
    result = run_with_retry(
        ['arch-chroot', str(chroot_dir), 'chown', f'{username}:{username}', *owned],
        max_retries=1, retry_delay=0, check=False,
        description='GTK input method settings ownership',
    )
    return result.returncode == 0


def _configure_gnome_keyring(chroot_dir: Path, username: str) -> bool:
    """Enable keyring sockets and expose the GCR SSH agent to user services."""
    environment_dir = chroot_dir / 'home' / username / '.config/environment.d'
    environment_dir.mkdir(parents=True, exist_ok=True)
    (environment_dir / '10-gcr-ssh-agent.conf').write_text(
        'SSH_AUTH_SOCK=${XDG_RUNTIME_DIR}/gcr/ssh\n'
    )
    result = run_with_retry(
        ['arch-chroot', str(chroot_dir), 'chown', '-R', f'{username}:{username}',
         f'/home/{username}/.config/environment.d'],
        max_retries=1, retry_delay=0, check=False,
        description='GCR SSH agent environment ownership',
    )
    if result.returncode:
        return False
    result = run_with_retry(
        ['arch-chroot', str(chroot_dir), 'systemctl', '--global', 'enable',
         'gnome-keyring-daemon.socket', 'p11-kit-server.socket', 'gcr-ssh-agent.socket'],
        max_retries=1, retry_delay=0, check=False,
        description='GNOME Keyring and GCR SSH agent sockets',
    )
    return result.returncode == 0


def _enable_sunshine(chroot_dir: Path) -> bool:
    """Enable the packaged user service, never a duplicate custom unit."""
    service = 'app-dev.lizardbyte.app.Sunshine.service'
    if not (chroot_dir / 'usr/lib/systemd/user' / service).is_file():
        _debug(f'Sunshine service missing: {service}')
        return False
    result = run_with_retry(
        ['arch-chroot', str(chroot_dir), 'systemctl', '--global', 'enable', service],
        max_retries=1, retry_delay=0, check=False,
        description='Sunshine user service',
    )
    return result.returncode == 0


# =============================================================================
# Installation
# =============================================================================

def perform_installation(
    config: ArchConfig,
    mirror_list_handler: MirrorListHandler,
    state: 'WizardState',
) -> None:
    """Execute the installation using archinstall's Installer."""
    from .wizard import WizardState  # noqa: F811 — deferred to avoid circular import
    # Normalize hidden selections before either package phase or service setup.
    _, repo_packages, aur_packages = collect_optional_packages(state)

    # Unpack frequently used state fields
    kmscon_font_name = state.kmscon_font_name
    screen_resolution = state.screen_resolution
    gpu_vendors = state.gpu_vendors
    username = state.username
    country = state.country
    desktop_env = state.desktop_env
    dms_compositor = state.dms_compositor
    dms_terminal = state.dms_terminal
    browsers = state.browsers

    start_time = time.monotonic()
    tracker = InstallationTracker()
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
    iommu_parameters: list[str] = []
    if 'gpu_passthrough' in state.vm_options:
        if not config.bootloader_config or config.bootloader_config.bootloader == Bootloader.NO_BOOTLOADER:
            raise ValueError(t('post.gpu_iommu_unsupported'))
        iommu_parameters = _gpu_passthrough_parameters(Path('/proc/cpuinfo').read_text())

    with Installer(
        mountpoint,
        disk_config,
        kernels=config.kernels,
        silent=False,
    ) as installation:
        # archinstall 4.x uses this list for every bootloader and embedded UKI
        # command line. Set it before boot generation, not in host boot files.
        if iommu_parameters:
            _info(t('post.gpu_iommu'))
            installation._kernel_params.extend(iommu_parameters)
        if disk_config.config_type != DiskLayoutType.Pre_mount:
            installation.mount_ordered_layout()

        installation.sanity_check(skip_ntp=False, skip_wkd=False)

        if country == 'CN':
            # CN live ISO mirrorlist was already written by
            # apply_mirrors_to_live_iso() during the wizard phase — skip.
            pass
        elif mirror_config := config.mirror_config:
            installation.set_mirrors(mirror_list_handler, mirror_config, on_target=False)

        installation.minimal_installation(
            optional_repositories=optional_repos,
            mkinitcpio=run_mkinitcpio,
            hostname=config.hostname,
            locale_config=locale_config,
        )

        if country == 'CN':
            _write_cn_mirrorlist(mountpoint / 'etc' / 'pacman.d' / 'mirrorlist')
        elif mirror_config := config.mirror_config:
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
            tracker.record('summary.step.network', StepStatus.SUCCESS)
        else:
            tracker.record('summary.step.network', StepStatus.SKIPPED)

        users = None
        if config.auth_config:
            if config.auth_config.users:
                users = config.auth_config.users
                installation.create_users(config.auth_config.users)
                auth_handler.setup_auth(installation, config.auth_config, config.hostname)
                tracker.record('summary.step.user_accounts', StepStatus.SUCCESS)
            else:
                tracker.record('summary.step.user_accounts', StepStatus.SKIPPED)
        else:
            tracker.record('summary.step.user_accounts', StepStatus.SKIPPED)

        # Force English XDG user directories regardless of locale.
        # This runs xdg-user-dirs-update with LC_ALL=C so directories
        # like Downloads, Documents, Desktop stay in English, then
        # disables automatic updates to prevent locale changes from
        # renaming them on subsequent logins.
        if users:
            _info(t('post.xdg_user_dirs'))
            # The English XDG directory names and their XDG keys.
            _xdg_dirs = {
                'DESKTOP': 'Desktop',
                'DOWNLOAD': 'Downloads',
                'TEMPLATES': 'Templates',
                'PUBLICSHARE': 'Public',
                'DOCUMENTS': 'Documents',
                'MUSIC': 'Music',
                'PICTURES': 'Pictures',
                'VIDEOS': 'Videos',
            }
            _user_dirs_content = (
                '# This file is written by xdg-user-dirs-update\n'
                + ''.join(
                    f'XDG_{k}_DIR="$HOME/{v}"\n' for k, v in _xdg_dirs.items()
                )
            )
            for user in users:
                home = mountpoint / 'home' / user.username
                config_dir = home / '.config'
                config_dir.mkdir(parents=True, exist_ok=True)

                # 1. Write user-dirs.dirs directly — this is authoritative
                #    and does not depend on xdg-user-dirs-update succeeding
                #    inside the chroot.
                (config_dir / 'user-dirs.dirs').write_text(_user_dirs_content)

                # 2. Disable automatic xdg-user-dirs-update on login so a
                #    non-English locale will not rename the directories.
                (config_dir / 'user-dirs.conf').write_text('enabled=False\n')

                # 3. Create the actual directories.
                for dirname in _xdg_dirs.values():
                    (home / dirname).mkdir(exist_ok=True)

                # 4. Fix ownership (files were created as root).
                subprocess.run(
                    ['arch-chroot', str(mountpoint),
                     'chown', '-R', f'{user.username}:{user.username}',
                     f'/home/{user.username}/.config/user-dirs.dirs',
                     f'/home/{user.username}/.config/user-dirs.conf',
                     ] + [f'/home/{user.username}/{d}' for d in _xdg_dirs.values()],
                    check=False,
                )
                _debug(f'XDG user directories set to English for {user.username}')

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

    tracker.record('summary.step.base_system', StepStatus.SUCCESS)

    # Post-install: write keyboard layout to vconsole.conf
    chroot_dir = mountpoint
    if not (chroot_dir / 'etc').exists():
        chroot_dir = Path('/mnt')

    vconsole = chroot_dir / 'etc' / 'vconsole.conf'
    vconsole.write_text('KEYMAP=us\n')
    tracker.record('summary.step.console', StepStatus.SUCCESS)

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

        # Write login warning for minimal installs where kmscon is on tty1.
        # Users who later install greetd will see a reminder to move kmscon.
        if desktop_env not in ('dms', 'exo'):
            warning_dir = chroot_dir / 'etc' / 'profile.d'
            warning_dir.mkdir(parents=True, exist_ok=True)
            warning_file = warning_dir / 'kmscon-warning.sh'
            warning_file.write_text(get_kmscon_greetd_warning())
            _info('Written /etc/profile.d/kmscon-warning.sh (kmscon on tty1)')

        tracker.record('summary.step.kmscon', StepStatus.SUCCESS)
    else:
        tracker.record('summary.step.kmscon', StepStatus.SKIPPED)

    # Post-install: write user fontconfig for CJK locales
    if needs_kmscon(locale) and kmscon_font_name and username:
        nerd_font_families = [
            NERD_FONT_OPTIONS[k]['family']
            for k in state.nerd_fonts
            if k in NERD_FONT_OPTIONS
        ]
        fontconfig_content = generate_fontconfig(kmscon_font_name, locale, nerd_font_families)
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
                found = False
                for line in passwd_file.read_text().splitlines():
                    fields = line.split(':')
                    if len(fields) >= 4 and fields[0] == username:
                        uid, gid = int(fields[2]), int(fields[3])
                        found = True
                        break
                if not found:
                    _debug(f'Warning: user {username} not found in passwd, using UID/GID 1000 as fallback')

            # chown the entire .config/fontconfig tree
            for path in [user_home / '.config', fontconfig_dir, fontconfig_file]:
                if path.exists():
                    os.chown(path, uid, gid)
        except (ValueError, OSError):
            pass  # best-effort ownership fix

        _info(f'Written fontconfig for user {username}')
        tracker.record('summary.step.fonts', StepStatus.SUCCESS)
    else:
        tracker.record('summary.step.fonts', StepStatus.SKIPPED)

    # Post-install: copy WiFi connections from live ISO
    _copy_wifi_connections(chroot_dir)
    tracker.record('summary.step.wifi', StepStatus.SUCCESS)

    # Post-install: CN-specific setup (git proxy + archlinuxcn repo)
    if country == 'CN':
        _setup_cn_git_proxy(chroot_dir)
        tracker.record('summary.step.git_proxy', StepStatus.SUCCESS)
        _setup_archlinuxcn(chroot_dir)
        tracker.record('summary.step.cn_repo', StepStatus.SUCCESS)
    else:
        tracker.record('summary.step.git_proxy', StepStatus.SKIPPED)
        tracker.record('summary.step.cn_repo', StepStatus.SKIPPED)

    # Post-install: grant temporary NOPASSWD sudo for AUR operations
    sudoers_aur = None
    if username:
        sudoers_aur = chroot_dir / 'etc' / 'sudoers.d' / 'aur-tmp'
        sudoers_aur.write_text(
            f'{username} ALL=(ALL) NOPASSWD: ALL\n'
        )
        sudoers_aur.chmod(0o440)
        _debug('Temporary NOPASSWD sudoers rule created for AUR operations')

    try:
        # Post-install: install paru AUR helper
        has_paru = False
        if username:
            has_paru = _install_paru(chroot_dir, username, country)
            if has_paru:
                tracker.record('summary.step.aur_helper', StepStatus.SUCCESS)
            else:
                tracker.record('summary.step.aur_helper', StepStatus.FAILED, 'paru installation failed')
        else:
            tracker.record('summary.step.aur_helper', StepStatus.SKIPPED)

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
                    f'sh -c "$(curl -fsSL {OMZ_INSTALL_URL})" "" --unattended --skip-chsh'
                )
            else:
                omz_cmd = f'sh -c "$(curl -fsSL {OMZ_INSTALL_URL})" "" --unattended --skip-chsh'

            _zsh_ok = True
            try:
                result = run_with_retry(
                    ['arch-chroot', str(chroot_dir),
                     'runuser', '-l', username, '-c', omz_cmd],
                    description='oh-my-zsh',
                    check=False,
                    timeout=120,
                )
                if result.returncode == 0:
                    _info(f'Installed oh-my-zsh for user {username}')
                else:
                    _info(f'oh-my-zsh installation failed (exit {result.returncode}), skipping')
                    _zsh_ok = False
            except subprocess.TimeoutExpired:
                _debug('oh-my-zsh installation timed out after 120s, skipping')
                _zsh_ok = False

        # Post-install: zsh plugins
        is_cn = country == 'CN'
        if username:
            _info(t('post.zsh_plugins'))
            home = f'/home/{username}'
            omz_custom = f'{home}/.oh-my-zsh/custom/plugins'

            # zsh-autosuggestions (pacman)
            run_with_retry(
                ['arch-chroot', str(chroot_dir),
                 'env', 'LANG=C.UTF-8', 'pacman', '-S', '--noconfirm', '--needed', 'zsh-autosuggestions'],
                max_retries=3, retry_delay=5,
                description='zsh-autosuggestions',
            )

            # fast-syntax-highlighting (git clone into oh-my-zsh custom plugins)
            fsh_url = get_clone_url('https://github.com/zdharma-continuum/fast-syntax-highlighting.git', is_cn)
            fsh_cmd = f"git clone {fsh_url} {omz_custom}/fast-syntax-highlighting"
            run_with_retry(
                ['arch-chroot', str(chroot_dir), 'runuser', '-l', username, '-c', fsh_cmd],
                max_retries=3, retry_delay=5,
                description='fast-syntax-highlighting plugin',
            )

            # Patch .zshrc to enable plugins:
            # - fast-syntax-highlighting lives in $ZSH_CUSTOM/plugins so add to plugins=()
            # - zsh-autosuggestions is installed by pacman to /usr/share/zsh/plugins/,
            #   which is outside Oh My Zsh's search path, so source it explicitly
            zshrc = f'{chroot_dir}/{home}/.zshrc'
            _patch_zshrc_plugins(zshrc)

            if _zsh_ok:
                tracker.record('summary.step.zsh', StepStatus.SUCCESS)
            else:
                tracker.record('summary.step.zsh', StepStatus.FAILED, 'oh-my-zsh installation failed or timed out')
        else:
            tracker.record('summary.step.zsh', StepStatus.SKIPPED)

        # Post-install: DMS desktop environment
        if desktop_env == 'dms' and username:
            from .dms import install_dms
            _info(t('step.desktop.dms'))
            desktop_ok = install_dms(
                chroot_dir=chroot_dir,
                username=username,
                compositor=dms_compositor,
                terminal=dms_terminal,
                file_managers=state.file_managers,
            )
            tracker.record(
                'summary.step.desktop',
                StepStatus.SUCCESS if desktop_ok else StepStatus.FAILED,
                '' if desktop_ok else t('dms.install_incomplete'),
            )

        # Post-install: Exo desktop environment
        elif desktop_env == 'exo' and username:
            from .exo import install_exo
            _info('Setting up Exo desktop environment...')
            install_exo(
                chroot_dir=chroot_dir,
                username=username,
                country=country,
                gpu_vendors=gpu_vendors,
            )
            tracker.record('summary.step.desktop', StepStatus.SUCCESS)
        else:
            tracker.record('summary.step.desktop', StepStatus.SKIPPED)

        # Post-install: AUR browsers (requires paru)
        if has_paru and browsers:
            _install_aur_browsers(chroot_dir, username, browsers)
            tracker.record('summary.step.browser', StepStatus.SUCCESS)
        elif browsers:
            tracker.record('summary.step.browser', StepStatus.FAILED, 'paru not available')
        else:
            tracker.record('summary.step.browser', StepStatus.SKIPPED)

        # Post-install: application-specific display and GPU configuration
        if desktop_env != 'minimal' and username:
            _info(t('post.electron_flags'))
            flags_ok = _configure_application_flags(
                chroot_dir, username, browsers, state.dev_editors, state.cn_apps,
            )
            tracker.record(
                'summary.step.electron_flags',
                StepStatus.SUCCESS if flags_ok else StepStatus.FAILED,
            )
        else:
            tracker.record('summary.step.electron_flags', StepStatus.SKIPPED)

        # Post-install: fcitx5 input method environment variables
        if state.input_methods:
            _info(t('post.input_method'))
            env_file = f'{chroot_dir}/etc/environment'
            with open(env_file, 'a') as f:
                for key, value in FCITX5_ENVIRONMENT.items():
                    f.write(f'{key}={value}\n')

            input_ok = True
            if username:
                input_ok = _configure_gtk_input_method(chroot_dir, username)
                _install_prebuilt_input_dictionaries(
                    chroot_dir,
                    username,
                    state.input_methods,
                    country,
                )

            tracker.record(
                'summary.step.input_method',
                StepStatus.SUCCESS if input_ok else StepStatus.FAILED,
            )
        else:
            tracker.record('summary.step.input_method', StepStatus.SKIPPED)

        # Region-qualified packages are installed only after archlinuxcn setup.
        # The shared collector also includes all selected AUR application groups.

        additional_packages = bool(repo_packages or aur_packages)
        additional_failed = False

        if repo_packages:
            result = run_with_retry(
                ['arch-chroot', str(chroot_dir),
                 'env', 'LANG=C.UTF-8',
                 'pacman', '-S', '--noconfirm', '--needed', *repo_packages],
                max_retries=3, retry_delay=5,
                description='additional repository packages',
                check=False,
            )
            additional_failed = result.returncode != 0

        if aur_packages:
            if has_paru and username:
                aur_cmd = build_paru_aur_install_command(aur_packages)
                result = run_with_retry(
                    ['arch-chroot', str(chroot_dir), 'runuser', '-l', username, '-c', aur_cmd],
                    max_retries=3, retry_delay=5,
                    description='additional AUR packages',
                    check=False,
                )
                additional_failed = additional_failed or result.returncode != 0
            else:
                additional_failed = True

        if additional_failed:
            tracker.record('summary.step.aur_packages', StepStatus.FAILED, 'additional package installation failed')
        elif additional_packages:
            tracker.record('summary.step.aur_packages', StepStatus.SUCCESS)
        else:
            tracker.record('summary.step.aur_packages', StepStatus.SKIPPED)

        if 'sunshine' in state.remote_desktop and desktop_env != 'minimal':
            _info(t('post.sunshine'))
            sunshine_ok = not additional_failed and _enable_sunshine(chroot_dir)
            tracker.record(
                'summary.step.sunshine',
                StepStatus.SUCCESS if sunshine_ok else StepStatus.FAILED,
            )
        else:
            tracker.record('summary.step.sunshine', StepStatus.SKIPPED)

        if desktop_env != 'minimal' and username:
            _info(t('post.desktop_defaults'))
            defaults_ok = _configure_desktop_defaults(chroot_dir, username, state.file_managers)
            tracker.record(
                'summary.step.desktop_defaults',
                StepStatus.SUCCESS if defaults_ok else StepStatus.FAILED,
            )
        else:
            tracker.record('summary.step.desktop_defaults', StepStatus.SKIPPED)

        # Post-install: enable services for dev tools (docker, etc.)
        if state.dev_environments:
            _info(t('post.dev_services'))
            for de_key in state.dev_environments:
                if de_key in DEV_ENVIRONMENT_OPTIONS:
                    for service in DEV_ENVIRONMENT_OPTIONS[de_key].get('services', []):
                        run_with_retry(
                            ['arch-chroot', str(chroot_dir),
                             'systemctl', 'enable', service],
                            max_retries=1, retry_delay=0,
                            description=f'enable {service}',
                        )
            tracker.record('summary.step.dev_services', StepStatus.SUCCESS)
        else:
            tracker.record('summary.step.dev_services', StepStatus.SKIPPED)

        # Post-install: add user to development tool groups (Docker, etc.)
        dev_groups = _collect_dev_environment_groups(state.dev_environments)
        if dev_groups and username:
            _info(t('post.dev_groups'))
            if _ensure_user_in_groups(chroot_dir, username, dev_groups):
                tracker.record('summary.step.dev_groups', StepStatus.SUCCESS)
            else:
                tracker.record(
                    'summary.step.dev_groups',
                    StepStatus.FAILED,
                    'could not configure user groups',
                )
        elif dev_groups:
            tracker.record(
                'summary.step.dev_groups',
                StepStatus.FAILED,
                'username not configured',
            )
        else:
            tracker.record('summary.step.dev_groups', StepStatus.SKIPPED)

        # Post-install: VM services
        if state.vm_options:
            for vm_key in state.vm_options:
                if vm_key in VM_OPTIONS:
                    for service in VM_OPTIONS[vm_key].get('services', []):
                        run_with_retry(
                            ['arch-chroot', str(chroot_dir), 'systemctl', 'enable', service],
                            description=f'enable {service}',
                        )

            # Post-install: VM user groups
            run_with_retry(
                ['arch-chroot', str(chroot_dir), 'usermod', '-a', '-G', 'libvirt,kvm', username],
                description='add user to libvirt and kvm groups',
            )

            tracker.record('summary.step.virtual_machine', StepStatus.SUCCESS)
        else:
            tracker.record('summary.step.virtual_machine', StepStatus.SKIPPED)

        # Post-install: Docker + KVM compatibility
        # Docker sets iptables FORWARD policy to DROP, which blocks libvirt
        # NAT traffic (virbr0). The ip-forward-no-drop option (Docker 28.0+)
        # prevents this, allowing KVM VMs to access the network.
        if 'docker' in state.dev_environments and 'kvm_base' in state.vm_options:
            docker_conf_dir = chroot_dir / 'etc' / 'docker'
            docker_conf_dir.mkdir(parents=True, exist_ok=True)
            daemon_json = docker_conf_dir / 'daemon.json'
            if daemon_json.exists():
                conf = json.loads(daemon_json.read_text())
            else:
                conf = {}
            conf['ip-forward-no-drop'] = True
            daemon_json.write_text(json.dumps(conf, indent=4) + '\n')

        # Post-install: KVM network setup first-boot service
        if 'kvm_base' in state.vm_options:
            service_dir = chroot_dir / 'etc' / 'systemd' / 'system'
            service_dir.mkdir(parents=True, exist_ok=True)
            service_file = service_dir / 'kvm-network-setup.service'
            service_file.write_text(textwrap.dedent("""\
                [Unit]
                Description=KVM Default Network Setup
                After=libvirtd.service
                Requires=libvirtd.service
                ConditionPathExists=!/etc/kvm-network-configured

                [Service]
                Type=oneshot
                ExecStart=/bin/bash -c 'virsh net-start default; virsh net-autostart default; touch /etc/kvm-network-configured'
                RemainAfterExit=yes

                [Install]
                WantedBy=multi-user.target
            """))
            run_with_retry(
                ['arch-chroot', str(chroot_dir), 'systemctl', 'enable', 'kvm-network-setup'],
                description='enable KVM network setup service',
            )

        # Post-install: nested virtualization
        if 'nested_virt' in state.vm_options:
            cpuinfo = Path('/proc/cpuinfo').read_text()
            if 'GenuineIntel' in cpuinfo:
                kvm_module = 'kvm_intel'
            else:
                kvm_module = 'kvm_amd'

            modprobe_dir = chroot_dir / 'etc' / 'modprobe.d'
            modprobe_dir.mkdir(parents=True, exist_ok=True)
            (modprobe_dir / f'{kvm_module}.conf').write_text(f'options {kvm_module} nested=1\n')

        # Post-install: OVMF nvram configuration
        if 'kvm_base' in state.vm_options:
            qemu_conf = chroot_dir / 'etc' / 'libvirt' / 'qemu.conf'
            if qemu_conf.exists():
                content = qemu_conf.read_text()
                nvram_line = 'nvram = [\n    "/usr/share/ovmf/x64/OVMF_CODE.fd:/usr/share/ovmf/x64/OVMF_VARS.fd"\n]'
                if 'nvram' not in content or '#nvram' in content:
                    # Append nvram config at end of file
                    content = content.rstrip() + '\n\n' + nvram_line + '\n'
                    qemu_conf.write_text(content)

        # Post-install: GPU hot-switch script
        if 'gpu_passthrough' in state.vm_options:
            # Try to install from AUR via paru
            try:
                subprocess.run(
                    ['arch-chroot', str(chroot_dir),
                     'runuser', '-l', state.username, '-c',
                     build_paru_aur_install_command(['gpu-hotswitch-vfio'])],
                    check=True, capture_output=True)
                _info('gpu-hotswitch-vfio installed from AUR')
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback: download from GitHub release
                _info('AUR install failed, downloading gpu-hotswitch-vfio from GitHub...')
                _gh_url = 'https://github.com/ParticleG/gpu-hotswitch-vfio/releases/latest/download/gpu-hotswitch-vfio'
                gpu_script_dir = chroot_dir / 'usr' / 'local' / 'bin'
                gpu_script_dir.mkdir(parents=True, exist_ok=True)
                gpu_script = gpu_script_dir / 'gpu-hotswitch-vfio'
                try:
                    subprocess.run(
                        ['curl', '-fsSL', '-o', str(gpu_script), _gh_url],
                        check=True, capture_output=True)
                    gpu_script.chmod(0o755)
                    _info('gpu-hotswitch-vfio downloaded from GitHub')
                except subprocess.CalledProcessError:
                    _info('WARNING: Failed to install gpu-hotswitch-vfio. '
                          'Install manually: paru -S --aur --noprovides gpu-hotswitch-vfio')

        # Post-install: LookingGlass KVMFR configuration
        if 'looking_glass' in state.vm_options:
            modprobe_dir = chroot_dir / 'etc' / 'modprobe.d'
            modprobe_dir.mkdir(parents=True, exist_ok=True)
            (modprobe_dir / 'kvmfr.conf').write_text('options kvmfr static_size_mb=512\n')

            modules_dir = chroot_dir / 'etc' / 'modules-load.d'
            modules_dir.mkdir(parents=True, exist_ok=True)
            (modules_dir / 'kvmfr.conf').write_text('# KVMFR Looking Glass module\nkvmfr\n')

            udev_dir = chroot_dir / 'etc' / 'udev' / 'rules.d'
            udev_dir.mkdir(parents=True, exist_ok=True)
            (udev_dir / '99-kvmfr.rules').write_text(
                f'SUBSYSTEM=="kvmfr", OWNER="{username}", GROUP="kvm", MODE="0660"\n'
            )

            qemu_conf = chroot_dir / 'etc' / 'libvirt' / 'qemu.conf'
            if qemu_conf.exists():
                content = qemu_conf.read_text()
                if '/dev/kvmfr0' not in content:
                    cgroup_block = '''
cgroup_device_acl = [
    "/dev/null", "/dev/full", "/dev/zero",
    "/dev/random", "/dev/urandom",
    "/dev/ptmx", "/dev/kvm", "/dev/kqemu",
    "/dev/rtc", "/dev/hpet", "/dev/vfio/vfio",
    "/dev/kvmfr0"
]
'''
                    content = content.rstrip() + '\n' + cgroup_block
                    qemu_conf.write_text(content)

        # Initialize rustup default toolchain
        if 'rustup' in state.dev_environments and state.username:
            run_with_retry(
                ['arch-chroot', str(chroot_dir), 'runuser', '-l', state.username, '-c',
                 'rustup default stable'],
                max_retries=3, retry_delay=5,
                description='rustup default stable',
            )

        # Post-install: enable snapper timers for btrfs snapshots
        _info(t('post.snapper_timers'))
        for timer in ('snapper-timeline.timer', 'snapper-cleanup.timer', 'snapper-boot.timer'):
            run_with_retry(
                ['arch-chroot', str(chroot_dir), 'systemctl', 'enable', timer],
                max_retries=1, retry_delay=0,
                description=f'enable {timer}',
            )

        # GCR supplies SSH-agent functionality separately from GNOME Keyring.
        if state.keyring == 'gnome' and username:
            _info(t('post.gcr_ssh'))
            keyring_ok = _configure_gnome_keyring(chroot_dir, username)
            tracker.record(
                'summary.step.keyring',
                StepStatus.SUCCESS if keyring_ok else StepStatus.FAILED,
            )
        else:
            tracker.record('summary.step.keyring', StepStatus.SKIPPED)

        # Post-install: configure PAM for keyring auto-unlock at login
        if state and state.keyring and state.keyring in KEYRING_OPTIONS:
            keyring_cfg = KEYRING_OPTIONS[state.keyring]
            pam_auth = keyring_cfg['pam_auth']
            pam_session = keyring_cfg['pam_session']
            for pam_file in ('greetd', 'login'):
                pam_path = chroot_dir / 'etc' / 'pam.d' / pam_file
                if pam_path.exists():
                    content = pam_path.read_text()
                    if keyring_cfg['pam_module'] not in content:
                        _info(f'Configuring PAM ({pam_file}) for {state.keyring} keyring...')
                        content = content.rstrip('\n') + '\n' + pam_auth + '\n' + pam_session + '\n'
                        pam_path.write_text(content)

        tracker.record('summary.step.snapper', StepStatus.SUCCESS)

        # Post-install: reflector setup for non-CN users
        if country != 'CN':
            _info(t('post.reflector'))
            reflector_dir = chroot_dir / 'etc' / 'xdg' / 'reflector'
            reflector_dir.mkdir(parents=True, exist_ok=True)
            (reflector_dir / 'reflector.conf').write_text(REFLECTOR_CONF)
            run_with_retry(
                ['arch-chroot', str(chroot_dir),
                 'systemctl', 'enable', 'reflector.timer'],
                max_retries=1, retry_delay=0,
                description='enable reflector.timer',
            )
            tracker.record('summary.step.reflector', StepStatus.SUCCESS)
        else:
            tracker.record('summary.step.reflector', StepStatus.SKIPPED)

        # Post-install: hibernation setup (btrfs swapfile + resume parameters)
        if state and state.hibernation:
            _info(t('post.hibernation'))

            # Create swapfile sized to match RAM
            ram_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
            ram_gib = max(1, round(ram_bytes / (1024**3)))

            # Ensure @swap subvolume is mounted
            swap_mount = chroot_dir / 'swap'
            if not swap_mount.is_mount():
                os.makedirs(str(swap_mount), exist_ok=True)
                # Find the root btrfs UUID from fstab and mount @swap subvolume
                fstab_path = chroot_dir / 'etc' / 'fstab'
                fstab_root_uuid = None
                for line in fstab_path.read_text().splitlines():
                    line = line.strip()
                    if line.startswith('#') or not line:
                        continue
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == '/':
                        if parts[0].startswith('UUID='):
                            fstab_root_uuid = parts[0].split('=', 1)[1]
                        break
                if fstab_root_uuid:
                    run_with_retry([
                        'mount', '-t', 'btrfs', '-o', 'subvol=@swap',
                        f'UUID={fstab_root_uuid}', str(swap_mount),
                    ])

            # Create swapfile
            run_with_retry(
                ['arch-chroot', str(chroot_dir),
                 'btrfs', 'filesystem', 'mkswapfile',
                 '--size', f'{ram_gib}g', '--uuid', 'clear', '/swap/swapfile'],
                max_retries=1, retry_delay=0,
                description='create btrfs swapfile',
            )
            run_with_retry(
                ['arch-chroot', str(chroot_dir), 'swapon', '/swap/swapfile'],
                max_retries=1, retry_delay=0,
                description='activate swapfile',
            )

            # Get resume_offset for the swapfile
            result = subprocess.run(
                ['arch-chroot', str(chroot_dir),
                 'btrfs', 'inspect-internal', 'map-swapfile', '-r', '/swap/swapfile'],
                capture_output=True, text=True,
            )
            resume_offset = result.stdout.strip()

            # Find the root (btrfs) partition UUID from the generated fstab
            root_uuid = None
            fstab_path = chroot_dir / 'etc' / 'fstab'
            for line in fstab_path.read_text().splitlines():
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == '/':
                    # Extract UUID from UUID=xxxx format
                    if parts[0].startswith('UUID='):
                        root_uuid = parts[0].split('=', 1)[1]
                    break

            # Add swap entry to fstab
            fstab_path = chroot_dir / 'etc' / 'fstab'
            with open(fstab_path, 'a') as f:
                f.write('\n# Swap for hibernation\n')
                f.write('/swap/swapfile none swap defaults 0 0\n')

            # Add resume parameters to kernel cmdline
            if root_uuid and resume_offset:
                cmdline_path = chroot_dir / 'etc' / 'kernel' / 'cmdline'
                if cmdline_path.exists():
                    cmdline = cmdline_path.read_text().strip()
                    cmdline += f' resume=UUID={root_uuid} resume_offset={resume_offset}'
                    # Disable zswap (conflicts with hibernation)
                    cmdline += ' zswap.enabled=0'
                    cmdline_path.write_text(cmdline + '\n')
                else:
                    _info(t('post.hibernation_cmdline_warning'))

            # Add 'resume' hook to mkinitcpio.conf (before fsck)
            mkinitcpio_path = chroot_dir / 'etc' / 'mkinitcpio.conf'
            if mkinitcpio_path.exists():
                content = mkinitcpio_path.read_text()
                new_content = content.replace('filesystems fsck', 'filesystems resume fsck')
                if new_content == content:
                    _info(t('post.hibernation_hook_warning'))
                else:
                    mkinitcpio_path.write_text(new_content)

            # Regenerate initramfs and UKI (picks up new cmdline + resume hook)
            run_with_retry(
                ['arch-chroot', str(chroot_dir), 'mkinitcpio', '-P'],
                max_retries=1, retry_delay=0,
                description='regenerate initramfs for hibernation',
            )

            # Enable NVIDIA sleep services if NVIDIA GPU is present.
            # Without these, nvidia_drm blocks the S4 power-off path (causing the
            # system to hang with keyboard backlight on) and GPU state is not properly
            # saved/restored (causing display freeze after suspend/hibernate resume).
            has_nvidia = any(v in ('nvidia_open', 'nvidia')
                            for v in gpu_vendors)
            if has_nvidia:
                nvidia_sleep_services = [
                    'nvidia-suspend',
                    'nvidia-hibernate',
                    'nvidia-resume',
                    'nvidia-suspend-then-hibernate',
                ]
                for svc in nvidia_sleep_services:
                    run_with_retry(
                        ['arch-chroot', str(chroot_dir),
                         'systemctl', 'enable', f'{svc}.service'],
                        max_retries=1, retry_delay=0,
                        description=f'enable {svc}.service',
                    )

            tracker.record('summary.step.hibernation', StepStatus.SUCCESS)
        else:
            tracker.record('summary.step.hibernation', StepStatus.SKIPPED)

        # Post-install: optionally remove CN git proxy (ghfast.top)
        # If proxy was set up AND user installed a clash-like proxy tool,
        # they likely don't need the GitHub mirror anymore.
        if country == 'CN':
            has_proxy_tool = bool(state and state.proxy_tool
                                 and state.proxy_tool in PROXY_TOOL_OPTIONS)
            result = tui.run(lambda: Confirmation(
                header=t('post.remove_git_proxy_prompt'),
                allow_skip=False,
                preset=has_proxy_tool,
            ).show())

            should_remove = (result.type_ == ResultType.Selection
                             and result.item() == MenuItem.yes())
            if should_remove:
                _remove_cn_git_proxy(chroot_dir)
                tracker.record('summary.step.remove_git_proxy', StepStatus.SUCCESS)
            else:
                tracker.record('summary.step.remove_git_proxy', StepStatus.SKIPPED)
        else:
            tracker.record('summary.step.remove_git_proxy', StepStatus.SKIPPED)

    finally:
        # Post-install: remove temporary NOPASSWD sudo rule
        if sudoers_aur is not None and sudoers_aur.exists():
            sudoers_aur.unlink()
            _debug('Removed temporary NOPASSWD sudoers rule')

    elapsed_time = time.monotonic() - start_time
    _info(f'Installation completed in {elapsed_time:.0f} seconds.')

    _print_summary(tracker)

    # Copy the installation log to the new system
    copy_log_to_target(chroot_dir)

    # Post-installation action
    action: PostInstallationAction = tui.run(lambda: select_post_installation(elapsed_time))
    match action:
        case PostInstallationAction.EXIT:
            pass
        case PostInstallationAction.REBOOT:
            subprocess.run(['reboot'], check=False)
        case PostInstallationAction.CHROOT:
            subprocess.run(['arch-chroot', str(chroot_dir)], check=False)
