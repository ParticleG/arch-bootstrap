#!/bin/bash
# English translations — authoritative key set (fallback language)

[[ -n "${_I18N_EN_LOADED:-}" ]] && return 0
declare -r _I18N_EN_LOADED=1

declare -gA _I18N_EN=(
    # ── Common status ──
    [status.set]="Set"
    [status.not_set]="Not set"
    [status.enabled]="Enabled"
    [status.not_enabled]="Not enabled"
    [status.added]="Added"
    [status.not_needed]="Not needed"
    [status.cancelled]="Cancelled"

    # ── Validation ──
    [validate.username.empty]="Username cannot be empty"
    [validate.username.format]="Only lowercase letters, digits, underscores, hyphens"

    # ── Mirror ──
    [mirror.no_reflector]="reflector not found, using built-in mirror list"
    [mirror.fetching]="Fetching China mirrors via reflector (sorted by speed)..."
    [mirror.fetch_failed]="reflector failed, using built-in mirror list"
    [mirror.no_results]="reflector returned no mirrors, using built-in list"
    [mirror.found]="Found %s mirrors (sorted by speed)"

    # ── Navigation (wizard step names & progress labels) ──
    [nav.lang]="Language"
    [nav.disk]="Disk"
    [nav.net]="Network"
    [nav.repos]="Repos"
    [nav.gpu]="GPU"
    [nav.user]="Username"
    [nav.passwd]="Password"
    [nav.root]="Root Passwd"
    [nav.confirm]="Confirm"

    # ── Step titles (fzf / input prompts) ──
    [step.lang.title]="System Language"
    [step.disk.title]="Target Disk"
    [step.net.title]="Network Backend"
    [step.gpu.title]="GPU Drivers"
    [step.user.title]="Username"
    [step.passwd.title]="User Password"
    [step.root.title]="Root Password (empty = none)"

    # ── Step messages ──
    [step.lang.success]="Language: %s"
    [step.lang.kmscon]="Auto-added %s for non-English TTY rendering"
    [step.disk.success]="Target disk: %s"
    [step.net.success]="Network: %s"
    [step.repos.confirm]="Enable multilib repo? (32-bit compat, e.g. Steam)"
    [step.repos.enabled]="multilib: enabled"
    [step.repos.disabled]="multilib: not enabled"
    [step.gpu.success]="GPU drivers: %s"
    [step.gpu.mesa_only]="GPU drivers: mesa only (generic)"
    [step.gpu.mesa_generic]="mesa (generic)"
    [step.user.success]="Username: %s"
    [step.passwd.empty]="User password cannot be empty"
    [step.root.set]="Root password: set"
    [step.root.unset]="Root password: not set"

    # ── Confirm step ──
    [confirm.lang]="Language"
    [confirm.disk]="Disk"
    [confirm.net]="Network"
    [confirm.gpu]="GPU Drivers"
    [confirm.user]="Username"
    [confirm.root]="Root Passwd"
    [confirm.version]="Version"
    [confirm.prompt]="Confirm configuration? Generate JSON files?"
    [confirm.preview_title]="CONFIGURATION SUMMARY"

    # ── Fixed summary items ──
    [fixed.boot]="Boot"
    [fixed.fs]="FS"
    [fixed.audio]="Audio"
    [fixed.bt]="BT"

    # ── Post-generation ──
    [post.title]="Files Generated"
    [post.sys_config]="(system config)"
    [post.credentials]="(credentials)"
    [post.kmscon_hint]="Hint: After first boot, enable kmscon to replace default TTY:"

    # ── ISO install ──
    [iso.title]="Install"
    [iso.detected]="Arch Linux ISO environment detected"
    [iso.run_now]="Run archinstall now?"
    [iso.mount_not_found]="Mount point not found, enable kmscon manually:"
    [iso.complete_title]="Installation Complete"
    [iso.success]="System installed successfully"
    [iso.reboot]="Reboot into the new system:"

    # ── Wizard engine ──
    [wizard.first_step]="Already at first step"
    [wizard.aborted]="Aborted"
    [wizard.step_failed]="Step '%s' failed (exit %s)"

    # ── Option labels (dynamically-built arrays) ──
    [opt.lang.zh_CN]="Chinese   zh_CN.UTF-8"
    [opt.lang.en_US]="English   en_US.UTF-8"
    [opt.lang.ja_JP]="Japanese  ja_JP.UTF-8"
    [opt.net.nm_iwd]="NetworkManager + iwd  (recommended)"
    [opt.net.nm]="NetworkManager + wpa_supplicant  (legacy)"
)
