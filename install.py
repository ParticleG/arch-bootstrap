#!/usr/bin/env python3
"""arch-bootstrap: Opinionated Arch Linux installer powered by archinstall.

Usage on Arch ISO (single command, pipe-friendly):
    curl -sL https://raw.githubusercontent.com/ParticleG/arch-bootstrap/main/install.py | python3

Or download and run:
    curl -LO https://github.com/ParticleG/arch-bootstrap/releases/latest/download/arch_bootstrap.pyz
    python3 arch_bootstrap.pyz

Or with the source tree (development):
    python3 -m arch_bootstrap
"""

from __future__ import annotations

import hashlib
import importlib
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = 'ParticleG/arch-bootstrap'
GITHUB_URL = f'https://github.com/{REPO}/releases/latest/download/arch_bootstrap.pyz'

# Proxy resolution constants
GHPROXY_CHUNK_URL = 'https://ghproxy.link/js/src_views_home_HomeView_vue.js'
FALLBACK_PROXY = 'https://ghfast.top'

# ASCII art banner (version info is inside the .pyz and shown later)
_C = '\033[1;36m'  # cyan bold
_B = '\033[1;34m'  # blue bold
_M = '\033[1;35m'  # magenta bold
_0 = '\033[0m'     # reset

_BANNER = f"""\
{_C}                 -@              {_0}  {_B}  ___           _          _     _                         {_0}
{_C}                .##@             {_0}  {_B} / _ \\         | |        | |   (_)                       {_0}
{_C}               .####@            {_0}  {_B}/ /_\\ \\_ __ ___| |__      | |    _ _ __  _   ___  __     {_0}
{_C}               @#####@           {_0}  {_B}|  _  | '__/ __| '_ \\     | |   | | '_ \\| | | \\ \\/ /   {_0}
{_C}             . *######@          {_0}  {_B}| | | | | | (__| | | |    | |___| | | | | |_| |>  <        {_0}
{_C}            .##@o@#####@         {_0}  {_B}\\_| |_/_|  \\___|_| |_|    \\_____/_|_| |_|\\__,_/_/\\_\\ {_0}
{_C}           /############@        {_0}
{_C}          /##############@       {_0}  {_M}______             _       _                               {_0}
{_C}         @######@**%######@      {_0}  {_M}| ___ \\           | |     | |                             {_0}
{_C}        @######`     %#####o     {_0}  {_M}| |_/ / ___   ___ | |_ ___| |_ _ __ __ _ _ __              {_0}
{_C}       @######@       ######%    {_0}  {_M}| ___ \\/ _ \\ / _ \\| __/ __| __| '__/ _` | '_ \\         {_0}
{_C}     -@#######h       ######@.`  {_0}  {_M}| |_/ / (_) | (_) | |_\\__ \\ |_| | | (_| | |_) |          {_0}
{_C}    /#####h**``       `**%@####@ {_0}  {_M}\\____/ \\___/ \\___/ \\__|___/\\__|_|  \\__,_| .__/       {_0}
{_C}   @H@*`                    `*%#@{_0}  {_M}                                        | |                {_0}
{_C}  *`                            `*{_0} {_M}                                        |_|                {_0}
"""

# Geolocation endpoints (tried in order, 2s timeout each)
_GEO_ENDPOINTS = [
    'https://ifconfig.co/country-iso',
    'https://ipinfo.io/country',
    'https://api.country.is/',
]

# Fallback mirror pools per country (subset inlined from constants.py)
_FALLBACK_MIRRORS: dict[str, list[str]] = {
    'CN': [
        'https://mirrors.ustc.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.bfsu.edu.cn/archlinux/$repo/os/$arch',
        'https://mirrors.aliyun.com/archlinux/$repo/os/$arch',
        'https://mirrors.hit.edu.cn/archlinux/$repo/os/$arch',
        'https://mirror.nju.edu.cn/archlinux/$repo/os/$arch',
    ],
    'JP': [
        'https://ftp.jaist.ac.jp/pub/Linux/ArchLinux/$repo/os/$arch',
        'https://mirrors.cat.net/archlinux/$repo/os/$arch',
    ],
    'US': [
        'https://mirrors.kernel.org/archlinux/$repo/os/$arch',
        'https://mirror.rackspace.com/archlinux/$repo/os/$arch',
    ],
    'DE': [
        'https://mirror.f4st.host/archlinux/$repo/os/$arch',
        'https://ftp.fau.de/archlinux/$repo/os/$arch',
    ],
}


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
            print(
                '[WARN] Could not reopen /dev/tty — interactive prompts may not work',
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Region detection + fast mirrors (applied BEFORE archinstall upgrade)
# ---------------------------------------------------------------------------

def _detect_country() -> str | None:
    """Detect country via IP geolocation. Returns ISO 3166-1 alpha-2 or None.

    Inlined from arch_bootstrap.detection — uses only stdlib so it works
    before archinstall is available.
    """
    import json

    for url in _GEO_ENDPOINTS:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'curl/8.0'})
            with urllib.request.urlopen(req, timeout=2) as resp:
                body = resp.read().decode().strip()
                try:
                    data = json.loads(body)
                    code = str(data.get('country', '')).strip().upper()
                except (json.JSONDecodeError, AttributeError):
                    code = body.upper()
                if re.match(r'^[A-Z]{2}$', code):
                    return code
        except Exception:
            continue
    return None


