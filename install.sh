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

# ─── Country / Region Detection & Mirror Fetching ───

# Resolve fallback mirror array for a given ISO country code.
# Falls back to MIRRORS_WORLDWIDE if no country-specific pool exists.
_get_fallback_mirrors() {
    local iso="$1"
    local arr_name="MIRRORS_${iso}"

    # Check if the country-specific array exists and has elements
    if [[ -n "$iso" ]] && declare -p "$arr_name" &>/dev/null; then
        local -n ref="${arr_name}"
        if (( ${#ref[@]} > 0 )); then
            ACTIVE_MIRRORS=("${ref[@]}")
            return 0
        fi
    fi
    ACTIVE_MIRRORS=("${MIRRORS_WORLDWIDE[@]}")
}

# Detect country via IP geolocation (lightweight, works on Arch ISO with network).
# Sets MIRROR_COUNTRY to ISO 3166-1 alpha-2 code (e.g. "CN", "US") or "" on failure.
_detect_country() {
    MIRROR_COUNTRY=""
    local iso=""

    # Try multiple geolocation services (2s timeout each)
    for url in "https://ifconfig.co/country-iso" \
               "https://ipinfo.io/country" \
               "https://icanhazip.com/country"; do
        iso=$(curl -sf --max-time 2 "$url" 2>/dev/null) && break
        iso=""
    done

    # Validate: must be exactly 2 uppercase letters
    if [[ "$iso" =~ ^[A-Z]{2}$ ]]; then
        MIRROR_COUNTRY="$iso"
    fi
}

# Fetch mirrors via reflector for the configured MIRROR_COUNTRY.
# On failure or unavailability, falls back to hardcoded per-country pools.
_fetch_mirrors() {
    local country_name="${COUNTRY_REFLECTOR_NAME[$MIRROR_COUNTRY]:-}"

    # Load fallback mirrors first (overridden if reflector succeeds)
    _get_fallback_mirrors "$MIRROR_COUNTRY"

    if ! command -v reflector &>/dev/null; then
        ui::warn "$(ui::t 'mirror.no_reflector')"
        return 0
    fi

    if [[ -z "$country_name" ]]; then
        # Unknown country — use Worldwide reflector query
        ui::log "$(ui::t 'mirror.fetching_worldwide')"
        local reflector_args=(--protocol https --sort rate --age 24 --number 20 --download-timeout 3)
    else
        ui::log "$(ui::t 'mirror.fetching_country' "$country_name")"
        local reflector_args=(--country "$country_name" --protocol https --sort rate --age 24 --number 20 --download-timeout 3)
    fi

    local output
    output=$(reflector "${reflector_args[@]}" 2>/dev/null) || {
        ui::warn "$(ui::t 'mirror.fetch_failed')"
        return 0
    }

    local -a fetched=()
    local line
    while IFS= read -r line; do
        if [[ "$line" =~ ^Server\ =\ (.+)$ ]]; then
            fetched+=("${BASH_REMATCH[1]}")
        fi
    done <<< "$output"

    if (( ${#fetched[@]} == 0 )); then
        ui::warn "$(ui::t 'mirror.no_results')"
        return 0
    fi

    ACTIVE_MIRRORS=("${fetched[@]}")
    ui::success "$(ui::t 'mirror.found' "${#fetched[@]}")"

    # Apply detected mirrors to live ISO pacman so subsequent installs (fzf,
    # archinstall upgrade, etc.) use the fast mirrors instead of ISO defaults.
    if [[ -d /run/archiso ]] && (( ${#ACTIVE_MIRRORS[@]} > 0 )); then
        local ml=""
        for m in "${ACTIVE_MIRRORS[@]}"; do
            ml+="Server = ${m}"$'\n'
        done
        printf '%s' "$ml" > /etc/pacman.d/mirrorlist
    fi
}

# Run initial detection (before wizard starts)
ui::log "$(ui::t 'region.detecting')"
_detect_country
if [[ -n "$MIRROR_COUNTRY" ]]; then
    ui::success "$(ui::t 'region.detected' "$MIRROR_COUNTRY")"
fi
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

_step_region() {
    # Build region menu: show detected country as default, plus common options
    local -a opts=()
    local detected_label=""

    for iso in "${REGION_MENU_COUNTRIES[@]}"; do
        local label="${COUNTRY_REFLECTOR_NAME[$iso]:-$iso}"
        if [[ "$iso" == "$MIRROR_COUNTRY" ]]; then
            # Mark the auto-detected country
            detected_label="$label"
            opts+=("${label} ($(ui::t 'region.auto_detected'))|${iso}")
        else
            opts+=("${label}|${iso}")
        fi
    done

    # If detected country is not in menu, prepend it
    if [[ -n "$MIRROR_COUNTRY" ]] && [[ -z "$detected_label" ]]; then
        local label="${COUNTRY_REFLECTOR_NAME[$MIRROR_COUNTRY]:-$MIRROR_COUNTRY}"
        # Insert at the beginning
        opts=("${label} ($(ui::t 'region.auto_detected'))|${MIRROR_COUNTRY}" "${opts[@]}")
    fi

    local rc=0
    local selected
    selected=$(ui::select "$(ui::t 'step.region.title')" "${opts[@]}") || rc=$?
    (( rc != 0 )) && return $rc

    # Update country and re-fetch mirrors if changed
    if [[ "$selected" != "$MIRROR_COUNTRY" ]]; then
        MIRROR_COUNTRY="$selected"
        _fetch_mirrors
    fi

    local display_name="${COUNTRY_REFLECTOR_NAME[$MIRROR_COUNTRY]:-$MIRROR_COUNTRY}"
    local tz="${COUNTRY_TIMEZONE[$MIRROR_COUNTRY]:-UTC}"
    ui::success "$(ui::t 'step.region.success' "$display_name")"
    ui::progress_set "$(ui::t 'nav.region')" "${display_name}"
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
        ui::error "${TARGET_DEV} does not exist"; return 1
    fi

    ui::success "$(ui::t 'step.disk.success' "$TARGET_DEV")"
    ui::progress_set "$(ui::t 'nav.disk')" "${TARGET_DEV}"

    # Partition layout (all values aligned to 1 MiB for archinstall 4.1)
    DISK_SIZE_BYTES=$($SUDO blockdev --getsize64 "$TARGET_DEV")
    EFI_START_MIB=1
    EFI_SIZE_GIB=1
    BTRFS_START_MIB=$((EFI_START_MIB + EFI_SIZE_GIB * 1024))  # 1 + 1024 = 1025 MiB
    BTRFS_SIZE_MIB=$(((DISK_SIZE_BYTES / 1048576) - BTRFS_START_MIB - 1))  # floor to MiB, -1 MiB for GPT backup header
    DISK_SIZE_HUMAN=$(numfmt --to=iec-i --suffix=B "$DISK_SIZE_BYTES" 2>/dev/null || echo "${DISK_SIZE_BYTES} bytes")
    BTRFS_SIZE_HUMAN=$(numfmt --to=iec-i --suffix=B "$((BTRFS_SIZE_MIB * 1048576))" 2>/dev/null || echo "${BTRFS_SIZE_MIB} MiB")

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
    local preselect="" lspci_out="" lspci_nn=""
    if command -v lspci &>/dev/null; then
        lspci_out=$(lspci 2>/dev/null || true)
        lspci_nn=$(lspci -nn 2>/dev/null || true)
    fi

    # Detect non-NVIDIA vendors (AMD, Intel)
    for vendor in "${GPU_VENDOR_ORDER[@]}"; do
        [[ "$vendor" == nvidia_open || "$vendor" == nouveau ]] && continue
        if printf '%s' "$lspci_out" | grep -qiE "${GPU_DETECT[$vendor]}"; then
            preselect+="${vendor},"
        fi
    done

    # NVIDIA: decide between nvidia_open (Turing+) and nouveau (older)
    if printf '%s' "$lspci_out" | grep -qiE "${GPU_DETECT[nvidia_open]}"; then
        local nvidia_driver="nouveau"  # default to nouveau for older cards
        # Extract NVIDIA PCI Device IDs (vendor 10de) and check architecture
        # Turing (TU1xx) starts at Device ID 0x1e00; anything >= is Turing+
        local dev_id
        while IFS= read -r dev_id; do
            if (( 16#${dev_id} >= 16#1e00 )); then
                nvidia_driver="nvidia_open"
                break
            fi
        done < <(printf '%s\n' "$lspci_nn" | grep -ioE '\[10de:[0-9a-f]{4}\]' \
                   | grep -ioE '[0-9a-f]{4}\]' | tr -d ']')
        preselect+="${nvidia_driver},"
    fi
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
    USERNAME=$(ui::input_validate "$(ui::t 'step.user.title')" _validate_username "$DEFAULT_USER") || rc=$?
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

    local region_display="${COUNTRY_REFLECTOR_NAME[$MIRROR_COUNTRY]:-$MIRROR_COUNTRY}"
    local tz_display="${COUNTRY_TIMEZONE[$MIRROR_COUNTRY]:-UTC}"

    # Build summary items (single source for dashboard + preview)
    local -a summary_items=(
        "$(ui::t 'confirm.lang')|${SYS_LANG}"
        "$(ui::t 'confirm.region')|${region_display}"
        "$(ui::t 'confirm.timezone')|${tz_display}"
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
wizard::register "nav.region"  _step_region
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

        # Upgrade archinstall to latest version (ISO ships outdated 3.x)
        ui::log "Upgrading archinstall to latest version..."
        pacman -Sy --noconfirm archinstall || {
            ui::error "Failed to upgrade archinstall"
            exit 1
        }

        ui::log "Starting archinstall..."
        echo ""

        INSTALL_EXIT=0
        archinstall --config user_configuration.json --creds user_credentials.json --silent || INSTALL_EXIT=$?

        if [[ $INSTALL_EXIT -ne 0 ]]; then
            ui::error "archinstall exited with code ${INSTALL_EXIT}"
            exit $INSTALL_EXIT
        fi

        ui::success "archinstall completed successfully"

        # Post-install: set keyboard layout (skipped in archinstall to avoid
        # systemd-nspawn Boot session hang on minimal pacstrap environments)
        CHROOT_DIR="/mnt/archinstall"
        [[ ! -d "$CHROOT_DIR/etc" ]] && CHROOT_DIR="/mnt"

        if [[ -d "$CHROOT_DIR/etc" ]]; then
            ui::log "Setting keyboard layout to 'us'..."
            echo "KEYMAP=us" > "$CHROOT_DIR/etc/vconsole.conf"
        fi

        # Post-install: enable kmscon in the new system via chroot
        if [[ "$NEED_KMSCON" == true && -d "$CHROOT_DIR/etc" ]]; then
            ui::step 1 1 "Enabling kmscon@tty1 in new system..."
            ui::exe arch-chroot "$CHROOT_DIR" systemctl enable kmscon@tty1
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
