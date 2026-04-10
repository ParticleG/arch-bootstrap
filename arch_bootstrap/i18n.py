from __future__ import annotations

# Module-level state
_current_lang: str = 'en'

# All 85 keys x 3 languages
TRANSLATIONS: dict[str, dict[str, str]] = {
    'en': {
        # -- Common status --
        'status.set': 'Set',
        'status.not_set': 'Not set',
        'status.enabled': 'Enabled',
        'status.not_enabled': 'Not enabled',
        'status.added': 'Added',
        'status.not_needed': 'Not needed',
        'status.cancelled': 'Cancelled',
        # -- Validation --
        'validate.username.empty': 'Username cannot be empty',
        'validate.username.format': 'Only lowercase letters, digits, underscores, hyphens',
        # -- Mirror --
        'mirror.no_reflector': 'reflector not found, using built-in mirror list',
        'mirror.fetching_country': 'Fetching %s mirrors via reflector (sorted by speed)...',
        'mirror.fetching_worldwide': 'Fetching worldwide mirrors via reflector (sorted by speed)...',
        'mirror.fetch_failed': 'reflector failed, using built-in mirror list',
        'mirror.no_results': 'reflector returned no mirrors, using built-in list',
        'mirror.found': 'Found %s mirrors (sorted by speed)',
        # -- Region / Country --
        'region.detecting': 'Detecting country via IP geolocation...',
        'region.detected': 'Detected country: %s',
        'region.auto_detected': 'auto-detected',
        # -- Navigation --
        'nav.lang': 'Language',
        'nav.region': 'Region',
        'nav.disk': 'Disk',
        'nav.net': 'Network',
        'nav.repos': 'Repos',
        'nav.gpu': 'GPU',
        'nav.user': 'Username',
        'nav.passwd': 'Password',
        'nav.root': 'Root Passwd',
        'nav.confirm': 'Confirm',
        # -- Step titles --
        'step.lang.title': 'System Language',
        'step.region.title': 'Mirror Region',
        'step.disk.title': 'Target Disk',
        'step.net.title': 'Network Backend',
        'step.gpu.title': 'GPU Drivers',
        'step.user.title': 'Username',
        'step.passwd.title': 'User Password',
        'step.root.title': 'Root Password (empty = none)',
        # -- kmscon --
        'step.kmscon_font.title': 'Console Font (kmscon)',
        # -- Step messages --
        'step.lang.success': 'Language: %s',
        'step.lang.kmscon': 'Auto-added %s for non-English TTY rendering',
        'step.region.success': 'Region: %s',
        'step.disk.success': 'Target disk: %s',
        'step.net.success': 'Network: %s',
        'step.repos.confirm': 'Enable multilib repo? (32-bit compat, e.g. Steam)',
        'step.repos.enabled': 'multilib: enabled',
        'step.repos.disabled': 'multilib: not enabled',
        'step.gpu.success': 'GPU drivers: %s',
        'step.gpu.mesa_only': 'GPU drivers: mesa only (generic)',
        'step.gpu.mesa_generic': 'mesa (generic)',
        'step.user.success': 'Username: %s',
        'step.passwd.empty': 'User password cannot be empty',
        'step.root.set': 'Root password: set',
        'step.root.unset': 'Root password: not set',
        # -- Confirm step --
        'confirm.lang': 'Language',
        'confirm.region': 'Region',
        'confirm.timezone': 'Timezone',
        'confirm.disk': 'Disk',
        'confirm.net': 'Network',
        'confirm.gpu': 'GPU Drivers',
        'confirm.user': 'Username',
        'confirm.root': 'Root Passwd',
        'confirm.version': 'Version',
        'confirm.prompt': 'Confirm configuration? Generate JSON files?',
        'confirm.preview_title': 'CONFIGURATION SUMMARY',
        # -- Fixed summary items --
        'fixed.boot': 'Boot',
        'fixed.fs': 'FS',
        'fixed.audio': 'Audio',
        'fixed.bt': 'BT',
        # -- Post-generation --
        'post.title': 'Files Generated',
        'post.sys_config': '(system config)',
        'post.credentials': '(credentials)',
        'post.kmscon_hint': 'Hint: After first boot, enable kmscon to replace default TTY:',
        # -- ISO install --
        'iso.title': 'Install',
        'iso.detected': 'Arch Linux ISO environment detected',
        'iso.run_now': 'Run archinstall now?',
        'iso.mount_not_found': 'Mount point not found, enable kmscon manually:',
        'iso.complete_title': 'Installation Complete',
        'iso.success': 'System installed successfully',
        'iso.reboot': 'Reboot into the new system:',
        # -- Wizard engine --
        'wizard.first_step': 'Already at first step',
        'wizard.aborted': 'Aborted',
        'wizard.step_failed': "Step '%s' failed (exit %s)",
        # -- Option labels --
        'opt.lang.zh_CN': 'Chinese   zh_CN.UTF-8',
        'opt.lang.en_US': 'English   en_US.UTF-8',
        'opt.lang.ja_JP': 'Japanese  ja_JP.UTF-8',
        'opt.net.nm_iwd': 'NetworkManager + iwd  (recommended)',
        'opt.net.nm': 'NetworkManager + wpa_supplicant  (legacy)',
        # -- DMS desktop --
        'step.desktop.title': 'Desktop Environment',
        'step.desktop.dms': 'DankMaterialShell (DankInstall)',
        'step.desktop.minimal': 'Minimal (no desktop)',
        'step.compositor.title': 'DMS Compositor',
        'step.compositor.niri': 'niri (scrolling tiling, Recommended)',
        'step.compositor.hyprland': 'Hyprland (dynamic tiling)',
        'step.terminal.title': 'DMS Terminal',
        'step.terminal.ghostty': 'Ghostty (Recommended)',
        'step.terminal.kitty': 'kitty',
        'step.terminal.alacritty': 'Alacritty',
        'confirm.desktop': 'Desktop',
        'confirm.compositor': 'Compositor',
        'confirm.terminal': 'Terminal',
        'dms.running_dankinstall': 'Running dankinstall (headless)...',
        'dms.complete': 'DMS desktop environment installed successfully',
        'dms.failed': 'dankinstall failed (exit %d)',
        # -- Exo desktop --
        'step.desktop.exo': 'Exo (Material Design 3 + Niri)',
        'exo.installing_deps': 'Installing Exo dependencies via paru...',
        'exo.cloning_repo': 'Cloning Exo repository...',
        'exo.copying_configs': 'Copying Exo configuration files...',
        'exo.running_matugen': 'Running matugen for initial color generation...',
        'exo.configuring_greetd': 'Configuring greetd for Niri greeter...',
        'exo.enabling_services': 'Enabling Exo desktop services...',
        'exo.complete': 'Exo desktop environment installed successfully',
        'exo.failed': 'Exo installation failed (exit %d)',
        # -- Browser --
        'step.browser.title': 'Web Browser (multi-select, skip = none)',
        'confirm.browser': 'Browser',
        # -- paru --
        'paru.installing': 'Installing paru AUR helper...',
        'paru.installed_pacman': 'Installed paru from archlinuxcn',
        'paru.installed_aur': 'Installed paru from AUR',
        'paru.failed': 'paru installation failed (exit %s), AUR packages will be built manually',
        # -- WiFi --
        'wifi.copying': 'Copying WiFi connections to new system...',
        'wifi.copied': 'Copied %s WiFi connection(s)',
    },
    'zh': {
        # -- Common status --
        'status.set': '已设置',
        'status.not_set': '未设置',
        'status.enabled': '已启用',
        'status.not_enabled': '未启用',
        'status.added': '已添加',
        'status.not_needed': '不需要',
        'status.cancelled': '已取消',
        # -- Validation --
        'validate.username.empty': '用户名不能为空',
        'validate.username.format': '用户名只能包含小写字母、数字、下划线和连字符',
        # -- Mirror --
        'mirror.no_reflector': 'reflector 未安装，使用内置镜像列表',
        'mirror.fetching_country': '正在通过 reflector 获取 %s 镜像并测速排序...',
        'mirror.fetching_worldwide': '正在通过 reflector 获取全球镜像并测速排序...',
        'mirror.fetch_failed': 'reflector 获取失败，使用内置镜像列表',
        'mirror.no_results': 'reflector 未返回任何镜像，使用内置列表',
        'mirror.found': '获取到 %s 个镜像 (按速度排序)',
        # -- Region / Country --
        'region.detecting': '正在通过 IP 地理位置检测所在国家...',
        'region.detected': '检测到国家: %s',
        'region.auto_detected': '自动检测',
        # -- Navigation --
        'nav.lang': '语言',
        'nav.region': '地区',
        'nav.disk': '磁盘',
        'nav.net': '网络',
        'nav.repos': '仓库',
        'nav.gpu': '显卡',
        'nav.user': '用户名',
        'nav.passwd': '用户密码',
        'nav.root': 'Root密码',
        'nav.confirm': '确认',
        # -- Step titles --
        'step.lang.title': '系统语言',
        'step.region.title': '镜像地区',
        'step.disk.title': '安装目标磁盘',
        'step.net.title': '网络后端',
        'step.gpu.title': '显卡驱动',
        'step.user.title': '用户名',
        'step.passwd.title': '用户密码',
        'step.root.title': 'Root 密码 (留空则不设置)',
        # -- kmscon --
        'step.kmscon_font.title': '控制台字体 (kmscon)',
        # -- Step messages --
        'step.lang.success': '语言: %s',
        'step.lang.kmscon': '已自动添加 %s 用于非英文 TTY 显示支持',
        'step.region.success': '地区: %s',
        'step.disk.success': '目标磁盘: %s',
        'step.net.success': '网络: %s',
        'step.repos.confirm': '启用 multilib 仓库? (32 位兼容，如 Steam)',
        'step.repos.enabled': 'multilib: 已启用',
        'step.repos.disabled': 'multilib: 未启用',
        'step.gpu.success': '显卡驱动: %s',
        'step.gpu.mesa_only': '显卡驱动: 仅 mesa (通用)',
        'step.gpu.mesa_generic': 'mesa (通用)',
        'step.user.success': '用户名: %s',
        'step.passwd.empty': '用户密码不能为空',
        'step.root.set': 'Root 密码: 已设置',
        'step.root.unset': 'Root 密码: 未设置',
        # -- Confirm step --
        'confirm.lang': '系统语言',
        'confirm.region': '镜像地区',
        'confirm.timezone': '时区',
        'confirm.disk': '目标磁盘',
        'confirm.net': '网络后端',
        'confirm.gpu': '显卡驱动',
        'confirm.user': '用户名',
        'confirm.root': 'Root 密码',
        'confirm.version': '版本',
        'confirm.prompt': '以上配置正确？生成 JSON 文件?',
        'confirm.preview_title': '配置总览',
        # -- Fixed summary items --
        'fixed.boot': '引导',
        'fixed.fs': '文件系统',
        'fixed.audio': '音频',
        'fixed.bt': '蓝牙',
        # -- Post-generation --
        'post.title': '生成完毕',
        'post.sys_config': '(系统配置)',
        'post.credentials': '(用户凭据)',
        'post.kmscon_hint': '提示: 安装完成首次启动后，请启用 kmscon 替代默认 TTY:',
        # -- ISO install --
        'iso.title': '安装',
        'iso.detected': '检测到 Arch Linux ISO 安装环境',
        'iso.run_now': '立刻执行 archinstall 安装?',
        'iso.mount_not_found': '未找到安装目标挂载点，请手动启用 kmscon:',
        'iso.complete_title': '安装完成',
        'iso.success': '系统已安装成功',
        'iso.reboot': '重启进入新系统:',
        # -- Wizard engine --
        'wizard.first_step': '已经是第一步',
        'wizard.aborted': '已中止',
        'wizard.step_failed': "步骤 '%s' 失败 (exit %s)",
        # -- Option labels --
        'opt.lang.zh_CN': '简体中文  zh_CN.UTF-8',
        'opt.lang.en_US': 'English   en_US.UTF-8',
        'opt.lang.ja_JP': '日本語    ja_JP.UTF-8',
        'opt.net.nm_iwd': 'NetworkManager + iwd  (推荐，更省电)',
        'opt.net.nm': 'NetworkManager + wpa_supplicant  (传统)',
        # -- DMS 桌面 --
        'step.desktop.title': '桌面环境',
        'step.desktop.dms': 'DankMaterialShell (DankInstall)',
        'step.desktop.minimal': '最小安装（无桌面）',
        'step.compositor.title': 'DMS 合成器',
        'step.compositor.niri': 'niri（滚动平铺，推荐）',
        'step.compositor.hyprland': 'Hyprland（动态平铺）',
        'step.terminal.title': 'DMS 终端模拟器',
        'step.terminal.ghostty': 'Ghostty（推荐）',
        'step.terminal.kitty': 'kitty',
        'step.terminal.alacritty': 'Alacritty',
        'confirm.desktop': '桌面',
        'confirm.compositor': '合成器',
        'confirm.terminal': '终端',
        'dms.running_dankinstall': '正在运行 dankinstall（无头模式）...',
        'dms.complete': 'DMS 桌面环境安装完成',
        'dms.failed': 'dankinstall 执行失败（退出码 %d）',
        # -- Exo 桌面 --
        'step.desktop.exo': 'Exo（Material Design 3 + Niri）',
        'exo.installing_deps': '正在通过 paru 安装 Exo 依赖...',
        'exo.cloning_repo': '正在克隆 Exo 仓库...',
        'exo.copying_configs': '正在复制 Exo 配置文件...',
        'exo.running_matugen': '正在运行 matugen 生成初始配色...',
        'exo.configuring_greetd': '正在为 Niri 配置 greetd...',
        'exo.enabling_services': '正在启用 Exo 桌面服务...',
        'exo.complete': 'Exo 桌面环境安装完成',
        'exo.failed': 'Exo 安装失败（退出码 %d）',
        # -- 浏览器 --
        'step.browser.title': '网页浏览器（多选，跳过 = 不安装）',
        'confirm.browser': '浏览器',
        # -- paru --
        'paru.installing': '正在安装 paru AUR 助手...',
        'paru.installed_pacman': '已从 archlinuxcn 安装 paru',
        'paru.installed_aur': '已从 AUR 安装 paru',
        'paru.failed': 'paru 安装失败（退出码 %s），AUR 包将手动构建',
        # -- WiFi --
        'wifi.copying': '正在复制 WiFi 连接信息到新系统...',
        'wifi.copied': '已复制 %s 个 WiFi 连接',
    },
    'ja': {
        # -- Common status --
        'status.set': '設定済み',
        'status.not_set': '未設定',
        'status.enabled': '有効',
        'status.not_enabled': '無効',
        'status.added': '追加済み',
        'status.not_needed': '不要',
        'status.cancelled': 'キャンセル済み',
        # -- Validation --
        'validate.username.empty': 'ユーザー名は空にできません',
        'validate.username.format': '小文字英字、数字、アンダースコア、ハイフンのみ使用可能',
        # -- Mirror --
        'mirror.no_reflector': 'reflector 未インストール、内蔵ミラーリストを使用',
        'mirror.fetching_country': 'reflector で %s ミラーを取得中 (速度順)...',
        'mirror.fetching_worldwide': 'reflector でワールドワイドミラーを取得中 (速度順)...',
        'mirror.fetch_failed': 'reflector 取得失敗、内蔵ミラーリストを使用',
        'mirror.no_results': 'reflector がミラーを返さず、内蔵リストを使用',
        'mirror.found': '%s 個のミラーを取得 (速度順)',
        # -- Region / Country --
        'region.detecting': 'IPジオロケーションで国を検出中...',
        'region.detected': '検出された国: %s',
        'region.auto_detected': '自動検出',
        # -- Navigation --
        'nav.lang': '言語',
        'nav.region': '地域',
        'nav.disk': 'ディスク',
        'nav.net': 'ネットワーク',
        'nav.repos': 'リポジトリ',
        'nav.gpu': 'GPU',
        'nav.user': 'ユーザー名',
        'nav.passwd': 'パスワード',
        'nav.root': 'Rootパスワード',
        'nav.confirm': '確認',
        # -- Step titles --
        'step.lang.title': 'システム言語',
        'step.region.title': 'ミラー地域',
        'step.disk.title': 'インストール先ディスク',
        'step.net.title': 'ネットワークバックエンド',
        'step.gpu.title': 'GPUドライバー',
        'step.user.title': 'ユーザー名',
        'step.passwd.title': 'ユーザーパスワード',
        'step.root.title': 'Root パスワード (空欄 = 設定なし)',
        # -- kmscon --
        'step.kmscon_font.title': 'コンソールフォント (kmscon)',
        # -- Step messages --
        'step.lang.success': '言語: %s',
        'step.lang.kmscon': '非英語 TTY 表示のため %s を自動追加',
        'step.region.success': '地域: %s',
        'step.disk.success': 'インストール先: %s',
        'step.net.success': 'ネットワーク: %s',
        'step.repos.confirm': 'multilib リポジトリを有効にしますか？ (32ビット互換、Steam等)',
        'step.repos.enabled': 'multilib: 有効',
        'step.repos.disabled': 'multilib: 無効',
        'step.gpu.success': 'GPUドライバー: %s',
        'step.gpu.mesa_only': 'GPUドライバー: mesa のみ (汎用)',
        'step.gpu.mesa_generic': 'mesa (汎用)',
        'step.user.success': 'ユーザー名: %s',
        'step.passwd.empty': 'ユーザーパスワードは空にできません',
        'step.root.set': 'Root パスワード: 設定済み',
        'step.root.unset': 'Root パスワード: 未設定',
        # -- Confirm step --
        'confirm.lang': 'システム言語',
        'confirm.region': 'ミラー地域',
        'confirm.timezone': 'タイムゾーン',
        'confirm.disk': 'ディスク',
        'confirm.net': 'ネットワーク',
        'confirm.gpu': 'GPUドライバー',
        'confirm.user': 'ユーザー名',
        'confirm.root': 'Rootパスワード',
        'confirm.version': 'バージョン',
        'confirm.prompt': 'この設定で正しいですか？JSONファイルを生成しますか？',
        'confirm.preview_title': '設定概要',
        # -- Fixed summary items --
        'fixed.boot': 'ブート',
        'fixed.fs': 'FS',
        'fixed.audio': 'オーディオ',
        'fixed.bt': 'BT',
        # -- Post-generation --
        'post.title': 'ファイル生成完了',
        'post.sys_config': '(システム設定)',
        'post.credentials': '(認証情報)',
        'post.kmscon_hint': 'ヒント: 初回起動後、デフォルトTTYの代わりにkmsconを有効にしてください:',
        # -- ISO install --
        'iso.title': 'インストール',
        'iso.detected': 'Arch Linux ISO インストール環境を検出',
        'iso.run_now': '今すぐ archinstall を実行しますか？',
        'iso.mount_not_found': 'マウントポイントが見つかりません、手動でkmsconを有効にしてください:',
        'iso.complete_title': 'インストール完了',
        'iso.success': 'システムのインストールが成功しました',
        'iso.reboot': '新しいシステムで再起動:',
        # -- Wizard engine --
        'wizard.first_step': '最初のステップです',
        'wizard.aborted': '中止しました',
        'wizard.step_failed': "ステップ '%s' が失敗しました (exit %s)",
        # -- Option labels --
        'opt.lang.zh_CN': '簡体中文  zh_CN.UTF-8',
        'opt.lang.en_US': 'English   en_US.UTF-8',
        'opt.lang.ja_JP': '日本語    ja_JP.UTF-8',
        'opt.net.nm_iwd': 'NetworkManager + iwd  (推奨、省電力)',
        'opt.net.nm': 'NetworkManager + wpa_supplicant  (レガシー)',
        # -- DMS デスクトップ --
        'step.desktop.title': 'デスクトップ環境',
        'step.desktop.dms': 'DankMaterialShell (DankInstall)',
        'step.desktop.minimal': '最小構成（デスクトップなし）',
        'step.compositor.title': 'DMS コンポジター',
        'step.compositor.niri': 'niri（スクロールタイル、推奨）',
        'step.compositor.hyprland': 'Hyprland（ダイナミックタイル）',
        'step.terminal.title': 'DMS ターミナル',
        'step.terminal.ghostty': 'Ghostty（推奨）',
        'step.terminal.kitty': 'kitty',
        'step.terminal.alacritty': 'Alacritty',
        'confirm.desktop': 'デスクトップ',
        'confirm.compositor': 'コンポジター',
        'confirm.terminal': 'ターミナル',
        'dms.running_dankinstall': 'dankinstall を実行中（ヘッドレスモード）...',
        'dms.complete': 'DMS デスクトップ環境のインストールが完了しました',
        'dms.failed': 'dankinstall の実行に失敗しました（終了コード %d）',
        # -- Exo デスクトップ --
        'step.desktop.exo': 'Exo（Material Design 3 + Niri）',
        'exo.installing_deps': 'paru で Exo の依存関係をインストール中...',
        'exo.cloning_repo': 'Exo リポジトリをクローン中...',
        'exo.copying_configs': 'Exo 設定ファイルをコピー中...',
        'exo.running_matugen': 'matugen で初期カラースキームを生成中...',
        'exo.configuring_greetd': 'Niri 用に greetd を設定中...',
        'exo.enabling_services': 'Exo デスクトップサービスを有効化中...',
        'exo.complete': 'Exo デスクトップ環境のインストールが完了しました',
        'exo.failed': 'Exo インストールに失敗しました（終了コード %d）',
        # -- ブラウザ --
        'step.browser.title': 'ウェブブラウザ（複数選択可、スキップ = インストールしない）',
        'confirm.browser': 'ブラウザ',
        # -- paru --
        'paru.installing': 'paru AUR ヘルパーをインストール中...',
        'paru.installed_pacman': 'archlinuxcn から paru をインストール',
        'paru.installed_aur': 'AUR から paru をインストール',
        'paru.failed': 'paru インストール失敗（終了コード %s）、AUR パッケージは手動ビルドします',
        # -- WiFi --
        'wifi.copying': 'WiFi 接続情報を新システムにコピー中...',
        'wifi.copied': '%s 個の WiFi 接続をコピー',
    },
}


def set_lang(lang: str) -> None:
    """Set current language ('en', 'zh', 'ja').

    On raw TTY (no kmscon), CJK characters cannot be rendered,
    so the UI language is forced to English regardless of selection.
    The system locale choice is unaffected — only UI display language.
    """
    global _current_lang
    if lang not in TRANSLATIONS:
        return
    if lang != 'en':
        from .detection import is_raw_tty
        if is_raw_tty():
            return  # keep English — TTY cannot render CJK
    _current_lang = lang


def get_lang() -> str:
    """Get current language code."""
    return _current_lang


def t(key: str, *args: object) -> str:
    """Translate key with optional printf-style args.

    Fallback chain: current_lang -> 'en' -> raw key.
    """
    text = TRANSLATIONS.get(_current_lang, {}).get(key)
    if text is None:
        text = TRANSLATIONS.get('en', {}).get(key, key)
    if args:
        try:
            return text % args
        except (TypeError, ValueError):
            return text
    return text