def _apply_fast_mirrors() -> str | None:
    """Detect region and write fast mirrors to /etc/pacman.d/mirrorlist on ISO.

    Only runs when /run/archiso exists. Detects country via IP geolocation
    and replaces the mirror list with known-fast mirrors for that region.
    If detection fails or the country has no fallback pool, does nothing
    (the existing mirror list is left untouched).

    Returns the detected country code (or None) so callers can reuse it
    (e.g. to decide whether a GitHub proxy is needed for .pyz download).
    """
    if not Path('/run/archiso').exists():
        return None

    mirrorlist = Path('/etc/pacman.d/mirrorlist')
    if not mirrorlist.exists():
        return None

    print('arch-bootstrap: Detecting region for fast mirrors...')
    country = _detect_country()

    if not country:
        print('  Could not detect region, keeping default mirrors.')
        return None

    mirrors = _FALLBACK_MIRRORS.get(country)
    if not mirrors:
        print(f'  Region {country} detected, no custom mirror pool — keeping defaults.')
        return country

    print(f'  Region: {country} — applying {len(mirrors)} fast mirrors.')

    # Build Server lines
    lines = [f'Server = {url}\n' for url in mirrors]

    # Prepend to existing mirrorlist (keep originals as fallback)
    try:
        original = mirrorlist.read_text()
        content = (
            '# Fast mirrors applied by arch-bootstrap\n'
            + ''.join(lines)
            + '\n# Original mirrors\n'
            + original
        )
        tmp = mirrorlist.with_suffix('.tmp')
        tmp.write_text(content)
        os.replace(str(tmp), str(mirrorlist))
    except OSError as exc:
        print(f'  WARNING: Could not write mirrorlist: {exc}', file=sys.stderr)

    return country


# ---------------------------------------------------------------------------
# Bootstrap: upgrade archinstall on ISO before importing anything from it.
# ---------------------------------------------------------------------------

def _needs_archinstall_upgrade() -> bool:
    """Return True if running on ISO and archinstall is not 4.x+."""
    if not Path('/run/archiso').exists():
        return False
    try:
        from importlib.metadata import version as pkg_version
        ver = pkg_version('archinstall')
        major = int(ver.split('.')[0])
        return major < 4
    except Exception:
        return True


