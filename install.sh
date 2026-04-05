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
for _i18n_f in "${SCRIPT_DIR}/lib/i18n/"*.sh; do
    source "$_i18n_f"
done
unset _i18n_f
source "${SCRIPT_DIR}/lib/config.sh"
source "${SCRIPT_DIR}/lib/wizard.sh"
source "${SCRIPT_DIR}/lib/generate.sh"

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
        echo "$(ui::t 'validate.username.empty')" >&2; return 1
    fi
    if [[ ! "$u" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
        echo "$(ui::t 'validate.username.format')" >&2; return 1
    fi
    return 0
}

# Fetch China mirrors via reflector (fallback to hardcoded CHINA_MIRRORS in config.sh)
_fetch_mirrors() {
    if ! command -v reflector &>/dev/null; then
        ui::warn "$(ui::t 'mirror.no_reflector')"
        return 0
    fi

    ui::log "$(ui::t 'mirror.fetching')"
    local output
    output=$(reflector --country China --protocol https \
        --sort rate --age 24 --number 20 --download-timeout 3 2>/dev/null) || {
        ui::warn "$(ui::t 'mirror.fetch_failed')"
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
        ui::warn "$(ui::t 'mirror.no_results')"
        return 0
    fi

    CHINA_MIRRORS=("${fetched[@]}")
    ui::success "$(ui::t 'mirror.found' "${#fetched[@]}")"
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
    # Build option array dynamically from LANG_VALUES + i18n keys
    local -a opts=()
    for val in "${LANG_VALUES[@]}"; do
        local key="opt.lang.${val%%.*}"
        opts+=("$(ui::t "$key")|${val}")
    done

    local rc=0
    SYS_LANG=$(ui::select "$(ui::t 'step.lang.title')" "${opts[@]}") || rc=$?
    (( rc != 0 )) && return $rc

    # Switch display language for all subsequent steps
    case "$SYS_LANG" in
        zh_CN*) ui::set_lang "zh" ;;
        ja_JP*) ui::set_lang "ja" ;;
        *)      ui::set_lang "en" ;;
    esac

    ui::success "$(ui::t 'step.lang.success' "$SYS_LANG")"
    ui::progress_set "$(ui::t 'nav.lang')" "${SYS_LANG}"

    # Reset language-dependent packages on re-entry
    LANG_PACKAGES=()
    NEED_KMSCON=false
    if [[ "$SYS_LANG" != "en_US.UTF-8" ]]; then
        LANG_PACKAGES=("kmscon")
        NEED_KMSCON=true
        ui::log "$(ui::t 'step.lang.kmscon' "${UI_BOLD}kmscon${UI_NC}")"
    fi
    return 0
}

_step_disk() {
    local rc=0
    TARGET_DISK=$(ui::select_with_preview "$(ui::t 'step.disk.title')" \
        "lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL /dev/{}" \
        "${DISK_ITEMS[@]}") || rc=$?
    (( rc != 0 )) && return $rc

    TARGET_DEV="/dev/${TARGET_DISK}"
    if [[ ! -b "$TARGET_DEV" ]]; then
        ui::error "${TARGET_DEV} does not exist"; exit 1
    fi

    ui::success "$(ui::t 'step.disk.success' "$TARGET_DEV")"
    ui::progress_set "$(ui::t 'nav.disk')" "${TARGET_DEV}"

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
    # Build option array dynamically from NET_VALUES + i18n keys
    local -a opts=()
    for val in "${NET_VALUES[@]}"; do
        opts+=("$(ui::t "opt.net.${val}")|${val}")
    done

    local rc=0
    NET_TYPE=$(ui::select "$(ui::t 'step.net.title')" "${opts[@]}") || rc=$?
    (( rc != 0 )) && return $rc

    ui::success "$(ui::t 'step.net.success' "$NET_TYPE")"
    ui::progress_set "$(ui::t 'nav.net')" "${NET_TYPE}"
    return 0
}

_step_repos() {
    local rc=0
    ui::confirm "$(ui::t 'step.repos.confirm')" "Y" || rc=$?
    if (( rc == 2 || rc == 130 )); then return $rc; fi

    if (( rc == 0 )); then
        OPTIONAL_REPOS=("multilib")
        ui::success "$(ui::t 'step.repos.enabled')"
        ui::progress_set "Multilib" "$(ui::t 'status.enabled')"
    else
        OPTIONAL_REPOS=()
        ui::log "$(ui::t 'step.repos.disabled')"
        ui::progress_set "Multilib" "$(ui::t 'status.not_enabled')"
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
    local checklist_out=""
    local rc=0
    checklist_out=$(ui::checklist "$(ui::t 'step.gpu.title')" "$preselect" \
        "${checklist_items[@]}") || rc=$?
    (( rc != 0 )) && return $rc
    readarray -t selected_vendors <<< "$checklist_out"

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
        ui::success "$(ui::t 'step.gpu.success' "$GPU_VENDORS")"
        ui::progress_set "$(ui::t 'nav.gpu')" "${GPU_VENDORS}"
    else
        ui::log "$(ui::t 'step.gpu.mesa_only')"
        ui::progress_set "$(ui::t 'nav.gpu')" "$(ui::t 'step.gpu.mesa_generic')"
    fi
    return 0
}

_step_username() {
    local rc=0
    if [[ -n "$DEFAULT_USER" ]]; then
        USERNAME=$(ui::input "$(ui::t 'step.user.title')" "$DEFAULT_USER") || rc=$?
    else
        USERNAME=$(ui::input_validate "$(ui::t 'step.user.title')" _validate_username) || rc=$?
    fi
    (( rc != 0 )) && return $rc

    ui::success "$(ui::t 'step.user.success' "$USERNAME")"
    ui::progress_set "$(ui::t 'nav.user')" "${USERNAME}"
    return 0
}

