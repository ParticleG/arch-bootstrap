from __future__ import annotations

# =============================================================================
# Constants
# =============================================================================

BASE_PACKAGES: list[str] = ['neovim', 'git', '7zip', 'base-devel', 'zsh']

# GPU driver configuration
GPU_VENDORS: list[str] = ['amd', 'intel', 'nvidia_open', 'nouveau']

GPU_DETECT_PATTERNS: dict[str, str] = {
    'amd': r'VGA.*AMD|VGA.*ATI|Display.*AMD',
    'intel': r'VGA.*Intel|Display.*Intel',
    'nvidia_open': r'VGA.*NVIDIA|3D.*NVIDIA|Display.*NVIDIA',
    'nouveau': r'VGA.*NVIDIA|3D.*NVIDIA|Display.*NVIDIA',
}

GPU_LABELS: dict[str, str] = {
    'amd': 'AMD (Radeon)',
    'intel': 'Intel (HD/UHD/Arc)',
    'nvidia_open': 'NVIDIA Proprietary (Turing+)',
    'nouveau': 'NVIDIA Nouveau (Open Source)',
}

GPU_PACKAGES: dict[str, list[str]] = {
    'common': ['mesa'],
    'amd': ['vulkan-radeon', 'xf86-video-amdgpu', 'xf86-video-ati'],
    'intel': ['intel-media-driver', 'libva-intel-driver', 'vulkan-intel'],
    'nvidia_open': ['nvidia-open-dkms', 'dkms', 'libva-nvidia-driver'],
    'nouveau': ['xf86-video-nouveau', 'vulkan-nouveau'],
}

# Language options
LANGUAGES: dict[str, str] = {
    'zh_CN.UTF-8': '简体中文',
    'en_US.UTF-8': 'English',
    'ja_JP.UTF-8': '日本語',
}

# Country/region metadata
COUNTRY_NAMES: dict[str, str] = {
    'CN': 'China',
    'US': 'United States',
    'JP': 'Japan',
    'DE': 'Germany',
    'GB': 'United Kingdom',
    'FR': 'France',
    'KR': 'South Korea',
    'AU': 'Australia',
    'CA': 'Canada',
    'SG': 'Singapore',
    'TW': 'Taiwan',
    'HK': 'Hong Kong',
    'SE': 'Sweden',
    'NL': 'Netherlands',
    'IN': 'India',
    'BR': 'Brazil',
    'RU': 'Russia',
}

COUNTRY_TIMEZONES: dict[str, str] = {
    'CN': 'Asia/Shanghai',
    'US': 'America/New_York',
    'JP': 'Asia/Tokyo',
    'DE': 'Europe/Berlin',
    'GB': 'Europe/London',
    'FR': 'Europe/Paris',
    'KR': 'Asia/Seoul',
    'AU': 'Australia/Sydney',
    'CA': 'America/Toronto',
    'SG': 'Asia/Singapore',
    'TW': 'Asia/Taipei',
    'HK': 'Asia/Hong_Kong',
    'SE': 'Europe/Stockholm',
    'NL': 'Europe/Amsterdam',
    'IN': 'Asia/Kolkata',
    'BR': 'America/Sao_Paulo',
    'RU': 'Europe/Moscow',
}

# Countries shown in the region selection menu (display order)
REGION_MENU_COUNTRIES: list[str] = [
    'CN', 'US', 'JP', 'DE', 'GB', 'FR', 'KR', 'AU', 'CA', 'SG', 'TW', 'HK',
]

ARCHLINUXCN_URL = 'https://repo.archlinuxcn.org/$arch'

