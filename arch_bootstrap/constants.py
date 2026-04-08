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

# oh-my-zsh
OMZ_INSTALL_URL = 'https://install.ohmyz.sh'
OMZ_REMOTE_GITHUB = 'https://github.com/ohmyzsh/ohmyzsh.git'

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

# =============================================================================
# Fontconfig: CJK font alias mappings
# =============================================================================

# Common CJK font names that should be aliased to the user-selected font.
# When these fonts are requested but not installed, fontconfig will substitute
# the selected CJK font instead of falling back to a random glyph provider.
FONTCONFIG_CJK_ALIASES: dict[str, list[str]] = {
    'zh': [
        'WenQuanYi Zen Hei',
        'WenQuanYi Micro Hei',
        'WenQuanYi Micro Hei Light',
        'Microsoft YaHei',
        'SimHei',
        'SimSun',
        'SimSun-18030',
        'FangSong',
        'KaiTi',
    ],
    'ja': [
        'MS Gothic',
        'MS PGothic',
        'MS Mincho',
        'MS PMincho',
        'Yu Gothic',
        'Yu Mincho',
        'Meiryo',
    ],
}

# ---------------------------------------------------------------------------
# DMS (DankMaterialShell) desktop environment
# ---------------------------------------------------------------------------

# Version marker — CI automation compares this against dankinstall releases
DMS_SYNCED_VERSION = 'v1.4.4'

# Pacman packages grouped by component
DMS_SYSTEM_PACKAGES: dict[str, list[str]] = {
    'common': [
        'dms-shell',
        'git',
        'greetd',
        'xdg-desktop-portal-gtk',
        'accountsservice',
        'matugen',
        'dgop',
    ],
    'niri': ['niri', 'xwayland-satellite'],
    'hyprland': ['hyprland', 'jq'],
    'ghostty': ['ghostty'],
    'kitty': ['kitty'],
    'alacritty': ['alacritty'],
}

# AUR packages (built via makepkg in chroot)
# Note: quickshell-git is NOT listed here — it is automatically pulled in
# as a dependency of dms-shell (which depends on the virtual package
# "quickshell", currently provided only by quickshell-git).
DMS_AUR_PACKAGES: dict[str, list[str]] = {
    'common': [],
    'greeter': ['greetd-dms-greeter-git'],
}

# GitHub raw base URL for configuration templates
DMS_TEMPLATE_BASE_URL = (
    'https://raw.githubusercontent.com/AvengeMedia/DankMaterialShell'
    '/master/core/internal/config/embedded'
)

# GitHub proxy constants (reused from install.py pattern)
GHPROXY_CHUNK_URL = 'https://ghproxy.link/js/src_views_home_HomeView_vue.js'
GHPROXY_FALLBACK = 'https://ghfast.top'

# Template files to download, keyed by compositor/terminal
# Values are (relative_path_in_embedded, deploy_target_relative_to_home)
DMS_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    'niri': [
        ('niri.kdl', '.config/niri/config.kdl'),
        ('niri-colors.kdl', '.config/niri/dms/colors.kdl'),
        ('niri-layout.kdl', '.config/niri/dms/layout.kdl'),
        ('niri-alttab.kdl', '.config/niri/dms/alttab.kdl'),
        ('niri-binds.kdl', '.config/niri/dms/binds.kdl'),
    ],
    'hyprland': [
        ('hyprland.conf', '.config/hypr/hyprland.conf'),
        ('hypr-colors.conf', '.config/hypr/dms/colors.conf'),
        ('hypr-layout.conf', '.config/hypr/dms/layout.conf'),
        ('hypr-binds.conf', '.config/hypr/dms/binds.conf'),
    ],
    'ghostty': [
        ('ghostty.conf', '.config/ghostty/config'),
        ('ghostty-colors.conf', '.config/ghostty/themes/dankcolors'),
    ],
    'kitty': [
        ('kitty.conf', '.config/kitty/kitty.conf'),
        ('kitty-tabs.conf', '.config/kitty/dank-tabs.conf'),
        ('kitty-theme.conf', '.config/kitty/dank-theme.conf'),
    ],
    'alacritty': [
        ('alacritty.toml', '.config/alacritty/alacritty.toml'),
        ('alacritty-theme.toml', '.config/alacritty/dank-theme.toml'),
    ],
}

# Placeholder config files to create (empty, for user customization)
DMS_PLACEHOLDER_FILES: dict[str, list[str]] = {
    'niri': [
        '.config/niri/dms/outputs.kdl',
        '.config/niri/dms/cursor.kdl',
    ],
    'hyprland': [
        '.config/hypr/dms/outputs.conf',
        '.config/hypr/dms/cursor.conf',
    ],
}

# systemd user service symlink targets
DMS_SYSTEMD_TARGETS: dict[str, tuple[str, str]] = {
    # compositor: (wants_dir_relative, service_unit_path)
    'niri': (
        '.config/systemd/user/niri.service.wants',
        '/usr/lib/systemd/user/dms.service',
    ),
    'hyprland': (
        '.config/systemd/user/hyprland-session.target.wants',
        '/usr/lib/systemd/user/dms.service',
    ),
}

# greetd config — written to /etc/greetd/config.toml
# The greeter runs as the "greeter" user (created by the greetd package)
# and launches dms-greeter which handles authentication and session start.
DMS_GREETD_CONFIG = """\
[terminal]
vt = 1

[default_session]
user = "greeter"
command = "/usr/bin/dms-greeter --command {compositor}"
"""
