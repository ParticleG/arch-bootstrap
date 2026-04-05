#!/bin/bash
# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║  config.sh — Pure data declarations for archinstall configuration            ║
# ║  No logic, no side effects — only arrays and associative arrays              ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

# Guard against double-sourcing (arrays would be reset, losing runtime overrides)
[[ -n "${_CONFIG_LOADED:-}" ]] && return 0
declare -r _CONFIG_LOADED=1

# ─── Base Packages (always installed) ───
declare -a BASE_PACKAGES=(neovim git 7zip base-devel zsh)

# ─── GPU Driver Configuration ───
# Vendor order determines checklist display order
declare -a GPU_VENDOR_ORDER=(amd intel nvidia_open nouveau)

# lspci detection patterns per vendor
declare -A GPU_DETECT=(
    [amd]='VGA.*AMD|VGA.*ATI|Display.*AMD'
    [intel]='VGA.*Intel|Display.*Intel'
    [nvidia_open]='VGA.*NVIDIA|3D.*NVIDIA|Display.*NVIDIA'
    [nouveau]='VGA.*NVIDIA|3D.*NVIDIA|Display.*NVIDIA'
)

# Human-readable labels for the checklist
declare -A GPU_LABELS=(
    [amd]="AMD (Radeon)"
    [intel]="Intel (HD/UHD/Arc)"
    [nvidia_open]="NVIDIA Proprietary (Turing+)"
    [nouveau]="NVIDIA Nouveau (Open Source)"
)

# Packages per vendor (space-separated); "common" always included
declare -A GPU_PACKAGES=(
    [common]="mesa"
    [amd]="vulkan-radeon xf86-video-amdgpu xf86-video-ati"
    [intel]="intel-media-driver libva-intel-driver vulkan-intel"
    [nvidia_open]="nvidia-open-dkms dkms libva-nvidia-driver"
    [nouveau]="xf86-video-nouveau vulkan-nouveau"
)

# ─── Language Option Values (labels come from i18n keys opt.lang.*) ───
declare -a LANG_VALUES=("zh_CN.UTF-8" "en_US.UTF-8" "ja_JP.UTF-8")

# ─── Network Backend Option Values (labels come from i18n keys opt.net.*) ───
declare -a NET_VALUES=("nm_iwd" "nm")

# ─── China Mirror URLs ───
# Note: \$ keeps literal $ in unquoted heredocs
declare -a CHINA_MIRRORS=(
    'https://mirrors.ustc.edu.cn/archlinux/\$repo/os/\$arch'
    'https://mirrors.tuna.tsinghua.edu.cn/archlinux/\$repo/os/\$arch'
    'https://mirrors.bfsu.edu.cn/archlinux/\$repo/os/\$arch'
    'https://mirrors.aliyun.com/archlinux/\$repo/os/\$arch'
    'https://mirrors.hit.edu.cn/archlinux/\$repo/os/\$arch'
    'https://mirrors.nju.edu.cn/archlinux/\$repo/os/\$arch'
    'https://mirrors.hust.edu.cn/archlinux/\$repo/os/\$arch'
    'https://mirrors.cqu.edu.cn/archlinux/\$repo/os/\$arch'
    'https://mirrors.xjtu.edu.cn/archlinux/\$repo/os/\$arch'
    'https://mirrors.jlu.edu.cn/archlinux/\$repo/os/\$arch'
    'https://mirrors.jcut.edu.cn/archlinux/\$repo/os/\$arch'
    'https://mirrors.qlu.edu.cn/archlinux/\$repo/os/\$arch'
)

# archlinuxcn repository URL
ARCHLINUXCN_URL='https://repo.archlinuxcn.org/\$arch'

# ─── Fixed Summary Keys (non-configurable, shown in confirm) ───
# Labels come from i18n keys fixed.*, values are constant technical terms.
declare -a FIXED_SUMMARY_KEYS=(boot fs audio bt)
declare -A FIXED_SUMMARY_VALS=(
    [boot]="EFISTUB (UKI)"
    [fs]="Btrfs + zstd + Snapper"
    [audio]="PipeWire"
    [bt]="Enabled"
)
