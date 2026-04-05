#!/bin/bash
# 简体中文翻译

[[ -n "${_I18N_ZH_LOADED:-}" ]] && return 0
declare -r _I18N_ZH_LOADED=1

declare -gA _I18N_ZH=(
    # ── 通用状态 ──
    [status.set]="已设置"
    [status.not_set]="未设置"
    [status.enabled]="已启用"
    [status.not_enabled]="未启用"
    [status.added]="已添加"
    [status.not_needed]="不需要"
    [status.cancelled]="已取消"

    # ── 输入校验 ──
    [validate.username.empty]="用户名不能为空"
    [validate.username.format]="用户名只能包含小写字母、数字、下划线和连字符"

    # ── 镜像源 ──
    [mirror.no_reflector]="reflector 未安装，使用内置镜像列表"
    [mirror.fetching_country]="正在通过 reflector 获取 %s 镜像并测速排序..."
    [mirror.fetching_worldwide]="正在通过 reflector 获取全球镜像并测速排序..."
    [mirror.fetch_failed]="reflector 获取失败，使用内置镜像列表"
    [mirror.no_results]="reflector 未返回任何镜像，使用内置列表"
    [mirror.found]="获取到 %s 个镜像 (按速度排序)"

    # ── 地区 / 国家 ──
    [region.detecting]="正在通过 IP 地理位置检测所在国家..."
    [region.detected]="检测到国家: %s"
    [region.auto_detected]="自动检测"

    # ── 导航 (向导步骤名 & 进度标签) ──
    [nav.lang]="语言"
    [nav.region]="地区"
    [nav.disk]="磁盘"
    [nav.net]="网络"
    [nav.repos]="仓库"
    [nav.gpu]="显卡"
    [nav.user]="用户名"
    [nav.passwd]="用户密码"
    [nav.root]="Root密码"
    [nav.confirm]="确认"

    # ── 步骤标题 (fzf / 输入提示) ──
    [step.lang.title]="系统语言"
    [step.region.title]="镜像地区"
    [step.disk.title]="安装目标磁盘"
    [step.net.title]="网络后端"
    [step.gpu.title]="显卡驱动"
    [step.user.title]="用户名"
    [step.passwd.title]="用户密码"
    [step.root.title]="Root 密码 (留空则不设置)"

    # ── 步骤消息 ──
    [step.lang.success]="语言: %s"
    [step.lang.kmscon]="已自动添加 %s 用于非英文 TTY 显示支持"
    [step.region.success]="地区: %s"
    [step.disk.success]="目标磁盘: %s"
    [step.net.success]="网络: %s"
    [step.repos.confirm]="启用 multilib 仓库? (32 位兼容，如 Steam)"
    [step.repos.enabled]="multilib: 已启用"
    [step.repos.disabled]="multilib: 未启用"
    [step.gpu.success]="显卡驱动: %s"
    [step.gpu.mesa_only]="显卡驱动: 仅 mesa (通用)"
    [step.gpu.mesa_generic]="mesa (通用)"
    [step.user.success]="用户名: %s"
    [step.passwd.empty]="用户密码不能为空"
    [step.root.set]="Root 密码: 已设置"
    [step.root.unset]="Root 密码: 未设置"

    # ── 确认步骤 ──
    [confirm.lang]="系统语言"
    [confirm.region]="镜像地区"
    [confirm.timezone]="时区"
    [confirm.disk]="目标磁盘"
    [confirm.net]="网络后端"
    [confirm.gpu]="显卡驱动"
    [confirm.user]="用户名"
    [confirm.root]="Root 密码"
    [confirm.version]="版本"
    [confirm.prompt]="以上配置正确？生成 JSON 文件?"
    [confirm.preview_title]="配置总览"

    # ── 固定摘要项 ──
    [fixed.boot]="引导"
    [fixed.fs]="文件系统"
    [fixed.audio]="音频"
    [fixed.bt]="蓝牙"

    # ── 生成完毕 ──
    [post.title]="生成完毕"
    [post.sys_config]="(系统配置)"
    [post.credentials]="(用户凭据)"
    [post.kmscon_hint]="提示: 安装完成首次启动后，请启用 kmscon 替代默认 TTY:"

    # ── ISO 安装 ──
    [iso.title]="安装"
    [iso.detected]="检测到 Arch Linux ISO 安装环境"
    [iso.run_now]="立刻执行 archinstall 安装?"
    [iso.mount_not_found]="未找到安装目标挂载点，请手动启用 kmscon:"
    [iso.complete_title]="安装完成"
    [iso.success]="系统已安装成功"
    [iso.reboot]="重启进入新系统:"

    # ── 向导引擎 ──
    [wizard.first_step]="已经是第一步"
    [wizard.aborted]="已中止"
    [wizard.step_failed]="步骤 '%s' 失败 (exit %s)"

    # ── 选项标签 (动态构建数组) ──
    [opt.lang.zh_CN]="简体中文  zh_CN.UTF-8"
    [opt.lang.en_US]="English   en_US.UTF-8"
    [opt.lang.ja_JP]="日本語    ja_JP.UTF-8"
    [opt.net.nm_iwd]="NetworkManager + iwd  (推荐，更省电)"
    [opt.net.nm]="NetworkManager + wpa_supplicant  (传统)"
)
