from __future__ import annotations

import os
import re
from pathlib import Path

from archinstall.lib.args import ArchConfig
from archinstall.lib.disk.device_handler import device_handler
from archinstall.lib.menu.helpers import Confirmation, Input, Selection
from archinstall.lib.menu.util import get_password
from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.models.device import BDevice, Unit
from archinstall.lib.models.network import NicType
from archinstall.lib.models.users import Password
from archinstall.tui.ui.components import OptionListScreen
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType

from .config import apply_wizard_state_to_config
from .disk import EFI_PARTITION_MIB, GPT_BACKUP_MIB, MIN_DISK_SIZE_MIB
from .constants import (
    BROWSER_OPTIONS,
    COUNTRY_NAMES,
    GPU_LABELS,
    GPU_VENDORS,
    KMSCON_FONT_OPTIONS,
    LANGUAGES,
    NETWORK_BACKENDS,
    REGION_MENU_COUNTRIES,
)
from .detection import is_raw_tty, needs_kmscon
from .i18n import set_lang, t
from .mirrors import apply_mirrors_to_live_iso


# =============================================================================
# TUI helpers
# =============================================================================

class _LeftAlignedScreen[ValueT](OptionListScreen[ValueT]):
    """OptionListScreen with left-aligned header text centered as a block.

    archinstall's default CSS sets `text-align: center` and `width: 100%`
    on `.header-text`, which makes the confirmation panel unreadable when
    labels have different lengths.  This subclass overrides those styles so
    the text block is internally left-aligned but centered on screen.
    """

    def on_mount(self) -> None:
        super().on_mount()
        try:
            from textual.widgets import Label
            header = self.query_one('#header_text', Label)
            header.styles.text_align = 'left'
            header.styles.width = 'auto'
            # Center the shrunk label inside its parent (content-container)
            if header.parent is not None:
                header.parent.styles.align_horizontal = 'center'
        except Exception:
            pass


# =============================================================================
# Wizard steps
# =============================================================================

# Each wizard step is an async function that modifies a WizardState.
# Returns 'next', 'back', or 'abort'.

class WizardState:
    """Mutable state accumulated during the wizard."""

    def __init__(self) -> None:
        self.country: str | None = None
        self.locale: str = 'en_US.UTF-8'
        self.disk_device: BDevice | None = None
        self.network_type: NicType = NicType.NM_IWD
        self.multilib: bool = True
        self.gpu_vendors: list[str] = []
        self.username: str = ''
        self.user_password: Password | None = None
        self.root_password: Password | None = None
        self.detected_country: str | None = None
        self.detected_gpu: list[str] = []
        self.preferred_disk: Path | None = None
        self.mirror_list_handler: MirrorListHandler | None = None
        # kmscon font selection
        self.kmscon_font_name: str = ''
        self.kmscon_font_package: str = ''
        self.screen_resolution: tuple[int, int] | None = None
        # DMS desktop environment
        self.desktop_env: str = 'minimal'      # 'minimal' | 'dms' | 'dms_manual' | 'exo'
        self.dms_compositor: str = 'niri'       # 'niri' | 'hyprland'
        self.dms_terminal: str = 'ghostty'      # 'ghostty' | 'kitty' | 'alacritty'
        # Browser selection
        self.browsers: list[str] = []           # ['firefox', 'chromium', ...]


