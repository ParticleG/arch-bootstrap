#!/usr/bin/env python3
"""arch-bootstrap: Opinionated Arch Linux installer powered by archinstall.

Usage (on Arch ISO):
    curl -LO https://raw.githubusercontent.com/.../arch_bootstrap.py
    python arch_bootstrap.py

Or with the package extracted alongside this file:
    python -m arch_bootstrap
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: upgrade archinstall BEFORE importing it.
#
# The Arch ISO ships archinstall 3.x, but this script requires 4.1.
# If we detect the ISO environment and archinstall is outdated, upgrade it
# via pacman, then purge stale modules from sys.modules so the subsequent
# top-level imports pick up the new package.
#
# This approach works regardless of invocation method (file, pipe/stdin,
# module import), unlike os.execv which requires a file on disk.
# ---------------------------------------------------------------------------


def _needs_archinstall_upgrade() -> bool:
    """Return True if running on ISO and archinstall is not 4.x+."""
    if not Path('/run/archiso').exists():
        return False
    try:
        import archinstall
        version = getattr(archinstall, '__version__', '0.0.0')
        major = int(version.split('.')[0])
        return major < 4
    except (ImportError, ValueError, AttributeError):
        # archinstall missing entirely or version unparseable — upgrade
        return True


def _upgrade_archinstall() -> None:
    """Upgrade archinstall via pacman and flush module caches in-process."""
    print('arch-bootstrap: ISO detected with archinstall < 4.x — upgrading...')
    result = subprocess.run(
        ['pacman', '-Sy', '--noconfirm', 'archinstall'],
        stderr=subprocess.PIPE, text=True,
    )
    if result.returncode != 0:
        print(
            f'WARNING: Failed to upgrade archinstall: {result.stderr.strip()}',
            file=sys.stderr,
        )
        print('Attempting to continue with existing version...', file=sys.stderr)
        return

    # Purge every archinstall entry from sys.modules so the 4.x package
    # is imported fresh by the top-level ``from archinstall...`` statements
    # that follow this block.
    stale = [k for k in sys.modules if k == 'archinstall' or k.startswith('archinstall.')]
    for key in stale:
        del sys.modules[key]

    import importlib
    importlib.invalidate_caches()


# Perform bootstrap check before ANY archinstall import
if __name__ == '__main__' and _needs_archinstall_upgrade():
    if os.geteuid() != 0:
        print('Error: This script must be run as root.', file=sys.stderr)
        sys.exit(1)
    _upgrade_archinstall()

# ---------------------------------------------------------------------------
# Delegate to the arch_bootstrap package
# ---------------------------------------------------------------------------

from arch_bootstrap.__main__ import main  # noqa: E402

if __name__ == '__main__':
    main()
