# TUI Split-Pane Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Restructure `arch_bootstrap.py` into a Python package and implement a split-pane TUI framework using a custom Textual App.

**Architecture:** Independent WizardApp (Textual App subclass) manages wizard phase with left-right split layout (55%/45%). Left panel hosts interactive step widgets, right panel shows persistent progress summary. GlobalMenu and post-install screens continue using archinstall's `tui.run()`.

**Tech Stack:** Python 3.11+, Textual (via archinstall dependency), archinstall 4.1 API

---

## Phase 0: Package Restructure

### Task 0.1: Create package skeleton

**Files:**
- Create: `arch_bootstrap/__init__.py`
- Create: `arch_bootstrap/constants.py`

**Step 1:** Create `arch_bootstrap/__init__.py`:

```python
"""arch-bootstrap: Opinionated Arch Linux installer powered by archinstall."""

__version__ = '0.2.0'
```

**Step 2:** Extract constants from `arch_bootstrap.py` lines 145-285 into `arch_bootstrap/constants.py`. Move ALL constant definitions:
- `BASE_PACKAGES`
- `GPU_VENDORS`, `GPU_DETECT_PATTERNS`, `GPU_LABELS`, `GPU_PACKAGES`
- `LANGUAGES`
- `COUNTRY_NAMES`, `COUNTRY_TIMEZONES`, `REGION_MENU_COUNTRIES`
- `ARCHLINUXCN_URL`, `FALLBACK_MIRRORS`
- `NETWORK_BACKENDS`
- `GEO_ENDPOINTS`
- `NVIDIA_TURING_THRESHOLD`

No archinstall imports needed — pure data module.

**Step 3:** Commit.

---

### Task 0.2: Extract detection module

**Files:**
- Create: `arch_bootstrap/detection.py`

**Step 1:** Move lines 287-436 from `arch_bootstrap.py` into `arch_bootstrap/detection.py`:
- `detect_country()` (L291-314)
- `detect_gpu()` (L317-344)
- `detect_preferred_disk()` (L347-377)
- `needs_kmscon()` (L380-382)
- `is_iso_environment()` (L385-387)
- `is_raw_tty()` (L390-404)
- `cleanup_disk_locks()` (L407-436)

**Imports needed:**
```python
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .constants import GPU_DETECT_PATTERNS, GEO_ENDPOINTS, NVIDIA_TURING_THRESHOLD
```

Note: `detect_gpu()` uses archinstall `device_handler` for PCI device IDs. Import:
```python
from archinstall.lib.disk.device_handler import device_handler
```

Note: `detect_preferred_disk()` uses `BDevice` type hint and `device_handler`. Import:
```python
from archinstall.lib.models.device import BDevice
```

**Step 2:** Commit.

---

### Task 0.3: Extract mirrors and disk modules

**Files:**
- Create: `arch_bootstrap/mirrors.py`
- Create: `arch_bootstrap/disk.py`

**Step 1:** `mirrors.py` — move `resolve_mirror_regions()` (L443-464):

```python
from __future__ import annotations

from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.models.mirrors import MirrorRegion

from .constants import COUNTRY_NAMES, FALLBACK_MIRRORS


def resolve_mirror_regions(
    country: str | None,
    mirror_list_handler: MirrorListHandler,
) -> list[MirrorRegion]:
    ...  # exact body from L443-464
```

**Step 2:** `disk.py` — move `build_disk_layout()` (L471-522):

```python
from __future__ import annotations

from pathlib import Path

from archinstall.lib.models.device import (
    BDevice, BtrfsMountOption, BtrfsOptions, DeviceModification,
    DiskLayoutConfiguration, DiskLayoutType, FilesystemType,
    ModificationStatus, PartitionFlag, PartitionModification,
    PartitionType, SectorSize, Size, SnapshotConfig, SnapshotType,
    SubvolumeModification, Unit,
)


def build_disk_layout(device: BDevice) -> DiskLayoutConfiguration:
    ...  # exact body from L471-522
```

