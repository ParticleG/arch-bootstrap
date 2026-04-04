#!/bin/bash
# 04-archinstall-template.sh - 生成 archinstall 4.1 可配置 JSON
# 用法: bash 04-archinstall-template.sh
# 在 USB 安装盘或正常系统环境中运行，交互式选择后生成 user_configuration.json 和 user_credentials.json
set -euo pipefail

# 权限处理: blockdev 等操作需要 root 权限
# 在 Live USB 中通常已是 root；在正常系统中需要 sudo
if [ "$EUID" -eq 0 ]; then
    SUDO=""
else
    if command -v sudo &>/dev/null && sudo -n true 2>/dev/null; then
        SUDO="sudo"
    else
        echo "部分操作需要 root 权限（读取磁盘信息），尝试 sudo 提权..."
        # 触发一次密码输入，后续命令在 sudo 缓存期内不再需要
        if sudo true 2>/dev/null; then
            SUDO="sudo"
        else
            echo "错误: 无法获取 root 权限，请使用 sudo 运行此脚本"
            exit 1
        fi
    fi
fi

echo "=== Archinstall 4.1 配置生成器 ==="
echo ""

# 1. 选择语言
echo "请选择系统语言:"
echo "  1) zh_CN.UTF-8 (简体中文)"
echo "  2) en_US.UTF-8 (English)"
echo "  3) ja_JP.UTF-8 (日本語)"
read -rp "选择 [1-3, 默认 1]: " LANG_CHOICE
LANG_CHOICE="${LANG_CHOICE:-1}"

case "$LANG_CHOICE" in
    1) SYS_LANG="zh_CN.UTF-8" ;;
    2) SYS_LANG="en_US.UTF-8" ;;
    3) SYS_LANG="ja_JP.UTF-8" ;;
    *) SYS_LANG="zh_CN.UTF-8" ;;
esac

# 2. 选择安装目标磁盘
echo ""
echo "可用磁盘:"
lsblk -d -o NAME,SIZE,MODEL | grep -v loop
echo ""
read -rp "请输入目标磁盘 (如 nvme1n1, sda) [默认 nvme1n1]: " TARGET_DISK
TARGET_DISK="${TARGET_DISK:-nvme1n1}"
TARGET_DEV="/dev/${TARGET_DISK}"

if [ ! -b "$TARGET_DEV" ]; then
    echo "错误: $TARGET_DEV 不存在"
    exit 1
fi

# 3. 选择网络后端
echo ""
echo "请选择网络管理方式:"
echo "  1) nm_iwd  - NetworkManager + iwd (推荐，更省电)"
echo "  2) nm      - NetworkManager + wpa_supplicant (传统)"
read -rp "选择 [1-2, 默认 1]: " NET_CHOICE
NET_CHOICE="${NET_CHOICE:-1}"

case "$NET_CHOICE" in
    1) NET_TYPE="nm_iwd" ;;
    2) NET_TYPE="nm" ;;
    *) NET_TYPE="nm_iwd" ;;
esac

# 4. 是否启用 multilib
echo ""
read -rp "是否启用 multilib 仓库 (用于 32 位兼容，如 Steam)? [Y/n]: " MULTILIB_CHOICE
MULTILIB_CHOICE="${MULTILIB_CHOICE:-Y}"

if [[ "$MULTILIB_CHOICE" =~ ^[Yy] ]]; then
    OPTIONAL_REPOS='"multilib"'
else
    OPTIONAL_REPOS=''
fi

# 5. 非英文语言时的额外包
EXTRA_PACKAGES='"neovim", "git", "7zip", "base-devel", "zsh"'
if [ "$SYS_LANG" != "en_US.UTF-8" ]; then
    EXTRA_PACKAGES="$EXTRA_PACKAGES, \"kmscon\""
    echo ""
    echo "提示: 已自动添加 kmscon 包用于非英文 TTY 显示支持"
fi

# 6. 获取磁盘大小（字节）用于分区计算
DISK_SIZE_BYTES=$($SUDO blockdev --getsize64 "$TARGET_DEV")
# EFI 分区 1GiB，起始于 1MiB
EFI_START_BYTES=1048576
EFI_SIZE_GIB=1
BTRFS_START_BYTES=$((EFI_START_BYTES + EFI_SIZE_GIB * 1073741824))
BTRFS_SIZE_BYTES=$((DISK_SIZE_BYTES - BTRFS_START_BYTES))

# 7. 设置用户凭据
echo ""
# 默认用户名: 若通过 sudo 执行则取原始用户名，直接 root 则无默认值
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
    DEFAULT_USER="$SUDO_USER"
elif [ "$EUID" -ne 0 ] && [ -n "${USER:-}" ]; then
    DEFAULT_USER="$USER"
