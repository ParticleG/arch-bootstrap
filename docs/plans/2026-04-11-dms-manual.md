# DMS Manual Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "DankMaterialShell (Manual)" desktop environment option that installs DMS without the dankinstall binary, following the exo.py pattern.

**Architecture:** New `dms_manual.py` module installs all packages via paru in two phases (quickshell-git first to avoid conflicts, then everything else), runs `dms setup` with stdin piping for automation, configures greetd with dms-greeter, enables systemd services via manual symlinks. Wizard/installation/config/i18n modules updated to support the new `dms_manual` option.

**Tech Stack:** Python 3, archinstall, subprocess, pathlib

---

## Task 1: Add DMS Manual constants to constants.py

**Files:**
- Modify: `arch_bootstrap/constants.py` (after EXO constants block, around line 260)

**Add the following constants after `EXO_SYSTEM_PACKAGES`:**

```python
# DMS Manual installation packages
DMS_MANUAL_PREREQ_PACKAGES: list[str] = [
    'quickshell-git',               # Must be installed first to avoid dependency conflicts
]

DMS_MANUAL_AUR_PACKAGES: list[str] = [
    'greetd-dms-greeter-git',
]

DMS_MANUAL_SYSTEM_PACKAGES: list[str] = [
    'greetd', 'xdg-desktop-portal-gtk',
    'accountsservice', 'xwayland-satellite', 'matugen',
    'dgop', 'cava', 'cups-pk-helper', 'kimageformats',
    'libavif', 'libheif', 'libjxl', 'qt6ct',
]

DMS_MANUAL_COMPOSITOR_PACKAGES: dict[str, list[str]] = {
    'niri': ['niri', 'dms-shell-niri'],
    'hyprland': ['hyprland', 'dms-shell-hyprland'],
}

DMS_MANUAL_TERMINAL_PACKAGES: dict[str, str] = {
    'ghostty': 'ghostty',
    'kitty': 'kitty',
    'alacritty': 'alacritty',
}
```

**Commit:** `git commit -m "feat: add DMS Manual package constants"`

---

## Task 2: Create dms_manual.py

**Files:**
- Create: `arch_bootstrap/dms_manual.py`

**This module follows the `exo.py` pattern exactly.** Key patterns to match:
- `subprocess.run(['arch-chroot', str(chroot_dir), ...], check=False)` for all commands
- `runuser -l {username} -c '...'` for user-level commands
- `GIT_CONFIG_SYSTEM=/etc/gitconfig MAKEPKG_GIT_CONFIG=/etc/gitconfig LANG=C.UTF-8` env prefix for paru
- `_info()` / `_debug()` wrappers using `archinstall.lib.output`
- `try/finally` for sudoers cleanup
- Functions return `bool` for fatal operations, `None` for non-fatal
- NO nvidia workaround (removed from scope)

**Complete module structure:**

