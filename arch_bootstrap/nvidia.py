"""Shared NVIDIA workarounds for Niri-based desktop environments.

Contains the DRM retry workaround for NVIDIA Optimus systems where
greeter's compositor holds DRM devices open during close(), causing
the user's niri session to get EBUSY.

Uses a PATH-hijacking niri-session wrapper at /usr/local/bin/niri-session
that retries the real /usr/bin/niri-session on failure, combined with a
systemd drop-in for defense-in-depth restart behavior.

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
# priority over /usr/bin/niri-session).  When the greeter's niri compositor
# still holds the NVIDIA DRM master during the greeter-to-session transition,
# the user's niri fails with EBUSY.  This wrapper retries after a delay,
# giving greetd time to kill the greeter and release the DRM device.
_NIRI_SESSION_WRAPPER = r'''#!/usr/bin/env bash
# niri-session wrapper: retry on NVIDIA DRM EBUSY during greeter-to-session transition
# When switching from a graphical greeter (dms-greeter) to the user session, the greeter's
# niri compositor may still hold the DRM master on the NVIDIA GPU (card1), causing the user's
# niri to fail with EBUSY. This wrapper retries niri-session after a delay, by which time
# greetd has killed the greeter and the DRM device is released.

MAX_RETRIES=5
RETRY_DELAY=2

for attempt in $(seq 1 $MAX_RETRIES); do
    /usr/bin/niri-session
    rc=$?

    # Normal exit (user logout) — do not retry
    [ $rc -eq 0 ] && exit 0

    # Failed start (likely EBUSY). Reset systemd state and retry.
    systemctl --user reset-failed niri.service 2>/dev/null
    sleep "$RETRY_DELAY"
done

exit 1
'''

# Defense-in-depth systemd drop-in for niri.service.  The wrapper script
# handles the primary retry logic; this drop-in provides an additional
# safety net via systemd's own restart mechanism.
_NIRI_DRM_WAIT_DROPIN = '''\
[Service]
Restart=on-failure
RestartSec=2
StartLimitIntervalSec=30
StartLimitBurst=5
'''


def install_niri_drm_wait(chroot_dir: Path) -> None:
    """Deploy the niri DRM retry workaround for NVIDIA Optimus systems.

    Installs a PATH-hijacking wrapper at /usr/local/bin/niri-session that
    retries /usr/bin/niri-session on failure, working around EBUSY errors
    caused by the greeter's compositor still holding the NVIDIA DRM master
    during the greeter-to-session transition.
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
