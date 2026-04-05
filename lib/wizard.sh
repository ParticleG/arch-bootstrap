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
declare -a _WIZARD_NAMES=()    # step display names (for error messages)
declare -a _WIZARD_FUNCS=()    # step function names

# Register a wizard step.
# Each step function must return: 0=ok, 2=back, 130=abort
# Usage: wizard::register "语言" _step_language
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

    if (( max < 0 )); then
        ui::error "No wizard steps registered"
        return 1
    fi

    while (( step <= max )); do
        "${_WIZARD_FUNCS[$step]}"
        local rc=$?
        case $rc in
            0)   step=$(( step + 1 )) ;;
            2)   # Back — go to previous step (min 0)
                 if (( step > 0 )); then
                     step=$(( step - 1 ))
                 else
                     ui::warn "$(ui::t '已经是第一步' 'Already at first step')"
                 fi
                 ;;
            130) # Abort (Ctrl-C)
                 ui::warn "$(ui::t '已中止' 'Aborted')"
                 exit 1
                 ;;
            *)   # Unexpected error
                 ui::error "$(ui::t "步骤 '${_WIZARD_NAMES[$step]}' 失败 (exit ${rc})" "Step '${_WIZARD_NAMES[$step]}' failed (exit ${rc})")"
                 exit "$rc"
                 ;;
        esac
    done
}