**Step 3:** Commit.

---

### Task 0.4: Extract config module

**Files:**
- Create: `arch_bootstrap/config.py`

**Step 1:** Move `build_default_config()` (L529-597) and `apply_wizard_state_to_config()` (L964-1057):

Imports needed:
```python
from __future__ import annotations

from pathlib import Path

from archinstall.lib.args import ArchConfig
from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.models.application import (
    ApplicationConfiguration, Audio, AudioConfiguration,
    BluetoothConfiguration, PowerManagement, PowerManagementConfiguration,
    ZramAlgorithm, ZramConfiguration,
)
from archinstall.lib.models.authentication import AuthenticationConfiguration
from archinstall.lib.models.bootloader import Bootloader, BootloaderConfiguration
from archinstall.lib.models.locale import LocaleConfiguration
from archinstall.lib.models.mirrors import (
    CustomRepository, MirrorConfiguration, SignCheck, SignOption,
)
from archinstall.lib.models.network import NetworkConfiguration, NicType
from archinstall.lib.models.packages import Repository
from archinstall.lib.models.profile import ProfileConfiguration
from archinstall.lib.models.users import Password, User
from archinstall.lib.profile.profiles_handler import profile_handler

from .constants import (
    ARCHLINUXCN_URL, BASE_PACKAGES, COUNTRY_TIMEZONES,
    GPU_PACKAGES,
)
from .detection import needs_kmscon
from .mirrors import resolve_mirror_regions
```

Note: `apply_wizard_state_to_config` references `WizardState` from wizard module. To avoid circular imports, use `TYPE_CHECKING`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .wizard import WizardState
```

And at runtime, the function signature uses a string annotation: `def apply_wizard_state_to_config(state: 'WizardState', ...)`.

Actually, since we use `from __future__ import annotations`, all annotations are strings by default. So just import under TYPE_CHECKING.

**Step 2:** Commit.

---

### Task 0.5: Extract wizard module

**Files:**
- Create: `arch_bootstrap/wizard.py`

**Step 1:** Move:
- `WizardState` class (L607-622)
- All `step_*` functions (L625-957)
- `run_wizard()` (L1060-1115)

Imports needed:
```python
from __future__ import annotations

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
    COUNTRY_NAMES, GPU_LABELS, GPU_VENDORS, LANGUAGES,
    NETWORK_BACKENDS, REGION_MENU_COUNTRIES,
)
from .detection import is_raw_tty, needs_kmscon
```

**Step 2:** Commit.

---

### Task 0.6: Extract installation module

**Files:**
- Create: `arch_bootstrap/installation.py`

**Step 1:** Move:
- `perform_installation()` (L1141-1267)
- `run_global_menu()` (L1122-1134)

Imports needed:
```python
from __future__ import annotations

import os
import time
from pathlib import Path

from archinstall.lib.applications.application_handler import ApplicationHandler
from archinstall.lib.args import ArchConfig
from archinstall.lib.authentication.authentication_handler import AuthenticationHandler
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.disk.utils import disk_layouts
from archinstall.lib.general.general_menu import PostInstallationAction, select_post_installation
from archinstall.lib.global_menu import GlobalMenu
from archinstall.lib.installer import Installer, run_custom_user_commands
from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.models.bootloader import Bootloader
from archinstall.lib.models.device import DiskLayoutType
from archinstall.lib.models.network import NetworkConfiguration
from archinstall.lib.models.users import User
from archinstall.lib.network.network_handler import install_network_config
from archinstall.lib.output import debug, error, info
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.tui.ui.components import tui
```

**Step 2:** Commit.

---

### Task 0.7: Create entry points and build system

**Files:**
- Create: `arch_bootstrap/__main__.py`
- Modify: `arch_bootstrap.py` (root — rewrite as thin wrapper)
- Modify: `.gitignore` (add `*.pyz`)
- Modify: `.github/workflows/package.yml` (add zipapp build step)

**Step 1:** Create `arch_bootstrap/__main__.py` with the `main()` function (original L1274-1370). This is the actual entry point logic.

Imports needed:
```python
from __future__ import annotations

