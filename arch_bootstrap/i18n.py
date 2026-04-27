from __future__ import annotations

# Module-level state
_current_lang: str = 'en'

# All 85 keys x 3 languages
TRANSLATIONS: dict[str, dict[str, str]] = {
    'en': {
        # -- Category names (progress display) --
        'category.localization': 'Localization',
        'category.system': 'System',
        'category.hardware': 'Hardware',
        'category.desktop': 'Desktop',
        'category.software': 'Software',
        'category.account': 'Account',
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
        'dms.configuring_i2c': 'Configuring I2C/DDC for monitor brightness control...',
        'dms.i2c_configured': 'I2C/DDC configured (user added to i2c group)',
        'dms.dsearch_enabling': 'Enabling DankSearch filesystem search service...',
        'dms.dsearch_indexing': 'Generating initial DankSearch index...',
        'dms.dsearch_complete': 'DankSearch enabled and initial index built',
        # -- DMS Manual --
        'step.desktop.dms_manual':       'DankMaterialShell (Manual)',
        'dms_manual.setting_up_sudoers': 'Setting up temporary sudo access...',
        'dms_manual.installing_prereqs': 'Installing quickshell (this may take a while)...',
        'dms_manual.installing_deps':    'Installing DMS dependencies via paru...',
        'dms_manual.running_setup':      'Running dms setup for initial configuration...',
        'dms_manual.configuring_greetd': 'Configuring greetd for DMS greeter...',
        'dms_manual.enabling_services':  'Enabling DMS desktop services...',
        'dms_manual.complete':           'DMS desktop environment installed successfully',
        'dms_manual.failed':             'DMS manual installation failed (exit %d)',
        # -- Exo desktop --
        'step.desktop.exo': 'Exo (Material Design 3 + Niri)',
        'exo.installing_deps': 'Installing Exo dependencies via paru...',
        'exo.cloning_repo': 'Cloning Exo repository...',
        'exo.copying_configs': 'Copying Exo configuration files...',
        'exo.running_matugen': 'Running matugen for initial color generation...',
        'exo.configuring_greetd': 'Configuring greetd for Niri autologin...',
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
        # -- Retry --
        'retry.attempt': 'Retry %d/%d: %s',
        'retry.prompt': '\n%s failed. Retry? [Y/n]: ',
        # -- GitHub proxy --
        'proxy.installing_dl': 'Installing GitHub download proxy for makepkg...',
        # --- Extra install steps ---
        # -- Input method --
        'step.input_method': 'Input Method',
        'opt.input_method.title': 'Select input method (multi-select, press Enter to skip)',
        # -- Fonts --
        'step.fonts': 'Fonts',
        'opt.fonts.base_title': 'Select base fonts (multi-select, press Enter to skip)',
        'opt.fonts.nerd_title': 'Select Nerd Fonts (multi-select, press Enter to skip)',
        # -- Proxy tools --
        'step.proxy_tools': 'Proxy Tools',
        'opt.proxy_tools.title': 'Select proxy tool (single-select, press Enter to skip)',
        # -- Audio firmware --
        'step.audio_firmware': 'Audio Firmware',
        'opt.audio_firmware.title': 'Select audio firmware (multi-select, press Enter to skip)',
        # -- Polkit agent --
        'step.polkit_agent': 'Polkit Agent',
        'opt.polkit_agent.title': 'Select polkit agent',
        # -- Keyring --
        'step.keyring': 'Keyring',
        'opt.keyring.title': 'Select keyring implementation',
        # -- File manager --
        'step.file_manager': 'File Manager',
        'opt.file_manager.title': 'Select file manager (multi-select, press Enter to skip)',
        # -- Device purpose --
        'step.device_purpose': 'Device Purpose',
        'opt.device_purpose.title': 'Select device purpose (multi-select, press Enter to skip)',
        # -- Dev tools --
        'step.dev_tools': 'Development Tools',
        'opt.dev_env.title': 'Select development environment (multi-select, press Enter to skip)',
        'opt.dev_editor.title': 'Select development editor (multi-select, press Enter to skip)',
        # -- Gaming --
        'step.gaming': 'Gaming',
        'opt.gaming.title': 'Select gaming tools (multi-select, press Enter to skip)',
        # -- Remote desktop --
        'step.remote_desktop': 'Remote Desktop',
        'opt.remote_desktop.title': 'Select remote desktop tools (multi-select, press Enter to skip)',
        # -- Virtual machine --
        'opt.vm.title': 'Virtual Machine Setup',
        'opt.vm.desc': 'Select VM components to install',
        # -- Confirm panel (extra) --
        'confirm.input_method': 'Input Method',
        'confirm.fonts': 'Fonts',
        'confirm.proxy_tools': 'Proxy Tools',
        'confirm.audio_firmware': 'Audio Firmware',
        'confirm.polkit_agent': 'Polkit Agent',
        'confirm.keyring': 'Keyring',
        'confirm.file_manager': 'File Manager',
        'confirm.device_purpose': 'Device Purpose',
        'confirm.dev_tools': 'Development Tools',
        'confirm.gaming': 'Gaming',
        'confirm.remote_desktop': 'Remote Desktop',
        'confirm.vm_options': 'VM Components',
        # -- Post-install (extra) --
        'post.input_method': 'Setting up input method ...',
        'post.proxy_tools': 'Installing proxy tools ...',
        'post.clipboard': 'Setting up clipboard tools ...',
        'post.zsh_plugins': 'Installing zsh plugins ...',
        'post.electron_flags': 'Writing Electron Wayland flags ...',
        'post.dev_services': 'Enabling development services ...',
        'post.clipsync': 'Enabling clipboard sync service ...',
        'post.snapper_timers': 'Enabling snapper timers ...',
        'post.gnome_keyring': 'Enabling GNOME Keyring sockets ...',
        'post.reflector': 'Configuring reflector mirror auto-update ...',
        # -- CN communication apps --
        'step.cn_apps.title': 'Communication Apps',
        'confirm.cn_apps': 'Communication',
        'post.cn_apps': 'Installing communication apps...',
        # -- Hostname --
        'step.hostname.title': 'Hostname',
        'validate.hostname.empty': 'Hostname cannot be empty',
        'validate.hostname.format': 'Hostname must contain only lowercase letters, digits, and hyphens',
        'validate.hostname.length': 'Hostname must be at most 63 characters',
        'confirm.hostname': 'Hostname',
        # -- Hibernation --
        'step.hibernation.title': 'Enable hibernation? (A swap file will be created)',
        'confirm.hibernation': 'Hibernation',
        'post.hibernation': 'Setting up hibernation...',
        'post.hibernation_hook_warning': 'Warning: Could not add resume hook to mkinitcpio.conf. You may need to add it manually.',
        'post.hibernation_cmdline_warning': 'Warning: /etc/kernel/cmdline not found. Resume parameters not added.',
        'post.remove_git_proxy_prompt': 'Remove GitHub proxy (ghfast.top) from git config?\n'
                                        'Recommended if you have a local proxy tool (e.g. FlClash).',
        'post.git_proxy_removed': 'CN: removed GitHub proxy from git config',
        # -- xdg-user-dirs --
        'post.xdg_user_dirs': 'Forcing English XDG user directories ...',
        # -- Logging --
        'log.copied': 'Installation log copied to new system',
        # -- Dev tool labels --
        'opt.dev.chezmoi': 'Chezmoi (dotfile manager)',
        # -- Installation summary --
        'summary.title': 'Installation Summary',
        'summary.total': 'Total',
        'summary.log_path': 'Log file',
        'summary.step.base_system': 'Base system',
        'summary.step.network': 'Network configuration',
        'summary.step.user_accounts': 'User accounts',
        'summary.step.console': 'Console configuration',
        'summary.step.kmscon': 'Kmscon (CJK console)',
        'summary.step.fonts': 'Font configuration',
        'summary.step.wifi': 'WiFi connection',
        'summary.step.git_proxy': 'Git proxy',
        'summary.step.cn_repo': 'CN repository',
        'summary.step.aur_helper': 'AUR helper (paru)',
        'summary.step.clipboard': 'Clipboard support',
        'summary.step.zsh': 'Zsh + Oh-My-Zsh',
        'summary.step.desktop': 'Desktop environment',
        'summary.step.browser': 'Browser',
        'summary.step.electron_flags': 'Electron Wayland flags',
        'summary.step.input_method': 'Input method',
        'summary.step.aur_packages': 'AUR packages',
        'summary.step.dev_services': 'Development services',
        'summary.step.virtual_machine': 'Virtual machine support',
        'summary.step.snapper': 'Snapper + Keyring',
        'summary.step.reflector': 'Mirror configuration',
        'summary.step.hibernation': 'Hibernation',
        'summary.step.remove_git_proxy': 'Remove GitHub proxy',
    },
    'zh': {
        # -- Category names (progress display) --
        'category.localization': '本地化',
        'category.system': '系统',
        'category.hardware': '硬件',
        'category.desktop': '桌面',
        'category.software': '软件',
        'category.account': '账户',
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
        'dms.configuring_i2c': '正在配置 I2C/DDC 以支持显示器亮度控制...',
        'dms.i2c_configured': 'I2C/DDC 已配置（用户已加入 i2c 组）',
        'dms.dsearch_enabling': '正在启用 DankSearch 文件搜索服务...',
        'dms.dsearch_indexing': '正在生成 DankSearch 初始索引...',
        'dms.dsearch_complete': 'DankSearch 已启用并完成初始索引构建',
        # -- DMS 手动安装 --
        'step.desktop.dms_manual':       'DankMaterialShell（手动安装）',
        'dms_manual.setting_up_sudoers': '设置临时 sudo 权限...',
        'dms_manual.installing_prereqs': '安装 quickshell（可能需要较长时间）...',
        'dms_manual.installing_deps':    '通过 paru 安装 DMS 依赖...',
        'dms_manual.running_setup':      '运行 dms setup 生成初始配置...',
        'dms_manual.configuring_greetd': '配置 greetd 登录管理器...',
        'dms_manual.enabling_services':  '启用 DMS 桌面服务...',
        'dms_manual.complete':           'DMS 桌面环境安装成功',
        'dms_manual.failed':             'DMS 手动安装失败（退出码 %d）',
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
        # -- 重试 --
        'retry.attempt': '重试 %d/%d: %s',
        'retry.prompt': '\n%s 失败，是否重试？[Y/n]: ',
        # -- GitHub 代理 --
        'proxy.installing_dl': '正在为 makepkg 安装 GitHub 下载代理...',
        # --- Extra install steps ---
        # -- 输入法 --
        'step.input_method': '输入法',
        'opt.input_method.title': '选择输入法（多选，按回车跳过）',
        # -- 字体 --
        'step.fonts': '字体',
        'opt.fonts.base_title': '选择基础字体（多选，按回车跳过）',
        'opt.fonts.nerd_title': '选择 Nerd 字体（多选，按回车跳过）',
        # -- 代理工具 --
        'step.proxy_tools': '代理工具',
        'opt.proxy_tools.title': '选择代理工具（单选，按回车跳过）',
        # -- 声卡固件 --
        'step.audio_firmware': '声卡固件',
        'opt.audio_firmware.title': '选择声卡固件（多选，按回车跳过）',
        # -- Polkit 代理 --
        'step.polkit_agent': 'Polkit 代理',
        'opt.polkit_agent.title': '选择 Polkit 代理',
        # -- 密钥环 --
        'step.keyring': '密钥环',
        'opt.keyring.title': '选择密钥环实现',
        # -- 文件管理器 --
        'step.file_manager': '文件管理器',
        'opt.file_manager.title': '选择文件管理器（多选，按回车跳过）',
        # -- 设备用途 --
        'step.device_purpose': '设备用途',
        'opt.device_purpose.title': '选择设备主要用途（多选，按回车跳过）',
        # -- 开发工具 --
        'step.dev_tools': '开发工具',
        'opt.dev_env.title': '选择开发环境（多选，按回车跳过）',
        'opt.dev_editor.title': '选择开发编辑器（多选，按回车跳过）',
        # -- 游戏 --
        'step.gaming': '游戏',
        'opt.gaming.title': '选择游戏工具（多选，按回车跳过）',
        # -- 远程桌面 --
        'step.remote_desktop': '远程桌面',
        'opt.remote_desktop.title': '选择远程桌面工具（多选，按回车跳过）',
        # -- 虚拟机 --
        'opt.vm.title': '虚拟机配置',
        'opt.vm.desc': '选择要安装的虚拟机组件',
        # -- 确认面板（扩展） --
        'confirm.input_method': '输入法',
        'confirm.fonts': '字体',
        'confirm.proxy_tools': '代理工具',
        'confirm.audio_firmware': '声卡固件',
        'confirm.polkit_agent': 'Polkit 代理',
        'confirm.keyring': '密钥环',
        'confirm.file_manager': '文件管理器',
        'confirm.device_purpose': '设备用途',
        'confirm.dev_tools': '开发工具',
        'confirm.gaming': '游戏',
        'confirm.remote_desktop': '远程桌面',
        'confirm.vm_options': '虚拟机组件',
        # -- 安装后（扩展） --
        'post.input_method': '正在设置输入法 ...',
        'post.proxy_tools': '正在安装代理工具 ...',
        'post.clipboard': '正在设置剪贴板工具 ...',
        'post.zsh_plugins': '正在安装 zsh 插件 ...',
        'post.electron_flags': '正在写入 Electron Wayland 标志 ...',
        'post.dev_services': '正在启用开发服务 ...',
        'post.clipsync': '正在启用剪贴板同步服务 ...',
        'post.snapper_timers': '正在启用 snapper 定时器 ...',
        'post.gnome_keyring': '正在启用 GNOME 密钥环套接字 ...',
        'post.reflector': '正在配置 reflector 镜像自动更新 ...',
        # -- 通讯应用 --
        'step.cn_apps.title': '通讯应用',
        'confirm.cn_apps': '通讯应用',
        'post.cn_apps': '正在安装通讯应用...',
        # -- 主机名 --
        'step.hostname.title': '主机名',
        'validate.hostname.empty': '主机名不能为空',
        'validate.hostname.format': '主机名只能包含小写字母、数字和连字符',
        'validate.hostname.length': '主机名最长 63 个字符',
        'confirm.hostname': '主机名',
        # -- 休眠 --
        'step.hibernation.title': '是否启用休眠？（将创建交换文件）',
        'confirm.hibernation': '休眠',
        'post.hibernation': '正在配置休眠...',
        'post.hibernation_hook_warning': '警告：无法将 resume hook 添加到 mkinitcpio.conf，可能需要手动添加。',
        'post.hibernation_cmdline_warning': '警告：未找到 /etc/kernel/cmdline，未添加 resume 参数。',
        'post.remove_git_proxy_prompt': '是否移除 git 配置中的 GitHub 代理（ghfast.top）？\n'
                                        '如果已安装本地代理工具（如 FlClash），建议移除。',
        'post.git_proxy_removed': 'CN：已移除 git 配置中的 GitHub 代理',
        # -- xdg-user-dirs --
        'post.xdg_user_dirs': '正在强制设置英文 XDG 用户目录 ...',
        # -- 日志 --
        'log.copied': '安装日志已复制到新系统',
        # -- 开发工具标签 --
        'opt.dev.chezmoi': 'Chezmoi（Dotfile 管理器）',
        # -- 安装总结 --
        'summary.title': '安装总结',
        'summary.total': '总计',
        'summary.log_path': '日志文件',
        'summary.step.base_system': '基础系统',
        'summary.step.network': '网络配置',
        'summary.step.user_accounts': '用户账户',
        'summary.step.console': '控制台配置',
        'summary.step.kmscon': 'Kmscon（CJK 控制台）',
        'summary.step.fonts': '字体配置',
        'summary.step.wifi': 'WiFi 连接',
        'summary.step.git_proxy': 'Git 代理',
        'summary.step.cn_repo': 'CN 仓库',
        'summary.step.aur_helper': 'AUR 助手（paru）',
        'summary.step.clipboard': '剪贴板支持',
        'summary.step.zsh': 'Zsh + Oh-My-Zsh',
        'summary.step.desktop': '桌面环境',
        'summary.step.browser': '浏览器',
        'summary.step.electron_flags': 'Electron Wayland 标志',
        'summary.step.input_method': '输入法',
        'summary.step.aur_packages': 'AUR 软件包',
        'summary.step.dev_services': '开发服务',
        'summary.step.virtual_machine': '虚拟机支持',
        'summary.step.snapper': 'Snapper + 密钥环',
        'summary.step.reflector': '镜像源配置',
        'summary.step.hibernation': '休眠',
        'summary.step.remove_git_proxy': '移除 GitHub 代理',
    },
    'ja': {
        # -- Category names (progress display) --
        'category.localization': 'ローカライズ',
        'category.system': 'システム',
        'category.hardware': 'ハードウェア',
        'category.desktop': 'デスクトップ',
        'category.software': 'ソフトウェア',
        'category.account': 'アカウント',
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
        'dms.configuring_i2c': 'I2C/DDC を設定中（モニター輝度制御用）...',
        'dms.i2c_configured': 'I2C/DDC の設定が完了しました（ユーザーを i2c グループに追加）',
        'dms.dsearch_enabling': 'DankSearch ファイル検索サービスを有効化中...',
        'dms.dsearch_indexing': 'DankSearch の初期インデックスを生成中...',
        'dms.dsearch_complete': 'DankSearch が有効化され、初期インデックスが構築されました',
        # -- DMS 手動インストール --
        'step.desktop.dms_manual':       'DankMaterialShell（手動インストール）',
        'dms_manual.setting_up_sudoers': '一時的なsudo権限を設定中...',
        'dms_manual.installing_prereqs': 'quickshellをインストール中（時間がかかる場合があります）...',
        'dms_manual.installing_deps':    'paruでDMS依存パッケージをインストール中...',
        'dms_manual.running_setup':      'dms setupで初期設定を生成中...',
        'dms_manual.configuring_greetd': 'greetdログインマネージャーを設定中...',
        'dms_manual.enabling_services':  'DMSデスクトップサービスを有効化中...',
        'dms_manual.complete':           'DMSデスクトップ環境のインストールが完了しました',
        'dms_manual.failed':             'DMS手動インストールに失敗しました（終了コード %d）',
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
        # -- リトライ --
        'retry.attempt': 'リトライ %d/%d: %s',
        'retry.prompt': '\n%s が失敗しました。再試行しますか？ [Y/n]: ',
        # -- GitHub プロキシ --
        'proxy.installing_dl': 'makepkg 用の GitHub ダウンロードプロキシをインストール中...',
        # --- Extra install steps ---
        # -- 入力メソッド --
        'step.input_method': '入力メソッド',
        'opt.input_method.title': '入力メソッドを選択（複数選択可、Enterでスキップ）',
        # -- フォント --
        'step.fonts': 'フォント',
        'opt.fonts.base_title': '基本フォントを選択（複数選択可、Enterでスキップ）',
        'opt.fonts.nerd_title': 'Nerd Fontsを選択（複数選択可、Enterでスキップ）',
        # -- プロキシツール --
        'step.proxy_tools': 'プロキシツール',
        'opt.proxy_tools.title': 'プロキシツールを選択（単一選択、Enterでスキップ）',
        # -- オーディオファームウェア --
        'step.audio_firmware': 'オーディオファームウェア',
        'opt.audio_firmware.title': 'オーディオファームウェアを選択（複数選択可、Enterでスキップ）',
        # -- Polkit エージェント --
        'step.polkit_agent': 'Polkit エージェント',
        'opt.polkit_agent.title': 'Polkit エージェントを選択',
        # -- キーリング --
        'step.keyring': 'キーリング',
        'opt.keyring.title': 'キーリング実装を選択',
        # -- ファイルマネージャー --
        'step.file_manager': 'ファイルマネージャー',
        'opt.file_manager.title': 'ファイルマネージャーを選択（複数選択可、Enterでスキップ）',
        # -- デバイスの用途 --
        'step.device_purpose': 'デバイスの用途',
        'opt.device_purpose.title': 'デバイスの用途を選択（複数選択可、Enterでスキップ）',
        # -- 開発ツール --
        'step.dev_tools': '開発ツール',
        'opt.dev_env.title': '開発環境を選択（複数選択可、Enterでスキップ）',
        'opt.dev_editor.title': '開発エディタを選択（複数選択可、Enterでスキップ）',
        # -- ゲーム --
        'step.gaming': 'ゲーム',
        'opt.gaming.title': 'ゲームツールを選択（複数選択可、Enterでスキップ）',
        # -- リモートデスクトップ --
        'step.remote_desktop': 'リモートデスクトップ',
        'opt.remote_desktop.title': 'リモートデスクトップツールを選択（複数選択可、Enterでスキップ）',
        # -- 仮想マシン --
        'opt.vm.title': '仮想マシン設定',
        'opt.vm.desc': 'インストールするVMコンポーネントを選択',
        # -- 確認パネル（追加） --
        'confirm.input_method': '入力メソッド',
        'confirm.fonts': 'フォント',
        'confirm.proxy_tools': 'プロキシツール',
        'confirm.audio_firmware': 'オーディオファームウェア',
        'confirm.polkit_agent': 'Polkit エージェント',
        'confirm.keyring': 'キーリング',
        'confirm.file_manager': 'ファイルマネージャー',
        'confirm.device_purpose': 'デバイスの用途',
        'confirm.dev_tools': '開発ツール',
        'confirm.gaming': 'ゲーム',
        'confirm.remote_desktop': 'リモートデスクトップ',
        'confirm.vm_options': 'VMコンポーネント',
        # -- インストール後（追加） --
        'post.input_method': '入力メソッドを設定中 ...',
        'post.proxy_tools': 'プロキシツールをインストール中 ...',
        'post.clipboard': 'クリップボードツールを設定中 ...',
        'post.zsh_plugins': 'zsh プラグインをインストール中 ...',
        'post.electron_flags': 'Electron Wayland フラグを書き込み中 ...',
        'post.dev_services': '開発サービスを有効化中 ...',
        'post.clipsync': 'クリップボード同期サービスを有効化中 ...',
        'post.snapper_timers': 'snapper タイマーを有効化中 ...',
        'post.gnome_keyring': 'GNOME キーリングソケットを有効化中 ...',
        'post.reflector': 'reflector ミラー自動更新を設定中 ...',
        # -- CN通信アプリ --
        'step.cn_apps.title': '通信アプリ',
        'confirm.cn_apps': '通信アプリ',
        'post.cn_apps': '通信アプリをインストール中...',
        # -- ホスト名 --
        'step.hostname.title': 'ホスト名',
        'validate.hostname.empty': 'ホスト名を空にできません',
        'validate.hostname.format': 'ホスト名には小文字、数字、ハイフンのみ使用できます',
        'validate.hostname.length': 'ホスト名は63文字以内にしてください',
        'confirm.hostname': 'ホスト名',
        # -- ハイバネーション --
        'step.hibernation.title': 'ハイバネーションを有効にしますか？（スワップファイルが作成されます）',
        'confirm.hibernation': 'ハイバネーション',
        'post.hibernation': 'ハイバネーションを設定中...',
        'post.hibernation_hook_warning': '警告：mkinitcpio.conf に resume フックを追加できませんでした。手動で追加が必要な場合があります。',
        'post.hibernation_cmdline_warning': '警告：/etc/kernel/cmdline が見つかりません。resume パラメータは追加されませんでした。',
        'post.remove_git_proxy_prompt': 'git 設定から GitHub プロキシ（ghfast.top）を削除しますか？\n'
                                        'ローカルプロキシツール（FlClash など）がある場合は削除を推奨します。',
        'post.git_proxy_removed': 'CN：git 設定から GitHub プロキシを削除しました',
        # -- xdg-user-dirs --
        'post.xdg_user_dirs': '英語の XDG ユーザーディレクトリを強制設定中 ...',
        # -- ログ --
        'log.copied': 'インストールログを新システムにコピーしました',
        # -- 開発ツールラベル --
        'opt.dev.chezmoi': 'Chezmoi（dotfileマネージャー）',
        # -- インストールサマリー --
        'summary.title': 'インストールサマリー',
        'summary.total': '合計',
        'summary.log_path': 'ログファイル',
        'summary.step.base_system': 'ベースシステム',
        'summary.step.network': 'ネットワーク設定',
        'summary.step.user_accounts': 'ユーザーアカウント',
        'summary.step.console': 'コンソール設定',
        'summary.step.kmscon': 'Kmscon（CJKコンソール）',
        'summary.step.fonts': 'フォント設定',
        'summary.step.wifi': 'WiFi 接続',
        'summary.step.git_proxy': 'Git プロキシ',
        'summary.step.cn_repo': 'CN リポジトリ',
        'summary.step.aur_helper': 'AUR ヘルパー（paru）',
        'summary.step.clipboard': 'クリップボードサポート',
        'summary.step.zsh': 'Zsh + Oh-My-Zsh',
        'summary.step.desktop': 'デスクトップ環境',
        'summary.step.browser': 'ブラウザ',
        'summary.step.electron_flags': 'Electron Wayland フラグ',
        'summary.step.input_method': '入力メソッド',
        'summary.step.aur_packages': 'AUR パッケージ',
        'summary.step.dev_services': '開発サービス',
        'summary.step.virtual_machine': '仮想マシンサポート',
        'summary.step.snapper': 'Snapper + キーリング',
        'summary.step.reflector': 'ミラー設定',
        'summary.step.hibernation': 'ハイバネーション',
        'summary.step.remove_git_proxy': 'GitHub プロキシ削除',
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
