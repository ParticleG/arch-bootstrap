#!/bin/bash
# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║  wizard.sh — Generic multi-step wizard engine with back/abort navigation     ║
# ║  Requires ui.sh to be sourced first (for ui::warn, ui::error, ui::enable_nav)║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

# ─── Dependencies ───
source "$(dirname "${BASH_SOURCE[0]}")/ui.sh"

# Guard against double-sourcing (arrays would be reset)
[[ -n "${_WIZARD_LOADED:-}" ]] && return 0
declare -r _WIZARD_LOADED=1

# ─── Step Registry ───
declare -a _WIZARD_NAMES=()    # step i18n keys (resolved at display time via ui::t)
declare -a _WIZARD_FUNCS=()    # step function names

# Register a wizard step.
# $1 = i18n key for the step name (resolved via ui::t when displayed)
# $2 = step function name (must return: 0=ok, 2=back, 130=abort)
# Usage: wizard::register "nav.lang" _step_language
wizard::register() {
    local name="$1" func="$2"
    _WIZARD_NAMES+=("$name")
    _WIZARD_FUNCS+=("$func")
}

# Return count of registered steps.
wizard::step_count() {
    echo "${#_WIZARD_FUNCS[@]}"
}

# Run the wizard loop — dispatches registered steps with back/abort handling.
# Precondition: ui::enable_nav has been called.
wizard::run() {
    local step=0
    local max=$(( ${#_WIZARD_FUNCS[@]} - 1 ))
    local _log_file=""

    if (( max < 0 )); then
        ui::error "No wizard steps registered"
        return 1
    fi

    local rc=0
    while (( step <= max )); do
        rc=0
        "${_WIZARD_FUNCS[$step]}" || rc=$?
        case $rc in
            0)   step=$(( step + 1 )) ;;
            2)   # Back — go to previous step (min 0)
                 if (( step > 0 )); then
                     step=$(( step - 1 ))
                 else
                     ui::warn "$(ui::t 'wizard.first_step')"
                 fi
                 ;;
            130) # Abort (Ctrl-C)
                 ui::warn "$(ui::t 'wizard.aborted')"
                 exit 1
                 ;;
            *)   # Unexpected error
                 local _step_name _log_hint=""
                 _step_name="$(ui::t "${_WIZARD_NAMES[$step]}")"
                 # Point user to the log file for fzf/TUI diagnostics
                 _log_file="$(ui::log_path 2>/dev/null)"
                 if [[ -n "$_log_file" ]] && [[ -f "$_log_file" ]]; then
                     _log_hint=" (see $_log_file)"
                 fi
                 ui::error "$(ui::t 'wizard.step_failed' "$_step_name" "$rc")${_log_hint}"
                 # Dump last few log lines to stderr for immediate visibility
                 if [[ -n "$_log_hint" ]]; then
                     echo "--- Last 10 log lines ---" >&2
                     tail -10 "$_log_file" 2>/dev/null >&2 || true
                     echo "---" >&2
                 fi
                 exit "$rc"
                 ;;
        esac
    done
}