import os
import sys
from pathlib import Path

from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.output import info
from archinstall.tui.ui.components import tui

from .config import build_default_config
from .constants import COUNTRY_NAMES, GPU_LABELS
from .detection import (
    cleanup_disk_locks, detect_country, detect_gpu,
    detect_preferred_disk, is_iso_environment,
)
from .installation import perform_installation, run_global_menu
from .wizard import WizardState, run_wizard
```

Also include: `from archinstall.lib.disk.filesystem import FilesystemHandler` and `from archinstall.lib.menu.util import delayed_warning` (used in main()).

**Step 2:** Rewrite root `arch_bootstrap.py` as thin wrapper:

```python
#!/usr/bin/env python3
"""arch-bootstrap: Opinionated Arch Linux installer powered by archinstall.

Usage (on Arch ISO):
    curl -LO https://raw.githubusercontent.com/.../arch_bootstrap.py
    python arch_bootstrap.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _needs_archinstall_upgrade() -> bool:
    ...  # keep original L31-42

def _upgrade_archinstall() -> None:
    ...  # keep original L45-68

# Perform bootstrap check before ANY archinstall import
if __name__ == '__main__' and _needs_archinstall_upgrade():
    if os.geteuid() != 0:
        print('Error: This script must be run as root.', file=sys.stderr)
        sys.exit(1)
    _upgrade_archinstall()

from arch_bootstrap.__main__ import main

if __name__ == '__main__':
    main()
```

**Step 3:** Add `*.pyz` to `.gitignore`.

**Step 4:** Update `.github/workflows/package.yml` to add zipapp build step:
```yaml
- name: Build Python zipapp
  run: python3 -m zipapp arch_bootstrap -o arch_bootstrap.pyz -m "arch_bootstrap.__main__:main" -p "/usr/bin/env python3"
```

**Step 5:** Commit.

---

## Phase 1: WizardApp Split-Pane Framework

### Task 1.1: Create TUI subpackage and WizardApp

**Files:**
- Create: `arch_bootstrap/tui/__init__.py`
- Create: `arch_bootstrap/tui/app.py`

**Step 1:** Create `arch_bootstrap/tui/__init__.py`:
```python
"""TUI components for arch-bootstrap wizard."""
```

**Step 2:** Create `arch_bootstrap/tui/app.py`:

```python
"""WizardApp: Custom Textual App for the split-pane wizard."""

from __future__ import annotations

from typing import Any

from textual.app import App

from .screen import WizardScreen


class WizardApp(App[str]):
    """Independent Textual App for the wizard phase.

    Manages step navigation and provides split-pane layout via WizardScreen.
    Returns 'install', 'advanced', or 'abort' when wizard completes.
    """

    ENABLE_COMMAND_PALETTE = False

    CSS = \"\"\"
    Screen {
        background: $surface;
    }

    #split-pane {
        height: 1fr;
    }

    #left-panel {
        width: 55%;
        height: 100%;
        padding: 1 2;
    }

    #right-panel {
        width: 45%;
        height: 100%;
        padding: 1 2;
    }

    #step-container {
        height: 1fr;
    }

    #progress-panel {
        height: 1fr;
    }
    \"\"\"

    def __init__(
        self,
        steps: list[dict[str, Any]],
        *,
        ansi_color: bool = True,
    ) -> None:
        super().__init__(ansi_color=ansi_color)
        self._steps = steps

    def on_mount(self) -> None:
        self.push_screen(WizardScreen(self._steps))
```

`steps` is a list of dicts like: `[{'name': 'Language', 'widget_class': SelectStep, 'kwargs': {...}}, ...]`

**Step 3:** Commit.

---

### Task 1.2: Create WizardScreen with split-pane layout

**Files:**
- Create: `arch_bootstrap/tui/screen.py`

**Step 1:** Implement WizardScreen:

```python
"""WizardScreen: Split-pane layout with step container and progress panel."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Rule