# Fallback mirror pools (used when MirrorListHandler has no data for a region)
FALLBACK_MIRRORS: dict[str, list[str]] = {
    'CN': [
        'https://mirrors.ustc.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.bfsu.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.aliyun.com/archlinux/$repo/os/$arch',
        'https://mirrors.hit.edu.cn/archlinux/$repo/os/$arch',
        'https://mirror.nju.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.hust.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.cqu.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.xjtu.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.jlu.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.jcut.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.qlu.edu.cn/archlinux/$repo/os/$arch',
    ],
    'US': [
        'https://mirrors.kernel.org/archlinux/$repo/os/$arch',
        'https://mirror.rackspace.com/archlinux/$repo/os/$arch',
        'https://mirrors.rit.edu/archlinux/$repo/os/$arch',
        'https://mirror.mtu.edu/archlinux/$repo/os/$arch',
        'https://mirrors.mit.edu/archlinux/$repo/os/$arch',
    ],
    'JP': [
        'https://ftp.jaist.ac.jp/pub/Linux/ArchLinux/$repo/os/$arch',
        'https://mirrors.cat.net/archlinux/$repo/os/$arch',
        'https://ftp.tsukuba.wide.ad.jp/Linux/archlinux/$repo/os/$arch',
    ],
    'DE': [
        'https://mirror.f4st.host/archlinux/$repo/os/$arch',
        'https://ftp.fau.de/archlinux/$repo/os/$arch',
        'https://mirror.netcologne.de/archlinux/$repo/os/$arch',
    ],
    'Worldwide': [
        'https://geo.mirror.pkgbuild.com/$repo/os/$arch',
        'https://mirror.rackspace.com/archlinux/$repo/os/$arch',
    ],
}

# Network backend options
NETWORK_BACKENDS: dict[str, str] = {
    'nm_iwd': 'NetworkManager (iwd backend)',
    'nm': 'NetworkManager (default backend)',
}

# Geolocation endpoints (tried in order, 2s timeout each)
GEO_ENDPOINTS: list[str] = [
    'https://ifconfig.co/country-iso',
    'https://ipinfo.io/country',
    'https://api.country.is/',
]

# NVIDIA Turing+ threshold (PCI Device ID >= 0x1e00)
NVIDIA_TURING_THRESHOLD = 0x1E00

# =============================================================================
# kmscon font configuration
# =============================================================================

# Font options per locale prefix, ordered by recommendation
# Each entry: label (display), name (font-name in kmscon.conf), package (pacman)
KMSCON_FONT_OPTIONS: dict[str, list[dict[str, str]]] = {
    'zh_CN': [
        {'label': 'Noto Sans CJK SC', 'name': 'Noto Sans CJK SC', 'package': 'noto-fonts-cjk'},
        {'label': 'WenQuanYi Micro Hei', 'name': 'WenQuanYi Micro Hei', 'package': 'wqy-microhei'},
        {'label': 'Sarasa Gothic SC', 'name': 'Sarasa Gothic SC', 'package': 'ttf-sarasa-gothic'},
        {'label': 'Source Han Sans SC', 'name': 'Source Han Sans SC', 'package': 'adobe-source-han-sans-cn-fonts'},
    ],
    'ja_JP': [
        {'label': 'Noto Sans CJK JP', 'name': 'Noto Sans CJK JP', 'package': 'noto-fonts-cjk'},
        {'label': 'IPAex Gothic', 'name': 'IPAexGothic', 'package': 'otf-ipafont'},
        {'label': 'Source Han Sans JP', 'name': 'Source Han Sans JP', 'package': 'adobe-source-han-sans-jp-fonts'},
    ],
}

# Font size thresholds: (max_vertical_pixels, font_size)
# Evaluated in order; first match wins. Final entry is the fallback.
KMSCON_FONT_SIZE_THRESHOLDS: list[tuple[int, int]] = [
    (768, 14),    # 720p and below
    (1080, 18),   # 1080p
    (1440, 24),   # 1440p
    (2160, 32),   # 4K
    (99999, 40),  # 5K+ (fallback)
]

# Default font size when resolution detection fails (assumes 1080p)
KMSCON_DEFAULT_FONT_SIZE = 18
