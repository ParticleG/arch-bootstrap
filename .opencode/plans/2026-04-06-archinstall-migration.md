# arch-bootstrap → archinstall Python Script Migration

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate the Bash `install.sh` to a standalone Python script `arch_bootstrap.py` that uses archinstall's Python API and TUI for an opinionated Arch Linux installation.

**Architecture:** Single-file Python script (`arch_bootstrap.py`) that imports archinstall as a library. Runs standalone via `python arch_bootstrap.py` on Arch ISO. Uses archinstall's textual-based TUI components (`Selection`, `Input`, `Confirmation`) for a sequential wizard, with a GlobalMenu escape hatch for advanced users.

**Tech Stack:** Python 3.12+, archinstall 4.1 (pre-installed on Arch ISO), textual TUI framework (via archinstall)

---

## Flow

```
1. Auto-detect (silent): IP geolocation → country/timezone/mirrors, GPU → drivers, Disk → preferred
2. Sequential wizard (9 steps, each with pre-selected defaults, ESC=back):
   Language → Region → Disk → Network → Repos → GPU Drivers → Username → User Password → Root Password
3. Confirmation panel: [Install] [Advanced Modify (GlobalMenu)] [Cancel]
4. Execute installation via archinstall Installer + post-install hooks
```

## Tasks

### Task 1: Script skeleton
- Create `arch_bootstrap.py` with all imports from archinstall
- Port data constants from `lib/config.sh` (countries, GPU packages, mirrors, etc.)
- Stub `main()` entry point

### Task 2: Detection helpers
- `detect_country()`: IP geolocation via 3 services (2s timeout each)
- `detect_gpu()`: lspci parsing, NVIDIA Turing+ logic (Device ID >= 0x1e00)
- `detect_preferred_disk()`: No partitions → first NVMe → None

### Task 3: Config builder
- `build_default_config()`: Construct ArchConfig with opinionated defaults
  - Bootloader: EFISTUB + UKI
  - Filesystem: Btrfs + zstd + Snapper + 4 subvolumes
  - Audio: PipeWire, Bluetooth: enabled, Power: tuned
  - Swap: zram + lzo-rle, Profile: Minimal, Kernel: linux
  - Hostname: archlinux, NTP: true

### Task 4: Wizard steps
- Each step: async function using archinstall TUI components
- Returns 'back' (ESC/Skip), 'abort', or updates config and returns 'next'
- Pre-selected defaults from detection results
- Step navigation loop with back support

### Task 5: Confirmation + GlobalMenu
- Summary display of all configured values
- Three options: Install / Advanced Modify / Cancel
- Advanced Modify: pass current ArchConfig to archinstall GlobalMenu
- Return to confirmation after GlobalMenu exit

### Task 6: Installation + post-install
- Wrap archinstall's Installer context manager (follow guided.py sequence)
- Post-install: kmscon systemd service swap, vconsole.conf keyboard layout

### Task 7: Integration
- Wire wizard → confirmation → installation in main()
- Error handling, root check, ISO environment detection

## Key APIs

```python
# TUI components (helpers layer - standalone, no GlobalMenu needed)
from archinstall.lib.menu.helpers import Selection, Input, Confirmation
from archinstall.tui.ui.components import tui
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType

# Config models
from archinstall.lib.args import ArchConfig, ArchConfigHandler
from archinstall.lib.models.device import DiskLayoutConfiguration, DeviceModification, ...
from archinstall.lib.models.bootloader import Bootloader, BootloaderConfiguration
from archinstall.lib.models.application import ApplicationConfiguration, ...
from archinstall.lib.models.authentication import AuthenticationConfiguration
from archinstall.lib.models.mirrors import MirrorConfiguration, MirrorRegion, CustomRepository
from archinstall.lib.models.network import NetworkConfiguration, NicType
from archinstall.lib.models.locale import LocaleConfiguration
from archinstall.lib.models.users import User, Password
from archinstall.lib.models.profile import ProfileConfiguration

# Installation
from archinstall.lib.installer import Installer
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.disk.device_handler import device_handler
from archinstall.lib.global_menu import GlobalMenu
from archinstall.lib.mirror.mirror_handler import MirrorListHandler
```
