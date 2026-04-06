from __future__ import annotations

import os
import re
from pathlib import Path

from archinstall.lib.args import ArchConfig
from archinstall.lib.disk.device_handler import device_handler
from archinstall.lib.menu.helpers import Confirmation, Input, Selection
from archinstall.lib.menu.util import get_password
from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.models.device import BDevice
from archinstall.lib.models.network import NicType
from archinstall.lib.models.users import Password
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType

from .config import apply_wizard_state_to_config
from .constants import (
    COUNTRY_NAMES,
    GPU_LABELS,
    GPU_VENDORS,
    LANGUAGES,
    NETWORK_BACKENDS,
    REGION_MENU_COUNTRIES,
)
from .detection import is_raw_tty, needs_kmscon
from .tui.app import WizardApp
from .tui.steps import DemoSelectStep


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
        header='Select your country/region',
        allow_skip=True,
        enable_filter=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.country = result.get_value()
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
        header='Select target disk (ALL DATA WILL BE ERASED)',
        allow_skip=True,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            state.disk_device = result.get_value()
            return 'next'
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
        header='Select network backend',
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
        header='Enable multilib repository? (32-bit library support)',
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
        header='Select GPU drivers (Space to toggle, Enter to confirm)',
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


async def step_username(state: WizardState) -> str:
    """Step 7: Enter username."""
    default = state.username or os.environ.get('SUDO_USER', '') or os.environ.get('USER', '')
    # Filter out 'root' — not a useful default
    if default == 'root':
        default = ''

    def validate(value: str) -> str | None:
        if not value:
            return 'Username cannot be empty'
        if not re.match(r'^[a-z_][a-z0-9_-]*$', value):
            return 'Must start with a-z or _, followed by a-z 0-9 _ -'
        if len(value) > 32:
            return 'Username must be 32 characters or fewer'
        return None

    result = await Input(
        header='Enter username',
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
        header=f'Enter password for {state.username}',
        allow_skip=True,
    )

    if password is None:
        return 'back'

    state.user_password = password
    return 'next'


async def step_root_password(state: WizardState) -> str:
    """Step 9: Enter root password (optional)."""
    result = await Confirmation(
        header='Set a root password? (skip for no root login)',
        allow_skip=True,
        preset=False,
    ).show()

    match result.type_:
        case ResultType.Skip:
            return 'back'
        case ResultType.Selection:
            if result.item() == MenuItem.yes():
                password = await get_password(
                    header='Enter root password',
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
        f'Language:     {state.locale}',
        f'Region:       {COUNTRY_NAMES.get(state.country, "Unknown") if state.country else "Not set"}',
        f'Timezone:     {config.timezone}',
        f'Disk:         {state.disk_device.device_info.path if state.disk_device else "Not set"}'
        f'  ({state.disk_device.device_info.total_size.format_highest() if state.disk_device else ""})',
        f'Network:      {state.network_type.display_msg()}',
        f'Multilib:     {"Enabled" if state.multilib else "Disabled"}',
        f'GPU Drivers:  {", ".join(GPU_LABELS.get(v, v) for v in state.gpu_vendors) or "None"}',
        f'Username:     {state.username}',
        f'Root login:   {"Enabled" if state.root_password else "Disabled"}',
        f'kmscon:       {"Added (CJK console)" if kmscon_needed else "Not needed"}',
        '',
        '── Fixed defaults ──',
        'Bootloader:   EFISTUB (UKI)',
        'Filesystem:   Btrfs + zstd + Snapper',
        'Audio:        PipeWire',
        'Bluetooth:    Enabled',
        'Power:        tuned',
        'Swap:         zram (lzo-rle)',
        'Profile:      Minimal',
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
    steps = [
        step_language,
        step_region,
        step_disk,
        step_network,
        step_repos,
        step_gpu_drivers,
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


# =============================================================================
# TUI-based wizard runner (split-pane)
# =============================================================================

def _build_tui_steps(state: WizardState) -> list[dict]:
    """Build step definitions for WizardApp using DemoSelectStep placeholders.

    Phase 2 will replace these with real SelectStep / InputStep / PasswordStep.
    """
    # Language options
    lang_options = [
        f'{label} ({code})' for code, label in LANGUAGES.items()
    ]

    # Region options
    region_options = [
        f'{COUNTRY_NAMES[code]} ({code})'
        for code in REGION_MENU_COUNTRIES
    ]

    # Disk — placeholder (real step needs device_handler)
    disk_options = ['(disk detection requires live environment)']

    # Network options
    network_options = [label for label in NETWORK_BACKENDS.values()]

    # Repos
    repo_options = ['Enable multilib', 'Disable multilib']

    # GPU options
    gpu_options = [GPU_LABELS[v] for v in GPU_VENDORS]

    # Username — placeholder (real step will use InputStep)
    username_options = [
        f'Use detected: {state.username}' if state.username else '(enter username)',
    ]

    # Passwords — placeholders (real steps will use PasswordStep)
    user_pw_options = ['Set password', 'Skip']
    root_pw_options = ['Set root password', 'No root login']

    # Confirmation
    confirm_options = ['Install', 'Advanced Modify (archinstall menu)', 'Cancel']

    return [
        {
            'widget_class': DemoSelectStep,
            'kwargs': {
                'title': 'Select Language / 选择系统语言',
                'options': lang_options,
            },
        },
        {
            'widget_class': DemoSelectStep,
            'kwargs': {
                'title': 'Select Country/Region',
                'options': region_options,
            },
        },
        {
            'widget_class': DemoSelectStep,
            'kwargs': {
                'title': 'Select Target Disk',
                'options': disk_options,
            },
        },
        {
            'widget_class': DemoSelectStep,
            'kwargs': {
                'title': 'Select Network Backend',
                'options': network_options,
            },
        },
        {
            'widget_class': DemoSelectStep,
            'kwargs': {
                'title': 'Multilib Repository',
                'options': repo_options,
            },
        },
        {
            'widget_class': DemoSelectStep,
            'kwargs': {
                'title': 'Select GPU Drivers',
                'options': gpu_options,
            },
        },
        {
            'widget_class': DemoSelectStep,
            'kwargs': {
                'title': 'Enter Username',
                'options': username_options,
            },
        },
        {
            'widget_class': DemoSelectStep,
            'kwargs': {
                'title': 'User Password',
                'options': user_pw_options,
            },
        },
        {
            'widget_class': DemoSelectStep,
            'kwargs': {
                'title': 'Root Password',
                'options': root_pw_options,
            },
        },
        {
            'widget_class': DemoSelectStep,
            'kwargs': {
                'title': 'Confirm Installation',
                'options': confirm_options,
            },
        },
    ]


def run_wizard_tui(
    state: WizardState,
    config: ArchConfig,
    mirror_list_handler: MirrorListHandler,
) -> str:
    """Run the wizard using the split-pane TUI.

    Returns 'install', 'advanced', or 'abort'.
    This is a synchronous function — it calls WizardApp.run() which blocks
    until the user completes or exits the wizard.
    """
    steps = _build_tui_steps(state)
    app = WizardApp(steps)
    result = app.run()

    if result == 'install':
        # Apply wizard state to config (Phase 2 steps will update state)
        apply_wizard_state_to_config(state, config, mirror_list_handler)
        return 'install'
    elif result == 'advanced':
        return 'advanced'
    else:
        return 'abort'
