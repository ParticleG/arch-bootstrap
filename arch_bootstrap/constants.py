from __future__ import annotations

# =============================================================================
# Constants
# =============================================================================

BASE_PACKAGES: list[str] = [
    '7zip',
    'base-devel',
    'neovim',
    'git',
    'openssh',
    'zsh'
]

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
    'common': ['mesa', 'vulkan-icd-loader'],
    'amd': ['lib32-mesa', 'lib32-vulkan-radeon', 'vulkan-radeon'],
    'intel': ['intel-media-driver', 'lib32-mesa', 'lib32-vulkan-intel', 'libva-intel-driver', 'linux-firmware-intel', 'vulkan-intel'],
    'nvidia_open': ['dkms', 'egl-wayland', 'lib32-nvidia-utils', 'libva-nvidia-driver', 'linux-headers', 'nvidia-open-dkms', 'nvidia-settings', 'nvidia-utils'],
    'nouveau': ['lib32-mesa', 'lib32-vulkan-nouveau', 'vulkan-nouveau'],
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

# CERNET smart-routing CDN — automatically redirects to the nearest Chinese
# educational mirror, effectively acting as a built-in mirror pool.
ARCHLINUXCN_URL = 'https://mirrors.cernet.edu.cn/archlinuxcn/$arch'

# Hardcoded official Arch mirrors for CN — bypasses archinstall's mirror
# speed-testing entirely.  CERNET CDN first (smart-routes to nearest edu
# mirror), with TUNA and USTC as fallbacks.
CN_OFFICIAL_MIRRORS: list[str] = [
    'https://mirrors.cernet.edu.cn/archlinux/$repo/os/$arch',  # CERNET smart CDN
    'https://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch',  # Tsinghua TUNA
    'https://mirrors.ustc.edu.cn/archlinux/$repo/os/$arch',  # USTC
]

# oh-my-zsh
OMZ_INSTALL_URL = 'https://install.ohmyz.sh'
OMZ_REMOTE_GITHUB = 'https://github.com/ohmyzsh/ohmyzsh.git'

