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
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType

from .config import apply_wizard_state_to_config
from .constants import (
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
        self.desktop_env: str = 'minimal'      # 'minimal' | 'dms'
        self.dms_compositor: str = 'niri'       # 'niri' | 'hyprland'
        self.dms_terminal: str = 'ghostty'      # 'ghostty' | 'kitty' | 'alacritty'


async def step_language(state: WizardState) -> str:
    """Step 1: Select system language."""
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
    """Step 1.5: Select kmscon font (only shown for non-English locales).

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
    """Step 2: Select country/region."""
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
    """Step 3: Select target disk."""
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

    items = []
    for dev in devices:
        di = dev.device_info
        size_str = di.total_size.format_highest()
        part_count = len(dev.partition_infos)
        label = f'{di.path}  {di.model}  {size_str}  ({part_count} partitions)'
        items.append(MenuItem(label, value=dev))

    group = MenuItemGroup(items)

    # Try to preselect preferred disk
    if state.preferred_disk:
        for dev in devices:
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

            # Calculate partition sizes (must match disk.py logic)
            total_bytes = selected.device_info.total_size.convert(Unit.B, None).value
            total_mib = total_bytes // (1024 * 1024)
            root_mib = total_mib - 1025 - 1  # EFI start+size + GPT backup
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
                    # User said No -> return to disk selection (re-enter this step)
                    return await step_disk(state)
                case _:
                    return 'back'
        case _:
            return 'back'


async def step_network(state: WizardState) -> str:
    """Step 4: Select network backend."""
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
    """Step 5: Enable multilib repository."""
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
    """Step 6: Select GPU drivers."""
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
    """Step 7: Select desktop environment."""
    items = [
        MenuItem(t('step.desktop.minimal'), value='minimal'),
        MenuItem(t('step.desktop.dms'), value='dms'),
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
            return 'next'
        case _:
            return 'back'


async def step_dms_compositor(state: WizardState) -> str:
    """Step 8: Select DMS compositor (only shown if DMS selected)."""
    if state.desktop_env != 'dms':
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
    """Step 9: Select DMS terminal emulator (only shown if DMS selected)."""
    if state.desktop_env != 'dms':
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


async def step_username(state: WizardState) -> str:
    """Step 10: Enter username."""
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
    """Step 8: Enter user password."""
    password = await get_password(
        header=t('step.passwd.title'),
        allow_skip=True,
    )

    if password is None:
        return 'back'

    state.user_password = password
    return 'next'


async def step_root_password(state: WizardState) -> str:
    """Step 9: Enter root password (optional)."""
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
    # Build summary text
    kmscon_needed = needs_kmscon(state.locale)
    lines = [
        f'{t("confirm.lang")}:     {state.locale}',
        f'{t("confirm.region")}:   {COUNTRY_NAMES.get(state.country, "Unknown") if state.country else t("status.not_set")}',
        f'{t("confirm.timezone")}:   {config.timezone}',
        f'{t("confirm.disk")}:     {state.disk_device.device_info.path if state.disk_device else t("status.not_set")}'
        f'  ({state.disk_device.device_info.total_size.format_highest() if state.disk_device else ""})',
        f'{t("confirm.net")}:      {state.network_type.display_msg()}',
        f'Multilib:     {"Enabled" if state.multilib else "Disabled"}',
        f'{t("confirm.gpu")}:  {", ".join(GPU_LABELS.get(v, v) for v in state.gpu_vendors) or "None"}',
        f'{t("confirm.user")}:   {state.username}',
        f'{t("confirm.root")}:   {t("status.set") if state.root_password else t("status.not_set")}',
        f'kmscon:       {"Added (CJK console)" if kmscon_needed else t("status.not_needed")}',
        *(
            [f'  Font:       {state.kmscon_font_name} ({state.kmscon_font_package})']
            if kmscon_needed and state.kmscon_font_name else []
        ),
        '',
        '── Fixed defaults ──',
        f'{t("fixed.boot")}:    EFISTUB (UKI)',
        f'{t("fixed.fs")}:      Btrfs + zstd + Snapper',
        f'{t("fixed.audio")}:   PipeWire',
        f'{t("fixed.bt")}:      {t("status.enabled")}',
        'Power:        tuned',
        'Swap:         zram (lzo-rle)',
        *(
            [
                f'{t("confirm.desktop")}:  DMS (DankMaterialShell)',
                f'  {t("confirm.compositor")}:  {state.dms_compositor}',
                f'  {t("confirm.terminal")}:   {state.dms_terminal}',
            ]
            if state.desktop_env == 'dms'
            else [f'{t("confirm.desktop")}:  Minimal']
        ),
    ]
    summary = '\n'.join(lines)

    items = [
        MenuItem('Install', value='install'),
        MenuItem('Advanced Modify (archinstall menu)', value='advanced'),
        MenuItem('Cancel', value='cancel'),
    ]
    group = MenuItemGroup(items)
    group.set_focus_by_value('install')

    result = await Selection[str](
        group,
        header=summary,
        allow_skip=True,
    ).show()

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
            # If at first step, stay there (can't go further back)
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
