# 额外安装步骤计划

## 需要新增的自动化安装步骤

以下步骤无需用户交互，根据已有配置自动执行。

### 1. 剪贴板工具

- 始终安装：`cliphist`、`xclip`
- 若选择了任意桌面环境（`dms` / `dms_manual` / `exo`，即非 `minimal`），额外安装：
  - `wl-clipboard`（Wayland 剪贴板命令行工具）
  - `comalot-clipsync-git`（AUR，专为 niri / xwayland-satellite 组合设计的剪贴板同步工具）
    - 备选：`clipsync-git`（AUR，1 star，通用但不针对 niri 优化）
    - 项目目标合成器为 niri，推荐 `comalot-clipsync-git`
  - 安装后需执行 `systemctl --user enable --now clipsync`
- 说明：所有支持的桌面选项（dms/dms_manual/exo）均基于 Wayland，minimal 无桌面环境，因此条件简化为"选择了任意桌面环境"

### 2. 终端增强工具

- 始终安装以下包：
  - `fzf` — 模糊搜索
  - `fastfetch` — 系统信息展示

### 3. xwayland-satellite

- 条件：选择了基于 Niri 的桌面环境
  - `exo`（始终使用 niri）
  - `dms_manual` 且合成器选择了 `niri`
- 安装 `xwayland-satellite` 以提供 XWayland 支持

### 4. unzip

- 始终安装 `unzip` 作为 base package

### 5. VS Code / Electron Wayland 标志

- 条件：选择了任意桌面环境（非 minimal）
- 写入以下文件以启用 Wayland Ozone 平台：
  - `~/.config/code-flags.conf`（VS Code 专用）
  - `~/.config/electron-flags.conf`（所有 Electron 应用通用）
- 文件内容：
  ```
  --enable-features=UseOzonePlatform,WaylandWindowDecorations
  --ozone-platform-hint=auto
  ```

### 6. zsh 插件

- `zsh-autosuggestions`：`extra` 仓库中可用，通过 `pacman -S zsh-autosuggestions` 安装，然后在 `.zshrc` 或 oh-my-zsh 插件配置中 source
- `fast-syntax-highlighting`：不在任何官方仓库中，需通过 `git clone` 安装为 oh-my-zsh 自定义插件：
  ```bash
  git clone https://github.com/zdharma-continuum/fast-syntax-highlighting.git \
    ~/.oh-my-zsh/custom/plugins/fast-syntax-highlighting
  ```
  然后在 `.zshrc` 的 `plugins=()` 中添加 `fast-syntax-highlighting`

### ~~已排除的项目~~

| 原计划项目 | 排除原因 |
|-----------|---------|
| CPU ucode 自动安装 | archinstall 的 `minimal_installation()` 已自动检测 CPU 并安装 `intel-ucode` / `amd-ucode`，无需手动处理 |
| efibootmgr 自动安装 | archinstall 的 `_add_efistub_bootloader()` 已自动为所有 EFI 引导类型安装 `efibootmgr` |

---

## 需要新增的交互式安装步骤

以下步骤需要用户交互选择。每项标注了建议的向导插入位置。

### 1. 输入法（step_input_method）

- **向导位置**：紧接 `step_language`（步骤 1）之后，因为依赖语言选择结果
- **条件**：用户选择了非英文语言
- **交互方式**：多选可不选列表，自动选中推荐项
- **中文方案**：
  - `fcitx5`（框架）
  - `fcitx5-chinese-addons`（拼音等中文输入法）
  - `fcitx5-configtool`（图形配置工具）
- **日文方案**：
  - `fcitx5`（框架）
  - `fcitx5-mozc`（Google 日语输入，推荐，`extra` 仓库）
  - 备选：`fcitx5-anthy`（`extra` 仓库）
  - `fcitx5-configtool`（图形配置工具）
- **环境变量**：安装后必须写入 `/etc/environment`，否则应用无法检测到输入法：
  ```
  XMODIFIERS=@im=fcitx
  GTK_IM_MODULE=fcitx
  QT_IM_MODULE=fcitx
  ```

### 2. 字体（step_fonts）

- **向导位置**：输入法步骤之后
- **交互方式**：多选可不选列表，自动选中推荐项
- **基础字体**（单选或多选）：

  | 包名 | 说明 | 推荐 |
  |------|------|------|
  | `noto-fonts` + `noto-fonts-emoji` | Google Noto 全系列，覆盖广 | ✅ 推荐 |
  | `ttf-liberation` | Liberation 字体族 | |
  | `ttf-dejavu` | DejaVu 字体族 | |