from .progress import ProgressPanel
from .steps import StepComplete, StepWidget


class WizardScreen(Screen[str]):
    """Main wizard screen with left-right split layout."""

    def __init__(self, steps: list[dict[str, Any]]) -> None:
        super().__init__()
        self._steps = steps
        self._current_index = 0
        self._active_step: StepWidget | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id='split-pane'):
            with Vertical(id='left-panel'):
                pass  # steps mounted dynamically
            yield Rule(orientation='vertical')
            with Vertical(id='right-panel'):
                yield ProgressPanel(id='progress-panel')

    def on_mount(self) -> None:
        self._show_step(0)

    def _show_step(self, index: int) -> None:
        """Mount the step widget at the given index."""
        if self._active_step is not None:
            self._active_step.remove()

        step_def = self._steps[index]
        widget_class = step_def['widget_class']
        kwargs = step_def.get('kwargs', {})
        step = widget_class(**kwargs)
        self._active_step = step
        self._current_index = index

        left = self.query_one('#left-panel')
        left.mount(step)

    def on_step_complete(self, message: StepComplete) -> None:
        """Handle step navigation."""
        progress = self.query_one('#progress-panel', ProgressPanel)

        if message.action == 'next':
            # Record progress
            if message.label and message.value is not None:
                progress.add_entry(message.label, str(message.value))

            next_idx = self._current_index + 1
            if next_idx < len(self._steps):
                self._show_step(next_idx)
            else:
                self.dismiss('install')

        elif message.action == 'back':
            if self._current_index > 0:
                self._show_step(self._current_index - 1)

        elif message.action == 'abort':
            self.dismiss('abort')

        elif message.action == 'advanced':
            self.dismiss('advanced')
```

**Step 2:** Commit.

---

### Task 1.3: Create StepWidget base class and StepComplete message

**Files:**
- Create: `arch_bootstrap/tui/steps.py`

**Step 1:** Implement base classes:

```python
"""Step widgets for the wizard."""

from __future__ import annotations

from typing import Any

from textual.message import Message
from textual.widget import Widget


class StepComplete(Message):
    """Posted by a step widget when the user completes or navigates."""

    def __init__(
        self,
        action: str,
        *,
        label: str | None = None,
        value: Any = None,
    ) -> None:
        self.action = action   # 'next', 'back', 'abort', 'advanced'
        self.label = label     # display label for progress panel
        self.value = value     # selected value
        super().__init__()


class StepWidget(Widget):
    """Base class for wizard step widgets.

    Subclasses should call self.complete() to signal navigation.
    """

    step_title: str = ''

    def complete(
        self,
        action: str,
        *,
        label: str | None = None,
        value: Any = None,
    ) -> None:
        """Signal step completion/navigation."""
        self.post_message(StepComplete(action, label=label, value=value))
