#!/bin/bash
# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║  archinstall-template.sh — Archinstall 4.1 Interactive Configuration Generator
# ║  Generates user_configuration.json & user_credentials.json                  ║
# ║  Run from Arch ISO or a running Arch system                                 ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝
set -euo pipefail

# ─── Source libraries ───
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/ui.sh"
source "${SCRIPT_DIR}/lib/config.sh"
source "${SCRIPT_DIR}/lib/wizard.sh"
source "${SCRIPT_DIR}/lib/generate.sh"

# ─── Native TTY: switch to English-only option labels ───
if (( _UI_NATIVE_TTY )); then
    LANG_OPTIONS=("${LANG_OPTIONS_TTY[@]}")
    NET_OPTIONS=("${NET_OPTIONS_TTY[@]}")
fi

# ─── Initialize ───
ui::log_init "/tmp/archinstall-template-$(date '+%Y%m%d-%H%M%S').log"
ui::fullscreen "Archinstall 4.1 Config"
ui::progress_init

# ═══════════════════════════════════════════════════════════════════════════════
# Banner — Arch logo (left) + FIGlet text (right)
# ═══════════════════════════════════════════════════════════════════════════════

# Banner colors: {C}=cyan {B}=blue {M}=magenta {D}=dim {0}=reset
# Art is stored in a quoted heredoc (no expansion) to keep source clean,
# then placeholders are replaced with actual ANSI codes before printing.
_BANNER=$(cat << 'BANNER'
{C}                 -@               {0}  {B}  ___           _          _     _                                {0}
{C}                .##@              {0}  {B} / _ \         | |        | |   (_)                               {0}
{C}               .####@             {0}  {B}/ /_\ \_ __ ___| |__      | |    _ _ __  _   ___  __              {0}
{C}               @#####@            {0}  {B}|  _  | '__/ __| '_ \     | |   | | '_ \| | | \ \/ /              {0}
{C}             . *######@           {0}  {B}| | | | | | (__| | | |    | |___| | | | | |_| |>  <               {0}
{C}            .##@o@#####@          {0}  {B}\_| |_/_|  \___|_| |_|    \_____/_|_| |_|\__,_/_/\_\              {0}
{C}           /############@         {0}  {M}                                                               {0}
{C}          /##############@        {0}  {M}______             _       _                                   {0}
{C}         @######@**%######@       {0}  {M}| ___ \           | |     | |                                  {0}
{C}        @######`     %#####o      {0}  {M}| |_/ / ___   ___ | |_ ___| |_ _ __ __ _ _ __  _ __   ___ _ __ {0}
{C}       @######@       ######%     {0}  {M}| ___ \/ _ \ / _ \| __/ __| __| '__/ _` | '_ \| '_ \ / _ \ '__|{0}
{C}     -@#######h       ######@.`   {0}  {M}| |_/ / (_) | (_) | |_\__ \ |_| | | (_| | |_) | |_) |  __/ |   {0}
{C}    /#####h**``       `**%@####@  {0}  {M}\____/ \___/ \___/ \__|___/\__|_|  \__,_| .__/| .__/ \___|_|   {0}
{C}   @H@*`                    `*%#@ {0}  {M}                                        | |   | |              {0}
{C}  *`                            `*{0}  {M}                                        |_|   |_|              {0}

  {D}Archinstall 4.1 Configuration Generator{0}
BANNER
)

declare -A _BANNER_COLORS=([C]=$'\033[1;36m' [B]=$'\033[1;34m' [M]=$'\033[1;35m' [D]=$'\033[2m' [0]=$'\033[0m')
for _k in "${!_BANNER_COLORS[@]}"; do
    _BANNER="${_BANNER//\{${_k}\}/${_BANNER_COLORS[$_k]}}"
done
unset _k

_show_banner() { printf '%s\n' "$_BANNER"; }
ui::set_banner _show_banner 17
_show_banner

