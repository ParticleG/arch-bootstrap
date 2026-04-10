"""Shared NVIDIA workarounds for Niri-based desktop environments.

Contains the DRM wait workaround for NVIDIA Optimus systems where
greeter's compositor holds DRM devices open during close(), causing
the user's niri session to get EBUSY.

Used by both dms.py and exo.py.
"""

from __future__ import annotations

from pathlib import Path

from archinstall.lib.output import Font, debug, info

_PREFIX = '[NVIDIA]'


def _info(msg: str) -> None:
    """Log an info message with a colored [NVIDIA] prefix."""
    info(f'{_PREFIX} {msg}', fg='green', font=[Font.bold])


def _debug(msg: str) -> None:
    """Log a debug message with a colored [NVIDIA] prefix."""
    debug(f'{_PREFIX} {msg}', fg='green')


# Wrapper script that waits for the greeter user's processes to fully exit
# before allowing niri to start.  This works around a race condition where
# NVIDIA GSP firmware takes ~5 seconds to release DRM devices when the
# greeter's compositor is killed, causing the user's niri to get EBUSY on
# first login attempt.
_NIRI_DRM_WAIT_SCRIPT = r'''#!/usr/bin/env bash
# niri-drm-wait.sh — wait for greeter to fully release DRM devices
#
# NVIDIA GSP firmware may take ~5 seconds to process a device close after
# the greeter's compositor exits.  During this window, all DRM file
# descriptors (including the AMD iGPU that has the display attached) are
# held open, causing niri to get EBUSY.
#
# This script polls until the greeter user has no remaining processes,
# then adds a small buffer for the kernel to finish cleanup.

set -euo pipefail

GREETER_USER="greeter"
MAX_ITERS=150     # 150 × 0.1s = 15s max wait (GSP timeout is ~5.2s)
SETTLE_TIME=0.5   # kernel buffer after greeter processes exit

i=0
while pgrep -u "$GREETER_USER" > /dev/null 2>&1; do
    if (( i >= MAX_ITERS )); then
        echo "niri-drm-wait: greeter still running after $((MAX_ITERS / 10))s, proceeding anyway" >&2
        break
    fi
    sleep 0.1
    (( i++ ))
done

if (( i > 0 )); then
    elapsed=$(awk "BEGIN {printf \"%.1f\", $i / 10}")
    echo "niri-drm-wait: greeter exited after ${elapsed}s, settling ${SETTLE_TIME}s" >&2
    sleep "$SETTLE_TIME"
fi
'''

_NIRI_DRM_WAIT_DROPIN = '''\
[Service]
ExecStartPre=/usr/local/bin/niri-drm-wait.sh
'''


def install_niri_drm_wait(chroot_dir: Path) -> None:
    """Deploy the niri DRM wait workaround for NVIDIA Optimus systems.

    Installs a script that waits for the greeter user's processes to
    fully exit before niri starts, preventing EBUSY errors caused by
    NVIDIA GSP firmware holding DRM devices open during close().
    """
    _info('Installing niri DRM wait workaround for NVIDIA...')

    # Deploy wrapper script
    script_path = chroot_dir / 'usr' / 'local' / 'bin' / 'niri-drm-wait.sh'
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(_NIRI_DRM_WAIT_SCRIPT)
    script_path.chmod(0o755)
    _debug(f'Wrote {script_path}')

    # Deploy systemd drop-in
    dropin_dir = chroot_dir / 'etc' / 'systemd' / 'user' / 'niri.service.d'
    dropin_dir.mkdir(parents=True, exist_ok=True)
    dropin_path = dropin_dir / '10-drm-wait.conf'
    dropin_path.write_text(_NIRI_DRM_WAIT_DROPIN)
    _debug(f'Wrote {dropin_path}')

    _info('niri DRM wait workaround installed')
