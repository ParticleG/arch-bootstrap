"""Installation logging: captures stdout/stderr and subprocess output to a file.

The log is written to ``/var/log/arch-bootstrap/install.log`` on the live ISO
and later copied into the installed system.  Logging is transparent — all
terminal output is preserved via :class:`TeeStream`.
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from io import TextIOWrapper
from pathlib import Path
from typing import IO

LOG_DIR = Path('/var/log/arch-bootstrap')
LOG_FILE = 'install.log'

# Module-level state
_log_file: IO[str] | None = None
_original_stdout: TextIOWrapper | None = None
_original_stderr: TextIOWrapper | None = None


class TeeStream:
    """A stream wrapper that writes to both the original stream and a log file.

    Designed as a drop-in replacement for ``sys.stdout`` / ``sys.stderr``.
    Subprocess compatibility is maintained by delegating :meth:`fileno` and
    :meth:`isatty` to the original stream.
    """

    def __init__(self, original_stream: TextIOWrapper, log_file: IO[str]) -> None:
        self._original = original_stream
        self._log_file = log_file

    def write(self, data: str) -> int:
        self._original.write(data)
        try:
            if data.strip():  # Don't log empty/whitespace-only writes
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self._log_file.write(f'[{timestamp}] {data}')
                if not data.endswith('\n'):
                    self._log_file.write('\n')
                self._log_file.flush()
        except Exception:
            pass  # Never let logging crash the installer
        return len(data)

    def flush(self) -> None:
        self._original.flush()
        try:
            self._log_file.flush()
        except Exception:
            pass

    def fileno(self) -> int:
        return self._original.fileno()  # Important: subprocess uses this

    def isatty(self) -> bool:
        return self._original.isatty()

    def __getattr__(self, name: str) -> object:
        return getattr(self._original, name)


def setup_logging() -> None:
    """Create the log directory, open the log file, and install TeeStream.

    Safe to call multiple times — subsequent calls are no-ops if logging
    is already active.  Fails gracefully if the log directory cannot be
    created or the file cannot be opened.
    """
    global _log_file, _original_stdout, _original_stderr

    if _log_file is not None:
        return  # Already set up

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        _log_file = open(LOG_DIR / LOG_FILE, 'a', encoding='utf-8')
    except Exception:
        return  # Cannot create log — continue without file logging

    _original_stdout = sys.stdout
    _original_stderr = sys.stderr

    sys.stdout = TeeStream(_original_stdout, _log_file)  # type: ignore[assignment]
    sys.stderr = TeeStream(_original_stderr, _log_file)  # type: ignore[assignment]

    # Write a session header
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        _log_file.write(f'\n{"=" * 72}\n')
        _log_file.write(f'[{timestamp}] arch-bootstrap session started\n')
        _log_file.write(f'{"=" * 72}\n')
        _log_file.flush()
    except Exception:
        pass


def teardown_logging() -> None:
    """Restore original stdout/stderr streams.

    The log file is kept open so that :func:`resume_logging` can re-attach
    the TeeStream wrappers.  This is needed before the TUI wizard which
    requires raw terminal access.

    Note: this is called before the TUI wizard where passwords are entered,
    so passwords are NOT captured in the log file.  During the installation
    phase, passwords are passed as archinstall ``Password`` objects and never
    printed to stdout/stderr.
    """
    global _original_stdout, _original_stderr

    if _original_stdout is not None:
        sys.stdout = _original_stdout
    if _original_stderr is not None:
        sys.stderr = _original_stderr


def resume_logging() -> None:
    """Re-install TeeStream wrappers after the TUI wizard completes.

    Must be called after :func:`teardown_logging`.  No-op if the log file
    was never opened.
    """
    global _original_stdout, _original_stderr

    if _log_file is None:
        return

    _original_stdout = sys.stdout
    _original_stderr = sys.stderr

    sys.stdout = TeeStream(_original_stdout, _log_file)  # type: ignore[assignment]
    sys.stderr = TeeStream(_original_stderr, _log_file)  # type: ignore[assignment]


def get_log_file() -> IO[str] | None:
    """Return the open log file handle, or ``None`` if logging is inactive.

    Callers can write directly to this handle for subprocess output
    redirection.
    """
    return _log_file


def copy_log_to_target(chroot_dir: Path) -> None:
    """Copy the installation log to the newly installed system.

    Creates ``{chroot_dir}/var/log/arch-bootstrap/install.log``.
    Fails silently if the source log doesn't exist or the copy fails.
    """
    from .i18n import t  # local import to avoid circular dependency

    src = LOG_DIR / LOG_FILE
    if not src.exists():
        return

    try:
        dst_dir = chroot_dir / 'var' / 'log' / 'arch-bootstrap'
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst_dir / LOG_FILE)

        from archinstall.lib.output import info
        info(f'[arch-bootstrap] {t("log.copied")}', fg='cyan')
    except Exception:
        pass  # Best-effort — don't crash the installer
