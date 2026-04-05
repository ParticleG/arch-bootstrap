#!/bin/bash
# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║  ui.sh — Reusable TUI Visual Engine for Bash Scripts                        ║
# ║  Usage: source "$(dirname "${BASH_SOURCE[0]}")/lib/ui.sh"                   ║
# ║  Requires: bash 4.0+, coreutils; optional: fzf (auto-installed if needed)   ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

# Guard against double-sourcing
[[ -n "${_UI_LOADED:-}" ]] && return 0
_UI_LOADED=1

# ═══════════════════════════════════════════════════════════════════════════════
# §0. Native TTY Detection & Locale-Aware Text Helper
# ═══════════════════════════════════════════════════════════════════════════════

# Detect native Linux VT (framebuffer console without CJK-capable renderer).
# On native VT, non-ASCII text (CJK, etc.) cannot render — force English.
#
# Primary: TERM=linux is set by the kernel fbcon driver and is inherited
#   across all process layers (curl|bash → exec → makeself → eval)
#   regardless of fd redirections.  kmscon and terminal emulators always
#   set a different TERM value (xterm-256color, etc.).
# Fallback: resolve the terminal device attached to stderr (fd 2).
#   stdin (fd 0) may be a pipe when invoked via `curl … | bash`.
#   /dev/tty[0-9]* = native VT; /dev/pts/* = pty (emulator/SSH/kmscon).
_UI_NATIVE_TTY=0
if [[ "${TERM:-}" == "linux" ]]; then
    _UI_NATIVE_TTY=1
elif [[ -e /proc/self/fd/2 ]]; then
    _ui_tty_dev=$(readlink -f /proc/self/fd/2 2>/dev/null) || true
    [[ "${_ui_tty_dev:-}" == /dev/tty[0-9]* ]] && _UI_NATIVE_TTY=1
    unset _ui_tty_dev
fi

# Display language code: "zh", "en", "ja", etc.
# Must match the suffix of a loaded _I18N_XX associative array (uppercased).
# - Native TTY: locked to "en" (CJK cannot render on framebuffer console).
# - Non-TTY: defaults to "zh", then follows user locale choice via ui::set_lang.
_UI_LANG="zh"
(( _UI_NATIVE_TTY )) && _UI_LANG="en"

# Switch display language at runtime (e.g. after user selects locale).
# No-op on native TTY (always English — CJK rendering is impossible).
# Accepts any code with a corresponding _I18N_XX array: "zh", "en", "ja", ...
# Usage: ui::set_lang "ja"
ui::set_lang() {
    (( _UI_NATIVE_TTY )) && return 0
    _UI_LANG="$1"
}