```

**Step 2:** Add a concrete `DemoSelectStep` for testing:

```python
class DemoSelectStep(StepWidget):
    """Demo step with a simple option list for testing the framework."""

    def __init__(self, title: str, options: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._options = options

    def compose(self) -> ComposeResult:
        from textual.app import ComposeResult
        from textual.widgets import Label, OptionList
        from textual.widgets.option_list import Option

        yield Label(self._title, classes='step-header')
        yield OptionList(
            *[Option(opt, id=f'opt-{i}') for i, opt in enumerate(self._options)],
            id='step-options',
        )

    def on_option_list_option_selected(self, event) -> None:
        selected = self._options[event.option_index]
        self.complete('next', label=self._title, value=selected)

    def key_escape(self) -> None:
        self.complete('back')
```

**Step 3:** Commit.

---

### Task 1.4: Create ProgressPanel widget

**Files:**
- Create: `arch_bootstrap/tui/progress.py`

**Step 1:** Implement ProgressPanel:

```python
"""ProgressPanel: Persistent right-side summary of wizard progress."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widget import Widget
from textual.app import ComposeResult, RenderResult
from textual.widgets import Static


class ProgressPanel(Static):
    """Displays completed wizard step summaries."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._entries: list[tuple[str, str]] = []

    def add_entry(self, key: str, value: str) -> None:
        """Add or update a progress entry."""
        # Update existing entry with same key
        for i, (k, _) in enumerate(self._entries):
            if k == key:
                self._entries[i] = (key, value)
                self.refresh()
                return
        self._entries.append((key, value))
        self.refresh()

    def render(self) -> RenderResult:
        if not self._entries:
            return '── Configuration ──\n\n  (no selections yet)'

        lines = ['── Configuration ──', '']
        for key, val in self._entries:
            lines.append(f'  [green]✓[/green] {key}: {val}')
        return '\n'.join(lines)
```

**Step 2:** Commit.

---

### Task 1.5: Wire up demo and verify split-pane rendering

**Files:**
- Create: `arch_bootstrap/tui/demo.py` (temporary, for visual testing)

**Step 1:** Create a standalone demo that runs the WizardApp with mock steps:

```python
"""Demo script to test split-pane layout. Run: python -m arch_bootstrap.tui.demo"""

from .app import WizardApp
from .steps import DemoSelectStep


def main() -> None:
    steps = [
        {
            'name': 'Language',
            'widget_class': DemoSelectStep,
            'kwargs': {'title': 'Select Language', 'options': ['English', '简体中文', '日本語']},
        },
        {
            'name': 'Region',
            'widget_class': DemoSelectStep,
            'kwargs': {'title': 'Select Region', 'options': ['China', 'United States', 'Japan', 'Germany']},
        },
        {
            'name': 'Confirm',
            'widget_class': DemoSelectStep,
            'kwargs': {'title': 'Ready to install?', 'options': ['Install', 'Cancel']},
        },
    ]

    result = WizardApp(steps).run()
    print(f'Wizard result: {result}')


if __name__ == '__main__':
    main()
```

**Step 2:** Verify by running `python -m arch_bootstrap.tui.demo` on a terminal. Confirm:
- Split-pane renders with left (55%) and right (45%) panels
- OptionList displays in left panel
- Selecting an option advances to next step
- Progress panel on right accumulates selections
- Esc goes back to previous step
- After last step, app exits with 'install'

**Step 3:** Commit.

---

### Task 1.6: Integration — connect WizardApp to wizard.py

**Files:**
- Modify: `arch_bootstrap/wizard.py`
- Modify: `arch_bootstrap/__main__.py`

**Step 1:** Add a `run_wizard_tui()` function to `wizard.py` that:
- Creates step definitions from existing step functions
- Launches WizardApp
- Returns the result ('install', 'advanced', 'abort')

For now (Phase 1), this will use DemoSelectStep placeholders. Phase 2 will replace these with real step implementations using native Textual widgets.

**Step 2:** Modify `main()` in `__main__.py` to call `run_wizard_tui()` instead of `tui.run(lambda: run_wizard(...))` for the wizard phase. Keep `tui.run()` for GlobalMenu and post-install.

**Step 3:** Commit.

---

## Verification

After Phase 0: `python -c "from arch_bootstrap.__main__ import main"` should not error (import check only, don't run main).

After Phase 1: `python -m arch_bootstrap.tui.demo` should show split-pane wizard with mock steps.

## Notes

- No unit tests (runtime depends on archinstall + Arch ISO environment)
- Each task = one commit
- Phase 2 (not in this plan) will replace DemoSelectStep with real SelectStep, InputStep, etc.
