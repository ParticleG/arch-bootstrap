#!/bin/bash
# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║  archinstall-template.sh — Archinstall 4.1 Interactive Configuration Generator
# ║  Generates user_configuration.json & user_credentials.json                  ║
# ║  Run from Arch ISO or a running Arch system                                 ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝
set -euo pipefail

# ─── Source UI library ───
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/ui.sh"

# ─── Initialize logging ───
ui::log_init "/tmp/archinstall-template-$(date '+%Y%m%d-%H%M%S').log"

# ─── Enable fullscreen fzf with progress panel ───
ui::fullscreen "Archinstall 4.1 Config"
ui::progress_init

# ═══════════════════════════════════════════════════════════════════════════════
# Banner — Arch logo (left) + FIGlet text (right)
# ═══════════════════════════════════════════════════════════════════════════════

# Use $'...' for actual ESC bytes so printf %s outputs them correctly
# (avoids echo -e issues with backslashes in figlet text)
_BC=$'\033[1;36m'  _BB=$'\033[1;34m'  _BM=$'\033[1;35m'
_BD=$'\033[2m'     _BR=$'\033[0m'

cat << EOF
${_BC}                    -@                ${_BR}   ${_BB}  ___           _       _     _                                ${_BR}
${_BC}                   .##@               ${_BR}   ${_BB} / _ \         | |     | |   (_)                               ${_BR}
${_BC}                  .####@              ${_BR}   ${_BB}/ /_\ \_ __ ___| |__   | |    _ _ __  _   ___  __              ${_BR}
${_BC}                  @#####@             ${_BR}   ${_BB}|  _  | '__/ __| '_ \  | |   | | '_ \| | | \ \/ /              ${_BR}
${_BC}                . *######@            ${_BR}   ${_BB}| | | | | | (__| | | | | |___| | | | | |_| |>  <               ${_BR}
${_BC}               .##@o@#####@           ${_BR}   ${_BB}\_| |_/_|  \___|_| |_| \_____/_|_| |_|\__,_/_/\_\              ${_BR}
${_BC}              /############@          ${_BR}   ${_BM}                                                               ${_BR}
${_BC}             /##############@         ${_BR}   ${_BM}______             _       _                                   ${_BR}
${_BC}            @######@**%######@        ${_BR}   ${_BM}| ___ \           | |     | |                                  ${_BR}
${_BC}           @######\`     %#####o       ${_BR}   ${_BM}| |_/ / ___   ___ | |_ ___| |_ _ __ __ _ _ __  _ __   ___ _ __ ${_BR}
${_BC}          @######@       ######%      ${_BR}   ${_BM}| ___ \/ _ \ / _ \| __/ __| __| '__/ _\` | '_ \| '_ \ / _ \ '__|${_BR}
${_BC}        -@#######h       ######@.\`    ${_BR}   ${_BM}| |_/ / (_) | (_) | |_\__ \ |_| | | (_| | |_) | |_) |  __/ |   ${_BR}
${_BC}       /#####h**\`\`       \`**%@####@   ${_BR}   ${_BM}\____/ \___/ \___/ \__|___/\__|_|  \__,_| .__/| .__/ \___|_|   ${_BR}
${_BC}      @H@*\`                    \`*%#@  ${_BR}   ${_BM}                                        | |   | |              ${_BR}
${_BC}     *\`                            \`* ${_BR}   ${_BM}                                        |_|   |_|              ${_BR}
EOF

echo ""
echo "  ${_BD}Archinstall 4.1 Configuration Generator${_BR}"
echo ""
unset _BC _BB _BM _BD _BR

# ═══════════════════════════════════════════════════════════════════════════════
# §0. Privilege Check
# ═══════════════════════════════════════════════════════════════════════════════

ui::require_root || exit 1

# ═══════════════════════════════════════════════════════════════════════════════
# §1. Select System Language
# ═══════════════════════════════════════════════════════════════════════════════

ui::section "语言 / Language" "选择系统语言 (locale)"

SYS_LANG=$(ui::select "系统语言 System Language" \
    "简体中文  zh_CN.UTF-8|zh_CN.UTF-8" \
    "English   en_US.UTF-8|en_US.UTF-8" \
    "日本語    ja_JP.UTF-8|ja_JP.UTF-8") || SYS_LANG="zh_CN.UTF-8"

ui::success "语言: ${SYS_LANG}"
ui::progress_set "语言 Language" "${SYS_LANG}"

# ═══════════════════════════════════════════════════════════════════════════════
# §2. Select Target Disk (with preview)
# ═══════════════════════════════════════════════════════════════════════════════

ui::section "磁盘 / Disk" "选择安装目标磁盘"

# Build disk list dynamically
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

# Preview command shows detailed partition/filesystem info for the selected disk
TARGET_DISK=$(ui::select_with_preview "安装目标磁盘 Target Disk" \
    "lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL /dev/{}" \
    "${DISK_ITEMS[@]}") || {
    ui::warn "No disk selected, defaulting to first available disk"
    TARGET_DISK=$(echo "${DISK_ITEMS[0]}" | cut -d'|' -f2)
}

TARGET_DEV="/dev/${TARGET_DISK}"

if [[ ! -b "$TARGET_DEV" ]]; then
    ui::error "${TARGET_DEV} does not exist"
    exit 1
fi

ui::success "目标磁盘: ${TARGET_DEV}"
ui::progress_set "磁盘 Disk" "${TARGET_DEV}"

# ═══════════════════════════════════════════════════════════════════════════════
# §3. Select Network Backend
# ═══════════════════════════════════════════════════════════════════════════════

ui::section "网络 / Network" "选择网络管理方式"

NET_TYPE=$(ui::select "网络后端 Network Backend" \
    "NetworkManager + iwd  (推荐，更省电)|nm_iwd" \
    "NetworkManager + wpa_supplicant  (传统)|nm") || NET_TYPE="nm_iwd"

ui::success "网络: ${NET_TYPE}"
ui::progress_set "网络 Network" "${NET_TYPE}"

# ═══════════════════════════════════════════════════════════════════════════════
# §4. Optional Repositories
# ═══════════════════════════════════════════════════════════════════════════════

ui::section "仓库 / Repositories" "选择要启用的可选仓库"

OPTIONAL_REPOS=""
if ui::confirm "启用 multilib 仓库? (32 位兼容，如 Steam)" "Y"; then
    OPTIONAL_REPOS='"multilib"'
    ui::success "multilib: 已启用"
    ui::progress_set "Multilib" "已启用"
else
    ui::log "multilib: 未启用"
    ui::progress_set "Multilib" "未启用"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# §5. Extra Packages (auto-detect based on language)
# ═══════════════════════════════════════════════════════════════════════════════

EXTRA_PACKAGES='"neovim", "git", "7zip", "base-devel", "zsh"'
NEED_KMSCON=false

if [[ "$SYS_LANG" != "en_US.UTF-8" ]]; then
    EXTRA_PACKAGES="${EXTRA_PACKAGES}, \"kmscon\""
    NEED_KMSCON=true
    ui::log "已自动添加 ${UI_BOLD}kmscon${UI_NC} 用于非英文 TTY 显示支持"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# §6. Partition Calculation
# ═══════════════════════════════════════════════════════════════════════════════

ui::step 1 2 "Reading disk geometry..."

DISK_SIZE_BYTES=$($SUDO blockdev --getsize64 "$TARGET_DEV")
# EFI: 1GiB starting at 1MiB
EFI_START_BYTES=1048576
EFI_SIZE_GIB=1
BTRFS_START_BYTES=$((EFI_START_BYTES + EFI_SIZE_GIB * 1073741824))
BTRFS_SIZE_BYTES=$((DISK_SIZE_BYTES - BTRFS_START_BYTES))

DISK_SIZE_HUMAN=$(numfmt --to=iec-i --suffix=B "$DISK_SIZE_BYTES" 2>/dev/null || echo "${DISK_SIZE_BYTES} bytes")
BTRFS_SIZE_HUMAN=$(numfmt --to=iec-i --suffix=B "$BTRFS_SIZE_BYTES" 2>/dev/null || echo "${BTRFS_SIZE_BYTES} bytes")

ui::step 2 2 "Partition layout calculated"
ui::info_kv "EFI" "1 GiB" "(FAT32, /boot)"
ui::info_kv "Btrfs" "${BTRFS_SIZE_HUMAN}" "(compress=zstd, subvols: @ @home @log @pkg)"

# ═══════════════════════════════════════════════════════════════════════════════
# §7. User Credentials
# ═══════════════════════════════════════════════════════════════════════════════

ui::section "用户 / User Account" "配置用户名和密码"

# Smart default: SUDO_USER > USER > (no default if root)
if [[ -n "${SUDO_USER:-}" ]] && [[ "$SUDO_USER" != "root" ]]; then
    DEFAULT_USER="$SUDO_USER"
elif [[ "$EUID" -ne 0 ]] && [[ -n "${USER:-}" ]]; then
    DEFAULT_USER="$USER"
else
    DEFAULT_USER=""
fi

if [[ -n "$DEFAULT_USER" ]]; then
    USERNAME=$(ui::input "用户名 Username" "$DEFAULT_USER")
else
    # No default — require input with validation
    _validate_username() {
        local u="$1"
        if [[ -z "$u" ]]; then
            echo "用户名不能为空" >&2
            return 1
        fi
        if [[ ! "$u" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
            echo "用户名只能包含小写字母、数字、下划线和连字符" >&2
            return 1
        fi
        return 0
    }
    USERNAME=$(ui::input_validate "用户名 Username" _validate_username)
fi

ui::success "用户名: ${USERNAME}"
ui::progress_set "用户 User" "${USERNAME}"

# Passwords
echo ""
USER_PASSWORD=$(ui::password "用户密码 User Password")
while [[ -z "$USER_PASSWORD" ]]; do
    ui::warn "用户密码不能为空"
    USER_PASSWORD=$(ui::password "用户密码 User Password")
done

ROOT_PASSWORD=$(ui::password "Root 密码 (留空则不设置)")

# Generate encrypted passwords
USER_ENC_PASSWORD=$(openssl passwd -6 -stdin <<< "$USER_PASSWORD" 2>/dev/null \
    || python3 -c "import crypt; print(crypt.crypt('$USER_PASSWORD', crypt.mksalt(crypt.METHOD_SHA512)))")

ROOT_ENC_PASSWORD=""
if [[ -n "$ROOT_PASSWORD" ]]; then
    ROOT_ENC_PASSWORD=$(openssl passwd -6 -stdin <<< "$ROOT_PASSWORD" 2>/dev/null \
        || python3 -c "import crypt; print(crypt.crypt('$ROOT_PASSWORD', crypt.mksalt(crypt.METHOD_SHA512)))")
    ui::success "Root 密码: 已设置"
    ui::progress_set "Root 密码" "已设置"
else
    ui::log "Root 密码: 未设置"
    ui::progress_set "Root 密码" "未设置"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# §8. Configuration Summary
# ═══════════════════════════════════════════════════════════════════════════════

# Build summary for both terminal output and confirm preview panel
MULTILIB_STATUS=$([ -n "$OPTIONAL_REPOS" ] && echo '已启用' || echo '未启用')
ROOT_PW_STATUS=$([ -n "$ROOT_ENC_PASSWORD" ] && echo '已设置' || echo '未设置')
KMSCON_STATUS=$([ "$NEED_KMSCON" = true ] && echo '已添加' || echo '不需要')

# Print dashboard to scrollback (visible after fzf exits)
ui::dashboard \
    "系统语言|${SYS_LANG}" \
    "目标磁盘|${TARGET_DEV} (${DISK_SIZE_HUMAN})" \
    "网络后端|${NET_TYPE}" \
    "Multilib|${MULTILIB_STATUS}" \
    "用户名|${USERNAME}" \
    "Root 密码|${ROOT_PW_STATUS}" \
    "kmscon|${KMSCON_STATUS}" \
    "版本|archinstall 4.1"

# Build ANSI-formatted summary for the confirm preview panel
_summary=""
_summary+="\033[1;36m  ╔══════════════════════════════════════╗\033[0m\n"
_summary+="\033[1;36m  ║  \033[1;35mCONFIGURATION SUMMARY\033[0m\n"
_summary+="\033[1;36m  ╚══════════════════════════════════════╝\033[0m\n"
_summary+="\n"
_summary+="  \033[1;32m✔\033[0m \033[1m系统语言\033[0m    ${SYS_LANG}\n"
_summary+="  \033[1;32m✔\033[0m \033[1m目标磁盘\033[0m    ${TARGET_DEV} (${DISK_SIZE_HUMAN})\n"
_summary+="  \033[1;32m✔\033[0m \033[1m网络后端\033[0m    ${NET_TYPE}\n"
_summary+="  \033[1;32m✔\033[0m \033[1mMultilib\033[0m    ${MULTILIB_STATUS}\n"
_summary+="  \033[1;32m✔\033[0m \033[1m用户名\033[0m      ${USERNAME}\n"
_summary+="  \033[1;32m✔\033[0m \033[1mRoot 密码\033[0m   ${ROOT_PW_STATUS}\n"
_summary+="  \033[1;32m✔\033[0m \033[1mkmscon\033[0m      ${KMSCON_STATUS}\n"
_summary+="  \033[1;32m✔\033[0m \033[1m版本\033[0m        archinstall 4.1\n"
_summary+="\n"
_summary+="  \033[2m─────────────────────────────────────────\033[0m\n"
_summary+="  \033[1;34mBoot\033[0m    EFISTUB (UKI)\n"
_summary+="  \033[1;34mFS\033[0m      Btrfs + zstd + Snapper\n"
_summary+="  \033[1;34mAudio\033[0m   PipeWire\n"
_summary+="  \033[1;34mBT\033[0m      Enabled\n"

if ! ui::confirm "以上配置正确？生成 JSON 文件?" "Y" "" "$_summary"; then
    ui::warn "已取消"
    exit 0
fi

# ═══════════════════════════════════════════════════════════════════════════════
# §9. Generate user_configuration.json
# ═══════════════════════════════════════════════════════════════════════════════

ui::step 1 2 "Generating user_configuration.json..."

cat > user_configuration.json << JSONEOF
{
    "app_config": {
        "audio_config": {
            "audio": "pipewire"
        },
        "bluetooth_config": {
            "enabled": true
        },
        "power_management_config": {
            "power_management": "tuned"
        },
        "print_service_config": {
            "enabled": false
        }
    },
    "archinstall-language": "English",
    "auth_config": {},
    "bootloader_config": {
        "bootloader": "Efistub",
        "removable": false,
        "uki": true
    },
    "custom_commands": [],
    "disk_config": {
        "btrfs_options": {
            "snapshot_config": {
                "type": "Snapper"
            }
        },
        "config_type": "default_layout",
        "device_modifications": [
            {
                "device": "${TARGET_DEV}",
                "partitions": [
                    {
                        "btrfs": [],
                        "dev_path": null,
                        "flags": ["boot", "esp"],
                        "fs_type": "fat32",
                        "mount_options": [],
                        "mountpoint": "/boot",
                        "obj_id": "efi-part",
                        "size": {
                            "sector_size": {"unit": "B", "value": 512},
                            "unit": "GiB",
                            "value": 1
                        },
                        "start": {
                            "sector_size": {"unit": "B", "value": 512},
                            "unit": "MiB",
                            "value": 1
                        },
                        "status": "create",
                        "type": "primary"
                    },
                    {
                        "btrfs": [
                            {"mountpoint": "/", "name": "@"},
                            {"mountpoint": "/home", "name": "@home"},
                            {"mountpoint": "/var/log", "name": "@log"},
                            {"mountpoint": "/var/cache/pacman/pkg", "name": "@pkg"}
                        ],
                        "dev_path": null,
                        "flags": [],
                        "fs_type": "btrfs",
                        "mount_options": ["compress=zstd"],
                        "mountpoint": null,
                        "obj_id": "btrfs-part",
                        "size": {
                            "sector_size": {"unit": "B", "value": 512},
                            "unit": "B",
                            "value": ${BTRFS_SIZE_BYTES}
                        },
                        "start": {
                            "sector_size": {"unit": "B", "value": 512},
                            "unit": "B",
                            "value": ${BTRFS_START_BYTES}
                        },
                        "status": "create",
                        "type": "primary"
                    }
                ],
                "wipe": true
            }
        ]
    },
    "hostname": "archlinux",
    "kernels": ["linux"],
    "locale_config": {
        "kb_layout": "us",
        "sys_enc": "UTF-8",
        "sys_lang": "${SYS_LANG}"
    },
    "mirror_config": {
        "custom_repositories": [
            {
                "name": "archlinuxcn",
                "sign_check": "Optional",
                "sign_option": "TrustAll",
                "url": "https://repo.archlinuxcn.org/\$arch"
            }
        ],
        "custom_servers": [],
        "mirror_regions": {
            "China": [
                "https://mirrors.ustc.edu.cn/archlinux/\$repo/os/\$arch",
                "https://mirrors.tuna.tsinghua.edu.cn/archlinux/\$repo/os/\$arch",
                "https://mirrors.bfsu.edu.cn/archlinux/\$repo/os/\$arch",
                "https://mirrors.aliyun.com/archlinux/\$repo/os/\$arch",
                "https://mirrors.hit.edu.cn/archlinux/\$repo/os/\$arch",
                "https://mirrors.nju.edu.cn/archlinux/\$repo/os/\$arch",
                "https://mirrors.hust.edu.cn/archlinux/\$repo/os/\$arch",
                "https://mirrors.cqu.edu.cn/archlinux/\$repo/os/\$arch",
                "https://mirrors.xjtu.edu.cn/archlinux/\$repo/os/\$arch",
                "https://mirrors.jlu.edu.cn/archlinux/\$repo/os/\$arch",
                "https://mirrors.jcut.edu.cn/archlinux/\$repo/os/\$arch",
                "https://mirrors.qlu.edu.cn/archlinux/\$repo/os/\$arch"
            ]
        },
        "optional_repositories": [${OPTIONAL_REPOS}]
    },
    "network_config": {
        "type": "${NET_TYPE}"
    },
    "ntp": true,
    "packages": [${EXTRA_PACKAGES}],
    "parallel_downloads": 0,
    "profile_config": {
        "gfx_driver": null,
        "greeter": null,
        "profile": {
            "custom_settings": {},
            "details": [],
            "main": "Minimal"
        }
    },
    "script": null,
    "services": [],
    "swap": {
        "algorithm": "lzo-rle",
        "enabled": true
    },
    "timezone": "Asia/Shanghai",
    "version": "4.1"
}
JSONEOF

ui::success "user_configuration.json generated"

# ═══════════════════════════════════════════════════════════════════════════════
# §10. Generate user_credentials.json
# ═══════════════════════════════════════════════════════════════════════════════

ui::step 2 2 "Generating user_credentials.json..."

# Build root password line conditionally
if [[ -n "$ROOT_ENC_PASSWORD" ]]; then
    ROOT_CRED_LINE="    \"root_enc_password\": \"${ROOT_ENC_PASSWORD}\","
else
    ROOT_CRED_LINE=""
fi

cat > user_credentials.json << JSONEOF
{
${ROOT_CRED_LINE}
    "users": [
        {
            "enc_password": "${USER_ENC_PASSWORD}",
            "groups": [],
            "sudo": true,
            "username": "${USERNAME}"
        }
    ]
}
JSONEOF

# Clean up empty lines when no root password
if [[ -z "$ROOT_ENC_PASSWORD" ]]; then
    sed -i '/^$/d' user_credentials.json
fi

ui::success "user_credentials.json generated"

# ═══════════════════════════════════════════════════════════════════════════════
# §11. Output Summary
# ═══════════════════════════════════════════════════════════════════════════════

ui::box "生成完毕 / Files Generated" \
    "${UI_GREEN}✔${UI_NC}  user_configuration.json  ${UI_DIM}(系统配置)${UI_NC}" \
    "${UI_GREEN}✔${UI_NC}  user_credentials.json    ${UI_DIM}(用户凭据)${UI_NC}" \
    "" \
    "${UI_DIM}Usage:${UI_NC}" \
    "  archinstall --config user_configuration.json --creds user_credentials.json"

if [[ "$NEED_KMSCON" == true ]] && [[ ! -d /run/archiso ]]; then
    echo ""
    ui::log "提示: 安装完成首次启动后，请启用 kmscon 替代默认 TTY:"
    echo -e "      ${UI_BOLD}sudo systemctl enable --now kmscon@tty1${UI_NC}"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# §12. ISO Detection — Auto Install
# ═══════════════════════════════════════════════════════════════════════════════

if [[ -d /run/archiso ]]; then
    echo ""
    ui::section "安装 / Install" "检测到 Arch Linux ISO 安装环境"

    if ui::confirm "立刻执行 archinstall 安装?" "N"; then
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

            # archinstall 4.x mounts to /mnt/archinstall
            CHROOT_DIR="/mnt/archinstall"
            if [[ ! -d "$CHROOT_DIR/etc" ]]; then
                CHROOT_DIR="/mnt"
            fi

            if [[ -d "$CHROOT_DIR/etc" ]]; then
                ui::exe arch-chroot "$CHROOT_DIR" systemctl enable kmscon@tty1
            else
                ui::warn "未找到安装目标挂载点，请手动启用 kmscon:"
                echo -e "      ${UI_BOLD}arch-chroot /mnt systemctl enable kmscon@tty1${UI_NC}"
            fi
        fi

        # Completion banner
        echo ""
        ui::box "安装完成 / Installation Complete" \
            "${UI_GREEN}系统已安装成功${UI_NC}" \
            "" \
            "重启进入新系统:" \
            "  ${UI_BOLD}reboot${UI_NC}"

        if ui::countdown 30 "Auto-reboot" "n"; then
            reboot
        fi
    fi
fi

ui::log "Log file: $(ui::log_path)"
