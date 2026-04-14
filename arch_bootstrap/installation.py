from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import textwrap
import time
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

from .config import generate_fontconfig, generate_kmscon_config, get_kmscon_greetd_warning
from .constants import (
    ARCHLINUXCN_URL,
    BROWSER_OPTIONS,
    CLIPBOARD_WAYLAND_AUR_PACKAGES,
    CN_APP_OPTIONS,
    DEV_EDITOR_OPTIONS,
    DEV_ENVIRONMENT_OPTIONS,
    ELECTRON_WAYLAND_FLAGS,
    FCITX5_ENVIRONMENT,
    OMZ_INSTALL_URL,
    OMZ_REMOTE_GITHUB,
    PROXY_TOOL_OPTIONS,
    REFLECTOR_CONF,
    REMOTE_DESKTOP_OPTIONS,
    VM_OPTIONS,
)
from .detection import calculate_kmscon_font_size, needs_kmscon
from .i18n import t
from .log import copy_log_to_target
from .mirrors import format_cn_mirrorlist
from .utils import get_clone_url, install_github_proxy_dl, resolve_github_proxy, run_with_retry


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
    CERNET CDN is listed first (smart-routes to nearest edu mirror),
    followed by TUNA and USTC as fallbacks.
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

    Uses CERNET smart-routing CDN which redirects to the nearest Chinese
    educational mirror.  A temporary ``SigLevel = Never`` is used to
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
        if browser_info.get('aur', False):
            aur_packages.append(browser_info['package'])

    if not aur_packages:
        return

    pkg_str = ' '.join(shlex.quote(p) for p in aur_packages)
    _info(f'Installing AUR browsers: {", ".join(aur_packages)}')

    result = run_with_retry(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c',
         f'LANG=C.UTF-8 paru -S --noconfirm --needed --skipreview {pkg_str}'],
        description=f'AUR browsers: {", ".join(aur_packages)}',
        check=False,
    )
    if result.returncode != 0:
        _info(f'AUR browser installation failed (exit {result.returncode}), skipping')


# =============================================================================
# GPU passthrough script
# =============================================================================

