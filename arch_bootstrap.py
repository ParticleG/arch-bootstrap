#!/usr/bin/env python3
"""arch-bootstrap: Opinionated Arch Linux installer powered by archinstall.

Usage on Arch ISO (single command, pipe-friendly):
    curl -sL https://raw.githubusercontent.com/ParticleG/arch-bootstrap/main/arch_bootstrap.py | python3

Or download and run:
    curl -LO https://github.com/ParticleG/arch-bootstrap/releases/latest/download/arch_bootstrap.pyz
    python3 arch_bootstrap.pyz

Or with the source tree (development):
    python3 -m arch_bootstrap
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = 'ParticleG/arch-bootstrap'
PYZ_URL = f'https://github.com/{REPO}/releases/latest/download/arch_bootstrap.pyz'


# ---------------------------------------------------------------------------
# Stdin recovery for pipe invocation (curl ... | python3)
# ---------------------------------------------------------------------------

def _reopen_stdin() -> None:
    """Reopen stdin from /dev/tty when the original fd 0 is an exhausted pipe."""
    if not os.isatty(0):
        try:
            tty_fd = os.open('/dev/tty', os.O_RDONLY)
            os.dup2(tty_fd, 0)
            os.close(tty_fd)
            sys.stdin = open(0, closefd=False)
        except OSError:
            pass  # no controlling terminal (e.g. headless CI)


# ---------------------------------------------------------------------------
# Bootstrap: upgrade archinstall on ISO before importing anything from it.
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

    # Purge stale modules so the new version is imported fresh
    stale = [k for k in sys.modules if k == 'archinstall' or k.startswith('archinstall.')]
    for key in stale:
        del sys.modules[key]
    importlib.invalidate_caches()


# ---------------------------------------------------------------------------
# Self-bootstrap: download .pyz if the package isn't available locally.
# ---------------------------------------------------------------------------

def _download_pyz(dest: Path) -> bool:
    """Download arch_bootstrap.pyz from GitHub releases. Returns True on success."""
    print(f'arch-bootstrap: Downloading {PYZ_URL} ...')
    try:
        urllib.request.urlretrieve(PYZ_URL, dest)
        print(f'arch-bootstrap: Saved to {dest}')
        return True
    except Exception as exc:
        print(f'ERROR: Failed to download .pyz: {exc}', file=sys.stderr)
        print(f'Download manually: {PYZ_URL}', file=sys.stderr)
        return False


def _exec_pyz(pyz_path: Path) -> None:
    """Replace this process with python3 running the .pyz."""
    os.execv(sys.executable, [sys.executable, str(pyz_path)])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _main() -> None:
    if os.geteuid() != 0:
        print('Error: This script must be run as root.', file=sys.stderr)
        sys.exit(1)

    _reopen_stdin()

    # Upgrade archinstall on ISO if needed
    if _needs_archinstall_upgrade():
        _upgrade_archinstall()

    # Try to import from local package (development / source tree)
    try:
        from arch_bootstrap.__main__ import main
        main()
        return
    except ImportError:
        pass

    # Package not available — download .pyz and exec it
    pyz_path = Path(tempfile.gettempdir()) / 'arch_bootstrap.pyz'
    if not _download_pyz(pyz_path):
        sys.exit(1)

    _exec_pyz(pyz_path)


if __name__ == '__main__':
    _main()