def _upgrade_archinstall() -> None:
    """Upgrade archinstall via pacman and flush module caches in-process."""
    print('arch-bootstrap: ISO detected with archinstall < 4.x — upgrading...')
    result = subprocess.run(
        ['pacman', '-Syu', '--noconfirm', 'archinstall'],
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
# GitHub proxy resolution
# ---------------------------------------------------------------------------

def _head_request(url: str, timeout: float = 5.0) -> tuple[int, float]:
    """Send a HEAD request. Returns (http_status, elapsed_seconds).

    Returns (0, timeout) on connection failure or timeout.
    """
    req = urllib.request.Request(url, method='HEAD')
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = time.monotonic() - start
            return resp.status, elapsed
    except urllib.error.HTTPError as exc:
        # 3xx/4xx are still valid responses (proxy may 302 redirect)
        elapsed = time.monotonic() - start
        return exc.code, elapsed
    except Exception:
        return 0, timeout


def _resolve_ghproxy() -> str | None:
    """Fetch the latest available proxy domain from ghproxy.link.

    The publish page is a Vue SPA; domain status is embedded in a webpack
    JS chunk.  Available domains use ``href="URL"``, blocked ones use
    ``<del>URL</del>``.
    """
    try:
        req = urllib.request.Request(GHPROXY_CHUNK_URL)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return None

    # Match href=...https://gh<word>.<tld> (escaped quotes in the bundle)
    matches = re.findall(r'href=.{0,5}(https://gh[a-z0-9]+\.[a-z]+)', content)

    # Validate against known proxy domain patterns: must start with 'gh',
    # be a short domain, and look like a legitimate proxy host.
    for candidate in matches:
        # Extract domain from URL
        domain = candidate.split('//')[1] if '//' in candidate else ''
        parts = domain.split('.')
        # Must be a short two-part domain (e.g. ghfast.top, ghproxy.link)
        if len(parts) == 2 and parts[0].startswith('gh') and len(domain) <= 30:
            return candidate

    return None


def _test_proxy(proxy: str) -> bool:
    """Verify a proxy can reach the actual download URL (2xx or 3xx)."""
    proxied_url = f'{proxy}/{GITHUB_URL}'
    status, _ = _head_request(proxied_url, timeout=10)
    return 200 <= status < 400


def _resolve_download_url(country: str | None) -> str:
    """Determine the best download URL for .pyz.

    - Non-CN (or unknown): GitHub is directly accessible, use direct URL.
    - CN: GitHub is blocked/slow, resolve a proxy.

    Proxy resolution order for CN:
    1. Resolve proxy from ghproxy.link — test connectivity.
    2. Try hardcoded fallback proxy.
    3. Give up with an actionable error message.
    """
    if country != 'CN':
        return GITHUB_URL

    print('arch-bootstrap: China detected, resolving GitHub proxy...')

    # Step 1: ghproxy.link
    proxy = _resolve_ghproxy()
    if proxy:
        print(f'  Found proxy: {proxy}')
        if _test_proxy(proxy):
            print('  Proxy is reachable.')
            return f'{proxy}/{GITHUB_URL}'
        print('  Proxy resolved but unreachable, trying fallback...')
    else:
        print('  Could not reach ghproxy.link, trying fallback...')

    # Step 2: hardcoded fallback
    print(f'  Trying fallback: {FALLBACK_PROXY}')
    if _test_proxy(FALLBACK_PROXY):
        print('  Fallback proxy is reachable.')
        return f'{FALLBACK_PROXY}/{GITHUB_URL}'

    print(
        'ERROR: Cannot reach GitHub through any proxy.\n'
        'Visit https://ghproxy.link/ for the latest proxy address,\n'
        f'or download manually: {GITHUB_URL}',
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Checksum verification
# ---------------------------------------------------------------------------

SHASUMS_URL = f'https://github.com/{REPO}/releases/latest/download/SHA256SUMS'


def _verify_checksum(pyz_path: Path, is_cn: bool) -> bool | None:
    """Download SHA256SUMS from the release and verify the .pyz file.

    Returns True if checksum matches, False if mismatch, None if the
    SHA256SUMS file could not be downloaded (best-effort).
    """
    # Build URL for SHA256SUMS (apply same proxy logic for CN)
    sums_url = SHASUMS_URL
    if is_cn:
        proxy = _resolve_ghproxy()
        if proxy and _test_proxy(proxy):
            sums_url = f'{proxy}/{SHASUMS_URL}'
        elif _test_proxy(FALLBACK_PROXY):
            sums_url = f'{FALLBACK_PROXY}/{SHASUMS_URL}'

    try:
        req = urllib.request.Request(sums_url, headers={'User-Agent': 'curl/8.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            sums_text = resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return None  # SHA256SUMS not available — best-effort skip

    # Parse expected hash for arch_bootstrap.pyz
    expected_hash = None
    for line in sums_text.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].lstrip('*') == 'arch_bootstrap.pyz':
            expected_hash = parts[0].lower()
            break

    if expected_hash is None:
        return None  # file not listed in SHA256SUMS

    # Compute actual hash
    sha256 = hashlib.sha256()
    with open(pyz_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            sha256.update(chunk)
    actual_hash = sha256.hexdigest().lower()

    return actual_hash == expected_hash


# ---------------------------------------------------------------------------
# Self-bootstrap: download .pyz if the package isn't available locally.
# ---------------------------------------------------------------------------

def _download_pyz(dest: Path, country: str | None) -> bool:
    """Download arch_bootstrap.pyz (with proxy for CN region).

    Returns True on success.
    """
    url = _resolve_download_url(country)
    print(f'arch-bootstrap: Downloading...\n  {url}')
    try:
        urllib.request.urlretrieve(url, dest)
        print(f'arch-bootstrap: Saved to {dest}')
    except Exception as exc:
        print(f'ERROR: Failed to download .pyz: {exc}', file=sys.stderr)
        print(f'Download manually: {GITHUB_URL}', file=sys.stderr)
        return False

    # Best-effort checksum verification
    is_cn = (country == 'CN')
    verified = _verify_checksum(dest, is_cn)
    if verified is None:
        print('arch-bootstrap: [WARN] Could not download SHA256SUMS — skipping integrity check.',
              file=sys.stderr)
    elif not verified:
        print('ERROR: SHA256 checksum mismatch! The downloaded file may be corrupted or tampered with.',
              file=sys.stderr)
        try:
            dest.unlink()
        except OSError:
            pass
        return False
    else:
        print('arch-bootstrap: SHA256 checksum verified.')

    return True


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

    # Show banner immediately on startup
    print(_BANNER)

    # Apply fast mirrors BEFORE upgrading archinstall (speeds up pacman -Sy)
    country = _apply_fast_mirrors()

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
    fd, tmp_path_str = tempfile.mkstemp(suffix='.pyz')
    os.close(fd)
    pyz_path = Path(tmp_path_str)
    os.chmod(pyz_path, 0o700)
    if not _download_pyz(pyz_path, country):
        try:
            pyz_path.unlink()
        except OSError:
            pass
        sys.exit(1)

    _exec_pyz(pyz_path)


if __name__ == '__main__':
    _main()