```python
"""DMS Manual installer - installs DankMaterialShell without dankinstall binary."""

from __future__ import annotations

import subprocess
from pathlib import Path

from archinstall.lib.output import Font, debug, info

from .constants import (
    DMS_MANUAL_AUR_PACKAGES,
    DMS_MANUAL_COMPOSITOR_PACKAGES,
    DMS_MANUAL_PREREQ_PACKAGES,
    DMS_MANUAL_SYSTEM_PACKAGES,
    DMS_MANUAL_TERMINAL_PACKAGES,
)
from .i18n import t


def _info(msg: str) -> None:
    info(msg, fg=Font.green)


def _debug(msg: str) -> None:
    debug(f'[dms-manual] {msg}')


_GREETD_CONFIG = """\
[terminal]
vt = 1

[default_session]
command = "dms-greeter"
user = "greeter"
"""

_SUDOERS_FILE = '99-dms-manual-temp'

# Maps compositor/terminal wizard values to dms setup stdin prompt choices
_DMS_SETUP_COMPOSITOR_MAP: dict[str, str] = {'niri': '1', 'hyprland': '2'}
_DMS_SETUP_TERMINAL_MAP: dict[str, str] = {'ghostty': '1', 'kitty': '2', 'alacritty': '3'}


def install_dms_manual(
    chroot_dir: Path,
    username: str,
    compositor: str = 'niri',
    terminal: str = 'ghostty',
    country: str | None = None,
    gpu_vendors: list[str] | None = None,
) -> None:
    """Install DMS desktop environment manually (without dankinstall)."""
    gpu_vendors = gpu_vendors or []
    sudoers_path = chroot_dir / 'etc' / 'sudoers.d' / _SUDOERS_FILE

    try:
        # 1. Temporary NOPASSWD sudoers
        _info(t('dms_manual.setting_up_sudoers'))
        sudoers_path.parent.mkdir(parents=True, exist_ok=True)
        sudoers_path.write_text(f'{username} ALL=(ALL) NOPASSWD: ALL\n')
        sudoers_path.chmod(0o440)

        # 2. Install quickshell-git first (must precede other packages)
        if not _install_prereq_packages(chroot_dir, username):
            return

        # 3. Install all remaining packages
        if not _install_packages(chroot_dir, username, compositor, terminal):
            return

        # 4. Run dms setup for initial configuration
        _run_dms_setup(chroot_dir, username, compositor, terminal)

    finally:
        # Always remove temporary sudoers
        if sudoers_path.exists():
            sudoers_path.unlink()
            _debug('Removed temporary sudoers rule')

    # 5. Configure greetd
    _configure_greetd(chroot_dir)

    # 6. Enable systemd services
    _enable_services(chroot_dir, username, compositor)

    # 7. Configure environment variables
    _configure_environment(chroot_dir)

    # 8. Fix file ownership
    _fix_ownership(chroot_dir, username)

    _info(t('dms_manual.complete'))


def _install_prereq_packages(chroot_dir: Path, username: str) -> bool:
    """Install quickshell-git first to avoid dependency conflicts."""
    _info(t('dms_manual.installing_prereqs'))

    cmd = (
        'GIT_CONFIG_SYSTEM=/etc/gitconfig '
        'MAKEPKG_GIT_CONFIG=/etc/gitconfig '
        'LANG=C.UTF-8 '
        f"paru -S --noconfirm --needed --skipreview {' '.join(DMS_MANUAL_PREREQ_PACKAGES)}"
    )

    result = subprocess.run(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c', cmd],
        check=False,
    )

    if result.returncode != 0:
        _info(t('dms_manual.failed') % result.returncode)
        return False

    return True


def _install_packages(
    chroot_dir: Path,
    username: str,
    compositor: str,
    terminal: str,
) -> bool:
    """Install all remaining DMS packages via paru."""
    _info(t('dms_manual.installing_deps'))

    packages = list(DMS_MANUAL_AUR_PACKAGES) + list(DMS_MANUAL_SYSTEM_PACKAGES)

    # Compositor-specific packages
    packages.extend(DMS_MANUAL_COMPOSITOR_PACKAGES.get(compositor, []))

    # Terminal package
    term_pkg = DMS_MANUAL_TERMINAL_PACKAGES.get(terminal)
    if term_pkg:
        packages.append(term_pkg)

    cmd = (
        'GIT_CONFIG_SYSTEM=/etc/gitconfig '
        'MAKEPKG_GIT_CONFIG=/etc/gitconfig '
        'LANG=C.UTF-8 '
        f"paru -S --noconfirm --needed --skipreview {' '.join(packages)}"
    )

    result = subprocess.run(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c', cmd],
        check=False,
    )

    if result.returncode != 0:
        _info(t('dms_manual.failed') % result.returncode)
        return False

    return True


def _run_dms_setup(
    chroot_dir: Path,
    username: str,
    compositor: str,
    terminal: str,
) -> None:
    """Run 'dms setup' with stdin piping for non-interactive execution.

    dms setup prompts (in order):
      1. Select compositor: 1=Niri, 2=Hyprland
      2. Select terminal:   1=Ghostty, 2=Kitty, 3=Alacritty
      3. Use systemd?:      1=Yes (always)
      4. Proceed?:          y (always)
    """
    _info(t('dms_manual.running_setup'))

    comp_choice = _DMS_SETUP_COMPOSITOR_MAP.get(compositor, '1')
    term_choice = _DMS_SETUP_TERMINAL_MAP.get(terminal, '1')
    stdin_input = f'{comp_choice}\n{term_choice}\n1\ny\n'

    result = subprocess.run(
        ['arch-chroot', str(chroot_dir),
         'runuser', '-l', username, '-c', 'dms setup'],
        input=stdin_input, text=True, check=False,
    )

    if result.returncode != 0:
        _debug(f'dms setup returned {result.returncode} (non-fatal)')


def _configure_greetd(chroot_dir: Path) -> None:
    """Write greetd configuration for DMS greeter."""
    _info(t('dms_manual.configuring_greetd'))

    greetd_dir = chroot_dir / 'etc' / 'greetd'
    greetd_dir.mkdir(parents=True, exist_ok=True)
    (greetd_dir / 'config.toml').write_text(_GREETD_CONFIG)


def _enable_services(chroot_dir: Path, username: str, compositor: str) -> None:
    """Enable systemd services via manual symlinks (systemctl doesn't work in chroot)."""
    _info(t('dms_manual.enabling_services'))

    # display-manager.service -> greetd.service
    dm_link = chroot_dir / 'etc' / 'systemd' / 'system' / 'display-manager.service'
    dm_link.parent.mkdir(parents=True, exist_ok=True)
    if dm_link.exists() or dm_link.is_symlink():
        dm_link.unlink()
    dm_link.symlink_to('/usr/lib/systemd/system/greetd.service')

    # default.target -> graphical.target
    target_link = chroot_dir / 'etc' / 'systemd' / 'system' / 'default.target'
    if target_link.exists() or target_link.is_symlink():
        target_link.unlink()
    target_link.symlink_to('/usr/lib/systemd/system/graphical.target')

    # DMS user service auto-start with compositor
    home = chroot_dir / 'home' / username
    if compositor == 'niri':
        wants_dir = home / '.config' / 'systemd' / 'user' / 'niri.service.wants'
    else:  # hyprland
        wants_dir = home / '.config' / 'systemd' / 'user' / 'hyprland-session.target.wants'

    wants_dir.mkdir(parents=True, exist_ok=True)
    dms_link = wants_dir / 'dms.service'
    if dms_link.exists() or dms_link.is_symlink():
        dms_link.unlink()
    dms_link.symlink_to('/usr/lib/systemd/user/dms.service')


def _configure_environment(chroot_dir: Path) -> None:
    """Write environment variables to /etc/environment."""
    env_file = chroot_dir / 'etc' / 'environment'

    entries = {
        'QT_QPA_PLATFORMTHEME': 'qt6ct',
        'QS_ICON_THEME': 'adwaita',
    }

    existing = env_file.read_text() if env_file.exists() else ''
    lines = existing.splitlines()

    for key, value in entries.items():
        if not any(line.startswith(f'{key}=') for line in lines):
            lines.append(f'{key}={value}')

    env_file.write_text('\n'.join(lines) + '\n' if lines else '')


def _fix_ownership(chroot_dir: Path, username: str) -> None:
    """Fix ownership of user configuration directories."""
    home = chroot_dir / 'home' / username
    config_dir = home / '.config'

    if config_dir.exists():
        subprocess.run(
            ['arch-chroot', str(chroot_dir), 'chown', '-R',
             f'{username}:{username}', f'/home/{username}/.config'],
            check=False,
        )
```