_GPU_PASSTHROUGH_SCRIPT = """\
#!/usr/bin/env bash
# gpu-passthrough - Hot-switch GPU passthrough for KVM virtual machines
# Usage: gpu-passthrough {on|off|status}
#
# Automatically detects discrete GPU (NVIDIA or AMD) and manages:
# - Driver unbinding/rebinding
# - VFIO-PCI binding
# - Hugepage allocation/release

set -euo pipefail

# --- Auto-detection functions ---

detect_dgpu() {
    # Find discrete GPU (NVIDIA vendor 10de, AMD vendor 1002 on non-root PCI bus)
    local gpu_type=""
    local pci_addrs=()

    # Check for NVIDIA
    local nvidia_addrs
    nvidia_addrs=$(lspci -D -nn | grep -i '10de:' | grep -Ei 'VGA|3D|Display|Audio' | awk '{print $1}' || true)
    if [[ -n "$nvidia_addrs" ]]; then
        gpu_type="nvidia"
        while IFS= read -r addr; do
            pci_addrs+=("$addr")
        done <<< "$nvidia_addrs"
    fi

    # Check for AMD discrete (bus != 00, to exclude iGPU)
    if [[ -z "$gpu_type" ]]; then
        local amd_addrs
        amd_addrs=$(lspci -D -nn | grep -i '1002:' | grep -Ei 'VGA|3D|Display|Audio' | grep -v '^0000:00:' | awk '{print $1}' || true)
        if [[ -n "$amd_addrs" ]]; then
            gpu_type="amd"
            while IFS= read -r addr; do
                pci_addrs+=("$addr")
            done <<< "$amd_addrs"
        fi
    fi

    if [[ -z "$gpu_type" ]]; then
        echo "ERROR: No discrete GPU detected" >&2
        return 1
    fi

    echo "$gpu_type"
    printf '%s\\n' "${pci_addrs[@]}"
}

get_iommu_group_devices() {
    # Given a PCI address, find all devices in the same IOMMU group
    local pci_addr="$1"
    local iommu_group
    iommu_group=$(basename "$(readlink /sys/bus/pci/devices/"$pci_addr"/iommu_group)")

    for dev in /sys/kernel/iommu_groups/"$iommu_group"/devices/*; do
        basename "$dev"
    done
}

get_current_driver() {
    local pci_addr="$1"
    local driver_link="/sys/bus/pci/devices/$pci_addr/driver"
    if [[ -L "$driver_link" ]]; then
        basename "$(readlink "$driver_link")"
    else
        echo "none"
    fi
}

# --- Hugepage management ---

get_total_ram_gb() {
    awk '/MemTotal/ {printf "%d", $2 / 1024 / 1024}' /proc/meminfo
}

allocate_hugepages() {
    local total_ram_gb
    total_ram_gb=$(get_total_ram_gb)
    local vm_mem_gb=$(( total_ram_gb / 2 ))

    echo "Allocating hugepages for ${vm_mem_gb}GB VM memory..."

    # Flush caches and compact memory
    sync
    echo 3 > /proc/sys/vm/drop_caches
    echo 1 > /proc/sys/vm/compact_memory

    if (( total_ram_gb >= 32 )); then
        # Use 1GB hugepages
        local nr_pages=$vm_mem_gb
        echo "Using 1GB hugepages: ${nr_pages} pages"
        echo "$nr_pages" > /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages
        local actual
        actual=$(cat /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages)
        echo "Allocated: ${actual} x 1GB hugepages"
    else
        # Use 2MB hugepages
        local nr_pages=$(( vm_mem_gb * 1024 / 2 ))
        echo "Using 2MB hugepages: ${nr_pages} pages"
        sysctl -w vm.nr_hugepages="$nr_pages" > /dev/null
        local actual
        actual=$(cat /proc/sys/vm/nr_hugepages)
        echo "Allocated: ${actual} x 2MB hugepages"
    fi
}

release_hugepages() {
    local total_ram_gb
    total_ram_gb=$(get_total_ram_gb)

    echo "Releasing hugepages..."

    if (( total_ram_gb >= 32 )); then
        echo 0 > /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages
    fi
    sysctl -w vm.nr_hugepages=0 > /dev/null

    echo "Hugepages released"
}

# --- GPU passthrough control ---

passthrough_on() {
    echo "=== Enabling GPU passthrough ==="

    # Detect GPU
    local detection
    detection=$(detect_dgpu)
    local gpu_type
    gpu_type=$(echo "$detection" | head -1)
    local -a gpu_addrs
    mapfile -t gpu_addrs < <(echo "$detection" | tail -n +2)

    echo "Detected ${gpu_type} GPU at: ${gpu_addrs[*]}"

    # Collect ALL IOMMU group devices
    local -a all_devices=()
    local -A seen_devices=()
    for addr in "${gpu_addrs[@]}"; do
        while IFS= read -r dev; do
            if [[ -z "${seen_devices[$dev]:-}" ]]; then
                all_devices+=("$dev")
                seen_devices[$dev]=1
            fi
        done < <(get_iommu_group_devices "$addr")
    done

    echo "IOMMU group devices: ${all_devices[*]}"

    # Kill GPU processes and unload driver modules
    case "$gpu_type" in
        nvidia)
            echo "Killing NVIDIA processes..."
            fuser -k -9 /dev/nvidia* 2>/dev/null || true

            echo "Unloading NVIDIA modules..."
            for mod in nvidia_drm nvidia_modeset nvidia_uvm nvidia; do
                rmmod "$mod" 2>/dev/null || true
            done
            ;;
        amd)
            echo "Unloading AMD GPU module..."
            rmmod amdgpu 2>/dev/null || true
            ;;
    esac

    # Unbind all devices from current drivers
    echo "Unbinding devices from current drivers..."
    for dev in "${all_devices[@]}"; do
        local current_driver
        current_driver=$(get_current_driver "$dev")
        if [[ "$current_driver" != "none" && "$current_driver" != "vfio-pci" ]]; then
            echo "  Unbinding $dev from $current_driver"
            echo "$dev" > "/sys/bus/pci/drivers/$current_driver/unbind" 2>/dev/null || true
        fi
    done

    # Load vfio-pci and bind devices
    echo "Loading vfio-pci module..."
    modprobe vfio-pci

    echo "Binding devices to vfio-pci..."
    for dev in "${all_devices[@]}"; do
        echo "vfio-pci" > "/sys/bus/pci/devices/$dev/driver_override"
        echo "$dev" > /sys/bus/pci/drivers_probe
    done

    # Allocate hugepages
    allocate_hugepages

    echo "=== GPU passthrough enabled ==="
    echo "You can now start your VM with GPU passthrough."
}

passthrough_off() {
    echo "=== Disabling GPU passthrough ==="

    # Detect GPU type
    local detection
    detection=$(detect_dgpu 2>/dev/null) || true
    local gpu_type

    # If detection fails (GPU bound to vfio), try to determine from loaded modules
    if [[ -z "$detection" ]]; then
        # Check vfio-bound devices to determine GPU type
        for dev in /sys/bus/pci/drivers/vfio-pci/*/; do
            local pci_addr
            pci_addr=$(basename "$dev")
            local vendor
            vendor=$(cat "/sys/bus/pci/devices/$pci_addr/vendor" 2>/dev/null || echo "")
            case "$vendor" in
                0x10de) gpu_type="nvidia"; break ;;
                0x1002) gpu_type="amd"; break ;;
            esac
        done
    else
        gpu_type=$(echo "$detection" | head -1)
    fi

    if [[ -z "${gpu_type:-}" ]]; then
        echo "ERROR: Cannot determine GPU type" >&2
        return 1
    fi

    # Find all vfio-pci bound devices
    local -a vfio_devices=()
    for dev_path in /sys/bus/pci/drivers/vfio-pci/*/; do
        [[ -d "$dev_path" ]] || continue
        local pci_addr
        pci_addr=$(basename "$dev_path")
        # Only process GPU-related devices (vendor 10de or 1002)
        local vendor
        vendor=$(cat "/sys/bus/pci/devices/$pci_addr/vendor" 2>/dev/null || echo "")
        if [[ "$vendor" == "0x10de" || "$vendor" == "0x1002" ]]; then
            vfio_devices+=("$pci_addr")
        fi
    done

    # Clear driver overrides and unbind from vfio-pci
    echo "Unbinding devices from vfio-pci..."
    for dev in "${vfio_devices[@]}"; do
        echo "" > "/sys/bus/pci/devices/$dev/driver_override"
        echo "$dev" > /sys/bus/pci/drivers/vfio-pci/unbind 2>/dev/null || true
    done

    # Reload original driver
    case "$gpu_type" in
        nvidia)
            echo "Reloading NVIDIA modules..."
            modprobe nvidia
            modprobe nvidia_drm
            modprobe nvidia_modeset
            modprobe nvidia_uvm
            ;;
        amd)
            echo "Reloading AMD GPU module..."
            modprobe amdgpu
            ;;
    esac

    # Reprobe devices
    echo "Reprobing devices..."
    for dev in "${vfio_devices[@]}"; do
        echo "$dev" > /sys/bus/pci/drivers_probe 2>/dev/null || true
    done

    # Release hugepages
    release_hugepages

    echo "=== GPU passthrough disabled ==="
}

passthrough_status() {
    echo "=== GPU Passthrough Status ==="

    # Show GPU devices and their current drivers
    echo ""
    echo "GPU Devices:"
    lspci -D -nn -k | grep -A 2 -Ei 'VGA|3D|Display' | head -30

    echo ""
    echo "VFIO-PCI bound devices:"
    if [[ -d /sys/bus/pci/drivers/vfio-pci ]]; then
        for dev_path in /sys/bus/pci/drivers/vfio-pci/*/; do
            [[ -d "$dev_path" ]] || { echo "  (none)"; break; }
            local pci_addr
            pci_addr=$(basename "$dev_path")
            echo "  $pci_addr: $(lspci -s "${pci_addr#*:}" 2>/dev/null || echo 'unknown')"
        done
    else
        echo "  vfio-pci module not loaded"
    fi

    echo ""
    echo "Hugepages:"
    echo "  2MB: $(cat /proc/sys/vm/nr_hugepages) allocated"
    if [[ -f /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages ]]; then
        echo "  1GB: $(cat /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages) allocated"
    fi

    echo ""
    echo "Total RAM: $(get_total_ram_gb) GB"
}

# --- Main ---

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use sudo)" >&2
    exit 1
fi

case "${1:-}" in
    on)  passthrough_on ;;
    off) passthrough_off ;;
    status) passthrough_status ;;
    *)
        echo "Usage: gpu-passthrough {on|off|status}" >&2
        exit 1
        ;;
esac
"""


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

        users = None
        if config.auth_config:
            if config.auth_config.users:
                users = config.auth_config.users
                installation.create_users(config.auth_config.users)
                auth_handler.setup_auth(installation, config.auth_config, config.hostname)

        # Force English XDG user directories regardless of locale.
        # This runs xdg-user-dirs-update with LC_ALL=C so directories
        # like Downloads, Documents, Desktop stay in English, then
        # disables automatic updates to prevent locale changes from
        # renaming them on subsequent logins.
        if users:
            _info(t('post.xdg_user_dirs'))
            for user in users:
                xdg_cmd = (
                    'LC_ALL=C xdg-user-dirs-update --force'
                    ' && mkdir -p ~/.config'
                    ' && printf \'enabled=False\\n\' > ~/.config/user-dirs.conf'
                )
                subprocess.run(
                    ['arch-chroot', str(mountpoint),
                     'runuser', '-l', user.username, '-c', xdg_cmd],
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

        # Write login warning for minimal installs where kmscon is on tty1.
        # Users who later install greetd will see a reminder to move kmscon.
        if desktop_env not in ('dms', 'dms_manual', 'exo'):
            warning_dir = chroot_dir / 'etc' / 'profile.d'
            warning_dir.mkdir(parents=True, exist_ok=True)
            warning_file = warning_dir / 'kmscon-warning.sh'
            warning_file.write_text(get_kmscon_greetd_warning())
            _info('Written /etc/profile.d/kmscon-warning.sh (kmscon on tty1)')

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

    # Post-install: copy WiFi connections from live ISO
    _copy_wifi_connections(chroot_dir)

    # Post-install: CN-specific setup (git proxy + archlinuxcn repo)
    if country == 'CN':
        _setup_cn_git_proxy(chroot_dir)
        _setup_archlinuxcn(chroot_dir)

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

        # Post-install: clipboard Wayland AUR packages
        if has_paru and desktop_env != 'minimal' and username:
            _info(t('post.clipboard'))
            aur_cmd = f"LANG=C.UTF-8 paru -S --noconfirm --needed --skipreview {' '.join(CLIPBOARD_WAYLAND_AUR_PACKAGES)}"
            run_with_retry(
                ['arch-chroot', str(chroot_dir), 'runuser', '-l', username, '-c', aur_cmd],
                max_retries=3, retry_delay=5,
                description='clipboard AUR packages',
            )

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
            except subprocess.TimeoutExpired:
                _debug('oh-my-zsh installation timed out after 120s, skipping')

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
                gpu_vendors=gpu_vendors,
            )

        # Post-install: DMS Manual desktop environment
        if desktop_env == 'dms_manual' and username:
            from .dms_manual import install_dms_manual
            _info('Setting up DMS Manual desktop environment...')
            install_dms_manual(
                chroot_dir=chroot_dir,
                username=username,
                compositor=dms_compositor,
                terminal=dms_terminal,
                country=country,
                gpu_vendors=gpu_vendors,
            )

        # Post-install: Exo desktop environment
        if desktop_env == 'exo' and username:
            from .exo import install_exo
            _info('Setting up Exo desktop environment...')
            install_exo(
                chroot_dir=chroot_dir,
                username=username,
                country=country,
                gpu_vendors=gpu_vendors,
            )

        # Post-install: AUR browsers (requires paru)
        if has_paru and browsers:
            _install_aur_browsers(chroot_dir, username, browsers)

        # Post-install: Electron / VS Code Wayland flags
        if desktop_env != 'minimal' and username:
            _info(t('post.electron_flags'))
            home = f'/home/{username}'
            config_dir = str(chroot_dir / 'home' / username / '.config')
            os.makedirs(config_dir, exist_ok=True)
            flag_files: list[str] = []
            # electron-flags.conf: always for non-minimal (catches generic electron apps)
            electron_path = os.path.join(config_dir, 'electron-flags.conf')
            with open(electron_path, 'w') as f:
                f.write(ELECTRON_WAYLAND_FLAGS)
            flag_files.append(f'{home}/.config/electron-flags.conf')
            # code-flags.conf: only when VS Code is selected
            if 'vscode' in state.dev_editors:
                code_path = os.path.join(config_dir, 'code-flags.conf')
                with open(code_path, 'w') as f:
                    f.write(ELECTRON_WAYLAND_FLAGS)
                flag_files.append(f'{home}/.config/code-flags.conf')
            # qq-flags.conf: only when QQ is selected
            if 'linuxqq-nt-bwrap' in state.cn_apps:
                qq_path = os.path.join(config_dir, 'qq-flags.conf')
                with open(qq_path, 'w') as f:
                    f.write(ELECTRON_WAYLAND_FLAGS)
                flag_files.append(f'{home}/.config/qq-flags.conf')
            # Fix ownership
            run_with_retry(
                ['arch-chroot', str(chroot_dir),
                 'chown', '-R', f'{username}:{username}'] + flag_files,
                max_retries=1, retry_delay=0,
                description='fix electron flags ownership',
            )

        # Post-install: fcitx5 input method environment variables
        if state.input_methods:
            _info(t('post.input_method'))
            env_file = f'{chroot_dir}/etc/environment'
            with open(env_file, 'a') as f:
                for key, value in FCITX5_ENVIRONMENT.items():
                    f.write(f'{key}={value}\n')

            # Write per-toolkit GTK IM config for XWayland apps.
            # GTK_IM_MODULE is not set globally (Wayland apps use
            # text-input-v3 natively); these files only affect
            # GTK2/3 apps running under XWayland.
            if username:
                # Create GTK IM config files as the user (not root)
                gtk_im_cmd = (
                    'printf \'gtk-im-module="fcitx"\\n\' >> ~/.gtkrc-2.0'
                    ' && mkdir -p ~/.config/gtk-3.0'
                    ' && printf \'[Settings]\\ngtk-im-module=fcitx\\n\' >> ~/.config/gtk-3.0/settings.ini'
                    ' && mkdir -p ~/.config/gtk-4.0'
                    ' && printf \'[Settings]\\ngtk-im-module=fcitx\\n\' >> ~/.config/gtk-4.0/settings.ini'
                )
                subprocess.run(
                    ['arch-chroot', str(chroot_dir),
                     'runuser', '-l', username, '-c', gtk_im_cmd],
                    check=False,
                )

        # Post-install: additional AUR/archlinuxcn packages (remote desktop, proxy, dev editors)
        aur_packages: list[str] = []

        for rd_key in state.remote_desktop:
            if rd_key in REMOTE_DESKTOP_OPTIONS and REMOTE_DESKTOP_OPTIONS[rd_key].get('aur', False):
                aur_packages.extend(REMOTE_DESKTOP_OPTIONS[rd_key]['packages'])

        # Proxy tools are installed here (both AUR and archlinuxcn) since
        # archlinuxcn repo and paru are already configured at this point.
        if state.proxy_tool and state.proxy_tool in PROXY_TOOL_OPTIONS:
            opt = PROXY_TOOL_OPTIONS[state.proxy_tool]
            aur_packages.extend(opt['packages'])

        for de_key in state.dev_editors:
            if de_key in DEV_EDITOR_OPTIONS and DEV_EDITOR_OPTIONS[de_key].get('aur', False):
                aur_packages.extend(DEV_EDITOR_OPTIONS[de_key]['packages'])

        # CN communication apps (all AUR)
        if state and state.cn_apps:
            for app_key in state.cn_apps:
                app = CN_APP_OPTIONS.get(app_key)
                if app and app.get('aur'):
                    aur_packages.extend(app['packages'])

        # VM AUR packages (looking_glass)
        for vm_key in state.vm_options:
            if vm_key in VM_OPTIONS:
                for pkg in VM_OPTIONS[vm_key].get('aur_packages', []):
                    if pkg not in aur_packages:
                        aur_packages.append(pkg)

        if has_paru and aur_packages and username:
            aur_cmd = f"LANG=C.UTF-8 paru -S --noconfirm --needed --skipreview {' '.join(aur_packages)}"
            run_with_retry(
                ['arch-chroot', str(chroot_dir), 'runuser', '-l', username, '-c', aur_cmd],
                max_retries=3, retry_delay=5,
                description='additional AUR packages',
            )

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

        # Post-install: VM services
        for vm_key in state.vm_options:
            if vm_key in VM_OPTIONS:
                for service in VM_OPTIONS[vm_key].get('services', []):
                    run_with_retry(
                        ['arch-chroot', str(chroot_dir), 'systemctl', 'enable', service],
                        description=f'enable {service}',
                    )

        # Post-install: VM user groups
        if state.vm_options:
            run_with_retry(
                ['arch-chroot', str(chroot_dir), 'usermod', '-a', '-G', 'libvirt,kvm', username],
                description='add user to libvirt and kvm groups',
            )

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
            gpu_script_dir = chroot_dir / 'usr' / 'local' / 'bin'
            gpu_script_dir.mkdir(parents=True, exist_ok=True)
            gpu_script = gpu_script_dir / 'gpu-passthrough'
            gpu_script.write_text(_GPU_PASSTHROUGH_SCRIPT)
            gpu_script.chmod(0o755)

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

        # Post-install: enable clipboard sync service
        if desktop_env != 'minimal' and username:
            _info(t('post.clipsync'))
            run_with_retry(
                ['arch-chroot', str(chroot_dir),
                 'systemctl', '--global', 'enable', 'clipsync'],
                max_retries=1, retry_delay=0,
                description='enable clipsync service',
            )

        # Post-install: enable snapper timers for btrfs snapshots
        _info(t('post.snapper_timers'))
        for timer in ('snapper-timeline.timer', 'snapper-cleanup.timer', 'snapper-boot.timer'):
            run_with_retry(
                ['arch-chroot', str(chroot_dir), 'systemctl', 'enable', timer],
                max_retries=1, retry_delay=0,
                description=f'enable {timer}',
            )

        # Post-install: enable GNOME Keyring sockets (user-level)
        if state and state.keyring == 'gnome':
            _info(t('post.gnome_keyring'))
            run_with_retry(
                ['arch-chroot', str(chroot_dir),
                 'systemctl', '--global', 'enable', 'gnome-keyring-daemon.socket'],
                max_retries=1, retry_delay=0,
                description='enable gnome-keyring-daemon.socket',
            )
            run_with_retry(
                ['arch-chroot', str(chroot_dir),
                 'systemctl', '--global', 'enable', 'p11-kit-server.socket'],
                max_retries=1, retry_delay=0,
                description='enable p11-kit-server.socket',
            )

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

    finally:
        # Post-install: remove temporary NOPASSWD sudo rule
        if sudoers_aur is not None and sudoers_aur.exists():
            sudoers_aur.unlink()
            _debug('Removed temporary NOPASSWD sudoers rule')

    elapsed_time = time.monotonic() - start_time
    _info(f'Installation completed in {elapsed_time:.0f} seconds.')

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
