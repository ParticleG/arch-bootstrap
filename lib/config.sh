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

# ─── Mirror Configuration ───
# Fallback mirrors per country (used when reflector is unavailable).
# URLs contain literal $repo/$arch — safe because they are always expanded
# MIRROR_COUNTRY is set at runtime by _detect_country() / _step_region().
MIRROR_COUNTRY=""

declare -a MIRRORS_CN=(
    'https://mirrors.ustc.edu.cn/archlinux/$repo/os/$arch'
    'https://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch'
    'https://mirrors.bfsu.edu.cn/archlinux/$repo/os/$arch'
    'https://mirrors.aliyun.com/archlinux/$repo/os/$arch'
    'https://mirrors.hit.edu.cn/archlinux/$repo/os/$arch'
    'https://mirrors.nju.edu.cn/archlinux/$repo/os/$arch'
    'https://mirrors.hust.edu.cn/archlinux/$repo/os/$arch'
    'https://mirrors.cqu.edu.cn/archlinux/$repo/os/$arch'
    'https://mirrors.xjtu.edu.cn/archlinux/$repo/os/$arch'
    'https://mirrors.jlu.edu.cn/archlinux/$repo/os/$arch'
    'https://mirrors.jcut.edu.cn/archlinux/$repo/os/$arch'
    'https://mirrors.qlu.edu.cn/archlinux/$repo/os/$arch'
)
declare -a MIRRORS_US=(
    'https://mirrors.kernel.org/archlinux/$repo/os/$arch'
    'https://mirror.rackspace.com/archlinux/$repo/os/$arch'
    'https://mirrors.rit.edu/archlinux/$repo/os/$arch'
    'https://mirrors.lug.mtu.edu/archlinux/$repo/os/$arch'
    'https://mirrors.mit.edu/archlinux/$repo/os/$arch'
)
declare -a MIRRORS_JP=(
    'https://ftp.jaist.ac.jp/pub/Linux/ArchLinux/$repo/os/$arch'
    'https://mirrors.cat.net/archlinux/$repo/os/$arch'
    'https://ftp.tsukuba.wide.ad.jp/Linux/archlinux/$repo/os/$arch'
)
declare -a MIRRORS_DE=(
    'https://mirror.f4st.host/archlinux/$repo/os/$arch'
    'https://ftp.fau.de/archlinux/$repo/os/$arch'
    'https://mirror.netcologne.de/archlinux/$repo/os/$arch'
)
# Worldwide fallback (used when country has no dedicated pool)
declare -a MIRRORS_WORLDWIDE=(
    'https://geo.mirror.pkgbuild.com/$repo/os/$arch'
    'https://mirror.rackspace.com/archlinux/$repo/os/$arch'
    'https://mirrors.kernel.org/archlinux/$repo/os/$arch'
)

# Active mirrors array — populated at runtime by _fetch_mirrors()
declare -a ACTIVE_MIRRORS=()

# ─── Country / Region Metadata ───
# ISO code → reflector country name (reflector uses English full names)
declare -A COUNTRY_REFLECTOR_NAME=(
    [CN]="China"  [US]="United States"  [JP]="Japan"
    [DE]="Germany"  [GB]="United Kingdom"  [FR]="France"
    [KR]="South Korea"  [AU]="Australia"  [CA]="Canada"
    [SG]="Singapore"  [TW]="Taiwan"  [HK]="Hong Kong"
    [SE]="Sweden"  [NL]="Netherlands"  [IN]="India"
    [BR]="Brazil"  [RU]="Russia"
)

# ISO code → default timezone
declare -A COUNTRY_TIMEZONE=(
    [CN]="Asia/Shanghai"  [US]="America/New_York"  [JP]="Asia/Tokyo"
    [DE]="Europe/Berlin"  [GB]="Europe/London"  [FR]="Europe/Paris"
    [KR]="Asia/Seoul"  [AU]="Australia/Sydney"  [CA]="America/Toronto"
    [SG]="Asia/Singapore"  [TW]="Asia/Taipei"  [HK]="Asia/Hong_Kong"
    [SE]="Europe/Stockholm"  [NL]="Europe/Amsterdam"  [IN]="Asia/Kolkata"
    [BR]="America/Sao_Paulo"  [RU]="Europe/Moscow"
)

# Countries shown in the region selection menu (ISO codes, display order)
declare -a REGION_MENU_COUNTRIES=(CN US JP DE GB FR KR AU CA SG TW HK)

# archlinuxcn repository URL (only added for CN users)
ARCHLINUXCN_URL='https://repo.archlinuxcn.org/$arch'

# ─── Fixed Summary Keys (non-configurable, shown in confirm) ───
# Labels come from i18n keys fixed.*, values are constant technical terms.
declare -a FIXED_SUMMARY_KEYS=(boot fs audio bt)
declare -A FIXED_SUMMARY_VALS=(
    [boot]="EFISTUB (UKI)"
    [fs]="Btrfs + zstd + Snapper"
    [audio]="PipeWire"
    [bt]="Enabled"
)
