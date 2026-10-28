from __future__ import annotations

from typing import TYPE_CHECKING

from .constants import (
    CN_APP_OPTIONS,
    DEV_EDITOR_OPTIONS,
    DEV_ENVIRONMENT_OPTIONS,
    DEVICE_PURPOSES,
    DUX_COMPOSITOR_PACKAGES,
    DUX_TERMINAL_PACKAGES,
    EXO_AUTO_FILE_MANAGER,
    FILE_MANAGER_OPTIONS,
    GAMING_OPTIONS,
    INDUSTRIAL_OPTIONS,
    INPUT_METHOD_PACKAGES,
    KEYRING_OPTIONS,
    MEDIA_OPTIONS,
    NAUTILUS_GHOSTTY_PACKAGES,
    POLKIT_AGENT_OPTIONS,
    PROXY_TOOL_OPTIONS,
    REMOTE_DESKTOP_OPTIONS,
    VM_OPTIONS,
)

if TYPE_CHECKING:
    from .wizard import WizardState


_DESKTOPS = frozenset({'minimal', 'dms', 'exo'})
_DUX_DESKTOP = 'dms'
_EXO_DESKTOP = 'exo'
GPU_VM_OPTIONS = frozenset({'gpu_passthrough', 'looking_glass'})
VM_DEPENDENT_OPTIONS = frozenset({'nested_virt', 'gpu_passthrough', 'looking_glass'})


def _selected(state: WizardState, field: str) -> list[str]:
    value = getattr(state, field, []) or []
    return [item for item in value if isinstance(item, str)]


def option_allowed(info: dict, country: str | None) -> bool:
    """Return whether an option is selectable in the current region."""
    countries = info.get('countries')
    return not countries or country in countries


def _valid_selection(
    values: list[str],
    options: dict[str, dict],
    country: str | None,
) -> list[str]:
    return [
        key
        for key in options
        if key in values and option_allowed(options[key], country)
    ]


def normalize_optional_state(state: WizardState) -> None:
    """Clear hidden selections and enforce optional package dependencies."""
    desktop_env = getattr(state, 'desktop_env', None)
    if desktop_env not in _DESKTOPS:
        raise ValueError(f'Unknown desktop environment: {desktop_env!r}')

    graphical = desktop_env != 'minimal'
    dux = desktop_env == _DUX_DESKTOP
    exo = desktop_env == _EXO_DESKTOP
    country = getattr(state, 'country', None)

    purpose_values = set(_selected(state, 'device_purposes'))
    state.device_purposes = [key for key in DEVICE_PURPOSES if key in purpose_values]
    purposes = set(state.device_purposes)

    if getattr(state, 'locale', 'en_US.UTF-8') == 'en_US.UTF-8':
        state.input_methods = []
    else:
        state.input_methods = _valid_selection(
            _selected(state, 'input_methods'),
            INPUT_METHOD_PACKAGES,
            country,
        )

    state.keyring = getattr(state, 'keyring', None)
    state.polkit_agent = getattr(state, 'polkit_agent', None)
    state.file_managers = _selected(state, 'file_managers')
    if graphical:
        if state.keyring not in KEYRING_OPTIONS:
            state.keyring = None
        if dux or state.polkit_agent not in POLKIT_AGENT_OPTIONS:
            state.polkit_agent = None
        state.file_managers = _valid_selection(
            state.file_managers,
            FILE_MANAGER_OPTIONS,
            country,
        )
        if exo and EXO_AUTO_FILE_MANAGER not in state.file_managers:
            state.file_managers.insert(0, EXO_AUTO_FILE_MANAGER)
    else:
        state.keyring = None
        state.polkit_agent = None
        state.file_managers = []

    if dux:
        if getattr(state, 'dms_compositor', None) not in DUX_COMPOSITOR_PACKAGES:
            raise ValueError(f'Unsupported Dux compositor: {state.dms_compositor}')
        if getattr(state, 'dms_terminal', None) not in DUX_TERMINAL_PACKAGES:
            raise ValueError(f'Unsupported Dux terminal: {state.dms_terminal}')
    else:
        state.dms_compositor = 'niri'
        state.dms_terminal = 'ghostty'

    state.proxy_tool = getattr(state, 'proxy_tool', None)
    if country != 'CN':
        state.proxy_tool = None
        state.cn_apps = []
    else:
        if state.proxy_tool not in PROXY_TOOL_OPTIONS:
            state.proxy_tool = None
        state.cn_apps = _valid_selection(
            _selected(state, 'cn_apps'),
            CN_APP_OPTIONS,
            country,
        )

    if 'development' not in purposes:
        state.dev_environments = []
        state.dev_editors = []
    else:
        state.dev_environments = _valid_selection(
            _selected(state, 'dev_environments'),
            DEV_ENVIRONMENT_OPTIONS,
            country,
        )
        state.dev_editors = _valid_selection(
            _selected(state, 'dev_editors'),
            DEV_EDITOR_OPTIONS,
            country,
        )

    if 'gaming' not in purposes or not getattr(state, 'multilib', False):
        state.gaming_tools = []
    else:
        state.gaming_tools = _valid_selection(
            _selected(state, 'gaming_tools'),
            GAMING_OPTIONS,
            country,
        )

    if 'virtual_machine' not in purposes:
        state.vm_options = []
    else:
        chosen = set(_valid_selection(
            _selected(state, 'vm_options'),
            VM_OPTIONS,
            country,
        ))
        if not getattr(state, 'detected_dgpu', False):
            chosen -= GPU_VM_OPTIONS
        if 'looking_glass' in chosen and 'gpu_passthrough' not in chosen:
            chosen.discard('looking_glass')
        if chosen & VM_DEPENDENT_OPTIONS:
            chosen.add('kvm_base')
        state.vm_options = [key for key in VM_OPTIONS if key in chosen]

    remote_desktop = _valid_selection(
        _selected(state, 'remote_desktop'),
        REMOTE_DESKTOP_OPTIONS,
        country,
    )
    if not graphical:
        remote_desktop = [
            key for key in remote_desktop
            if not REMOTE_DESKTOP_OPTIONS[key].get('graphical_only')
        ]
    state.remote_desktop = remote_desktop

    if 'media' not in purposes:
        state.media_tools = []
    else:
        state.media_tools = _valid_selection(
            _selected(state, 'media_tools'),
            MEDIA_OPTIONS,
            country,
        )

    if 'industrial' not in purposes:
        state.industrial_tools = []
    else:
        state.industrial_tools = _valid_selection(
            _selected(state, 'industrial_tools'),
            INDUSTRIAL_OPTIONS,
            country,
        )