- **Nerd Fonts**（单选或多选）：

  | 包名 | 说明 | 推荐 |
  |------|------|------|
  | `ttf-jetbrains-mono-nerd` | JetBrains Mono + Nerd 图标 | ✅ 推荐 |
  | `ttf-firacode-nerd` | Fira Code + Nerd 图标 | |
  | `ttf-hack-nerd` | Hack + Nerd 图标 | |

### 3. 声卡固件（step_audio_firmware）

- **向导位置**：靠近 `step_gpu_drivers`，在其之后
- **条件**：始终显示
- **检测方式**：类似现有 `detect_gpu()` 的实现，使用 `lspci | grep -i audio` 或 `aplay -l` 检测声卡硬件
- **交互方式**：多选可不选列表，根据检测结果自动选中推荐项
- **主要固件包**：

  | 包名 | 适用场景 |
  |------|---------|
  | `sof-firmware` | Intel SOF 平台，大多数现代 Intel 笔记本 |
  | `alsa-firmware` | 部分老设备 |

### 4. Polkit Agent（step_polkit_agent）

- **向导位置**：`step_desktop_env` 及条件步骤（compositor/terminal）之后
- **条件**：非 `minimal`（无桌面环境不需要 polkit agent）
- **交互方式**：单选必选列表，自动选中推荐项
- **注意**：需确认 DMS / Exo 方案是否已内置 polkit agent，若已内置则跳过此步骤
- **Niri WM 推荐选项**：

  | 包名 | 说明 |
  |------|------|
  | `mate-polkit` | 轻量，推荐 |
  | `polkit-gnome` | GNOME polkit agent |

### 5. Keyring（step_keyring）

- **向导位置**：`step_desktop_env` 及条件步骤之后（与 polkit 相邻）
- **条件**：非 `minimal`
- **交互方式**：单选必选列表，自动选中推荐项
- **选项**：

  | 包名 | 说明 | 推荐 |
  |------|------|------|
  | `gnome-keyring` | 适用于大多数 WM/DE | ✅ 推荐 |
  | `kwallet` | KDE 环境专用 | |

### 6. 远程桌面（step_remote_desktop）

- **向导位置**：`step_browser` 之后
- **交互方式**：多选可不选列表
- **选项**：

  | 包名 | 说明 | 来源 |
  |------|------|------|
  | `remmina` + `freerdp` | RDP/VNC 客户端 | `extra` |
  | `parsec-bin` | 低延迟游戏串流 | AUR |
  | `moonlight-qt` | NVIDIA GameStream / Sunshine 客户端 | `extra` |
  | `rustdesk` | 开源远程桌面 | AUR |

### 7. 文件管理器（step_file_manager）

- **向导位置**：`step_desktop_env` 及条件步骤之后
- **条件**：选择了 WM 环境
- **交互方式**：多选可不选列表
- 命令行选项：`yazi`、`ranger` 等
- 图形化选项：`dolphin`、`thunar`、`nautilus` 等
- 若选择了 `minimal`，默认安装 `yazi`

### 8. 代理工具（step_proxy_tools）

- **向导位置**：`step_region`（步骤 3）之后，因为依赖地区选择
- **条件**：地区选择了 China
- **交互方式**：单选或不选列表，默认选中 `flclash`
- **选项**：

  | 包名 | 说明 | 来源 | 推荐 |
  |------|------|------|------|
  | `flclash` | Flutter Clash GUI 客户端 | archlinuxcn | ✅ 推荐（已在 archlinuxcn 仓库） |
  | `mihomo` | CLI 代理内核（无 GUI） | archlinuxcn | CLI 用户备选 |
  | `mihomo-party-bin` | Mihomo GUI 客户端 | AUR | |
  | `clash-verge-rev-bin` | Clash Verge GUI 客户端 | AUR | |

- **备注**：非 CN 用户也可能需要代理工具，但优先级较低，暂维持仅 CN 地区触发

---

## 需要新增的大分支步骤

### 设备用途（step_device_purpose）

- **向导位置**：桌面环境 + compositor/terminal 条件步骤之后，`step_browser` 之前
- **交互方式**：多选可不选列表
- **选项**：开发、游戏、影音设计、工业设计 等

#### 架构设计注意事项