# Look up a translated string by key, with optional printf substitution.
# Requires _I18N_XX associative arrays to be loaded (lib/i18n/*.sh).
# Fallback chain: current language → English (_I18N_EN) → raw key.
# Usage: ui::t "step.lang.title"
#        ui::t "mirror.found" "$count"        # printf %s substitution
ui::t() {
    local key="$1"; shift
    local -n _i18n_map="_I18N_${_UI_LANG^^}"
    local tpl="${_i18n_map[$key]:-}"
    # Fallback: English → raw key
    [[ -z "$tpl" ]] && tpl="${_I18N_EN[$key]:-$key}"
    if (( $# > 0 )); then
        # shellcheck disable=SC2059
        printf "$tpl" "$@"
    else
        printf '%s' "$tpl"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# §1. ANSI Colors & Styles
# ═══════════════════════════════════════════════════════════════════════════════

# Reset
export UI_NC='\033[0m'

# Styles
export UI_BOLD='\033[1m'
export UI_DIM='\033[2m'
export UI_ITALIC='\033[3m'
export UI_UNDER='\033[4m'
export UI_BLINK='\033[5m'
export UI_REVERSE='\033[7m'
export UI_STRIKE='\033[9m'

# Bright foreground
export UI_RED='\033[1;31m'
export UI_GREEN='\033[1;32m'
export UI_YELLOW='\033[1;33m'
export UI_BLUE='\033[1;34m'
export UI_PURPLE='\033[1;35m'
export UI_CYAN='\033[1;36m'
export UI_WHITE='\033[1;37m'
export UI_GRAY='\033[1;90m'

# Normal (non-bold) foreground
export UI_N_RED='\033[0;31m'
export UI_N_GREEN='\033[0;32m'
export UI_N_YELLOW='\033[0;33m'
export UI_N_BLUE='\033[0;34m'
export UI_N_PURPLE='\033[0;35m'
export UI_N_CYAN='\033[0;36m'

# Background
export UI_BG_RED='\033[41m'
export UI_BG_GREEN='\033[42m'
export UI_BG_YELLOW='\033[43m'
export UI_BG_BLUE='\033[44m'
export UI_BG_PURPLE='\033[45m'
export UI_BG_CYAN='\033[46m'
export UI_BG_WHITE='\033[47m'
export UI_BG_GRAY='\033[100m'

# ═══════════════════════════════════════════════════════════════════════════════
# §2. Unicode Symbols & Icons
# ═══════════════════════════════════════════════════════════════════════════════

export UI_TICK="${UI_GREEN}✔${UI_NC}"
export UI_CROSS="${UI_RED}✘${UI_NC}"
export UI_INFO="${UI_BLUE}ℹ${UI_NC}"
export UI_WARN="${UI_YELLOW}⚠${UI_NC}"
export UI_ARROW="${UI_CYAN}➜${UI_NC}"
export UI_BULLET="${UI_BLUE}●${UI_NC}"
export UI_STAR="${UI_YELLOW}★${UI_NC}"
export UI_DOT="${UI_GRAY}·${UI_NC}"
export UI_ELLIPSIS="${UI_GRAY}…${UI_NC}"
export UI_RANGLE="${UI_CYAN}›${UI_NC}"
export UI_LANGLE="${UI_CYAN}‹${UI_NC}"

# Spinner frames (Braille dots — smooth animation)
_UI_SPINNER=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')

# Progress bar characters
_UI_BAR_FILL='█'
_UI_BAR_HALF='▓'
_UI_BAR_EMPTY='░'

# ═══════════════════════════════════════════════════════════════════════════════
# §3. Internal Helpers
# ═══════════════════════════════════════════════════════════════════════════════

# Strip ANSI escape sequences from a string
_ui_strip_ansi() {
    local text="$1"
    printf '%s\n' "$text" | sed 's/\x1b\[[0-9;]*m//g'
}

# Visible string length (excluding ANSI codes)
_ui_strlen() {
    local stripped
    stripped=$(_ui_strip_ansi "$1")
    echo "${#stripped}"
}

# Repeat a character (or multi-byte string) N times
# Uses bash string substitution instead of tr to correctly handle
# multi-byte UTF-8 characters like ─ (U+2500, 3 bytes), ═, ━, etc.
_ui_repeat() {
    local char="$1" count="$2"
    if (( count <= 0 )); then
        return
    fi
    local s
    printf -v s '%*s' "$count" ''
    printf '%s' "${s// /$char}"
}

# Get terminal width
_ui_cols() {
    echo "${COLUMNS:-$(tput cols 2>/dev/null || echo 80)}"
}

# Pad a raw string to width with spaces (for box-drawing alignment)
# Usage: _ui_pad_right "raw_string" width
_ui_pad_right() {
    local raw="$1" width="$2"
    local pad=$(( width - ${#raw} ))
    if (( pad > 0 )); then
        printf "%${pad}s" ''
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# §4. Logging System
# ═══════════════════════════════════════════════════════════════════════════════

_UI_LOG_FILE=""

# Initialize log file. Call once at script start.
# Usage: ui::log_init [filepath]
#   Default: /tmp/ui-<script_name>-<date>.log
ui::log_init() {
    local path="${1:-}"
    if [[ -z "$path" ]]; then
        local script_name
        script_name=$(basename "${BASH_SOURCE[-1]:-unknown}" .sh)
        path="/tmp/ui-${script_name}-$(date '+%Y%m%d').log"
    fi
    _UI_LOG_FILE="$path"
    : > "$_UI_LOG_FILE"
    chmod 644 "$_UI_LOG_FILE" 2>/dev/null || true
}

# Get log file path
ui::log_path() {
    echo "$_UI_LOG_FILE"
}

# Internal: write to log file (ANSI-stripped, timestamped)
_ui_write_log() {
    [[ -z "$_UI_LOG_FILE" ]] && return 0
    local level="$1" msg="$2"
    local clean
    clean=$(_ui_strip_ansi "$msg")
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [${level}] ${clean}" >> "$_UI_LOG_FILE"
}

# ─── Log Levels ───

ui::log() {
    echo -e "   ${UI_ARROW} $1"
    _ui_write_log "INFO" "$1"
}

ui::success() {
    echo -e "   ${UI_TICK} ${UI_GREEN}$1${UI_NC}"
    _ui_write_log "OK" "$1"
}

ui::warn() {
    echo -e "   ${UI_WARN} ${UI_YELLOW}${UI_BOLD}WARNING:${UI_NC} ${UI_YELLOW}$1${UI_NC}"
    _ui_write_log "WARN" "$1"
}

# Error: heavy-bordered box, auto-sized
ui::error() {
    local msg="$1"
    local prefix="ERROR: "
    local content="${prefix}${msg}"
    local content_len=${#content}
    local inner_w=$(( content_len + 4 ))
    local cols
    cols=$(_ui_cols)
    (( inner_w < 40 )) && inner_w=40
    (( inner_w > cols - 8 )) && inner_w=$(( cols - 8 ))

    local bar
    bar=$(_ui_repeat '━' "$inner_w")
    printf -v padded "%-${inner_w}s" "  ${content}"

    echo ""
    echo -e "   ${UI_RED}┏${bar}┓${UI_NC}"
    echo -e "   ${UI_RED}┃${padded}┃${UI_NC}"
    echo -e "   ${UI_RED}┗${bar}┛${UI_NC}"
    echo ""
    _ui_write_log "ERROR" "$msg"
}

# Debug: only shown when UI_DEBUG=1
ui::debug() {
    [[ "${UI_DEBUG:-0}" != "1" ]] && return 0
    echo -e "   ${UI_GRAY}[DBG] $1${UI_NC}"
    _ui_write_log "DEBUG" "$1"
}

# ═══════════════════════════════════════════════════════════════════════════════
# §4b. Progress Tracking System — Persistent right-pane via fzf --preview
# ═══════════════════════════════════════════════════════════════════════════════

# When fullscreen mode is enabled, all fzf calls use full terminal height
# and show a progress preview panel on the right side.
_UI_FULLSCREEN=0
_UI_PROGRESS_FILE=""
_UI_PREVIEW_SCRIPT=""
_UI_PROGRESS_HEADER=""

# Enable fullscreen fzf mode with progress panel
# Usage: ui::fullscreen "App Title"
ui::fullscreen() {
    _UI_FULLSCREEN=1
    _UI_PROGRESS_HEADER="${1:-Progress}"
}

# Initialize progress tracking. Creates temp files for progress state + preview script.
# Usage: ui::progress_init
ui::progress_init() {
    # Clean up any existing temp files from a previous call
    [[ -n "$_UI_PROGRESS_FILE" ]] && rm -f "$_UI_PROGRESS_FILE"
    [[ -n "$_UI_PREVIEW_SCRIPT" ]] && rm -f "$_UI_PREVIEW_SCRIPT"
    _UI_PROGRESS_FILE=$(mktemp /tmp/ui-progress-XXXXXX)
    _UI_PREVIEW_SCRIPT=$(mktemp /tmp/ui-preview-XXXXXX.sh)
    chmod +x "$_UI_PREVIEW_SCRIPT"

    # Write the preview script that fzf --preview will call.
    # It reads progress entries and formats them into a nice panel.
    cat > "$_UI_PREVIEW_SCRIPT" << 'PREVIEW_EOF'
#!/bin/bash
PROGRESS_FILE="$1"
LOG_FILE="$2"
HEADER="$3"

NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
CYAN='\033[1;36m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
PURPLE='\033[1;35m'
GRAY='\033[1;90m'
BLUE='\033[1;34m'

# Title
echo -e "${BOLD}${CYAN}  ╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}  ║  ${PURPLE}${HEADER}${CYAN}${NC}"
echo -e "${BOLD}${CYAN}  ╚══════════════════════════════════════╝${NC}"
echo ""

# Show completed steps from progress file
if [[ -f "$PROGRESS_FILE" ]] && [[ -s "$PROGRESS_FILE" ]]; then
    while IFS='|' read -r key val; do
        echo -e "  ${GREEN}✔${NC} ${BOLD}${key}${NC}  ${DIM}${val}${NC}"
    done < "$PROGRESS_FILE"
    echo ""
fi

# Show recent log entries
if [[ -n "$LOG_FILE" ]] && [[ -f "$LOG_FILE" ]] && [[ -s "$LOG_FILE" ]]; then
    echo -e "  ${GRAY}─── Recent Log ───${NC}"
    tail -5 "$LOG_FILE" | while IFS= read -r line; do
        echo -e "  ${DIM}${line}${NC}"
    done
fi
PREVIEW_EOF
}

# Record a completed step in the progress panel
# Usage: ui::progress_set "语言 Language" "zh_CN.UTF-8"
ui::progress_set() {
    local key="$1" val="$2"
    [[ -z "$_UI_PROGRESS_FILE" ]] && return 0
    echo "${key}|${val}" >> "$_UI_PROGRESS_FILE"
}

# Get common fzf args for fullscreen + preview mode
# Returns args array via stdout (one per line)
_ui_fzf_common_args() {
    local -a args=()
    args+=(--ansi)
    args+=(--layout=reverse)
    args+=(--color="marker:cyan,pointer:cyan,label:yellow,border:magenta")
    args+=(--pointer="›")
    args+=(--margin=0,2)
    # Navigation-aware bindings: when nav is enabled, write signal before aborting
    if [[ "$_UI_NAV_ENABLED" == "1" ]] && [[ -n "$_UI_NAV_FILE" ]]; then
        args+=(--bind "j:down,k:up")
        args+=(--bind "esc:execute-silent(printf %s BACK > ${_UI_NAV_FILE})+abort")
        args+=(--bind "ctrl-c:execute-silent(printf %s ABORT > ${_UI_NAV_FILE})+abort")
    else
        args+=(--bind 'j:down,k:up,ctrl-c:abort,esc:abort')
    fi

    if [[ "$_UI_FULLSCREEN" == "1" ]] && [[ -n "$_UI_PREVIEW_SCRIPT" ]]; then
        # Full-screen with progress preview on right
        args+=(--preview="${_UI_PREVIEW_SCRIPT} ${_UI_PROGRESS_FILE} ${_UI_LOG_FILE} '${_UI_PROGRESS_HEADER}'")
        args+=(--preview-window="right:45%:wrap:border-left")
    fi
    printf '%s\n' "${args[@]}"
}

# Build --height arg
# When banner is active: always returns a height that leaves room for the banner
# When no banner + fullscreen: returns empty (fzf uses full terminal)
# When no banner + not fullscreen: returns adaptive height
_ui_fzf_height_arg() {
    local count="$1"

    # Banner takes priority — if active, compute height to leave room for it
    local banner_height
    banner_height=$(_ui_fzf_height_with_banner "$count")
    if [[ -n "$banner_height" ]]; then
        echo "$banner_height"
        return
    fi

    if [[ "$_UI_FULLSCREEN" == "1" ]]; then
        echo ""
    else
        echo "--height=~$((count + 4))"
    fi
}

# Clean up progress temp files
ui::progress_cleanup() {
    [[ -n "$_UI_PROGRESS_FILE" ]] && rm -f "$_UI_PROGRESS_FILE"
    [[ -n "$_UI_PREVIEW_SCRIPT" ]] && rm -f "$_UI_PREVIEW_SCRIPT"
}

# ═══════════════════════════════════════════════════════════════════════════════
# §4c. Persistent Banner — Stays visible above fzf menus
# ═══════════════════════════════════════════════════════════════════════════════

# The banner system works by:
#   1. Registering a callback function that prints the banner to stdout
#   2. Before every fzf invocation, clearing the screen and re-printing the banner
#   3. Using --height to limit fzf to the remaining terminal rows below the banner
#
# Usage:
#   my_banner() { printf '%s\n' "$MY_BANNER_TEXT"; }
#   ui::set_banner my_banner 16   # function name, line count
#
# The banner is only shown when the terminal has enough vertical space
# (at least banner_height + 10 rows for fzf content).

_UI_BANNER_FN=""
_UI_BANNER_HEIGHT=0

# Register a banner function
# Usage: ui::set_banner <function_name> <line_count>
#   function_name: a bash function that prints the banner to stdout (with ANSI codes)
#   line_count:    number of terminal lines the banner occupies
ui::set_banner() {
    _UI_BANNER_FN="$1"
    _UI_BANNER_HEIGHT="${2:-0}"
}

# Internal: clear screen and print the banner before each fzf call
# Only prints when banner is registered and terminal is tall enough
# Writes to /dev/tty so it works even inside command substitution subshells
_ui_show_banner() {
    [[ -z "$_UI_BANNER_FN" ]] && return 0
    [[ "$_UI_BANNER_HEIGHT" -le 0 ]] && return 0

    local term_lines
    term_lines=$(tput lines 2>/dev/null) || term_lines=24

    local min_required=$(( _UI_BANNER_HEIGHT + 10 ))
    if (( term_lines < min_required )); then
        # Terminal too short — skip banner, let fzf use full height
        return 1
    fi

    # Clear screen and print banner to the real terminal.
    # Guard /dev/tty access — it may not be available in certain
    # execution chains (curl|bash → makeself → eval).
    if [[ -w /dev/tty ]]; then
        clear > /dev/tty 2>/dev/null || true
        "$_UI_BANNER_FN" > /dev/tty 2>/dev/null || true
    fi
    return 0
}

# Internal: compute fzf height accounting for banner
# When banner is active and visible, fzf gets the remaining rows.
# When banner is absent or terminal too short, uses existing logic.
_ui_fzf_height_with_banner() {
    local count="$1"
    [[ -z "$_UI_BANNER_FN" ]] && return 0
    [[ "$_UI_BANNER_HEIGHT" -le 0 ]] && return 0

    local term_lines
    term_lines=$(tput lines 2>/dev/null) || term_lines=24

    local min_required=$(( _UI_BANNER_HEIGHT + 10 ))
    if (( term_lines < min_required )); then
        return 0  # banner won't show, no height override
    fi

    # fzf gets remaining rows after banner (+ 1 for blank line after banner)
    local fzf_height=$(( term_lines - _UI_BANNER_HEIGHT - 1 ))
    echo "--height=${fzf_height}"
}

# ═══════════════════════════════════════════════════════════════════════════════
# §4d. Wizard Navigation — Back (Esc) / Abort (Ctrl-C)
# ═══════════════════════════════════════════════════════════════════════════════

# When navigation mode is enabled, fzf functions differentiate between:
#   Esc    → "go back" (return code 2)
#   Ctrl-C → "abort entire script" (return code 130)
#
# Without nav mode, both Esc and Ctrl-C produce the same result (cancel/fail),
# preserving backward compatibility for scripts that don't use wizard navigation.
#
# Signal communication: fzf's esc/ctrl-c bindings write "BACK" or "ABORT" to a
# temp file via execute-silent, then call abort. After fzf exits non-zero, we
# read the signal file to determine which action was taken.
#
# Usage:
#   ui::enable_nav       # call once before wizard loop
#   result=$(ui::select ...) ; rc=$?
#   case $rc in
#       0)   ;; # selected
#       2)   ;; # back (Esc)
#       130) ;; # abort (Ctrl-C)
#   esac
#   ui::nav_cleanup      # call on exit (or use trap)

_UI_NAV_ENABLED=0
_UI_NAV_FILE=""

# Enable wizard navigation mode
# Creates a temp file for signal communication between fzf and the shell
ui::enable_nav() {
    _UI_NAV_ENABLED=1
    _UI_NAV_FILE=$(mktemp /tmp/ui-nav-XXXXXX)
    : > "$_UI_NAV_FILE"
}

# Clean up navigation temp file
ui::nav_cleanup() {
    [[ -n "$_UI_NAV_FILE" ]] && rm -f "$_UI_NAV_FILE"
    _UI_NAV_FILE=""
    _UI_NAV_ENABLED=0
}

# Internal: clear signal file before each fzf invocation
_ui_nav_clear() {
    [[ "$_UI_NAV_ENABLED" == "1" ]] && [[ -n "$_UI_NAV_FILE" ]] && : > "$_UI_NAV_FILE"
}

# Internal: read signal file after fzf exits non-zero
# Returns: 2 = back (Esc), 130 = abort (Ctrl-C), 1 = legacy/unknown
_ui_nav_check() {
    if [[ "$_UI_NAV_ENABLED" != "1" ]] || [[ -z "$_UI_NAV_FILE" ]]; then
        return 1  # nav not enabled — legacy behavior
    fi
    local signal=""
    [[ -f "$_UI_NAV_FILE" ]] && signal=$(cat "$_UI_NAV_FILE" 2>/dev/null)
    case "$signal" in
        BACK)  return 2 ;;
        ABORT) return 130 ;;
        *)     return 1 ;;  # unknown — treat as generic cancel
    esac
}

# Internal: get fzf header hint text for navigation
# When nav is enabled: "[Esc] Back  [Ctrl-C] Abort"
# When nav is disabled: "[Esc] Cancel"
_ui_nav_header_hint() {
    if [[ "$_UI_NAV_ENABLED" == "1" ]]; then
        echo "[Esc] Back  [Ctrl-C] Abort"
    else
        echo "[Esc] Cancel"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# §5. Visual Components — Layout
# ═══════════════════════════════════════════════════════════════════════════════

# Horizontal rule (full terminal width)
ui::hr() {
    local char="${1:-─}"
    local cols
    cols=$(_ui_cols)
    echo -e "${UI_GRAY}$(_ui_repeat "$char" "$cols")${UI_NC}"
}

# ASCII art banner — pass each line as an argument
# Usage: ui::banner "line1" "line2" ...
ui::banner() {
    local color="${UI_CYAN}"
    echo ""
    for line in "$@"; do
        echo -e "   ${color}${line}${UI_NC}"
    done
    echo ""
}

# Section header — rounded box with title and subtitle
# Right-side border dropped from content lines to avoid CJK alignment issues
# (Chinese chars are 2 columns wide but ${#var} counts them as 1)
# Usage: ui::section "Title" "Subtitle"
ui::section() {
    local title="$1" subtitle="${2:-}"
    local cols
    cols=$(_ui_cols)
    local box_w=$(( cols < 80 ? cols - 2 : 78 ))
    local bar
    bar=$(_ui_repeat '─' "$box_w")

    echo ""
    echo -e "${UI_PURPLE}╭${bar}╮${UI_NC}"
    echo -e "${UI_PURPLE}│${UI_NC} ${UI_BOLD}${UI_WHITE}${title}${UI_NC}"
    if [[ -n "$subtitle" ]]; then
        echo -e "${UI_PURPLE}│${UI_NC} ${UI_CYAN}${subtitle}${UI_NC}"
    fi
    echo -e "${UI_PURPLE}╰${bar}╯${UI_NC}"
    _ui_write_log "SECTION" "${title}${subtitle:+ — ${subtitle}}"
}

# Key-value info line
# Usage: ui::info_kv "Key" "Value" ["Extra dim text"]
ui::info_kv() {
    local key="$1" val="$2" extra="${3:-}"
    printf "   ${UI_BULLET} %-18s : ${UI_BOLD}%s${UI_NC}" "$key" "$val"
    [[ -n "$extra" ]] && printf " ${UI_DIM}%s${UI_NC}" "$extra"
    printf "\n"
    _ui_write_log "KV" "${key}=${val}"
}

# Arbitrary content box — rounded border, auto-width
# Right-side border dropped from content lines to avoid CJK alignment issues
# Usage: ui::box "Title" "line1" "line2" ...
# Or piped: echo "content" | ui::box "Title"
ui::box() {
    local title="$1"
    shift

    # Collect lines from arguments or stdin
    local -a lines=()
    if [[ $# -gt 0 ]]; then
        lines=("$@")
    else
        while IFS= read -r line; do
            lines+=("$line")
        done
    fi

    # Calculate box width from content
    local max_len=${#title}
    for line in "${lines[@]}"; do
        local raw
        raw=$(_ui_strip_ansi "$line")
        (( ${#raw} > max_len )) && max_len=${#raw}
    done

    local cols
    cols=$(_ui_cols)
    local box_w=$(( max_len + 4 ))
    (( box_w < 30 )) && box_w=30
    (( box_w > cols - 4 )) && box_w=$(( cols - 4 ))

    local bar
    bar=$(_ui_repeat '─' "$box_w")

    echo ""
    echo -e "${UI_PURPLE}╭${bar}╮${UI_NC}"
    echo -e "${UI_PURPLE}│${UI_NC} ${UI_BOLD}${title}${UI_NC}"

    if [[ ${#lines[@]} -gt 0 ]]; then
        local sep
        sep=$(_ui_repeat '─' "$box_w")
        echo -e "${UI_PURPLE}├${sep}┤${UI_NC}"

        for line in "${lines[@]}"; do
            echo -e "${UI_PURPLE}│${UI_NC} ${line}"
        done
    fi
    echo -e "${UI_PURPLE}╰${bar}╯${UI_NC}"
    echo ""
}

# Table with borders
# Usage: ui::table "Col1|Col2|Col3" "val1|val2|val3" "val4|val5|val6" ...
ui::table() {
    local header="$1"
    shift
    local -a rows=("$@")

    # Parse header to get column count
    IFS='|' read -ra hdr_cols <<< "$header"
    local ncols=${#hdr_cols[@]}

    # Calculate max width per column
    local -a widths=()
    for (( c=0; c<ncols; c++ )); do
        widths[$c]=${#hdr_cols[$c]}
    done
    for row in "${rows[@]}"; do
        IFS='|' read -ra cells <<< "$row"
        for (( c=0; c<ncols; c++ )); do
            local cell="${cells[$c]:-}"
            local raw
            raw=$(_ui_strip_ansi "$cell")
            (( ${#raw} > widths[$c] )) && widths[$c]=${#raw}
        done
    done

    # Build format: add 2 padding per cell
    local total_w=1  # left border
    for (( c=0; c<ncols; c++ )); do
        (( total_w += widths[$c] + 3 ))  # " content " + border
    done

    # Top border
    local top="┌"
    for (( c=0; c<ncols; c++ )); do
        top+="$(_ui_repeat '─' $(( widths[$c] + 2 )))"
        (( c < ncols - 1 )) && top+="┬" || top+="┐"
    done
    echo -e "   ${UI_GRAY}${top}${UI_NC}"

    # Header row
    local hdr_line="│"
    for (( c=0; c<ncols; c++ )); do
        printf -v cell " %-${widths[$c]}s " "${hdr_cols[$c]}"
        hdr_line+="${UI_BOLD}${cell}${UI_NC}${UI_GRAY}│"
    done
    echo -e "   ${UI_GRAY}${hdr_line}${UI_NC}"

    # Header separator
    local sep="├"
    for (( c=0; c<ncols; c++ )); do
        sep+="$(_ui_repeat '─' $(( widths[$c] + 2 )))"
        (( c < ncols - 1 )) && sep+="┼" || sep+="┤"
    done
    echo -e "   ${UI_GRAY}${sep}${UI_NC}"

    # Data rows
    for row in "${rows[@]}"; do
        IFS='|' read -ra cells <<< "$row"
        local data_line="│"
        for (( c=0; c<ncols; c++ )); do
            local cell="${cells[$c]:-}"
            local raw
            raw=$(_ui_strip_ansi "$cell")
            local pad=$(( widths[$c] - ${#raw} ))
            data_line+=" ${cell}$(_ui_repeat ' ' "$pad") ${UI_GRAY}│"
        done
        echo -e "   ${UI_GRAY}${data_line}${UI_NC}"
    done

    # Bottom border
    local bot="└"
    for (( c=0; c<ncols; c++ )); do
        bot+="$(_ui_repeat '─' $(( widths[$c] + 2 )))"
        (( c < ncols - 1 )) && bot+="┴" || bot+="┘"
    done
    echo -e "   ${UI_GRAY}${bot}${UI_NC}"
}

# Indented text block
# Usage: ui::indent 4 "Some text here"
#   Or piped: echo "text" | ui::indent 4
ui::indent() {
    local n="$1"
    shift
    local pad
    pad=$(_ui_repeat ' ' "$n")

    if [[ $# -gt 0 ]]; then
        for line in "$@"; do
            echo -e "${pad}${line}"
        done
    else
        while IFS= read -r line; do
            echo -e "${pad}${line}"
        done
    fi
}

# Tree display
# Usage: ui::tree "root" "  child1" "  child2" "    grandchild" "  child3"
#   Indent level is determined by leading spaces (2 per level)
ui::tree() {
    local -a items=("$@")
    local total=${#items[@]}

    for (( i=0; i<total; i++ )); do
        local item="${items[$i]}"
        # Count leading spaces to determine depth
        local stripped="${item#"${item%%[! ]*}"}"
        local spaces=$(( ${#item} - ${#stripped} ))
        local depth=$(( spaces / 2 ))

        # Determine if this is the last item at this depth
        local is_last=true
        for (( j=i+1; j<total; j++ )); do
            local next="${items[$j]}"
            local next_stripped="${next#"${next%%[! ]*}"}"
            local next_spaces=$(( ${#next} - ${#next_stripped} ))
            local next_depth=$(( next_spaces / 2 ))
            if (( next_depth <= depth )); then
                if (( next_depth == depth )); then
                    is_last=false
                fi
                break
            fi
        done

        # Build prefix
        local prefix=""
        for (( d=0; d<depth; d++ )); do
            prefix+="   "
        done

        if (( depth == 0 )); then
            echo -e "   ${UI_BOLD}${stripped}${UI_NC}"
        elif [[ "$is_last" == true ]]; then
            echo -e "   ${prefix}${UI_GRAY}└── ${UI_NC}${stripped}"
        else
            echo -e "   ${prefix}${UI_GRAY}├── ${UI_NC}${stripped}"
        fi
    done
}

# ═══════════════════════════════════════════════════════════════════════════════
# §6. Command Execution
# ═══════════════════════════════════════════════════════════════════════════════

# Visual command executor — shows command + OK/FAIL status
# Usage: ui::exe pacman -S --noconfirm neovim
ui::exe() {
    local full_command="$*"
    local cols
    cols=$(_ui_cols)
    local bar_w=$(( cols < 80 ? cols - 8 : 72 ))
    local top_bar
    top_bar=$(_ui_repeat '─' "$bar_w")
    local bot_bar_ok
    bot_bar_ok=$(_ui_repeat '─' $(( bar_w - 5 )))
    local bot_bar_fail
    bot_bar_fail=$(_ui_repeat '─' $(( bar_w - 7 )))

    echo -e "   ${UI_GRAY}┌──[ ${UI_PURPLE}EXEC${UI_GRAY} ]${top_bar}${UI_NC}"
    echo -e "   ${UI_GRAY}│${UI_NC} ${UI_CYAN}\$ ${UI_NC}${UI_BOLD}${full_command}${UI_NC}"

    _ui_write_log "EXEC" "$full_command"

    local status=0
    "$@" || status=$?

    if [[ $status -eq 0 ]]; then
        echo -e "   ${UI_GRAY}└${bot_bar_ok} ${UI_GREEN}OK${UI_GRAY} ─┘${UI_NC}"
        _ui_write_log "EXEC_OK" "$full_command"
    else
        echo -e "   ${UI_GRAY}└${bot_bar_fail} ${UI_RED}FAIL($status)${UI_GRAY} ─┘${UI_NC}"
        _ui_write_log "EXEC_FAIL" "${full_command} (exit=$status)"
    fi
    return $status
}

# Quiet execution — only shows output on failure
# Usage: ui::exe_quiet pacman -Sy
ui::exe_quiet() {
    local full_command="$*"
    local output
    local status=0
    output=$("$@" 2>&1) || status=$?

    if [[ $status -ne 0 ]]; then
        ui::error "Command failed: ${full_command}"
        echo -e "${UI_DIM}${output}${UI_NC}" | ui::indent 6
    fi
    _ui_write_log "EXEC_QUIET" "${full_command} (exit=$status)"
    return $status
}

# Spinner — animated indicator while a command runs in background
# Usage: ui::spinner "Installing packages..." pacman -S --noconfirm neovim
ui::spinner() {
    local msg="$1"
    shift

    # Hide cursor
    tput civis 2>/dev/null || true

    # Run command in background, capture output to temp file
    local tmpout
    tmpout=$(mktemp)
    "$@" > "$tmpout" 2>&1 &
    local pid=$!

    local i=0
    local frame_count=${#_UI_SPINNER[@]}

    while kill -0 "$pid" 2>/dev/null; do
        local frame="${_UI_SPINNER[$((i % frame_count))]}"
        printf "\r   ${UI_CYAN}%s${UI_NC} %s" "$frame" "$msg"
        sleep 0.08
        (( i++ ))
    done

    # Get exit status
    wait "$pid"
    local status=$?

    # Clear spinner line
    printf "\r%*s\r" "$(( ${#msg} + 10 ))" ""

    # Show result
    if [[ $status -eq 0 ]]; then
        ui::success "$msg"
    else
        ui::error "$msg"
        [[ -s "$tmpout" ]] && echo -e "${UI_DIM}$(cat "$tmpout")${UI_NC}" | ui::indent 6
    fi

    # Restore cursor
    tput cnorm 2>/dev/null || true
    rm -f "$tmpout"
    return $status
}

# ═══════════════════════════════════════════════════════════════════════════════
# §7. Progress & Feedback
# ═══════════════════════════════════════════════════════════════════════════════

# Determinate progress bar
# Usage: ui::progress 30 100 "Downloading..."
#   Overwrites current line with \r (call repeatedly in a loop)
ui::progress() {
    local current="$1" total="$2" label="${3:-}"
    if (( total <= 0 )); then return 0; fi
    local cols
    cols=$(_ui_cols)
    local pct=$(( current * 100 / total ))
    (( pct > 100 )) && pct=100

    # Bar width: leave room for "   [bar] 100% label"
    local label_w=${#label}
    local bar_w=$(( cols - 12 - label_w ))
    (( bar_w < 10 )) && bar_w=10
    (( bar_w > 50 )) && bar_w=50

    local filled=$(( pct * bar_w / 100 ))
    local empty=$(( bar_w - filled ))

    local bar_str=""
    bar_str+=$(_ui_repeat "$_UI_BAR_FILL" "$filled")
    bar_str+=$(_ui_repeat "$_UI_BAR_EMPTY" "$empty")

    printf "\r   ${UI_CYAN}[${UI_GREEN}%s${UI_GRAY}%s${UI_CYAN}]${UI_NC} %3d%% %s" \
        "$(_ui_repeat "$_UI_BAR_FILL" "$filled")" \
        "$(_ui_repeat "$_UI_BAR_EMPTY" "$empty")" \
        "$pct" "$label"

    # Newline when complete
    (( current >= total )) && echo ""
}

# Step progress indicator
# Usage: ui::step 2 5 "Installing packages..."
ui::step() {
    local current="$1" total="$2" desc="$3"
    echo -e "   ${UI_CYAN}[${current}/${total}]${UI_NC} ${UI_BOLD}${desc}${UI_NC}"
    _ui_write_log "STEP" "[${current}/${total}] ${desc}"
}

# Countdown timer with cancel
# Usage: ui::countdown 10 "Rebooting" "n"
#   Returns 0 if countdown completed, 1 if cancelled
ui::countdown() {
    local seconds="$1" msg="$2" cancel_key="${3:-n}"

    for (( i=seconds; i>0; i-- )); do
        printf "\r   ${UI_DIM}%s in ${UI_BOLD}%ds${UI_NC}${UI_DIM}... (Press '%s' to cancel)${UI_NC}" \
            "$msg" "$i" "$cancel_key"
        local input=""
        read -t 1 -n 1 -s input 2>/dev/null || true
        if [[ "$input" == "$cancel_key" ]]; then
            printf "\r%*s\r" "$(_ui_cols)" ""
            ui::log "Cancelled by user"
            return 1
        fi
    done
    printf "\r%*s\r" "$(_ui_cols)" ""
    return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# §8. User Input
# ═══════════════════════════════════════════════════════════════════════════════

# Y/N confirmation via fzf (fullscreen-aware with preview)
# Usage: ui::confirm "Proceed with installation?" [Y|N] [timeout_seconds]
#   Returns 0 for yes, 1 for no
# Confirm dialog — fzf-based Yes/No selector with preview
# Usage: ui::confirm "prompt" [default] [timeout] [summary]
#   default:  "Y" or "N" (which option is pre-selected)
#   timeout:  auto-confirm after N seconds (non-fzf fallback only)
#   summary:  ANSI text to display in the preview panel (replaces default progress view)
#             Pass "" to skip. Useful for showing a configuration summary before final confirm.
ui::confirm() {
    local prompt="$1"
    local default="${2:-}"
    local timeout="${3:-}"
    local summary="${4:-}"

    # When fzf is not available or not fullscreen, fall back to read-based
    if ! command -v fzf &>/dev/null || [[ "$_UI_FULLSCREEN" != "1" ]]; then
        local hint=""
        case "$default" in
            [Yy]*) hint="Y/n" ;;
            [Nn]*) hint="y/N" ;;
            *)     hint="y/n" ;;
        esac

        local timeout_hint=""
        [[ -n "$timeout" ]] && timeout_hint=" (${timeout}s timeout)"

        local read_args=(-r)
        [[ -n "$timeout" ]] && read_args+=(-t "$timeout")

        local answer=""
        while true; do
            echo -ne "   ${UI_CYAN}${prompt} [${hint}]${timeout_hint}: ${UI_NC}"

            if read "${read_args[@]}" answer; then
                : # normal input
            else
                # Timeout or error
                echo ""
                answer="$default"
            fi
            answer="${answer:-$default}"

            case "$answer" in
                [Yy]|[Yy]es) return 0 ;;
                [Nn]|[Nn]o)  return 1 ;;
                "")
                    [[ -z "$default" ]] && { ui::warn "Please enter y or n"; continue; }
                    ;;
                *)
                    ui::warn "Please enter y or n"
                    continue
                    ;;
            esac
        done
    fi

    # fzf-based confirm with preview
    _ui_ensure_fzf || return 1

    local yes_label="  ✔  Yes"
    local no_label="  ✘  No"

    # Build items: default first
    local -a items=()
    case "$default" in
        [Yy]*) items=("${yes_label}" "${no_label}") ;;
        [Nn]*) items=("${no_label}" "${yes_label}") ;;
        *)     items=("${yes_label}" "${no_label}") ;;
    esac

    # Build fzf args
    local -a fzf_args=()
    readarray -t fzf_args < <(_ui_fzf_common_args)
    fzf_args+=(--info=hidden)
    fzf_args+=(--border=rounded)
    fzf_args+=(--border-label="  ${prompt}  ")
    fzf_args+=(--border-label-pos=5)
    fzf_args+=(--header=" [Enter] Confirm  $(_ui_nav_header_hint)")
    fzf_args+=(--no-multi)

    # Override preview with summary text if provided
    local _confirm_summary_file=""
    if [[ -n "$summary" ]]; then
        _confirm_summary_file=$(mktemp /tmp/ui-confirm-summary-XXXXXX)
        # Write summary text to temp file (ANSI codes preserved)
        echo -e "$summary" > "$_confirm_summary_file"
        # Build preview: summary + optional recent log
        local custom_preview="cat '${_confirm_summary_file}'"
        if [[ -n "$_UI_LOG_FILE" ]] && [[ -f "$_UI_LOG_FILE" ]]; then
            custom_preview+="; echo ''"
            custom_preview+="; echo -e '\033[1;90m  ─── Recent Log ───\033[0m'"
            custom_preview+="; tail -5 '${_UI_LOG_FILE}' 2>/dev/null | while IFS= read -r line; do echo -e \"  \033[2m\${line}\033[0m\"; done"
        fi
        # fzf uses the last --preview specified, so this overrides _ui_fzf_common_args
        fzf_args+=(--preview="${custom_preview}")
        fzf_args+=(--preview-window="right:45%:wrap:border-left")
    fi

    local height_arg
    height_arg=$(_ui_fzf_height_arg 2)
    [[ -n "$height_arg" ]] && fzf_args+=("$height_arg")

    _ui_nav_clear
    _ui_show_banner
    local selected
    selected=$(printf "%s\n" "${items[@]}" | fzf "${fzf_args[@]}" 2>>"$(_ui_fzf_stderr)") || {
        # Cleanup temp file on abort
        [[ -n "$_confirm_summary_file" ]] && rm -f "$_confirm_summary_file"
        if [[ "$_UI_NAV_ENABLED" == "1" ]]; then
            # Nav mode: propagate back/abort signals
            _ui_nav_check; return $?
        else
            # Legacy: Esc/abort — return based on default
            case "$default" in
                [Yy]*) return 0 ;;
                *)     return 1 ;;
            esac
        fi
    }

    [[ -n "$_confirm_summary_file" ]] && rm -f "$_confirm_summary_file"
    [[ "$selected" == *"Yes"* ]] && return 0
    return 1
}

# Text input with optional default via fzf (fullscreen-aware with preview)
# Usage: result=$(ui::input "Enter hostname" "archlinux")
# Uses fzf --print-query --disabled so user types in the query field
ui::input() {
    local prompt="$1"
    local default="${2:-}"

    # When fzf is not available or not fullscreen, fall back to /dev/tty
    if ! command -v fzf &>/dev/null || [[ "$_UI_FULLSCREEN" != "1" ]]; then
        local display_prompt="   ${UI_CYAN}${prompt}"
        [[ -n "$default" ]] && display_prompt+=" [${default}]"
        display_prompt+=": ${UI_NC}"

        local answer=""
        echo -ne "$display_prompt" > /dev/tty
        read -r answer < /dev/tty
        answer="${answer:-$default}"
        echo "$answer"
        return 0
    fi

    # fzf-based input: --print-query captures the query string, --disabled ignores item filtering
    _ui_ensure_fzf || return 1

    local placeholder_text="${prompt}"
    [[ -n "$default" ]] && placeholder_text+=" [${default}]"

    local -a fzf_args=()
    readarray -t fzf_args < <(_ui_fzf_common_args)
    fzf_args+=(--print-query)
    fzf_args+=(--disabled)
    fzf_args+=(--info=hidden)
    fzf_args+=(--border=rounded)
    fzf_args+=(--border-label="  ${prompt}  ")
    fzf_args+=(--border-label-pos=5)
    fzf_args+=(--header=" Type your answer, then press Enter  $(_ui_nav_header_hint)")
    fzf_args+=(--query="${default}")
    fzf_args+=(--prompt="  › ")

    local height_arg
    height_arg=$(_ui_fzf_height_arg 2)
    [[ -n "$height_arg" ]] && fzf_args+=("$height_arg")

    _ui_nav_clear
    _ui_show_banner
    local result
    if [[ "$_UI_NAV_ENABLED" == "1" ]]; then
        result=$(echo "" | fzf "${fzf_args[@]}" 2>>"$(_ui_fzf_stderr)") || {
            _ui_nav_check; return $?
        }
    else
        result=$(echo "" | fzf "${fzf_args[@]}" 2>>"$(_ui_fzf_stderr)") || true
    fi

    # --print-query outputs: line1=query, line2=selected item
    # We want line1 (the query = what user typed)
    local query
    query=$(head -1 <<< "$result")
    query="${query:-$default}"
    echo "$query"
}

# Text input with validation callback
# Usage: result=$(ui::input_validate "Enter port" validate_port "8080")
#   Validator function should return 0 for valid, non-zero with message on stderr for invalid
ui::input_validate() {
    local prompt="$1"
    local validator="$2"
    local default="${3:-}"
    local err_file
    err_file=$(mktemp /tmp/ui-validate-err-XXXXXX)
    trap "rm -f '$err_file'" RETURN

    while true; do
        local answer
        answer=$(ui::input "$prompt" "$default")
        local rc=$?
        # Propagate nav signals (back=2, abort=130)
        if (( rc == 2 || rc == 130 )); then
            return $rc
        fi

        if $validator "$answer" 2>"$err_file"; then
            echo "$answer"
            return 0
        else
            local err_msg
            err_msg=$(cat "$err_file" 2>/dev/null)
            ui::warn "${err_msg:-Invalid input}" > /dev/tty
        fi
    done
}

# Password input — fzf-based in fullscreen mode to maintain split-pane layout
# Uses transform-query to replace typed text with asterisks in real-time.
# The real password is reconstructed and stored in a temp file because
# transform-query mutates {q}, so we can't read it back directly.
#
# How reconstruction works:
#   After transform-query turns "abc" → "***", the next keystroke gives "***d".
#   The helper compares new {q} length with stored password length:
#     - Longer → new char(s) = {q}[old_len:], append to stored password
#     - Shorter → backspace detected, truncate stored password
#     - Same → no change (e.g. modifier keys)
#   Limitation: mid-string cursor edits won't work (acceptable for passwords).
#
# Usage: password=$(ui::password "Enter password")
ui::password() {
    local prompt="$1"

    # Fallback: read -s to /dev/tty when not in fullscreen
    if ! command -v fzf &>/dev/null || [[ "$_UI_FULLSCREEN" != "1" ]]; then
        local answer=""
        echo -ne "   ${UI_CYAN}${prompt}: ${UI_NC}" > /dev/tty
        read -rs answer < /dev/tty
        echo "" > /dev/tty
        echo "$answer"
        return 0
    fi

    _ui_ensure_fzf || return 1

    # Temp files for password state
    local pw_file pw_helper
    pw_file=$(mktemp /tmp/ui-pw-XXXXXX)
    pw_helper=$(mktemp /tmp/ui-pw-helper-XXXXXX.sh)
    : > "$pw_file"
    chmod 600 "$pw_file"

    # Helper: reconstruct real password from asterisk-corrupted query.
    # Called via fzf transform action — receives query via $FZF_QUERY env var
    # (safe from shell injection, unlike {q} which is interpolated literally).
    cat > "$pw_helper" << 'HELPER_EOF'
#!/usr/bin/env bash
pw_file="$1"
new_q="${FZF_QUERY:-}"
old_pw=""
[[ -f "$pw_file" ]] && old_pw=$(cat "$pw_file")
old_len=${#old_pw}
new_len=${#new_q}
if (( new_len > old_len )); then
    # New character(s) appended — extract the non-asterisk tail
    appended="${new_q:$old_len}"
    printf '%s' "${old_pw}${appended}" > "$pw_file"
elif (( new_len < old_len )); then
    # Backspace — truncate stored password
    printf '%s' "${old_pw:0:$new_len}" > "$pw_file"
fi
# Output asterisks (becomes new query via transform)
pw=$(cat "$pw_file")
printf '%*s' "${#pw}" '' | tr ' ' '*'
HELPER_EOF
    chmod +x "$pw_helper"

    # Build fzf args — NOT using _ui_fzf_common_args because j/k must be typeable
    local -a fzf_args=()
    fzf_args+=(--ansi)
    fzf_args+=(--layout=reverse)
    fzf_args+=(--color="marker:cyan,pointer:cyan,label:yellow,border:magenta")
    fzf_args+=(--margin=0,2)
    # Navigation-aware bindings (replicated from _ui_fzf_common_args, without j/k)
    if [[ "$_UI_NAV_ENABLED" == "1" ]] && [[ -n "$_UI_NAV_FILE" ]]; then
        fzf_args+=(--bind "esc:execute-silent(printf %s BACK > ${_UI_NAV_FILE})+abort")
        fzf_args+=(--bind "ctrl-c:execute-silent(printf %s ABORT > ${_UI_NAV_FILE})+abort")
    else
        fzf_args+=(--bind 'ctrl-c:abort,esc:abort')
    fi
    fzf_args+=(--info=hidden)
    fzf_args+=(--no-sort)
    fzf_args+=(--border=rounded)
    fzf_args+=(--border-label="  ${prompt}  ")
    fzf_args+=(--border-label-pos=5)
    fzf_args+=(--prompt="  🔒 ")
    fzf_args+=(--header=" Type password (masked), press Enter to confirm  $(_ui_nav_header_hint)")
    # On each keystroke: reconstruct password + replace query with asterisks (via transform)
    fzf_args+=(--bind "change:transform(${pw_helper} ${pw_file})")
    # On Enter: output the real password from the temp file
    fzf_args+=(--bind "enter:become(cat ${pw_file})")

    # Add preview panel for fullscreen mode
    if [[ "$_UI_FULLSCREEN" == "1" ]] && [[ -n "$_UI_PREVIEW_SCRIPT" ]]; then
        fzf_args+=(--preview="${_UI_PREVIEW_SCRIPT} ${_UI_PROGRESS_FILE} ${_UI_LOG_FILE} '${_UI_PROGRESS_HEADER}'")
        fzf_args+=(--preview-window="right:45%:wrap:border-left")
    fi

    local height_arg
    height_arg=$(_ui_fzf_height_arg 2)
    [[ -n "$height_arg" ]] && fzf_args+=("$height_arg")

    _ui_nav_clear
    _ui_show_banner
    local result
    if [[ "$_UI_NAV_ENABLED" == "1" ]]; then
        result=$(echo "" | fzf "${fzf_args[@]}" 2>>"$(_ui_fzf_stderr)") || {
            local _pw_rc=0
            _ui_nav_check; _pw_rc=$?
            rm -f "$pw_file" "$pw_helper"
            return $_pw_rc
        }
    else
        result=$(echo "" | fzf "${fzf_args[@]}" 2>>"$(_ui_fzf_stderr)") || true
    fi

    # Clean up temp files
    rm -f "$pw_file" "$pw_helper"

    echo "$result"
}

# ═══════════════════════════════════════════════════════════════════════════════
# §9. FZF-Powered Selection
# ═══════════════════════════════════════════════════════════════════════════════

# Internal: return stderr redirect target for fzf.
# Sends fzf's diagnostic output to the log file when available, /dev/null otherwise.
# fzf renders its TUI via /dev/tty so redirecting stderr doesn't affect display.
_ui_fzf_stderr() {
    if [[ -n "$_UI_LOG_FILE" ]]; then
        echo "$_UI_LOG_FILE"
    else
        echo "/dev/null"
    fi
}

# Ensure fzf is available
_ui_ensure_fzf() {
    command -v fzf &>/dev/null && return 0

    echo -e "   ${UI_DIM}fzf not found, attempting to install...${UI_NC}" > /dev/tty 2>/dev/null || true
    if command -v pacman &>/dev/null; then
        # Sync package database first — on a fresh Arch ISO the db may be
        # empty or stale, causing `pacman -S` to fail with "target not found".
        pacman -Sy --noconfirm 2>/dev/null || true
        pacman -S --noconfirm --needed fzf 2>/dev/null || true
    elif command -v apt-get &>/dev/null; then
        apt-get update -qq 2>/dev/null || true
        apt-get install -y fzf >/dev/null 2>&1 || true
    elif command -v dnf &>/dev/null; then
        dnf install -y fzf >/dev/null 2>&1 || true
    fi

    if ! command -v fzf &>/dev/null; then
        ui::error "fzf is required but could not be installed. Please install it manually."
        return 1
    fi
    ui::success "fzf installed"
}

# Single-select menu via fzf (fullscreen-aware with progress preview)
# Usage: result=$(ui::select "Select Language" "简体中文|zh_CN" "English|en_US" "日本語|ja_JP")
#   Each item: "Display Label|return_value" or just "Display Label" (value = label)
#   Returns the value portion of the selected item
ui::select() {
    _ui_ensure_fzf || return 1

    local title="$1"
    shift
    local -a items=("$@")

    # Build fzf input: "  [N] Display Label\tvalue"
    local -a fzf_lines=()
    local idx=1
    for item in "${items[@]}"; do
        local label="${item%%|*}"
        local value="${item##*|}"
        [[ "$label" == "$value" ]] && [[ "$item" != *"|"* ]] && value="$label"
        fzf_lines+=("$(printf "  ${UI_CYAN}[%d]${UI_NC}  %s\t%s" "$idx" "$label" "$value")")
        (( idx++ ))
    done

    # Build fzf args
    local -a fzf_args=()
    readarray -t fzf_args < <(_ui_fzf_common_args)
    fzf_args+=(--delimiter=$'\t')
    fzf_args+=(--with-nth=1)
    fzf_args+=(--info=hidden)
    fzf_args+=(--border=rounded)
    fzf_args+=(--border-label="  ${title}  ")
    fzf_args+=(--border-label-pos=5)
    fzf_args+=(--header=" [j/k] Navigate  [Enter] Select  $(_ui_nav_header_hint)")

    local height_arg
    height_arg=$(_ui_fzf_height_arg "${#items[@]}")
    [[ -n "$height_arg" ]] && fzf_args+=("$height_arg")

    _ui_nav_clear
    _ui_show_banner
    local selected
    selected=$(printf "%s\n" "${fzf_lines[@]}" | fzf "${fzf_args[@]}" 2>>"$(_ui_fzf_stderr)") || {
        _ui_nav_check; return $?
    }

    # Extract value (after tab)
    echo "${selected##*$'\t'}"
}

# Single-select with preview pane (split-pane effect)
# In fullscreen mode, the preview shows BOTH the item preview AND the progress panel
# Usage: result=$(ui::select_with_preview "Select Disk" "lsblk -o NAME,SIZE,FSTYPE /dev/{}" \
#          "nvme0n1|nvme0n1" "nvme1n1|nvme1n1")
#   The {} in preview_cmd is replaced with the value
ui::select_with_preview() {
    _ui_ensure_fzf || return 1

    local title="$1"
    local preview_cmd="$2"
    shift 2
    local -a items=("$@")

    local -a fzf_lines=()
    local idx=1
    for item in "${items[@]}"; do
        local label="${item%%|*}"
        local value="${item##*|}"
        [[ "$label" == "$value" ]] && [[ "$item" != *"|"* ]] && value="$label"
        fzf_lines+=("$(printf "  ${UI_CYAN}[%d]${UI_NC}  %s\t%s" "$idx" "$label" "$value")")
        (( idx++ ))
    done

    # Build combined preview command:
    # If fullscreen + progress enabled, show item preview first, then progress below
    local combined_preview
    if [[ "$_UI_FULLSCREEN" == "1" ]] && [[ -n "$_UI_PREVIEW_SCRIPT" ]]; then
        combined_preview="echo {2} | xargs -I{} ${preview_cmd}; echo ''; echo '────────────────────────────────'; ${_UI_PREVIEW_SCRIPT} ${_UI_PROGRESS_FILE} ${_UI_LOG_FILE} '${_UI_PROGRESS_HEADER}'"
    else
        combined_preview="echo {2} | xargs -I{} ${preview_cmd}"
    fi

    # Build fzf args
    local -a fzf_args=()
    # Don't use _ui_fzf_common_args here because we handle preview manually
    fzf_args+=(--ansi)
    fzf_args+=(--layout=reverse)
    fzf_args+=(--color="marker:cyan,pointer:cyan,label:yellow,border:magenta")
    fzf_args+=(--pointer="›")
    fzf_args+=(--margin=0,2)
    # Navigation-aware bindings (replicated from _ui_fzf_common_args)
    if [[ "$_UI_NAV_ENABLED" == "1" ]] && [[ -n "$_UI_NAV_FILE" ]]; then
        fzf_args+=(--bind "j:down,k:up")
        fzf_args+=(--bind "esc:execute-silent(printf %s BACK > ${_UI_NAV_FILE})+abort")
        fzf_args+=(--bind "ctrl-c:execute-silent(printf %s ABORT > ${_UI_NAV_FILE})+abort")
    else
        fzf_args+=(--bind 'j:down,k:up,ctrl-c:abort,esc:abort')
    fi
    fzf_args+=(--delimiter=$'\t')
    fzf_args+=(--with-nth=1)
    fzf_args+=(--info=hidden)
    fzf_args+=(--border=rounded)
    fzf_args+=(--border-label="  ${title}  ")
    fzf_args+=(--border-label-pos=5)
    fzf_args+=(--header=" [j/k] Navigate  [Enter] Select  $(_ui_nav_header_hint)")
    fzf_args+=(--preview="${combined_preview}")
    fzf_args+=(--preview-window="right:50%:wrap:border-left")

    local height_arg
    height_arg=$(_ui_fzf_height_arg "${#items[@]}")
    [[ -n "$height_arg" ]] && fzf_args+=("$height_arg")

    _ui_nav_clear
    _ui_show_banner
    local selected
    selected=$(printf "%s\n" "${fzf_lines[@]}" | fzf "${fzf_args[@]}" 2>>"$(_ui_fzf_stderr)") || {
        _ui_nav_check; return $?
    }

    echo "${selected##*$'\t'}"
}

# Multi-select menu via fzf (TAB to toggle, fullscreen-aware)
# Usage: readarray -t results < <(ui::multiselect "Select Packages" "neovim|neovim" "git|git" "zsh|zsh")
#   Returns one value per line
ui::multiselect() {
    _ui_ensure_fzf || return 1

    local title="$1"
    shift
    local -a items=("$@")

    local -a fzf_lines=()
    local idx=1
    for item in "${items[@]}"; do
        local label="${item%%|*}"
        local value="${item##*|}"
        [[ "$label" == "$value" ]] && [[ "$item" != *"|"* ]] && value="$label"
        fzf_lines+=("$(printf "  %s\t%s" "$label" "$value")")
        (( idx++ ))
    done

    # Build fzf args
    local -a fzf_args=()
    readarray -t fzf_args < <(_ui_fzf_common_args)
    fzf_args+=(--multi)
    fzf_args+=(--delimiter=$'\t')
    fzf_args+=(--with-nth=1)
    fzf_args+=(--info=inline)
    fzf_args+=(--border=rounded)
    fzf_args+=(--border-label="  ${title}  ")
    fzf_args+=(--border-label-pos=5)
    fzf_args+=(--header=" [TAB] Toggle  [Ctrl-A] All  [Ctrl-D] None  [Enter] Confirm  $(_ui_nav_header_hint)")
    fzf_args+=(--marker="✔ ")
    fzf_args+=(--bind 'ctrl-a:select-all,ctrl-d:deselect-all')

    local height_arg
    height_arg=$(_ui_fzf_height_arg "${#items[@]}")
    [[ -n "$height_arg" ]] && fzf_args+=("$height_arg")

    _ui_nav_clear
    _ui_show_banner
    local selected
    selected=$(printf "%s\n" "${fzf_lines[@]}" | fzf "${fzf_args[@]}" 2>>"$(_ui_fzf_stderr)") || {
        _ui_nav_check; return $?
    }

    # Extract values
    while IFS= read -r line; do
        echo "${line##*$'\t'}"
    done <<< "$selected"
}

# Checklist — multi-select with pre-selected items (fullscreen-aware)
# Usage: readarray -t results < <(ui::checklist "Modules" "grub,apps" \
#          "grub|GRUB Theme" "apps|Install Apps" "snapshot|Create Snapshot")
#   First arg after title is comma-separated pre-selected values
ui::checklist() {
    _ui_ensure_fzf || return 1

    local title="$1"
    local preselected="$2"
    shift 2
    local -a items=("$@")

    # Build fzf input with pre-selection markers
    local -a fzf_lines=()
    local -a bind_select=()
    local idx=1  # fzf pos() is 1-indexed
    for item in "${items[@]}"; do
        local value="${item%%|*}"
        local label="${item#*|}"
        fzf_lines+=("$(printf "%s\t%s" "$label" "$value")")

        # Check if pre-selected
        if [[ ",$preselected," == *",$value,"* ]]; then
            bind_select+=("$idx")
        fi
        (( idx++ ))
    done

    # Build initial selection bind (only if there are pre-selected items)
    local select_bind=""
    if (( ${#bind_select[@]} > 0 )); then
        select_bind="start:"
        for si in "${bind_select[@]}"; do
            select_bind+="pos($si)+select+"
        done
        select_bind+="first"  # Return cursor to the first item after selecting
    fi

    # Build fzf args
    local -a fzf_args=()
    readarray -t fzf_args < <(_ui_fzf_common_args)
    fzf_args+=(--multi)
    fzf_args+=(--delimiter=$'\t')
    fzf_args+=(--with-nth=1)
    fzf_args+=(--info=inline)
    fzf_args+=(--border=rounded)
    fzf_args+=(--border-label="  ${title}  ")
    fzf_args+=(--border-label-pos=5)
    fzf_args+=(--header=" [TAB] Toggle  [Ctrl-A] All  [Ctrl-D] None  [Enter] Confirm  $(_ui_nav_header_hint)")
    fzf_args+=(--marker="✔ ")
    [[ -n "${select_bind:-}" ]] && fzf_args+=(--bind "${select_bind}")
    fzf_args+=(--bind 'ctrl-a:select-all,ctrl-d:deselect-all')

    local height_arg
    height_arg=$(_ui_fzf_height_arg "${#items[@]}")
    [[ -n "$height_arg" ]] && fzf_args+=("$height_arg")

    _ui_nav_clear
    _ui_show_banner
    local selected
    selected=$(printf "%s\n" "${fzf_lines[@]}" | fzf "${fzf_args[@]}" 2>>"$(_ui_fzf_stderr)") || {
        _ui_nav_check; return $?
    }

    while IFS= read -r line; do
        echo "${line##*$'\t'}"
    done <<< "$selected"
}

# Action menu — select and execute
# Usage: ui::menu "Main Menu" \
#          "Install packages|install_packages" \
#          "Configure system|configure_system" \
#          "Exit|exit 0"
#   The value portion is eval'd as a command
ui::menu() {
    local title="$1"
    shift

    local -a display_items=()
    local -a actions=()
    for entry in "$@"; do
        local label="${entry%%|*}"
        local action="${entry#*|}"
        display_items+=("${label}|${label}")
        actions+=("$action")
    done

    local selected
    selected=$(ui::select "$title" "${display_items[@]}") || return 1

    # Find matching action
    for (( i=0; i<${#display_items[@]}; i++ )); do
        local label="${display_items[$i]%%|*}"
        if [[ "$label" == "$selected" ]]; then
            ${actions[$i]}
            return $?
        fi
    done
    return 1
}

# ═══════════════════════════════════════════════════════════════════════════════
# §10. System Integration
# ═══════════════════════════════════════════════════════════════════════════════

# Check required commands exist
# Usage: ui::require_cmd fzf git curl
ui::require_cmd() {
    local missing=()
    for cmd in "$@"; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        ui::error "Missing required commands: ${missing[*]}"
        return 1
    fi
    return 0
}

# Check/elevate to root. Sets $SUDO variable.
# Usage: ui::require_root
#   After calling: use $SUDO prefix for commands needing root
ui::require_root() {
    if [[ "$EUID" -eq 0 ]]; then
        SUDO=""
        return 0
    fi

    if command -v sudo &>/dev/null && sudo -n true 2>/dev/null; then
        SUDO="sudo"
        return 0
    fi

    ui::log "Root privileges required, requesting sudo..."
    if sudo true 2>/dev/null; then
        SUDO="sudo"
        return 0
    fi

    ui::error "Cannot obtain root privileges. Please run with sudo."
    return 1
}

# Trap handler — clean exit (restore terminal state + cleanup temps)
# Usage: trap ui::cleanup EXIT INT TERM
ui::cleanup() {
    # Restore cursor visibility
    tput cnorm 2>/dev/null || true
    # Reset colors
    echo -ne "${UI_NC}"
    # Clean up progress temp files
    ui::progress_cleanup 2>/dev/null || true
    # Clean up navigation temp file
    ui::nav_cleanup 2>/dev/null || true
}

# System dashboard — info panel in double-line box
# Right-side border dropped from content lines to avoid CJK alignment issues
# Usage: ui::dashboard "Kernel|$(uname -r)" "User|$(whoami)" "Disk|/dev/nvme0n1"
ui::dashboard() {
    local -a entries=("$@")

    # Calculate widths
    local max_key=0 max_val=0
    for entry in "${entries[@]}"; do
        local key="${entry%%|*}"
        local val="${entry#*|}"
        local val_raw
        val_raw=$(_ui_strip_ansi "$val")
        (( ${#key} > max_key )) && max_key=${#key}
        (( ${#val_raw} > max_val )) && max_val=${#val_raw}
    done

    local inner_w=$(( max_key + max_val + 7 ))  # " Key    : Value "
    (( inner_w < 40 )) && inner_w=40
    local cols
    cols=$(_ui_cols)
    (( inner_w > cols - 8 )) && inner_w=$(( cols - 8 ))

    local bar
    bar=$(_ui_repeat '═' "$inner_w")
    local title="CONFIGURATION SUMMARY"
    local title_pad=$(( (inner_w - ${#title}) / 2 ))

    echo ""
    echo -e "   ${UI_BLUE}╔${bar}╗${UI_NC}"
    printf "   ${UI_BLUE}║${UI_NC}%*s${UI_BOLD}%s${UI_NC}\n" \
        "$title_pad" "" "$title"
    echo -e "   ${UI_BLUE}╠${bar}╣${UI_NC}"

    for entry in "${entries[@]}"; do
        local key="${entry%%|*}"
        local val="${entry#*|}"

        printf "   ${UI_BLUE}║${UI_NC} %-${max_key}s  : %s\n" "$key" "$val"
    done

    echo -e "   ${UI_BLUE}╚${bar}╝${UI_NC}"
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════════════
# §11. Utilities
# ═══════════════════════════════════════════════════════════════════════════════

# Word wrap text to N columns
# Usage: ui::wrap 60 "Long text here..."
#   Or piped: echo "Long text" | ui::wrap 60
ui::wrap() {
    local width="$1"
    shift

    if [[ $# -gt 0 ]]; then
        echo "$*" | fold -s -w "$width"
    else
        fold -s -w "$width"
    fi
}

# Print a labeled divider
# Usage: ui::divider "Section Name"
ui::divider() {
    local label="${1:-}"
    local cols
    cols=$(_ui_cols)

    if [[ -z "$label" ]]; then
        ui::hr
        return
    fi

    local label_len=${#label}
    local side_len=$(( (cols - label_len - 4) / 2 ))
    (( side_len < 2 )) && side_len=2
    local left
    left=$(_ui_repeat '─' "$side_len")
    local right
    right=$(_ui_repeat '─' $(( cols - side_len - label_len - 4 )))

    echo -e "${UI_GRAY}${left}┤ ${UI_NC}${UI_BOLD}${label}${UI_NC}${UI_GRAY} ├${right}${UI_NC}"
}

# Colorize a value based on condition
# Usage: echo "Status: $(ui::colorize "running" green)"
ui::colorize() {
    local text="$1" color="$2"
    local code=""
    case "$color" in
        red)    code="$UI_RED" ;;
        green)  code="$UI_GREEN" ;;
        yellow) code="$UI_YELLOW" ;;
        blue)   code="$UI_BLUE" ;;
        purple) code="$UI_PURPLE" ;;
        cyan)   code="$UI_CYAN" ;;
        gray)   code="$UI_GRAY" ;;
        bold)   code="$UI_BOLD" ;;
        dim)    code="$UI_DIM" ;;
        *)      code="" ;;
    esac
    echo -e "${code}${text}${UI_NC}"
}

# Pairs display — two columns of key-value pairs side by side
# Usage: ui::pairs "Key1=Val1" "Key2=Val2" "Key3=Val3" "Key4=Val4"
#   Displays in two columns for compact information display
ui::pairs() {
    local -a items=("$@")
    local total=${#items[@]}
    local half=$(( (total + 1) / 2 ))

    # Find max key width
    local max_key=0
    for item in "${items[@]}"; do
        local key="${item%%=*}"
        (( ${#key} > max_key )) && max_key=${#key}
    done

    for (( i=0; i<half; i++ )); do
        local left="${items[$i]}"
        local l_key="${left%%=*}"
        local l_val="${left#*=}"

        local right_idx=$(( i + half ))
        if (( right_idx < total )); then
            local right="${items[$right_idx]}"
            local r_key="${right%%=*}"
            local r_val="${right#*=}"
            printf "   ${UI_BULLET} %-${max_key}s : ${UI_BOLD}%-20s${UI_NC}   ${UI_BULLET} %-${max_key}s : ${UI_BOLD}%s${UI_NC}\n" \
                "$l_key" "$l_val" "$r_key" "$r_val"
        else
            printf "   ${UI_BULLET} %-${max_key}s : ${UI_BOLD}%s${UI_NC}\n" "$l_key" "$l_val"
        fi
    done
}

# ═══════════════════════════════════════════════════════════════════════════════
# §12. Initialization
# ═══════════════════════════════════════════════════════════════════════════════

# Set up cleanup trap (appends to existing traps instead of overwriting)
_ui_append_trap() {
    local new_cmd="$1"; shift
    for sig in "$@"; do
        local existing
        existing=$(trap -p "$sig" 2>/dev/null | sed "s/^trap -- '//;s/' ${sig}\$//") || true
        if [[ -n "$existing" ]]; then
            trap "${existing}; ${new_cmd}" "$sig"
        else
            trap "$new_cmd" "$sig"
        fi
    done
}
_ui_append_trap 'ui::cleanup' EXIT INT TERM