# ═══════════════════════════════════════════════════════════════════════════════
# Privilege check & navigation
# ═══════════════════════════════════════════════════════════════════════════════

ui::require_root || exit 1
ui::enable_nav

# ═══════════════════════════════════════════════════════════════════════════════
# Pre-computed state (before wizard)
# ═══════════════════════════════════════════════════════════════════════════════

# Smart username default
if [[ -n "${SUDO_USER:-}" ]] && [[ "$SUDO_USER" != "root" ]]; then
    DEFAULT_USER="$SUDO_USER"
elif [[ "$EUID" -ne 0 ]] && [[ -n "${USER:-}" ]]; then
    DEFAULT_USER="$USER"
else
    DEFAULT_USER=""
fi

_validate_username() {
    local u="$1"
    if [[ -z "$u" ]]; then
        echo "$(ui::t '用户名不能为空' 'Username cannot be empty')" >&2; return 1
    fi
    if [[ ! "$u" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
        echo "$(ui::t '用户名只能包含小写字母、数字、下划线和连字符' 'Only lowercase letters, digits, underscores, hyphens')" >&2; return 1
    fi
    return 0
}

# Fetch China mirrors via reflector (fallback to hardcoded CHINA_MIRRORS in config.sh)
_fetch_mirrors() {
    if ! command -v reflector &>/dev/null; then
        ui::warn "$(ui::t 'reflector 未安装，使用内置镜像列表' 'reflector not found, using built-in mirror list')"
        return 0
    fi

    ui::log "$(ui::t '正在通过 reflector 获取中国镜像并测速排序...' 'Fetching China mirrors via reflector (sorted by speed)...')"
    local output
    output=$(reflector --country China --protocol https \
        --sort rate --age 24 --number 20 --download-timeout 3 2>/dev/null) || {
        ui::warn "$(ui::t 'reflector 获取失败，使用内置镜像列表' 'reflector failed, using built-in mirror list')"
        return 0
    }

    local -a fetched=()
    local line
    while IFS= read -r line; do
        if [[ "$line" =~ ^Server\ =\ (.+)$ ]]; then
            # Escape $ → \$ so the unquoted heredoc in generate.sh outputs literal $
            local url="${BASH_REMATCH[1]}"
            url="${url//\$/\\\$}"
            fetched+=("$url")
        fi
    done <<< "$output"

    if (( ${#fetched[@]} == 0 )); then
        ui::warn "$(ui::t 'reflector 未返回任何镜像，使用内置列表' 'reflector returned no mirrors, using built-in list')"
        return 0
    fi

    CHINA_MIRRORS=("${fetched[@]}")
    ui::success "$(ui::t "获取到 ${#fetched[@]} 个镜像 (按速度排序)" "Found ${#fetched[@]} mirrors (sorted by speed)")"
}
_fetch_mirrors

# Build disk list once
declare -a DISK_ITEMS=()
while IFS= read -r line; do
    disk_name=$(echo "$line" | awk '{print $1}')
    disk_size=$(echo "$line" | awk '{print $2}')
    disk_model=$(echo "$line" | awk '{$1=$2=""; print}' | sed 's/^ *//')
    DISK_ITEMS+=("${disk_name}  ${disk_size}  ${disk_model}|${disk_name}")
done < <(lsblk -d -n -o NAME,SIZE,MODEL | grep -v loop)

if [[ ${#DISK_ITEMS[@]} -eq 0 ]]; then
    ui::error "No disks found!"
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Wizard state — per-step contribution arrays (handles back-navigation cleanly)
# ═══════════════════════════════════════════════════════════════════════════════

declare -a LANG_PACKAGES=()         # kmscon if non-English
declare -a GPU_DRIVER_PACKAGES=()   # mesa + vendor drivers
declare -a OPTIONAL_REPOS=()        # multilib if enabled
NEED_KMSCON=false
GPU_VENDORS=""

# ═══════════════════════════════════════════════════════════════════════════════
# Step functions — each returns 0=ok, 2=back, 130=abort
# ═══════════════════════════════════════════════════════════════════════════════

_step_language() {
    SYS_LANG=$(ui::select "$(ui::t '系统语言 System Language' 'System Language')" "${LANG_OPTIONS[@]}")
    local rc=$?; (( rc != 0 )) && return $rc

    ui::success "$(ui::t "语言: ${SYS_LANG}" "Language: ${SYS_LANG}")"
    ui::progress_set "$(ui::t '语言 Language' 'Language')" "${SYS_LANG}"

    # Reset language-dependent packages on re-entry
    LANG_PACKAGES=()
    NEED_KMSCON=false
    if [[ "$SYS_LANG" != "en_US.UTF-8" ]]; then
        LANG_PACKAGES=("kmscon")
        NEED_KMSCON=true
        ui::log "$(ui::t "已自动添加 ${UI_BOLD}kmscon${UI_NC} 用于非英文 TTY 显示支持" "Auto-added ${UI_BOLD}kmscon${UI_NC} for non-English TTY rendering")"
    fi
    return 0
}

_step_disk() {
    TARGET_DISK=$(ui::select_with_preview "$(ui::t '安装目标磁盘 Target Disk' 'Target Disk')" \
        "lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL /dev/{}" \
        "${DISK_ITEMS[@]}")
    local rc=$?; (( rc != 0 )) && return $rc

    TARGET_DEV="/dev/${TARGET_DISK}"
    if [[ ! -b "$TARGET_DEV" ]]; then
        ui::error "${TARGET_DEV} does not exist"; exit 1
    fi

    ui::success "$(ui::t "目标磁盘: ${TARGET_DEV}" "Target disk: ${TARGET_DEV}")"
    ui::progress_set "$(ui::t '磁盘 Disk' 'Disk')" "${TARGET_DEV}"

    # Partition layout
    DISK_SIZE_BYTES=$($SUDO blockdev --getsize64 "$TARGET_DEV")
    EFI_START_BYTES=1048576
    EFI_SIZE_GIB=1
    BTRFS_START_BYTES=$((EFI_START_BYTES + EFI_SIZE_GIB * 1073741824))
    BTRFS_SIZE_BYTES=$((DISK_SIZE_BYTES - BTRFS_START_BYTES))
    DISK_SIZE_HUMAN=$(numfmt --to=iec-i --suffix=B "$DISK_SIZE_BYTES" 2>/dev/null || echo "${DISK_SIZE_BYTES} bytes")
    BTRFS_SIZE_HUMAN=$(numfmt --to=iec-i --suffix=B "$BTRFS_SIZE_BYTES" 2>/dev/null || echo "${BTRFS_SIZE_BYTES} bytes")

    ui::info_kv "EFI" "1 GiB" "(FAT32, /boot)"
    ui::info_kv "Btrfs" "${BTRFS_SIZE_HUMAN}" "(compress=zstd, subvols: @ @home @log @pkg)"
    return 0
}

_step_network() {
    NET_TYPE=$(ui::select "$(ui::t '网络后端 Network Backend' 'Network Backend')" "${NET_OPTIONS[@]}")
    local rc=$?; (( rc != 0 )) && return $rc

    ui::success "$(ui::t "网络: ${NET_TYPE}" "Network: ${NET_TYPE}")"
    ui::progress_set "$(ui::t '网络 Network' 'Network')" "${NET_TYPE}"
    return 0
}

_step_repos() {
    local rc=0
    ui::confirm "$(ui::t '启用 multilib 仓库? (32 位兼容，如 Steam)' 'Enable multilib repo? (32-bit compat, e.g. Steam)')" "Y" || rc=$?
    if (( rc == 2 || rc == 130 )); then return $rc; fi

    if (( rc == 0 )); then
        OPTIONAL_REPOS=("multilib")
        ui::success "$(ui::t 'multilib: 已启用' 'multilib: enabled')"
        ui::progress_set "Multilib" "$(ui::t '已启用' 'Enabled')"
    else
        OPTIONAL_REPOS=()
        ui::log "$(ui::t 'multilib: 未启用' 'multilib: not enabled')"
        ui::progress_set "Multilib" "$(ui::t '未启用' 'Not enabled')"
    fi
    return 0
}

_step_gpu_drivers() {
    # Auto-detect GPU vendors via lspci
    local preselect="" lspci_out=""
    if command -v lspci &>/dev/null; then
        lspci_out=$(lspci 2>/dev/null || true)
    fi
    for vendor in "${GPU_VENDOR_ORDER[@]}"; do
        if echo "$lspci_out" | grep -qiE "${GPU_DETECT[$vendor]}"; then
            preselect+="${vendor},"
        fi
    done
    preselect="${preselect%,}"

    # Build checklist items from config data
    local -a checklist_items=()
    for vendor in "${GPU_VENDOR_ORDER[@]}"; do
        checklist_items+=("${vendor}|${GPU_LABELS[$vendor]}")
    done

    local -a selected_vendors=()
    readarray -t selected_vendors < <(ui::checklist "$(ui::t '显卡驱动 GPU Drivers' 'GPU Drivers')" "$preselect" \
        "${checklist_items[@]}")
    local rc=$?; (( rc != 0 )) && return $rc

    # Reset on re-entry, always include common packages
    GPU_DRIVER_PACKAGES=()
    local pkg
    for pkg in ${GPU_PACKAGES[common]}; do
        GPU_DRIVER_PACKAGES+=("$pkg")
    done

    # Append vendor-specific packages
    GPU_VENDORS=""
    for v in "${selected_vendors[@]}"; do
        [[ -z "$v" ]] && continue
        if [[ -n "${GPU_PACKAGES[$v]:-}" ]]; then
            for pkg in ${GPU_PACKAGES[$v]}; do
                GPU_DRIVER_PACKAGES+=("$pkg")
            done
            GPU_VENDORS+="${GPU_LABELS[$v]%% *} "  # short name: "AMD" "Intel" "NVIDIA"
        fi
    done
    GPU_VENDORS="${GPU_VENDORS% }"

    if [[ -n "$GPU_VENDORS" ]]; then
        ui::success "$(ui::t "显卡驱动: ${GPU_VENDORS}" "GPU drivers: ${GPU_VENDORS}")"
        ui::progress_set "$(ui::t '显卡 GPU' 'GPU')" "${GPU_VENDORS}"
    else
        ui::log "$(ui::t '显卡驱动: 仅 mesa (通用)' 'GPU drivers: mesa only (generic)')"
        ui::progress_set "$(ui::t '显卡 GPU' 'GPU')" "$(ui::t 'mesa (通用)' 'mesa (generic)')"
    fi
    return 0
}

_step_username() {
    if [[ -n "$DEFAULT_USER" ]]; then
        USERNAME=$(ui::input "$(ui::t '用户名 Username' 'Username')" "$DEFAULT_USER")
    else
        USERNAME=$(ui::input_validate "$(ui::t '用户名 Username' 'Username')" _validate_username)
    fi
    local rc=$?; (( rc != 0 )) && return $rc

    ui::success "$(ui::t "用户名: ${USERNAME}" "Username: ${USERNAME}")"
    ui::progress_set "$(ui::t '用户 User' 'User')" "${USERNAME}"
    return 0
}

_step_user_password() {
    USER_PASSWORD=$(ui::password "$(ui::t '用户密码 User Password' 'User Password')")
    local rc=$?; (( rc != 0 )) && return $rc

    while [[ -z "$USER_PASSWORD" ]]; do
        ui::warn "$(ui::t '用户密码不能为空' 'User password cannot be empty')" > /dev/tty
        USER_PASSWORD=$(ui::password "$(ui::t '用户密码 User Password' 'User Password')")
        rc=$?; (( rc != 0 )) && return $rc
    done

    ui::progress_set "$(ui::t '用户密码' 'Password')" "$(ui::t '已设置' 'Set')"
    return 0
}

_step_root_password() {
    ROOT_PASSWORD=$(ui::password "$(ui::t 'Root 密码 (留空则不设置)' 'Root Password (empty = none)')")
    local rc=$?; (( rc != 0 )) && return $rc

    if [[ -n "$ROOT_PASSWORD" ]]; then
        ui::success "$(ui::t 'Root 密码: 已设置' 'Root password: set')"
        ui::progress_set "$(ui::t 'Root 密码' 'Root Passwd')" "$(ui::t '已设置' 'Set')"
    else
        ui::log "$(ui::t 'Root 密码: 未设置' 'Root password: not set')"
        ui::progress_set "$(ui::t 'Root 密码' 'Root Passwd')" "$(ui::t '未设置' 'Not set')"
    fi
    return 0
}

_step_confirm() {
    local multilib_status root_pw_status kmscon_status gpu_status
    multilib_status=$([[ ${#OPTIONAL_REPOS[@]} -gt 0 ]] && echo "$(ui::t '已启用' 'Enabled')" || echo "$(ui::t '未启用' 'Not enabled')")
    root_pw_status=$([[ -n "${ROOT_PASSWORD:-}" ]] && echo "$(ui::t '已设置' 'Set')" || echo "$(ui::t '未设置' 'Not set')")
    kmscon_status=$([[ "${NEED_KMSCON:-false}" == true ]] && echo "$(ui::t '已添加' 'Added')" || echo "$(ui::t '不需要' 'Not needed')")
    gpu_status="${GPU_VENDORS:-$(ui::t 'mesa (通用)' 'mesa (generic)')}"

    # Build summary items (single source for dashboard + preview)
    local -a summary_items=(
        "$(ui::t '系统语言' 'Language')|${SYS_LANG}"
        "$(ui::t '目标磁盘' 'Disk')|${TARGET_DEV} (${DISK_SIZE_HUMAN})"
        "$(ui::t '网络后端' 'Network')|${NET_TYPE}"
        "Multilib|${multilib_status}"
        "$(ui::t '显卡驱动' 'GPU Drivers')|${gpu_status}"
        "$(ui::t '用户名' 'Username')|${USERNAME}"
        "$(ui::t 'Root 密码' 'Root Passwd')|${root_pw_status}"
        "kmscon|${kmscon_status}"
        "$(ui::t '版本' 'Version')|archinstall 4.1"
    )

    ui::dashboard "${summary_items[@]}"

    local _summary
    _summary=$(generate::build_confirm_preview "${summary_items[@]}")

    local rc=0
    ui::confirm "$(ui::t '以上配置正确？生成 JSON 文件?' 'Confirm configuration? Generate JSON files?')" "Y" "" "$_summary" || rc=$?
    case $rc in
        0)   return 0 ;;
        1)   ui::warn "$(ui::t '已取消' 'Cancelled')"; exit 0 ;;
        2)   return 2 ;;
        130) return 130 ;;
        *)   return $rc ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# Register wizard steps & run
# ═══════════════════════════════════════════════════════════════════════════════

wizard::register "$(ui::t '语言'     'Language')"    _step_language
wizard::register "$(ui::t '磁盘'     'Disk')"        _step_disk
wizard::register "$(ui::t '网络'     'Network')"     _step_network
wizard::register "$(ui::t '仓库'     'Repos')"       _step_repos
wizard::register "$(ui::t '显卡'     'GPU')"         _step_gpu_drivers
wizard::register "$(ui::t '用户名'   'Username')"    _step_username
wizard::register "$(ui::t '用户密码' 'Password')"    _step_user_password
wizard::register "$(ui::t 'Root密码' 'Root Passwd')" _step_root_password
wizard::register "$(ui::t '确认'     'Confirm')"     _step_confirm

wizard::run

# ═══════════════════════════════════════════════════════════════════════════════
# Generate JSON files
# ═══════════════════════════════════════════════════════════════════════════════

ui::step 1 2 "Generating user_configuration.json..."
generate::user_configuration
ui::success "user_configuration.json generated"

ui::step 2 2 "Generating user_credentials.json..."
generate::user_credentials
ui::success "user_credentials.json generated"

# ═══════════════════════════════════════════════════════════════════════════════
# Output summary
# ═══════════════════════════════════════════════════════════════════════════════

ui::box "$(ui::t '生成完毕 / Files Generated' 'Files Generated')" \
    "${UI_GREEN}✔${UI_NC}  user_configuration.json  ${UI_DIM}$(ui::t '(系统配置)' '(system config)')${UI_NC}" \
    "${UI_GREEN}✔${UI_NC}  user_credentials.json    ${UI_DIM}$(ui::t '(用户凭据)' '(credentials)')${UI_NC}" \
    "" \
    "${UI_DIM}Usage:${UI_NC}" \
    "  archinstall --config user_configuration.json --creds user_credentials.json"

if [[ "$NEED_KMSCON" == true ]] && [[ ! -d /run/archiso ]]; then
    echo ""
    ui::log "$(ui::t '提示: 安装完成首次启动后，请启用 kmscon 替代默认 TTY:' 'Hint: After first boot, enable kmscon to replace default TTY:')"
    echo -e "      ${UI_BOLD}sudo systemctl enable --now kmscon@tty1${UI_NC}"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# ISO detection — auto install
# ═══════════════════════════════════════════════════════════════════════════════

if [[ -d /run/archiso ]]; then
    echo ""
    ui::section "$(ui::t '安装 / Install' 'Install')" "$(ui::t '检测到 Arch Linux ISO 安装环境' 'Arch Linux ISO environment detected')"

    if ui::confirm "$(ui::t '立刻执行 archinstall 安装?' 'Run archinstall now?')" "N"; then
        ui::divider "archinstall"
        ui::log "Starting archinstall..."
        echo ""

        INSTALL_EXIT=0
        archinstall --config user_configuration.json --creds user_credentials.json || INSTALL_EXIT=$?

        if [[ $INSTALL_EXIT -ne 0 ]]; then
            ui::error "archinstall exited with code ${INSTALL_EXIT}"
            exit $INSTALL_EXIT
        fi

        ui::success "archinstall completed successfully"

        # Post-install: enable kmscon in the new system via chroot
        if [[ "$NEED_KMSCON" == true ]]; then
            ui::step 1 1 "Enabling kmscon@tty1 in new system..."

            CHROOT_DIR="/mnt/archinstall"
            [[ ! -d "$CHROOT_DIR/etc" ]] && CHROOT_DIR="/mnt"

            if [[ -d "$CHROOT_DIR/etc" ]]; then
                ui::exe arch-chroot "$CHROOT_DIR" systemctl enable kmscon@tty1
            else
                ui::warn "$(ui::t '未找到安装目标挂载点，请手动启用 kmscon:' 'Mount point not found, enable kmscon manually:')"
                echo -e "      ${UI_BOLD}arch-chroot /mnt systemctl enable kmscon@tty1${UI_NC}"
            fi
        fi

        echo ""
        ui::box "$(ui::t '安装完成 / Installation Complete' 'Installation Complete')" \
            "${UI_GREEN}$(ui::t '系统已安装成功' 'System installed successfully')${UI_NC}" \
            "" \
            "$(ui::t '重启进入新系统:' 'Reboot into the new system:')" \
            "  ${UI_BOLD}reboot${UI_NC}"

        if ui::countdown 30 "Auto-reboot" "n"; then
            reboot
        fi
    fi
fi

ui::log "Log file: $(ui::log_path)"
