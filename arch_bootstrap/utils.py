"""Shared utility functions for arch-bootstrap."""
from __future__ import annotations

import re
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TypeVar

from archinstall.lib.output import debug, info

from .constants import GHPROXY_CHUNK_URL, GHPROXY_FALLBACK

_PREFIX = '[utils]'


def _debug(msg: str) -> None:
    """Log a debug message with a [utils] prefix."""
    debug(f'{_PREFIX} {msg}', fg='cyan')


def _info(msg: str) -> None:
    """Log an info message with a [utils] prefix."""
    info(f'{_PREFIX} {msg}', fg='green')


T = TypeVar('T')


def _log_cmd(cmd: str | list[str], returncode: int) -> None:
    """Write a command execution record to the installation log file."""
    try:
        from .log import get_log_file
        log_file = get_log_file()
        if log_file:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
            log_file.write(f'[{timestamp}] CMD: {cmd_str} -> rc={returncode}\n')
            log_file.flush()
    except Exception:
        pass  # Never let logging crash the installer


def resolve_github_proxy(is_cn: bool) -> str | None:
    """Resolve a GitHub proxy URL for CN users.

    Fetches available proxy domains from ghproxy.link's JS chunk and returns
    the first valid one.  Falls back to :data:`GHPROXY_FALLBACK` when the
    chunk is unreachable or contains no valid domains.

    Domain validation: must start with ``gh``, be a two-part domain
    (``name.tld``), and be ≤30 characters total.

    Args:
        is_cn: Whether the user is in China.

    Returns:
        Proxy base URL (e.g. ``'https://ghfast.top'``) or ``None`` for
        non-CN users.
    """
    if not is_cn:
        return None

    try:
        req = urllib.request.Request(GHPROXY_CHUNK_URL)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode('utf-8', errors='ignore')

        matches = re.findall(r'href=.{0,5}(https://gh[a-z0-9]+\.[a-z]+)', content)
        for candidate in matches:
            # Strip scheme for validation
            domain = candidate.removeprefix('https://')
            parts = domain.split('.')
            if (
                len(parts) == 2
                and domain.startswith('gh')
                and len(domain) <= 30
            ):
                _debug(f'Resolved GitHub proxy: {candidate}')
                return candidate

        _debug('No valid proxy domain found in chunk')
    except Exception:
        _debug('Failed to fetch ghproxy chunk')

    _debug(f'Using fallback proxy: {GHPROXY_FALLBACK}')
    return GHPROXY_FALLBACK


def get_clone_url(repo: str, is_cn: bool) -> str:
    """Build a git clone URL, with optional proxy for CN users.

    Args:
        repo: GitHub repo path like ``'user/repo'`` or
              ``'user/repo.git'``, or a full ``https://github.com/...`` URL.
        is_cn: Whether to use CN proxy.

    Returns:
        Full git clone URL.
    """
    # Normalise: if it's already a full URL, use as-is; otherwise build one
    if repo.startswith('https://'):
        base_url = repo
    else:
        base_url = f'https://github.com/{repo}'

    if not is_cn:
        return base_url

    proxy = resolve_github_proxy(is_cn=True)
    if proxy:
        return f'{proxy}/{base_url}'

    return base_url