async def step_language(state: WizardState) -> str:
    """Select system language."""
    raw_tty = is_raw_tty()

    items = [
        MenuItem(f'{label} ({code})', value=code)
        for code, label in LANGUAGES.items()
    ]
    group = MenuItemGroup(items)

    # On raw TTY, default to English to avoid CJK rendering issues
    if raw_tty and state.locale != 'en_US.UTF-8':
        header = (
            'Select system language\n'
            'NOTE: Raw TTY detected — CJK languages will install kmscon\n'
            'for proper console rendering after reboot.'
        )
    else:
        header = 'Select system language / 选择系统语言 / システム言語を選択'

    group.set_default_by_value(state.locale)
    group.set_focus_by_value(state.locale)

    result = await Selection[str](
        group,
        header=header,
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.locale = result.get_value()
            lang_map = {'zh_CN.UTF-8': 'zh', 'ja_JP.UTF-8': 'ja'}
            set_lang(lang_map.get(state.locale, 'en'))
            return 'next'
        case _:
            return 'back'


async def step_kmscon_font(state: WizardState) -> str:
    """Select kmscon font (only shown for non-English locales).

    This step is conditionally inserted after language selection when kmscon
    is needed for CJK console rendering.
    """
    if not needs_kmscon(state.locale):
        # Auto-skip: not needed for English locale
        # Clear any previously selected font if user switched back to English
        state.kmscon_font_name = ''
        state.kmscon_font_package = ''
        return 'next'

    # Determine locale prefix for font lookup (e.g. 'zh_CN' from 'zh_CN.UTF-8')
    locale_prefix = state.locale.split('.')[0]
    font_options = KMSCON_FONT_OPTIONS.get(locale_prefix, [])

    if not font_options:
        # No font options for this locale, fall back to Noto Sans CJK
        state.kmscon_font_name = 'Noto Sans CJK SC'
        state.kmscon_font_package = 'noto-fonts-cjk'
        return 'next'

    items = [
        MenuItem(f'{opt["label"]}  ({opt["package"]})', value=idx)
        for idx, opt in enumerate(font_options)
    ]
    group = MenuItemGroup(items)

    # Pre-select current choice or default to first option
    preset_idx = 0
    if state.kmscon_font_name:
        for idx, opt in enumerate(font_options):
            if opt['name'] == state.kmscon_font_name:
                preset_idx = idx
                break
    group.set_default_by_value(preset_idx)
    group.set_focus_by_value(preset_idx)

    result = await Selection[int](
        group,
        header=t('step.kmscon_font.title'),
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            selected_idx = result.get_value()
            selected = font_options[selected_idx]
            state.kmscon_font_name = selected['name']
            state.kmscon_font_package = selected['package']
            return 'next'
        case _:
            return 'back'


async def step_region(state: WizardState) -> str:
    """Select country/region."""
    items = [
        MenuItem(f'{COUNTRY_NAMES[code]} ({code})', value=code)
        for code in REGION_MENU_COUNTRIES
    ]
    group = MenuItemGroup(items)

    preset = state.country or state.detected_country
    if preset and preset in REGION_MENU_COUNTRIES:
        group.set_default_by_value(preset)
        group.set_focus_by_value(preset)

    result = await Selection[str](
        group,
        header=t('step.region.title'),
        allow_skip=True,
        enable_filter=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.country = result.get_value()
            # Apply mirrors to live ISO for faster pacstrap
            if state.mirror_list_handler:
                apply_mirrors_to_live_iso(state.country, state.mirror_list_handler)
            return 'next'
        case _:
            return 'back'


async def step_disk(state: WizardState) -> str:
    """Select target disk."""
    try:
        devices = [
            d for d in device_handler.devices
            if not d.device_info.read_only
            and d.device_info.type != 'loop'
        ]
    except Exception:
        devices = []

    if not devices:
        # No suitable disks found
        await Confirmation(
            header='No suitable disks found. Cannot proceed.',
            allow_skip=False,
            preset=True,
        ).show()
        return 'abort'

    # Filter out disks that are too small
    usable_devices = [
        d for d in devices
        if (d.device_info.total_size.convert(Unit.B, None).value // (1024 * 1024))
        >= MIN_DISK_SIZE_MIB
    ]

    if not usable_devices:
        await Confirmation(
            header=f'No disks with at least {MIN_DISK_SIZE_MIB // 1024} GiB found. Cannot proceed.',
            allow_skip=False,
            preset=True,
        ).show()
        return 'abort'

    while True:
        items = []
        for dev in usable_devices:
            di = dev.device_info
            size_str = di.total_size.format_highest()
            part_count = len(dev.partition_infos)
            label = f'{di.path}  {di.model}  {size_str}  ({part_count} partitions)'
            items.append(MenuItem(label, value=dev))

        group = MenuItemGroup(items)

        # Try to preselect preferred disk
        if state.preferred_disk:
            for dev in usable_devices:
                if dev.device_info.path == state.preferred_disk:
                    group.set_default_by_value(dev)
                    group.set_focus_by_value(dev)
                    break

        result = await Selection[BDevice](
            group,
            header=t('step.disk.title'),
            allow_skip=True,
        ).show()

        match result.type_:
            case ResultType.Skip:
                return 'back'
            case ResultType.Selection:
                selected = result.get_value()

                # Calculate partition sizes using shared constants from disk.py
                total_bytes = selected.device_info.total_size.convert(Unit.B, None).value
                total_mib = total_bytes // (1024 * 1024)
                root_mib = total_mib - EFI_PARTITION_MIB - GPT_BACKUP_MIB
                root_gib = root_mib / 1024

                total_display = selected.device_info.total_size.format_highest()
                preview = (
                    f'Partition layout for {selected.device_info.path} ({total_display}):\n'
                    f'\n'
                    f'  EFI     1 GiB        FAT32    /boot\n'
                    f'  Btrfs   {root_gib:.0f} GiB      zstd     subvols: @ @home @log @pkg\n'
                    f'\n'
                    f'ALL DATA ON THIS DISK WILL BE ERASED.'
                )

                confirm_result = await Confirmation(
                    header=preview,
                    allow_skip=True,
                    preset=True,
                ).show()

                match confirm_result.type_:
                    case ResultType.Selection:
                        if confirm_result.item() == MenuItem.yes():
                            state.disk_device = selected
                            return 'next'
                        # User said No -> loop back to disk selection
                        continue
                    case _:
                        return 'back'
            case _:
                return 'back'


async def step_network(state: WizardState) -> str:
    """Select network backend."""
    items = [
        MenuItem(label, value=key)
        for key, label in NETWORK_BACKENDS.items()
    ]
    group = MenuItemGroup(items)

    current = state.network_type.value
    group.set_default_by_value(current)
    group.set_focus_by_value(current)

    result = await Selection[str](
        group,
        header=t('step.net.title'),
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            value = result.get_value()
            state.network_type = NicType(value)
            return 'next'
        case _:
            return 'back'


async def step_repos(state: WizardState) -> str:
    """Enable multilib repository."""
    result = await Confirmation(
        header=t('step.repos.confirm'),
        allow_skip=True,
        preset=state.multilib,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.multilib = result.item() == MenuItem.yes()
            return 'next'
        case _:
            return 'back'


async def step_gpu_drivers(state: WizardState) -> str:
    """Select GPU drivers."""
    items = [
        MenuItem(GPU_LABELS[vendor], value=vendor)
        for vendor in GPU_VENDORS
    ]
    group = MenuItemGroup(items)

    # Pre-select detected GPUs
    preselect = state.gpu_vendors if state.gpu_vendors else state.detected_gpu
    if preselect:
        group.set_selected_by_value(preselect)

    result = await Selection[str](
        group,
        header=t('step.gpu.title'),
        multi=True,
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.gpu_vendors = result.get_values()
            return 'next'
        case _:
            return 'back'


async def step_desktop_env(state: WizardState) -> str:
    """Select desktop environment."""
    items = [
        MenuItem(t('step.desktop.minimal'), value='minimal'),
        MenuItem(t('step.desktop.dms'), value='dms'),
        MenuItem(t('step.desktop.dms_manual'), value='dms_manual'),
        MenuItem(t('step.desktop.exo'), value='exo'),
    ]
    group = MenuItemGroup(items)
    group.set_focus_by_value(state.desktop_env)

    result = await Selection[str](
        group,
        header=t('step.desktop.title'),
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.desktop_env = result.get_value()
            # Clear stale DMS state when switching away from DMS
            if state.desktop_env not in ('dms', 'dms_manual'):
                state.dms_compositor = 'niri'
                state.dms_terminal = 'ghostty'
            return 'next'
        case _:
            return 'back'


async def step_dms_compositor(state: WizardState) -> str:
    """Select DMS compositor (only shown if DMS selected)."""
    if state.desktop_env not in ('dms', 'dms_manual'):
        return 'next'

    items = [
        MenuItem(t('step.compositor.niri'), value='niri'),
        MenuItem(t('step.compositor.hyprland'), value='hyprland'),
    ]
    group = MenuItemGroup(items)
    group.set_focus_by_value(state.dms_compositor)

    result = await Selection[str](
        group,
        header=t('step.compositor.title'),
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.dms_compositor = result.get_value()
            return 'next'
        case _:
            return 'back'


async def step_dms_terminal(state: WizardState) -> str:
    """Select DMS terminal emulator (only shown if DMS selected)."""
    if state.desktop_env not in ('dms', 'dms_manual'):
        return 'next'

    items = [
        MenuItem(t('step.terminal.ghostty'), value='ghostty'),
        MenuItem(t('step.terminal.kitty'), value='kitty'),
        MenuItem(t('step.terminal.alacritty'), value='alacritty'),
    ]
    group = MenuItemGroup(items)
    group.set_focus_by_value(state.dms_terminal)

    result = await Selection[str](
        group,
        header=t('step.terminal.title'),
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.dms_terminal = result.get_value()
            return 'next'
        case _:
            return 'back'


async def step_browser(state: WizardState) -> str:
    """Select web browsers to install (multi-select, optional)."""
    items = [
        MenuItem(info['label'], value=key)
        for key, info in BROWSER_OPTIONS.items()
    ]
    group = MenuItemGroup(items)

    # Pre-select current choices
    if state.browsers:
        group.set_selected_by_value(state.browsers)

    result = await Selection[str](
        group,
        header=t('step.browser.title'),
        multi=True,
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.browsers = result.get_values()
            return 'next'
        case _:
            return 'back'


async def step_username(state: WizardState) -> str:
    """Enter username."""
    default = state.username or os.environ.get('SUDO_USER', '') or os.environ.get('USER', '')
    # Filter out 'root' — not a useful default
    if default == 'root':
        default = ''

    def validate(value: str) -> str | None:
        if not value:
            return t('validate.username.empty')
        if not re.match(r'^[a-z_][a-z0-9_-]*$', value):
            return t('validate.username.format')
        if len(value) > 32:
            return 'Username must be 32 characters or fewer'
        return None

    result = await Input(
        header=t('step.user.title'),
        default_value=default if default else None,
        allow_skip=True,
        validator_callback=validate,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            value = result.get_value()
            if value:
                state.username = value
                return 'next'
            return 'back'
        case _:
            return 'back'


async def step_user_password(state: WizardState) -> str:
    """Enter user password."""
    while True:
        password = await get_password(
            header=t('step.passwd.title'),
            allow_skip=True,
        )

        if password is None:
            return 'back'

        # Warn on empty password
        if not password.plaintext:
            confirm_empty = await Confirmation(
                header='No password set. Continue with empty password?',
                allow_skip=True,
                preset=False,
            ).show()
            if (confirm_empty.type_ == ResultType.Selection
                    and confirm_empty.item() == MenuItem.yes()):
                state.user_password = password
                return 'next'
            # User declined empty password -> re-prompt
            continue

        state.user_password = password
        return 'next'


async def step_root_password(state: WizardState) -> str:
    """Enter root password (optional)."""
    result = await Confirmation(
        header=t('step.root.title'),
        allow_skip=True,
        preset=False,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            if result.item() == MenuItem.yes():
                password = await get_password(
                    header=t('step.root.title'),
                    allow_skip=True,
                )
                if password is None:
                    return 'back'
                state.root_password = password
            else:
                state.root_password = None
            return 'next'
        case _:
            return 'back'


# =============================================================================
# Confirmation panel
# =============================================================================

async def step_confirm(
    state: WizardState,
    config: ArchConfig,
) -> str:
    """Confirmation panel: Install / Advanced Modify / Cancel."""
    # Build summary text with dynamic left-aligned padding
    kmscon_needed = needs_kmscon(state.locale)

    def _row(label: str, value: str, indent: int = 0) -> tuple[int, str, str]:
        """Return (indent, label, value) for later formatting."""
        return (indent, label, value)

    # Collect rows as (indent, label, value)
    rows: list[tuple[int, str, str]] = [
        _row(t('confirm.lang'), state.locale),
        _row(t('confirm.region'), COUNTRY_NAMES.get(state.country, 'Unknown') if state.country else t('status.not_set')),
        _row(t('confirm.timezone'), config.timezone),
        _row(
            t('confirm.disk'),
            (f'{state.disk_device.device_info.path}  '
             f'({state.disk_device.device_info.total_size.format_highest()})')
            if state.disk_device else t('status.not_set'),
        ),
        _row(t('confirm.net'), state.network_type.display_msg()),
        _row('Multilib', 'Enabled' if state.multilib else 'Disabled'),
        _row(t('confirm.gpu'), ', '.join(GPU_LABELS.get(v, v) for v in state.gpu_vendors) or 'None'),
        _row(
            t('confirm.browser'),
            ', '.join(BROWSER_OPTIONS[b]['label'] for b in state.browsers) if state.browsers else 'None',
        ),
        _row(t('confirm.user'), state.username),
        _row(t('confirm.root'), t('status.set') if state.root_password else t('status.not_set')),
        _row('kmscon', 'Added (CJK console)' if kmscon_needed else t('status.not_needed')),
    ]
    if kmscon_needed and state.kmscon_font_name:
        rows.append(_row('Font', f'{state.kmscon_font_name} ({state.kmscon_font_package})', indent=2))

    fixed_rows: list[tuple[int, str, str]] = [
        _row(t('fixed.boot'), 'EFISTUB (UKI)'),
        _row(t('fixed.fs'), 'Btrfs + zstd + Snapper'),
        _row(t('fixed.audio'), 'PipeWire'),
        _row(t('fixed.bt'), t('status.enabled')),
        _row('Power', 'tuned'),
        _row('Swap', 'zram (lzo-rle)'),
    ]
    if state.desktop_env == 'dms':
        fixed_rows.append(_row(t('confirm.desktop'), 'DankMaterialShell (DankInstall)'))
        fixed_rows.append(_row(t('confirm.compositor'), state.dms_compositor, indent=2))
        fixed_rows.append(_row(t('confirm.terminal'), state.dms_terminal, indent=2))
    elif state.desktop_env == 'dms_manual':
        fixed_rows.append(_row(t('confirm.desktop'), 'DankMaterialShell (Manual)'))
        fixed_rows.append(_row(t('confirm.compositor'), state.dms_compositor, indent=2))
        fixed_rows.append(_row(t('confirm.terminal'), state.dms_terminal, indent=2))
    elif state.desktop_env == 'exo':
        fixed_rows.append(_row(t('confirm.desktop'), 'Exo (Material Design 3 + Niri)'))
    else:
        fixed_rows.append(_row(t('confirm.desktop'), 'Minimal'))

    # Compute max label width (excluding indent) for uniform padding
    all_rows = rows + fixed_rows
    max_label_len = max((len(label) for _, label, _ in all_rows), default=12)

    def _fmt(indent: int, label: str, value: str) -> str:
        pad = ' ' * indent
        # Pad label+colon to fill (max_label_len + 1 - indent) so colons align
        field_width = max_label_len + 1 - indent
        return f'{pad}{label + ":":<{field_width}}  {value}'

    lines = [_fmt(*r) for r in rows]
    lines.append('')
    lines.append('── Fixed defaults ──')
    lines.extend(_fmt(*r) for r in fixed_rows)
    summary = '\n'.join(lines)

    items = [
        MenuItem('Install', value='install'),
        MenuItem('Advanced Modify (archinstall menu)', value='advanced'),
        MenuItem('Cancel', value='cancel'),
    ]
    group = MenuItemGroup(items)
    group.set_focus_by_value('install')

    result = await _LeftAlignedScreen[str](
        group,
        header=summary,
        allow_skip=True,
    ).run()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            return result.get_value()
        case _:
            return 'back'


# =============================================================================
# Wizard runner
# =============================================================================

async def run_wizard(
    state: WizardState,
    config: ArchConfig,
    mirror_list_handler: MirrorListHandler,
) -> str:
    """Run the complete wizard. Returns 'install', 'advanced', or 'abort'."""
    state.mirror_list_handler = mirror_list_handler

    steps = [
        step_language,
        step_kmscon_font,
        step_region,
        step_disk,
        step_network,
        step_repos,
        step_gpu_drivers,
        step_desktop_env,
        step_dms_compositor,
        step_dms_terminal,
        step_browser,
        step_username,
        step_user_password,
        step_root_password,
    ]

    current = 0
    while current < len(steps):
        result = await steps[current](state)
        if result == 'next':
            current += 1
        elif result == 'back':
            if current > 0:
                current -= 1
            else:
                # At first step: confirm abort instead of looping
                abort_result = await Confirmation(
                    header='Abort installation?',
                    allow_skip=True,
                    preset=False,
                ).show()
                if (abort_result.type_ == ResultType.Selection
                        and abort_result.item() == MenuItem.yes()):
                    return 'abort'
                # User said No or skipped -> re-show first step
        elif result == 'abort':
            return 'abort'

    # Apply wizard state to config before showing confirmation
    apply_wizard_state_to_config(state, config, mirror_list_handler)

    # Confirmation loop (can return to wizard or open GlobalMenu)
    while True:
        action = await step_confirm(state, config)
        if action == 'install':
            return 'install'
        elif action == 'cancel' or action == 'back':
            # Go back to the last wizard step
            current = len(steps) - 1
            while current >= 0:
                result = await steps[current](state)
                if result == 'next':
                    current += 1
                    if current >= len(steps):
                        apply_wizard_state_to_config(state, config, mirror_list_handler)
                        break
                elif result == 'back':
                    current = max(0, current - 1)
                elif result == 'abort':
                    return 'abort'
        elif action == 'advanced':
            return 'advanced'

    return 'abort'