**Commit:** `git commit -m "feat: add DMS Manual installation module"`

---

## Task 3: Update wizard.py

**Files:**
- Modify: `arch_bootstrap/wizard.py`

**Changes (4 locations):**

### 3a. Add menu item in `step_desktop_env` function

Find the `items` list and add `dms_manual` between `dms` and `exo`:
```python
items = [
    MenuItem(t('step.desktop.minimal'), value='minimal'),
    MenuItem(t('step.desktop.dms'),     value='dms'),
    MenuItem(t('step.desktop.dms_manual'), value='dms_manual'),  # NEW
    MenuItem(t('step.desktop.exo'),     value='exo'),
]
```

### 3b. Update state cleanup when switching away from DMS

Change the condition that resets DMS state:
```python
# Before:
if state.desktop_env != 'dms':
# After:
if state.desktop_env not in ('dms', 'dms_manual'):
```

### 3c. Update conditional step functions

In `step_dms_compositor`:
```python
# Before:
if state.desktop_env != 'dms':
    return 'next'
# After:
if state.desktop_env not in ('dms', 'dms_manual'):
    return 'next'
```

In `step_dms_terminal`:
```python
# Before:
if state.desktop_env != 'dms':
    return 'next'
# After:
if state.desktop_env not in ('dms', 'dms_manual'):
    return 'next'
```