_step_user_password() {
    local rc=0
    USER_PASSWORD=$(ui::password "$(ui::t 'step.passwd.title')") || rc=$?
    (( rc != 0 )) && return $rc

    while [[ -z "$USER_PASSWORD" ]]; do
        ui::warn "$(ui::t 'step.passwd.empty')" > /dev/tty
        rc=0
        USER_PASSWORD=$(ui::password "$(ui::t 'step.passwd.title')") || rc=$?
        (( rc != 0 )) && return $rc
    done

    ui::progress_set "$(ui::t 'nav.passwd')" "$(ui::t 'status.set')"
    return 0
}

_step_root_password() {
    local rc=0
    ROOT_PASSWORD=$(ui::password "$(ui::t 'step.root.title')") || rc=$?
    (( rc != 0 )) && return $rc

    if [[ -n "$ROOT_PASSWORD" ]]; then
        ui::success "$(ui::t 'step.root.set')"
        ui::progress_set "$(ui::t 'nav.root')" "$(ui::t 'status.set')"
    else
        ui::log "$(ui::t 'step.root.unset')"
        ui::progress_set "$(ui::t 'nav.root')" "$(ui::t 'status.not_set')"
    fi
    return 0
}

_step_confirm() {
    local multilib_status root_pw_status kmscon_status gpu_status
    multilib_status=$([[ ${#OPTIONAL_REPOS[@]} -gt 0 ]] && echo "$(ui::t 'status.enabled')" || echo "$(ui::t 'status.not_enabled')")
    root_pw_status=$([[ -n "${ROOT_PASSWORD:-}" ]] && echo "$(ui::t 'status.set')" || echo "$(ui::t 'status.not_set')")
    kmscon_status=$([[ "${NEED_KMSCON:-false}" == true ]] && echo "$(ui::t 'status.added')" || echo "$(ui::t 'status.not_needed')")
    gpu_status="${GPU_VENDORS:-$(ui::t 'step.gpu.mesa_generic')}"

    # Build summary items (single source for dashboard + preview)
    local -a summary_items=(
        "$(ui::t 'confirm.lang')|${SYS_LANG}"
        "$(ui::t 'confirm.disk')|${TARGET_DEV} (${DISK_SIZE_HUMAN})"
        "$(ui::t 'confirm.net')|${NET_TYPE}"
        "Multilib|${multilib_status}"
        "$(ui::t 'confirm.gpu')|${gpu_status}"
        "$(ui::t 'confirm.user')|${USERNAME}"
        "$(ui::t 'confirm.root')|${root_pw_status}"
        "kmscon|${kmscon_status}"
        "$(ui::t 'confirm.version')|archinstall 4.1"
    )

    ui::dashboard "${summary_items[@]}"

    local _summary
    _summary=$(generate::build_confirm_preview "${summary_items[@]}")

    local rc=0
    ui::confirm "$(ui::t 'confirm.prompt')" "Y" "" "$_summary" || rc=$?
    case $rc in
        0)   return 0 ;;
        1)   ui::warn "$(ui::t 'status.cancelled')"; exit 0 ;;
        2)   return 2 ;;
        130) return 130 ;;
        *)   return $rc ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# Register wizard steps & run
# ═══════════════════════════════════════════════════════════════════════════════

wizard::register "nav.lang"    _step_language
wizard::register "nav.disk"    _step_disk
wizard::register "nav.net"     _step_network
wizard::register "nav.repos"   _step_repos
wizard::register "nav.gpu"     _step_gpu_drivers
wizard::register "nav.user"    _step_username
wizard::register "nav.passwd"  _step_user_password
wizard::register "nav.root"    _step_root_password
wizard::register "nav.confirm" _step_confirm

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

ui::box "$(ui::t 'post.title')" \
    "${UI_GREEN}✔${UI_NC}  user_configuration.json  ${UI_DIM}$(ui::t 'post.sys_config')${UI_NC}" \
    "${UI_GREEN}✔${UI_NC}  user_credentials.json    ${UI_DIM}$(ui::t 'post.credentials')${UI_NC}" \
    "" \
    "${UI_DIM}Usage:${UI_NC}" \
    "  archinstall --config user_configuration.json --creds user_credentials.json"

if [[ "$NEED_KMSCON" == true ]] && [[ ! -d /run/archiso ]]; then
    echo ""
    ui::log "$(ui::t 'post.kmscon_hint')"
    echo -e "      ${UI_BOLD}sudo systemctl enable --now kmscon@tty1${UI_NC}"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# ISO detection — auto install
# ═══════════════════════════════════════════════════════════════════════════════

if [[ -d /run/archiso ]]; then
    echo ""
    ui::section "$(ui::t 'iso.title')" "$(ui::t 'iso.detected')"

    if ui::confirm "$(ui::t 'iso.run_now')" "N"; then
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
                ui::warn "$(ui::t 'iso.mount_not_found')"
                echo -e "      ${UI_BOLD}arch-chroot /mnt systemctl enable kmscon@tty1${UI_NC}"
            fi
        fi

        echo ""
        ui::box "$(ui::t 'iso.complete_title')" \
            "${UI_GREEN}$(ui::t 'iso.success')${UI_NC}" \
            "" \
            "$(ui::t 'iso.reboot')" \
            "  ${UI_BOLD}reboot${UI_NC}"

        if ui::countdown 30 "Auto-reboot" "n"; then
            reboot
        fi
    fi
fi

ui::log "Log file: $(ui::log_path)"