else
    DEFAULT_USER=""
fi

if [ -n "$DEFAULT_USER" ]; then
    read -rp "请输入用户名 [默认 ${DEFAULT_USER}]: " USERNAME
    USERNAME="${USERNAME:-$DEFAULT_USER}"
else
    while true; do
        read -rp "请输入用户名: " USERNAME
        [ -n "$USERNAME" ] && break
        echo "错误: 用户名不能为空"
    done
fi

echo ""
read -srp "请输入用户密码: " USER_PASSWORD
echo ""
read -srp "请输入 root 密码 (留空则不设置 root 密码): " ROOT_PASSWORD
echo ""

# 生成加密密码
USER_ENC_PASSWORD=$(openssl passwd -6 -stdin <<< "$USER_PASSWORD" 2>/dev/null || python3 -c "import crypt; print(crypt.crypt('$USER_PASSWORD', crypt.mksalt(crypt.METHOD_SHA512)))")
if [ -n "$ROOT_PASSWORD" ]; then
    ROOT_ENC_PASSWORD=$(openssl passwd -6 -stdin <<< "$ROOT_PASSWORD" 2>/dev/null || python3 -c "import crypt; print(crypt.crypt('$ROOT_PASSWORD', crypt.mksalt(crypt.METHOD_SHA512)))")
else
    ROOT_ENC_PASSWORD=""
fi

# 8. 生成 user_configuration.json (archinstall 4.1 格式)
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

# 9. 生成 user_credentials.json (archinstall 4.1 独立凭据文件)
# root_enc_password: 有值则写入，留空则不包含该字段（不设置 root 密码）
if [ -n "$ROOT_ENC_PASSWORD" ]; then
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

# 清理: 若无 root 密码，删除空行（root_enc_password 行为空时 cat 会产生空行）
if [ -z "$ROOT_ENC_PASSWORD" ]; then
    sed -i '/^$/d' user_credentials.json
fi

echo ""
echo "=== 配置已生成 ==="
echo "  user_configuration.json  (系统配置)"
echo "  user_credentials.json    (用户凭据)"
echo ""
echo "  系统语言: $SYS_LANG"
echo "  目标磁盘: $TARGET_DEV"
echo "  网络后端: $NET_TYPE"
echo "  multilib: $([ -n "$OPTIONAL_REPOS" ] && echo '已启用' || echo '未启用')"
echo "  用户名:   $USERNAME"
echo "  版本:     4.1"
echo ""
echo "使用方法:"
echo "  archinstall --config user_configuration.json --creds user_credentials.json"
echo ""
if [ "$SYS_LANG" != "en_US.UTF-8" ]; then
    echo "提示: 安装完成首次启动后，请启用 kmscon 替代默认 TTY:"
    echo "  sudo systemctl enable --now kmscon@tty1"
fi

# 10. 检测 ISO 安装环境并提示自动安装
NEED_KMSCON=false
if [ "$SYS_LANG" != "en_US.UTF-8" ]; then
    NEED_KMSCON=true
fi

if [ -d /run/archiso ]; then
    echo ""
    echo "检测到 Arch Linux ISO 安装环境"
    read -rp "是否立刻执行 archinstall 安装? [y/N]: " DO_INSTALL
    if [[ "$DO_INSTALL" =~ ^[Yy] ]]; then
        echo ""
        echo "开始执行 archinstall..."
        INSTALL_EXIT=0
        archinstall --config user_configuration.json --creds user_credentials.json || INSTALL_EXIT=$?

        if [ $INSTALL_EXIT -ne 0 ]; then
            echo "错误: archinstall 退出码 $INSTALL_EXIT"
            exit $INSTALL_EXIT
        fi

        # Fix 4: 安装后 chroot 启用 kmscon（仅在非英文语言时）
        if [ "$NEED_KMSCON" = true ]; then
            echo ""
            echo "安装完成，正在 chroot 启用 kmscon@tty1..."

            # archinstall 默认挂载点为 /mnt/archinstall
            CHROOT_DIR="/mnt/archinstall"
            if [ ! -d "$CHROOT_DIR/etc" ]; then
                # 回退到 /mnt
                CHROOT_DIR="/mnt"
            fi

            if [ -d "$CHROOT_DIR/etc" ]; then
                arch-chroot "$CHROOT_DIR" systemctl enable kmscon@tty1
                echo "已在新系统中启用 kmscon@tty1"
            else
                echo "警告: 未找到已安装系统的挂载点，请手动启用 kmscon:"
                echo "  arch-chroot /mnt systemctl enable kmscon@tty1"
            fi
        fi

        echo ""
        echo "=== 安装完成 ==="
        echo "可以重启进入新系统: reboot"
    fi
fi