# Fallback mirror pools (used when MirrorListHandler has no data for a region)
# NOTE: For CN region, CN_OFFICIAL_MIRRORS is used directly by
# format_cn_mirrorlist() and both call sites short-circuit before reaching
# FALLBACK_MIRRORS['CN'].  This CN fallback list is only retained for
# build_mirror_config() compatibility, which populates config.mirror_config
# for the optional_repositories path.
FALLBACK_MIRRORS: dict[str, list[str]] = {
    'CN': [
        'https://mirrors.cernet.edu.cn/archlinux/$repo/os/$arch',
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

# dankinstall is downloaded from this GitHub releases base URL.
# Currently using ParticleG's fork which adds headless CLI support.
# Once upstream merges the PR, switch to AvengeMedia/DankMaterialShell.
DANKINSTALL_RELEASE_BASE = (
    'https://github.com/ParticleG/DankMaterialShell'
    '/releases/latest/download'
)

# GitHub proxy constants (reused from install.py pattern)
GHPROXY_CHUNK_URL = 'https://ghproxy.link/js/src_views_home_HomeView_vue.js'
GHPROXY_FALLBACK = 'https://ghfast.top'

# ---------------------------------------------------------------------------
# Exo desktop shell (Material Design 3 for Niri)
# ---------------------------------------------------------------------------

EXO_REPO_URL = 'https://github.com/debuggyo/Exo.git'

# Essential AUR packages for Exo desktop
EXO_AUR_PACKAGES: list[str] = [
    'python-ignis-git',
    'ignis-gvc',
    'ttf-material-symbols-variable-git',
    'matugen-bin',
    'swww',
    'gnome-bluetooth-3.0',
    'adw-gtk-theme',
    'dart-sass',
]

# Packages installed alongside Exo (compositor, greetd, utils)
EXO_SYSTEM_PACKAGES: list[str] = [
    'niri',
    'xdg-desktop-portal-gnome',
    'xwayland-satellite',
    'greetd',
    'kitty',
    'nautilus',
    'playerctl',
    'brightnessctl',
]

# ---------------------------------------------------------------------------
# DMS Manual installation (without dankinstall binary)
# ---------------------------------------------------------------------------

# DMS Manual installation packages
DMS_MANUAL_PREREQ_PACKAGES: list[str] = []

DMS_MANUAL_AUR_PACKAGES: list[str] = [
    'greetd-dms-greeter-git',
]

DMS_MANUAL_SYSTEM_PACKAGES: list[str] = [
    'quickshell', 'greetd', 'xdg-desktop-portal-gtk',
    'accountsservice', 'matugen',
    'dgop', 'cava', 'cups-pk-helper', 'kimageformats',
    'libavif', 'libheif', 'libjxl', 'qt6ct',
]

DMS_MANUAL_COMPOSITOR_PACKAGES: dict[str, list[str]] = {
    'niri': ['niri', 'xwayland-satellite', 'dms-shell-niri'],
    'hyprland': ['hyprland', 'dms-shell-hyprland'],
}

DMS_MANUAL_TERMINAL_PACKAGES: dict[str, str] = {
    'ghostty': 'ghostty',
    'kitty': 'kitty',
    'alacritty': 'alacritty',
}

# ---------------------------------------------------------------------------
# Browser options
# ---------------------------------------------------------------------------

# Browser packages available for installation.
# key: internal identifier, package: pacman/AUR package name, aur: True if AUR
BROWSER_OPTIONS: dict[str, dict] = {
    'firefox': {'label': 'Firefox', 'package': 'firefox', 'aur': False},
    'chromium': {'label': 'Chromium', 'package': 'chromium', 'aur': False},
    'chrome': {'label': 'Google Chrome (AUR)', 'package': 'google-chrome', 'aur': True},
    'edge': {'label': 'Microsoft Edge (AUR)', 'package': 'microsoft-edge-stable-bin', 'aur': True},
}

# ---------------------------------------------------------------------------
# Clipboard tools
# ---------------------------------------------------------------------------

CLIPBOARD_PACKAGES: list[str] = ['cliphist', 'xclip']
CLIPBOARD_WAYLAND_PACKAGES: list[str] = ['wl-clipboard']
CLIPBOARD_WAYLAND_AUR_PACKAGES: list[str] = ['comalot-clipsync-git']

# ---------------------------------------------------------------------------
# Terminal enhancement (always installed)
# ---------------------------------------------------------------------------

TERMINAL_ENHANCEMENT_PACKAGES: list[str] = ['fastfetch', 'fzf']

# ---------------------------------------------------------------------------
# Input method options
# ---------------------------------------------------------------------------

INPUT_METHOD_PACKAGES: dict[str, dict] = {
    'fcitx5_zh': {
        'label': 'Fcitx5 (Chinese)',
        'packages': ['fcitx5', 'fcitx5-chinese-addons', 'fcitx5-configtool'],
        'aur': False,
    },
    'fcitx5_ja_mozc': {
        'label': 'Fcitx5 + Mozc (Japanese, recommended)',
        'packages': ['fcitx5', 'fcitx5-mozc', 'fcitx5-configtool'],
        'aur': False,
    },
    'fcitx5_ja_anthy': {
        'label': 'Fcitx5 + Anthy (Japanese)',
        'packages': ['fcitx5', 'fcitx5-anthy', 'fcitx5-configtool'],
        'aur': False,
    },
}

FCITX5_ENVIRONMENT: dict[str, str] = {
    'XMODIFIERS': '@im=fcitx',
    'QT_IM_MODULE': 'fcitx',
    'QT_IM_MODULES': 'wayland;fcitx',
    # GTK_IM_MODULE is intentionally not set globally: on Wayland,
    # Gtk3/4 use text-input-v3 natively. For XWayland Gtk2/3 apps,
    # per-toolkit config files are written instead (see installation.py).
    # QT_IM_MODULE is still needed because wlroots-based compositors
    # (niri, hyprland, sway) do not support text-input-v2 used by Qt5.
    # QT_IM_MODULES provides a fallback chain for Qt 6.7+.
    # Reference: https://fcitx-im.org/wiki/Using_Fcitx_5_on_Wayland
}

# ---------------------------------------------------------------------------
# Font options
# ---------------------------------------------------------------------------

BASE_FONT_OPTIONS: dict[str, dict] = {
    'noto': {
        'label': 'Noto Fonts + Emoji (recommended)',
        'packages': ['noto-fonts', 'noto-fonts-emoji'],
    },
    'liberation': {
        'label': 'Liberation Fonts',
        'packages': ['ttf-liberation'],
    },
    'dejavu': {
        'label': 'DejaVu Fonts',
        'packages': ['ttf-dejavu'],
    },
}

NERD_FONT_OPTIONS: dict[str, dict] = {
    'jetbrains-mono': {
        'label': 'JetBrains Mono Nerd Font (recommended)',
        'packages': ['ttf-jetbrains-mono-nerd'],
    },
    'firacode': {
        'label': 'Fira Code Nerd Font',
        'packages': ['ttf-firacode-nerd'],
    },
    'hack': {
        'label': 'Hack Nerd Font',
        'packages': ['ttf-hack-nerd'],
    },
}

# ---------------------------------------------------------------------------
# Audio firmware
# ---------------------------------------------------------------------------

AUDIO_FIRMWARE_OPTIONS: dict[str, dict] = {
    'sof': {
        'label': 'SOF Firmware (Intel, recommended for modern laptops)',
        'packages': ['sof-firmware'],
    },
    'alsa': {
        'label': 'ALSA Firmware (older devices)',
        'packages': ['alsa-firmware'],
    },
}

AUDIO_DETECT_PATTERNS: dict[str, list[str]] = {
    'sof': ['sof', 'Sound Open Firmware'],
    'alsa': ['HDA', 'Realtek', 'Conexant'],
}

# ---------------------------------------------------------------------------
# Polkit agent options
# ---------------------------------------------------------------------------

POLKIT_AGENT_OPTIONS: dict[str, dict] = {
    'mate': {
        'label': 'MATE Polkit Agent (recommended)',
        'packages': ['mate-polkit'],
    },
    'gnome': {
        'label': 'GNOME Polkit Agent',
        'packages': ['polkit-gnome'],
    },
}

# ---------------------------------------------------------------------------
# Keyring options
# ---------------------------------------------------------------------------

KEYRING_OPTIONS: dict[str, dict] = {
    'gnome': {
        'label': 'GNOME Keyring (recommended)',
        'packages': ['gnome-keyring'],
    },
    'kwallet': {
        'label': 'KWallet (KDE)',
        'packages': ['kwallet'],
    },
}

# ---------------------------------------------------------------------------
# Remote desktop options
# ---------------------------------------------------------------------------

REMOTE_DESKTOP_OPTIONS: dict[str, dict] = {
    'remmina': {
        'label': 'Remmina + FreeRDP',
        'packages': ['remmina', 'freerdp'],
        'aur': False,
    },
    'parsec': {
        'label': 'Parsec (AUR)',
        'packages': ['parsec-bin'],
        'aur': True,
    },
    'moonlight': {
        'label': 'Moonlight',
        'packages': ['moonlight-qt'],
        'aur': False,
    },
    'rustdesk': {
        'label': 'RustDesk (AUR)',
        'packages': ['rustdesk'],
        'aur': True,
    },
}

# ---------------------------------------------------------------------------
# File manager options
# ---------------------------------------------------------------------------

FILE_MANAGER_OPTIONS: dict[str, dict] = {
    'yazi': {
        'label': 'Yazi (terminal)',
        'packages': ['yazi'],
        'aur': False,
    },
    'nautilus': {
        'label': 'Nautilus (GNOME)',
        'packages': ['nautilus'],
        'aur': False,
    },
    'dolphin': {
        'label': 'Dolphin (KDE)',
        'packages': ['dolphin'],
        'aur': False,
    },
    'thunar': {
        'label': 'Thunar (XFCE)',
        'packages': ['thunar'],
        'aur': False,
    },
}

# ---------------------------------------------------------------------------
# Proxy tool options (CN region)
# ---------------------------------------------------------------------------

CN_APP_OPTIONS: dict[str, dict] = {
    'linuxqq-nt-bwrap': {
        'label': 'QQ',
        'packages': ['linuxqq-nt-bwrap'],
        'aur': True,
    },
    'wechat': {
        'label': 'WeChat',
        'packages': ['wechat-universal-bwrap'],
        'aur': True,
    },
    'feishu': {
        'label': 'Feishu / Lark',
        'packages': ['feishu-bin'],
        'aur': True,
    },
    'dingtalk': {
        'label': 'DingTalk',
        'packages': ['dingtalk-bin'],
        'aur': True,
    },
}

PROXY_TOOL_OPTIONS: dict[str, dict] = {
    'flclash': {
        'label': 'FlClash (recommended, in archlinuxcn)',
        'packages': ['flclash'],
        'aur': False,
    },
    'mihomo': {
        'label': 'Mihomo (CLI, in archlinuxcn)',
        'packages': ['mihomo'],
        'aur': False,
    },
    'mihomo_party': {
        'label': 'Mihomo Party (AUR)',
        'packages': ['mihomo-party-bin'],
        'aur': True,
    },
    'clash_verge': {
        'label': 'Clash Verge Rev (AUR)',
        'packages': ['clash-verge-rev-bin'],
        'aur': True,
    },
}

# ---------------------------------------------------------------------------
# Device purpose options
# ---------------------------------------------------------------------------

DEVICE_PURPOSES: dict[str, str] = {
    'development': 'Development',
    'gaming': 'Gaming',
    'media': 'Media Production',
    'industrial': 'Industrial Design',
}

DEV_ENVIRONMENT_OPTIONS: dict[str, dict] = {
    'docker': {
        'label': 'Docker',
        'packages': ['docker', 'docker-compose'],
        'aur': False,
        'services': ['docker'],
    },
    'go': {
        'label': 'Go',
        'packages': ['go'],
        'aur': False,
        'services': [],
    },
    'bun': {
        'label': 'Bun',
        'packages': ['bun'],
        'aur': False,
        'services': [],
    },
    'nodejs': {
        'label': 'Node.js (LTS)',
        # NOTE: Update LTS codename when new LTS is released (current: Jod/v22)
        'packages': ['nodejs-lts-jod', 'npm'],
        'aur': False,
        'services': [],
    },
    'python': {
        'label': 'Python',
        'packages': ['python', 'python-pip'],
        'aur': False,
        'services': [],
    },
    'rustup': {
        'label': 'Rust (rustup)',
        'packages': ['rustup'],
        'aur': False,
        'services': [],
    },
    'bat': {
        'label': 'bat (cat replacement)',
        'packages': ['bat'],
        'aur': False,
        'services': [],
    },
    'eza': {
        'label': 'eza (ls replacement)',
        'packages': ['eza'],
        'aur': False,
        'services': [],
    },
    'ripgrep': {
        'label': 'ripgrep (grep replacement)',
        'packages': ['ripgrep'],
        'aur': False,
        'services': [],
    },
    'chezmoi': {
        'label': 'Chezmoi',
        'packages': ['chezmoi'],
        'aur': False,
        'services': [],
    },
}

DEV_EDITOR_OPTIONS: dict[str, dict] = {
    'vscode': {
        'label': 'Visual Studio Code (AUR)',
        'packages': ['visual-studio-code-bin'],
        'aur': True,
    },
    'jetbrains': {
        'label': 'JetBrains Toolbox (AUR)',
        'packages': ['jetbrains-toolbox'],
        'aur': True,
    },
}

GAMING_OPTIONS: dict[str, dict] = {
    'steam': {
        'label': 'Steam',
        'packages': ['steam'],
        'aur': False,
    },
    'lutris': {
        'label': 'Lutris',
        'packages': ['lutris'],
        'aur': False,
    },
    'gamemode': {
        'label': 'GameMode',
        'packages': ['gamemode', 'lib32-gamemode'],
        'aur': False,
    },
    'mangohud': {
        'label': 'MangoHud',
        'packages': ['mangohud', 'lib32-mangohud'],
        'aur': False,
    },
}

# ---------------------------------------------------------------------------
# Electron / VS Code Wayland flags
# ---------------------------------------------------------------------------

ELECTRON_WAYLAND_FLAGS: str = """\
--enable-features=UseOzonePlatform,WaylandWindowDecorations
--ozone-platform-hint=auto
--enable-wayland-ime
"""

# ---------------------------------------------------------------------------
# Reflector configuration (non-CN users)
# ---------------------------------------------------------------------------

REFLECTOR_CONF: str = """--save /etc/pacman.d/mirrorlist
--protocol https
--latest 5
--sort age
"""
