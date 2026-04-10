"""Shared utility functions for arch-bootstrap."""
from __future__ import annotations

import re
import urllib.request

from archinstall.lib.output import debug

from .constants import GHPROXY_CHUNK_URL, GHPROXY_FALLBACK

_PREFIX = '[utils]'


def _debug(msg: str) -> None:
    """Log a debug message with a [utils] prefix."""
    debug(f'{_PREFIX} {msg}', fg='cyan')


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
