"""Entry point for arch-bootstrap: python -m arch_bootstrap."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.menu.util import delayed_warning
from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.output import info

from .config import build_default_config
from .constants import COUNTRY_NAMES, GPU_LABELS
from .detection import (
    cleanup_disk_locks,
    detect_country,
    detect_gpu,
    detect_preferred_disk,
    is_iso_environment,
)
from .installation import perform_installation, run_global_menu
from .wizard import WizardState, run_wizard


def main() -> None:
    """Main entry point for the installer."""
    # Root check (also checked in bootstrap, but needed when imported as library)
    if os.geteuid() != 0:
        print('Error: This script must be run as root.', file=sys.stderr)
        sys.exit(1)

    # When piped via stdin (e.g. curl ... | python), fd 0 is the exhausted
    # pipe — not the terminal.  Reopen it from /dev/tty so the TUI can read
    # keyboard input.
    if not os.isatty(0):
        tty_fd = os.open('/dev/tty', os.O_RDONLY)
        os.dup2(tty_fd, 0)
        os.close(tty_fd)
        sys.stdin = open(0, closefd=False)

    info('arch-bootstrap: Opinionated Arch Linux installer')
    info('Detecting environment...')

    # Phase 1: Auto-detection (silent)
    detected_country = detect_country()
    if detected_country:
        info(f'  Detected country: {detected_country} ({COUNTRY_NAMES.get(detected_country, "Unknown")})')

    detected_gpu = detect_gpu()
    if detected_gpu:
        info(f'  Detected GPU: {", ".join(GPU_LABELS.get(v, v) for v in detected_gpu)}')

    preferred_disk = detect_preferred_disk()
    if preferred_disk:
        info(f'  Preferred disk: {preferred_disk}')

    # Initialize mirror list handler
    mirror_list_handler = MirrorListHandler(offline=False, verbose=False)

    # Build initial config with defaults
    initial_locale = 'zh_CN.UTF-8' if detected_country == 'CN' else 'en_US.UTF-8'
    config = build_default_config(detected_country, initial_locale, mirror_list_handler)

    # Initialize wizard state with detection results
    state = WizardState()
    state.detected_country = detected_country
    state.country = detected_country
    state.locale = initial_locale
    state.detected_gpu = detected_gpu
    state.gpu_vendors = list(detected_gpu)
    state.preferred_disk = preferred_disk

    # Phase 2: Interactive wizard (archinstall native UI)
    while True:
        action = asyncio.run(run_wizard(state, config, mirror_list_handler))

        if action == 'abort':
            info('Installation aborted.')
            sys.exit(0)

        if action == 'advanced':
            # Open GlobalMenu for advanced modification
            result = run_global_menu(config, mirror_list_handler)
            if result is None:
                # User cancelled GlobalMenu, return to confirmation
                continue
            # Config was modified in-place by GlobalMenu
            continue

        if action == 'install':
            break

    # Phase 3: Disk formatting warning
    if config.disk_config:
        info('Preparing disk operations...')

        # Release disk locks (swap, LVM, LUKS) to avoid 'Device busy'
        cleanup_disk_locks()

        fs_handler = FilesystemHandler(config.disk_config)

        # Countdown warning before destructive operation
        delayed_warning('\nWARNING: All data on the selected disk will be destroyed!')

        fs_handler.perform_filesystem_operations()

    # Apply mirrors to live ISO before installation (speeds up pacstrap)
    if is_iso_environment() and config.mirror_config:
        mirrorlist_path = Path('/etc/pacman.d/mirrorlist')
        mirror_content = config.mirror_config.regions_config(
            mirror_list_handler, speed_sort=True,
        )
        if mirror_content.strip():
            mirrorlist_path.write_text(mirror_content)
            info('Applied fast mirrors to live ISO.')

    # Phase 4: Execute installation
    perform_installation(config, mirror_list_handler)


if __name__ == '__main__':
    main()
