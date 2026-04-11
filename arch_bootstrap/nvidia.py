"""Shared NVIDIA workarounds for Niri-based desktop environments.

Contains the DRM wait workaround for NVIDIA Optimus systems where
greeter's compositor holds DRM devices open during close(), causing
the user's niri session to get EBUSY.

Uses a PATH-hijacking niri-session wrapper at /usr/local/bin/niri-session
that waits for the greeter to exit before starting the real
/usr/bin/niri-session, combined with a systemd drop-in for
defense-in-depth restart behavior.

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


# PATH-hijacking wrapper installed to /usr/local/bin/niri-session (takes
# priority over /usr/bin/niri-session).  When the greeter's compositor
# still holds the NVIDIA DRM master during the greeter-to-session transition,
# the user's niri fails with EBUSY.  This wrapper polls until all greeter
# processes exit, then starts the real niri-session.
_NIRI_SESSION_WRAPPER = r'''#!/usr/bin/env bash
# niri-session wrapper: wait for greeter to release DRM before starting user session.
#
# On NVIDIA Optimus systems, the greeter's compositor holds DRM master on the NVIDIA
# GPU (card1). greetd sends SIGTERM to the greeter when starting the user session, but
# there is a race: the user's niri may try to open card1 before the greeter releases it,
# causing EBUSY (errno 16). This wrapper polls until all greeter-owned processes exit,
# then starts the real niri-session.

LOG_TAG="niri-session-wrapper"
log() { logger -t "$LOG_TAG" "$@"; }

log "started (PID=$$, PPID=$PPID, UID=$(id -u), args=$*)"

# Poll until all greeter-owned processes exit and release DRM master.
# greetd has already sent SIGTERM to the greeter by the time we start; we just
# need to wait for the process to actually terminate (usually < 1s).
MAX_WAIT=10
i=0
timed_out=0
while pgrep -u greeter >/dev/null 2>&1; do
    if [ $i -ge $MAX_WAIT ]; then
        log "WARNING: greeter processes still running after ${MAX_WAIT}s, proceeding anyway"
        timed_out=1
        break
    fi
    [ $i -eq 0 ] && log "greeter processes still running, waiting for exit..."
    sleep 1
    i=$((i + 1))
done

if [ $i -gt 0 ] && [ $timed_out -eq 0 ]; then
    log "greeter processes exited after ~${i}s, adding 500ms settle delay"
    sleep 0.5
elif [ $timed_out -eq 1 ]; then
    log "proceeding after ${MAX_WAIT}s timeout, adding 500ms settle delay"
    sleep 0.5
fi

log "starting /usr/bin/niri-session $*"
exec /usr/bin/niri-session "$@"
'''

# Defense-in-depth systemd drop-in for niri.service.  The wrapper script
# handles the primary wait logic; this drop-in provides an additional
# safety net via systemd's own restart mechanism.
_NIRI_DRM_WAIT_DROPIN = '''\
[Unit]
StartLimitIntervalSec=30
StartLimitBurst=5

[Service]
Restart=on-failure
RestartSec=2
'''


def install_niri_drm_wait(chroot_dir: Path) -> None:
    """Deploy the niri DRM wait workaround for NVIDIA Optimus systems.

    Installs a PATH-hijacking wrapper at /usr/local/bin/niri-session that
    waits for the greeter to exit before starting the real
    /usr/bin/niri-session, working around EBUSY errors caused by the
    greeter's compositor still holding the NVIDIA DRM master during the
    greeter-to-session transition.
    """
    _info('Installing niri DRM wait workaround for NVIDIA...')

    # Deploy niri-session wrapper (PATH priority over /usr/bin/niri-session)
    wrapper_path = chroot_dir / 'usr' / 'local' / 'bin' / 'niri-session'
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper_path.write_text(_NIRI_SESSION_WRAPPER)
    wrapper_path.chmod(0o755)
    _debug(f'Wrote {wrapper_path}')

    # Deploy systemd drop-in (defense-in-depth restart)
    dropin_dir = chroot_dir / 'etc' / 'systemd' / 'user' / 'niri.service.d'
    dropin_dir.mkdir(parents=True, exist_ok=True)
    dropin_path = dropin_dir / '10-drm-wait.conf'
    dropin_path.write_text(_NIRI_DRM_WAIT_DROPIN)
    _debug(f'Wrote {dropin_path}')

    _info('niri DRM wait workaround installed')
