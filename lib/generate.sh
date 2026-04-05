#!/bin/bash
# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║  generate.sh — Archinstall 4.1 JSON generation & confirm preview builder     ║
# ║  Requires config.sh (data) to be sourced first                               ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

# ─── Dependencies ───
source "$(dirname "${BASH_SOURCE[0]}")/ui.sh"
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

# ─── JSON Helpers ───

# Convert a bash array to a JSON-style quoted comma-separated string.
# Usage: _json_string_array "neovim" "git" "zsh"
# Output: "neovim", "git", "zsh"
_json_string_array() {
    local first=true
    for item in "$@"; do
        $first || printf ', '
        printf '"%s"' "$item"
        first=false
    done
}

# Build JSON array lines for mirror URLs with indentation.
# URLs contain literal $repo/$arch which pass through safely because
# variable expansion results are not re-scanned in unquoted heredocs.
# Usage: _json_mirror_lines "                " "${ACTIVE_MIRRORS[@]}"
_json_mirror_lines() {
    local indent="$1"; shift
    local first=true
    for url in "$@"; do
        $first || printf ',\n'
        printf '%s"%s"' "$indent" "$url"
        first=false
    done
}

# ─── Display Width (CJK-aware) ───

# Compute display width of a string, counting non-ASCII characters as width 2.
# This is a simple heuristic that handles CJK, fullwidth, and most Unicode correctly.
# Usage: w=$(_display_width "系统语言")  # → 8
_display_width() {
    local s="$1"
    local w=0 i c
    for (( i=0; i<${#s}; i++ )); do
        c="${s:$i:1}"
        if [[ "$c" == [[:ascii:]] ]]; then
            (( w++ ))
        else
            (( w += 2 ))
        fi
    done
    echo "$w"
}

# ─── Password Encryption ───

# Encrypt a plaintext password using SHA-512.
# Requires openssl (available on all Arch installations).
# Usage: enc=$(generate::encrypt_password "mypassword")
generate::encrypt_password() {
    local password="$1"
    if ! openssl passwd -6 -stdin <<< "$password" 2>/dev/null; then
        ui::error "Password encryption failed: openssl is required"
        return 1
    fi
}

# ─── Confirm Preview Builder ───

# Build an ANSI-formatted summary string for the confirm dialog preview panel.
# Takes "label|value" pairs (same format as ui::dashboard).
# Uses FIXED_SUMMARY_KEYS / FIXED_SUMMARY_VALS from config.sh for the non-configurable section.
# Usage: preview=$(generate::build_confirm_preview "语言|zh_CN.UTF-8" "磁盘|/dev/sda" ...)
generate::build_confirm_preview() {
    local s=""

    # Header
    local preview_title
    preview_title=$(ui::t 'confirm.preview_title')
    s+="\033[1;36m  ╔══════════════════════════════════════╗\033[0m\n"
    s+="\033[1;36m  ║  \033[1;35m${preview_title}\033[0m\n"
    s+="\033[1;36m  ╚══════════════════════════════════════╝\033[0m\n"
    s+="\n"

    # Dynamic items (from wizard steps)
    for item in "$@"; do
        local label="${item%%|*}"
        local value="${item#*|}"
        local w
        w=$(_display_width "$label")
        local pad=$(( 12 - w ))
        (( pad < 1 )) && pad=1
        s+="  \033[1;32m✔\033[0m \033[1m${label}\033[0m$(printf '%*s' "$pad" '')${value}\n"
    done

    # Separator + fixed config items (non-configurable)
    s+="\n"
    s+="  \033[2m─────────────────────────────────────────\033[0m\n"
    for key in "${FIXED_SUMMARY_KEYS[@]}"; do
        local label value
        label=$(ui::t "fixed.${key}")
        value="${FIXED_SUMMARY_VALS[$key]:-}"
        local w
        w=$(_display_width "$label")
        local pad=$(( 8 - w ))
        (( pad < 1 )) && pad=1
        s+="  \033[1;34m${label}\033[0m$(printf '%*s' "$pad" '')${value}\n"
    done

    printf '%s' "$s"
}

# ─── JSON File Generation ───

# Generate user_configuration.json from collected wizard state.
# Expects these globals: TARGET_DEV, BTRFS_SIZE_MIB, BTRFS_START_MIB,
#   SYS_LANG, NET_TYPE, OPTIONAL_REPOS[], LANG_PACKAGES[], GPU_DRIVER_PACKAGES[]
# Uses config.sh data: BASE_PACKAGES[], ACTIVE_MIRRORS[], MIRROR_COUNTRY,
#   ARCHLINUXCN_URL, COUNTRY_REFLECTOR_NAME[], COUNTRY_TIMEZONE[]
generate::user_configuration() {
    # Merge all package arrays into final list
    local -a all_packages=("${BASE_PACKAGES[@]}")
    [[ ${#LANG_PACKAGES[@]} -gt 0 ]] && all_packages+=("${LANG_PACKAGES[@]}")
    [[ ${#GPU_DRIVER_PACKAGES[@]} -gt 0 ]] && all_packages+=("${GPU_DRIVER_PACKAGES[@]}")

    local packages_json
    packages_json=$(_json_string_array "${all_packages[@]}")

    local repos_json=""
    if [[ ${#OPTIONAL_REPOS[@]} -gt 0 ]]; then
        repos_json=$(_json_string_array "${OPTIONAL_REPOS[@]}")
    fi

    local mirror_lines
    mirror_lines=$(_json_mirror_lines "                " "${ACTIVE_MIRRORS[@]}")

    # Resolve country display name for JSON key (reflector name or ISO code)
    local country_key="${COUNTRY_REFLECTOR_NAME[$MIRROR_COUNTRY]:-Worldwide}"
    local timezone="${COUNTRY_TIMEZONE[$MIRROR_COUNTRY]:-UTC}"

    # Conditionally build custom_repositories JSON (archlinuxcn only for CN)
    local custom_repos_json=""
    if [[ "$MIRROR_COUNTRY" == "CN" ]]; then
        custom_repos_json=$(cat << 'CREPO'
        "custom_repositories": [
            {
                "name": "archlinuxcn",
                "sign_check": "Optional",
                "sign_option": "TrustAll",
                "url": "ARCHLINUXCN_PLACEHOLDER"
            }
        ],
CREPO
)
        custom_repos_json="${custom_repos_json//ARCHLINUXCN_PLACEHOLDER/${ARCHLINUXCN_URL}}"
    else
        custom_repos_json='        "custom_repositories": [],'
    fi

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
                            "unit": "MiB",
                            "value": ${BTRFS_SIZE_MIB}
                        },
                        "start": {
                            "sector_size": {"unit": "B", "value": 512},
                            "unit": "MiB",
                            "value": ${BTRFS_START_MIB}
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
${custom_repos_json}
        "custom_servers": [],
        "mirror_regions": {
            "${country_key}": [
${mirror_lines}
            ]
        },
        "optional_repositories": [${repos_json}]
    },
    "network_config": {
        "type": "${NET_TYPE}"
    },
    "ntp": true,
    "packages": [${packages_json}],
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
    "timezone": "${timezone}",
    "version": "4.1"
}
JSONEOF
}

# Generate user_credentials.json from collected wizard state.
# Expects globals: USERNAME, USER_PASSWORD, ROOT_PASSWORD (may be empty)
generate::user_credentials() {
    local user_enc
    user_enc=$(generate::encrypt_password "$USER_PASSWORD")

    local root_line=""
    if [[ -n "${ROOT_PASSWORD:-}" ]]; then
        local root_enc
        root_enc=$(generate::encrypt_password "$ROOT_PASSWORD")
        root_line=$'\n    '"\"root_enc_password\": \"${root_enc}\","
    fi

    ( umask 077; cat > user_credentials.json << JSONEOF
{${root_line}
    "users": [
        {
            "enc_password": "${user_enc}",
            "groups": [],
            "sudo": true,
            "username": "${USERNAME}"
        }
    ]
}
JSONEOF
    )
}