def _add_option(
    official: list[str],
    late_repo: list[str],
    aur: list[str],
    options: dict[str, dict],
    key: str,
    country: str | None,
) -> None:
    info = options.get(key)
    if info is None or not option_allowed(info, country):
        return

    repo = info.get('repo')
    if repo == 'archlinuxcn':
        late_repo.extend(f'{repo}/{package}' for package in info.get('packages', []))
    else:
        official.extend(info.get('packages', []))

    regional = info.get('regional_packages', {})
    if country in regional:
        late_repo.extend(regional[country])
    elif repo != 'archlinuxcn':
        aur.extend(info.get('aur_packages', []))


def _dedupe(packages: list[str]) -> list[str]:
    return list(dict.fromkeys(packages))


def collect_optional_packages(
    state: WizardState,
) -> tuple[list[str], list[str], list[str]]:
    """Normalize selections and split optional packages by install source.

    Returns ``(official_packages, late_repo_packages, aur_packages)``.
    ``late_repo_packages`` are repo-qualified and must be installed only after
    the archlinuxcn repository has been configured. Browser packages are
    intentionally excluded; they remain owned by the dedicated browser path.
    """
    normalize_optional_state(state)
    country = getattr(state, 'country', None)
    official: list[str] = []
    late_repo: list[str] = []
    aur: list[str] = []

    if state.keyring:
        _add_option(official, late_repo, aur, KEYRING_OPTIONS, state.keyring, country)
    if state.polkit_agent:
        _add_option(
            official, late_repo, aur,
            POLKIT_AGENT_OPTIONS, state.polkit_agent, country,
        )
    for key in state.input_methods:
        _add_option(official, late_repo, aur, INPUT_METHOD_PACKAGES, key, country)
    for key in state.file_managers:
        _add_option(official, late_repo, aur, FILE_MANAGER_OPTIONS, key, country)
    if (
        state.desktop_env == _DUX_DESKTOP
        and state.dms_terminal == 'ghostty'
        and 'nautilus' in state.file_managers
    ):
        official.extend(NAUTILUS_GHOSTTY_PACKAGES)
    if state.proxy_tool:
        _add_option(official, late_repo, aur, PROXY_TOOL_OPTIONS, state.proxy_tool, country)
    for key in state.dev_environments:
        _add_option(official, late_repo, aur, DEV_ENVIRONMENT_OPTIONS, key, country)
    for key in state.dev_editors:
        _add_option(official, late_repo, aur, DEV_EDITOR_OPTIONS, key, country)
    for key in state.gaming_tools:
        _add_option(official, late_repo, aur, GAMING_OPTIONS, key, country)
    for key in state.vm_options:
        _add_option(official, late_repo, aur, VM_OPTIONS, key, country)
    for key in state.remote_desktop:
        _add_option(official, late_repo, aur, REMOTE_DESKTOP_OPTIONS, key, country)
    for key in state.cn_apps:
        _add_option(official, late_repo, aur, CN_APP_OPTIONS, key, country)
    for key in state.media_tools:
        _add_option(official, late_repo, aur, MEDIA_OPTIONS, key, country)
    for key in state.industrial_tools:
        _add_option(official, late_repo, aur, INDUSTRIAL_OPTIONS, key, country)

    return _dedupe(official), _dedupe(late_repo), _dedupe(aur)
