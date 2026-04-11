"""Shared NVIDIA helpers for Niri-based desktop environments."""

from __future__ import annotations

from archinstall.lib.output import Font, debug, info

_PREFIX = '[NVIDIA]'


def _info(msg: str) -> None:
    """Log an info message with a colored [NVIDIA] prefix."""
    info(f'{_PREFIX} {msg}', fg='green', font=[Font.bold])


def _debug(msg: str) -> None:
    """Log a debug message with a colored [NVIDIA] prefix."""
    debug(f'{_PREFIX} {msg}', fg='green')