### 3d. Update confirmation panel

Add `dms_manual` case after the `dms` case:
```python
elif state.desktop_env == 'dms_manual':
    fixed_rows.append(_row(t('confirm.desktop'), 'DankMaterialShell (Manual)'))
    fixed_rows.append(_row(t('confirm.compositor'), state.dms_compositor, indent=2))
    fixed_rows.append(_row(t('confirm.terminal'), state.dms_terminal, indent=2))
```

**Commit:** `git commit -m "feat: add DMS Manual option to wizard"`

---

## Task 4: Update installation.py

**Files:**
- Modify: `arch_bootstrap/installation.py`

**Add dispatch block after the existing `dms` block:**

```python
# Post-install: DMS Manual desktop environment
if desktop_env == 'dms_manual' and username:
    from .dms_manual import install_dms_manual
    install_dms_manual(
        chroot_dir=chroot_dir, username=username,
        compositor=dms_compositor, terminal=dms_terminal,
        country=country, gpu_vendors=gpu_vendors,
    )
```

**Commit:** `git commit -m "feat: add DMS Manual dispatch to installation"`

---

## Task 5: Update config.py

**Files:**
- Modify: `arch_bootstrap/config.py`

**Add `dms_manual` to the upower condition:**

```python
# Before:
if state.desktop_env in ('dms', 'exo') and 'upower' not in all_packages:
# After:
if state.desktop_env in ('dms', 'dms_manual', 'exo') and 'upower' not in all_packages:
```

**Commit:** `git commit -m "feat: include upower for DMS Manual"`

---

## Task 6: Update i18n.py

**Files:**
- Modify: `arch_bootstrap/i18n.py`

**Add these keys to each language section:**

### English (en):
```python
'step.desktop.dms_manual':       'DankMaterialShell (Manual)',
'dms_manual.setting_up_sudoers': 'Setting up temporary sudo access...',
'dms_manual.installing_prereqs': 'Installing quickshell (this may take a while)...',
'dms_manual.installing_deps':    'Installing DMS dependencies via paru...',
'dms_manual.running_setup':      'Running dms setup for initial configuration...',
'dms_manual.configuring_greetd': 'Configuring greetd for DMS greeter...',
'dms_manual.enabling_services':  'Enabling DMS desktop services...',
'dms_manual.complete':           'DMS desktop environment installed successfully',
'dms_manual.failed':             'DMS manual installation failed (exit %d)',
```

### Chinese (zh):
```python
'step.desktop.dms_manual':       'DankMaterialShell（手动安装）',
'dms_manual.setting_up_sudoers': '设置临时 sudo 权限...',
'dms_manual.installing_prereqs': '安装 quickshell（可能需要较长时间）...',
'dms_manual.installing_deps':    '通过 paru 安装 DMS 依赖...',
'dms_manual.running_setup':      '运行 dms setup 生成初始配置...',
'dms_manual.configuring_greetd': '配置 greetd 登录管理器...',
'dms_manual.enabling_services':  '启用 DMS 桌面服务...',
'dms_manual.complete':           'DMS 桌面环境安装成功',
'dms_manual.failed':             'DMS 手动安装失败（退出码 %d）',
```

### Japanese (ja):
```python
'step.desktop.dms_manual':       'DankMaterialShell（手動インストール）',
'dms_manual.setting_up_sudoers': '一時的なsudo権限を設定中...',
'dms_manual.installing_prereqs': 'quickshellをインストール中（時間がかかる場合があります）...',
'dms_manual.installing_deps':    'paruでDMS依存パッケージをインストール中...',
'dms_manual.running_setup':      'dms setupで初期設定を生成中...',
'dms_manual.configuring_greetd': 'greetdログインマネージャーを設定中...',
'dms_manual.enabling_services':  'DMSデスクトップサービスを有効化中...',
'dms_manual.complete':           'DMSデスクトップ環境のインストールが完了しました',
'dms_manual.failed':             'DMS手動インストールに失敗しました（終了コード %d）',
```

**Note:** Added `dms_manual.installing_prereqs` key (not in original plan) for the quickshell-git pre-installation step.

**Commit:** `git commit -m "feat: add DMS Manual i18n translations (en/zh/ja)"`
