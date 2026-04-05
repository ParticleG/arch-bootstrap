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
declare -a GPU_VENDOR_ORDER=(amd intel nvidia)

# lspci detection patterns per vendor
declare -A GPU_DETECT=(
    [amd]='VGA.*AMD|VGA.*ATI|Display.*AMD'
    [intel]='VGA.*Intel|Display.*Intel'
    [nvidia]='VGA.*NVIDIA|3D.*NVIDIA|Display.*NVIDIA'
)

# Human-readable labels for the checklist
declare -A GPU_LABELS=(
    [amd]="AMD (Radeon)"
    [intel]="Intel (HD/UHD/Arc)"
    [nvidia]="NVIDIA (GeForce/Quadro)"
)

# Packages per vendor (space-separated); "common" always included
declare -A GPU_PACKAGES=(
    [common]="mesa"
    [amd]="vulkan-radeon xf86-video-amdgpu xf86-video-ati"
    [intel]="intel-media-driver libva-intel-driver vulkan-intel"
    [nvidia]="dkms libva-nvidia-driver nvidia-open-dkms vulkan-nouveau xf86-video-nouveau"
)

# ─── Language Options (display|value) ───
declare -a LANG_OPTIONS=(
    "简体中文  zh_CN.UTF-8|zh_CN.UTF-8"
    "English   en_US.UTF-8|en_US.UTF-8"
    "日本語    ja_JP.UTF-8|ja_JP.UTF-8"
)
declare -a LANG_OPTIONS_TTY=(
    "Chinese   zh_CN.UTF-8|zh_CN.UTF-8"
    "English   en_US.UTF-8|en_US.UTF-8"
    "Japanese  ja_JP.UTF-8|ja_JP.UTF-8"
)

# ─── Network Backend Options (display|value) ───
declare -a NET_OPTIONS=(
    "NetworkManager + iwd  (推荐，更省电)|nm_iwd"
    "NetworkManager + wpa_supplicant  (传统)|nm"
)
declare -a NET_OPTIONS_TTY=(
    "NetworkManager + iwd  (recommended)|nm_iwd"
    "NetworkManager + wpa_supplicant  (legacy)|nm"
)

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

# ─── Fixed Summary Items (non-configurable, shown in confirm) ───
declare -a FIXED_SUMMARY_ITEMS=(
    "Boot|EFISTUB (UKI)"
    "FS|Btrfs + zstd + Snapper"
    "Audio|PipeWire"
    "BT|Enabled"
)