- 当前向导已有 14 步，加上用途分支子选项可能达到 20+ 步。需考虑：
  - 分组/折叠展示，避免用户疲劳
  - 用途子选项可合并为单步多选，减少步骤数
- **multilib（步骤 6）必须保持独立**：
  - 非游戏用户也可能需要 multilib（Wine、32 位兼容等）
  - 游戏选项应在 multilib 启用之后出现，但不应将 multilib 移入游戏分支

#### 各用途子选项

**开发（step_dev_tools）**：

- 条件：用途选择了"开发"
- 可进一步分为"开发环境"和"开发编辑器"两步
- 开发环境（多选可不选）：

  | 包名 | 说明 | 安装后操作 |
  |------|------|----------|
  | `bat` | cat 替代 | 纯安装 |
  | `eza` | ls 替代 | 纯安装 |
  | `ripgrep` | grep 替代 | 纯安装 |
  | `docker` | 容器运行时 | 需 `systemctl enable docker` |
  | `go` | Go 语言 | 纯安装 |
  | `bun` | Bun JS 运行时 | 纯安装 |
  | `nodejs` + `npm` | Node.js | 纯安装 |
  | `python` + `python-pip` | Python 3 | 纯安装 |
  | `rustup` | Rust 工具链管理 | 纯安装，需 `rustup default stable` |

- 开发编辑器（多选可不选）：

  | 包名 | 说明 | 来源 |
  |------|------|------|
  | `visual-studio-code-bin` | VS Code | AUR |
  | `jetbrains-toolbox` | JetBrains 全家桶管理器 | AUR |

- **注意**：需区分纯安装包和需要 `systemctl enable` 的服务包，实现时统一处理服务启用

**游戏（step_gaming）**：

- 条件：用途选择了"游戏"，且 multilib 已启用
- 选项（多选可不选）：

  | 包名 | 说明 |
  |------|------|
  | `steam` | Steam 客户端（需 multilib） |
  | `lutris` | 游戏管理器 |
  | `gamemode` + `lib32-gamemode` | Feral GameMode |
  | `mangohud` + `lib32-mangohud` | 性能 HUD |

**影音设计** / **工业设计**：具体子选项待定，后续补充

---

## 新步骤插入顺序建议

完整向导步骤排序（含新增步骤）：

| 序号 | 步骤 ID | 说明 | 条件 |
|------|---------|------|------|
| 1 | `step_language` | 语言选择 | — |
| 2 | **`step_input_method`** 🆕 | 输入法选择 | 非英文语言 |
| 3 | `step_kmscon_font` | CJK 控制台字体 | 非英文语言 |
| 4 | **`step_fonts`** 🆕 | 基础字体 + Nerd Fonts | — |
| 5 | `step_region` | 地区选择 | — |
| 6 | **`step_proxy_tools`** 🆕 | 代理工具 | CN 地区 |
| 7 | `step_disk` | 磁盘选择 | — |
| 8 | `step_network` | 网络后端 | — |
| 9 | `step_repos` | multilib 仓库 | — |
| 10 | `step_gpu_drivers` | GPU 驱动 | — |
| 11 | **`step_audio_firmware`** 🆕 | 声卡固件 | — |
| 12 | `step_desktop_env` | 桌面环境 | — |
| 13 | `step_dms_compositor` | DMS 合成器 | desktop = dms / dms_manual |
| 14 | `step_dms_terminal` | DMS 终端 | desktop = dms/dms_manual |
| 15 | **`step_polkit_agent`** 🆕 | Polkit Agent | 非 minimal |
| 16 | **`step_keyring`** 🆕 | Keyring 存储 | 非 minimal |
| 17 | **`step_file_manager`** 🆕 | 文件管理器 | WM 环境 |
| 18 | **`step_device_purpose`** 🆕 | 设备用途（多选） | — |
| 19 | **`step_dev_tools`** 🆕 | 开发工具 | 用途含"开发" |
| 20 | **`step_gaming`** 🆕 | 游戏工具 | 用途含"游戏" |
| 21 | `step_browser` | 浏览器 | — |
| 22 | **`step_remote_desktop`** 🆕 | 远程桌面 | — |
| 23 | `step_username` | 用户名 | — |
| 24 | `step_user_password` | 用户密码 | — |
| 25 | `step_root_password` | Root 密码 | — |
| — | **Confirm panel** | install / advanced / cancel | — |

共计 25 步（其中 11 步为新增），多数新增步骤为条件触发，实际用户体验约 15-18 步。