def run_with_retry(
    cmd: str | list[str],
    *,
    max_retries: int = 3,
    retry_delay: float = 5.0,
    description: str = '',
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run a subprocess command with automatic retry.

    Retries up to *max_retries* times when the return code is non-zero.
    After exhausting all automatic retries, interactively asks the user
    whether to keep retrying or give up.

    Args:
        cmd: Command string or list.
        max_retries: Number of automatic retries before prompting.
        retry_delay: Seconds to wait between automatic retries.
        description: Human-readable label for log messages.
        **kwargs: Forwarded to :func:`subprocess.run`.

    Returns:
        The final :class:`subprocess.CompletedProcess` result.
    """
    from .i18n import t  # local import to avoid circular dependency

    result: subprocess.CompletedProcess | None = None

    for attempt in range(1, max_retries + 1):
        result = subprocess.run(cmd, **kwargs)
        _log_cmd(cmd, result.returncode)
        if result.returncode == 0:
            return result
        if attempt < max_retries:
            _info(t('retry.attempt', attempt, max_retries, description))
            time.sleep(retry_delay)

    # All automatic retries exhausted — ask user interactively
    assert result is not None
    while True:
        try:
            answer = input(t('retry.prompt', description)).strip().lower()
        except EOFError:
            return result
        if answer in ('n', 'no'):
            return result
        # Default (empty / 'y' / 'yes') = retry
        result = subprocess.run(cmd, **kwargs)
        _log_cmd(cmd, result.returncode)
        if result.returncode == 0:
            return result


def retry_on_failure(
    operation: Callable[[], T],
    *,
    max_retries: int = 3,
    retry_delay: float = 5.0,
    description: str = '',
) -> T:
    """Run a callable with automatic retry on exception.

    Retries up to *max_retries* times when the callable raises.
    After exhausting all automatic retries, interactively asks the user
    whether to keep retrying or give up.

    Args:
        operation: Zero-argument callable to execute.
        max_retries: Number of automatic retries before prompting.
        retry_delay: Seconds to wait between automatic retries.
        description: Human-readable label for log messages.

    Returns:
        The return value of *operation* on success.

    Raises:
        The last exception if the user chooses not to retry.
    """
    from .i18n import t

    last_error: BaseException | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                _info(t('retry.attempt', attempt, max_retries, description))
                time.sleep(retry_delay)

    # All automatic retries exhausted — ask user interactively
    assert last_error is not None
    while True:
        try:
            answer = input(t('retry.prompt', description)).strip().lower()
        except EOFError:
            raise last_error
        if answer in ('n', 'no'):
            raise last_error
        try:
            return operation()
        except Exception as exc:
            last_error = exc


_GITHUB_PROXY_DL_TEMPLATE = r'''#!/usr/bin/env bash
# github-proxy-dl — makepkg DLAGENT wrapper that proxies GitHub URLs
# Deployed by arch-bootstrap for CN users.
set -euo pipefail

url="$1"
output="$2"
PROXY="__PROXY__"

CURL_OPTS=(-gqb "" -fLC - --retry 3 --retry-delay 3)

case "$url" in
    https://github.com/* \
    | https://raw.githubusercontent.com/* \
    | https://objects.githubusercontent.com/* \
    | https://codeload.github.com/* \
    | https://github-releases.githubusercontent.com/*)
        proxied="${PROXY}/${url}"
        if /usr/bin/curl "${CURL_OPTS[@]}" -o "$output" "$proxied" 2>/dev/null; then
            exit 0
        fi
        echo "github-proxy-dl: proxy failed, trying direct download..." >&2
        ;;
esac

exec /usr/bin/curl "${CURL_OPTS[@]}" -o "$output" "$url"
'''


def install_github_proxy_dl(chroot_dir: Path, proxy: str) -> None:
    """Deploy the GitHub proxy download agent and patch makepkg.conf.

    Installs ``/usr/local/bin/github-proxy-dl`` and rewrites the HTTPS
    DLAGENT in ``/etc/makepkg.conf`` so that makepkg source downloads
    from GitHub domains are transparently proxied.

    Args:
        chroot_dir: Absolute path to the mounted chroot.
        proxy: Proxy base URL, e.g. ``'https://ghfast.top'``.
    """
    # 1. Write the download agent script
    script = _GITHUB_PROXY_DL_TEMPLATE.replace('__PROXY__', proxy)
    script_path = chroot_dir / 'usr' / 'local' / 'bin' / 'github-proxy-dl'
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script)
    script_path.chmod(0o755)
    _info(f'Installed github-proxy-dl with proxy {proxy}')

    # 2. Patch makepkg.conf DLAGENTS to use the wrapper for HTTPS
    makepkg_conf = chroot_dir / 'etc' / 'makepkg.conf'
    if makepkg_conf.exists():
        content = makepkg_conf.read_text()
        patched = re.sub(
            r"'https::/usr/bin/curl[^']*'",
            "'https::/usr/local/bin/github-proxy-dl %u %o'",
            content,
        )
        if patched != content:
            makepkg_conf.write_text(patched)
            _info('Patched makepkg.conf DLAGENTS for GitHub proxy')
        else:
            _debug('makepkg.conf HTTPS DLAGENT not found or already patched')
