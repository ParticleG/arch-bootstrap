from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from archinstall.lib.disk.device_handler import device_handler
from archinstall.lib.models.device import BDevice, Unit

from .constants import GPU_DETECT_PATTERNS, GEO_ENDPOINTS, NVIDIA_TURING_THRESHOLD


# =============================================================================
# Detection helpers
# =============================================================================

def detect_country() -> str | None:
    """Detect country via IP geolocation. Returns ISO 3166-1 alpha-2 code or None."""
    import json
    import urllib.request

    for url in GEO_ENDPOINTS:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'curl/8.0'})
            with urllib.request.urlopen(req, timeout=2) as resp:
                body = resp.read().decode().strip()

                # Try JSON response first (e.g. api.country.is returns {"country":"US",...})
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


def detect_gpu() -> list[str]:
    """Detect GPUs via lspci. Returns list of pre-selected vendor keys.

    For NVIDIA, checks PCI Device ID to decide between nvidia_open (Turing+)
    and nouveau (older).
    """
    try:
        lspci_output = subprocess.check_output(
            ['lspci', '-nn'], text=True, stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    detected: list[str] = []

    # Check AMD and Intel
    for vendor in ('amd', 'intel'):
        if re.search(GPU_DETECT_PATTERNS[vendor], lspci_output):
            detected.append(vendor)

    # Check NVIDIA with Turing+ logic
    if re.search(GPU_DETECT_PATTERNS['nvidia_open'], lspci_output):
        # Extract NVIDIA PCI Device IDs: [10de:XXXX]
        nvidia_ids = re.findall(r'\[10de:([0-9a-fA-F]{4})\]', lspci_output)
        has_turing = any(int(did, 16) >= NVIDIA_TURING_THRESHOLD for did in nvidia_ids)
        detected.append('nvidia_open' if has_turing else 'nouveau')

    return detected


def detect_preferred_disk() -> Path | None:
    """Select preferred disk: first with no partitions, else first NVMe, else None."""
    try:
        devices = device_handler.devices
    except Exception:
        # Device enumeration can fail on exotic hardware or broken udev state
        return None

    # Filter out read-only, loop, and tiny disks (< 8 GiB)
    candidates = [
        d for d in devices
        if not d.device_info.read_only
        and d.device_info.type != 'loop'
        and d.device_info.total_size.convert(Unit.GiB, None).value >= 8
    ]

    if not candidates:
        return None

    # Prefer first disk with no partitions
    for dev in candidates:
        if not dev.partition_infos:
            return dev.device_info.path

    # Prefer first NVMe disk
    for dev in candidates:
        if 'nvme' in str(dev.device_info.path):
            return dev.device_info.path

    # No preference
    return None


def needs_kmscon(locale: str) -> bool:
    """Check if kmscon is needed for non-English locales (CJK console rendering)."""
    return locale != 'en_US.UTF-8'


def is_iso_environment() -> bool:
    """Check if running on the Arch ISO."""
    return Path('/run/archiso').exists()


def is_raw_tty() -> bool:
    """Check if running on a raw Linux TTY (no X/Wayland).

    Raw TTY cannot render CJK characters properly without kmscon.
    Returns True if TERM is 'linux' or stdin is /dev/tty[0-9]+.
    """
    if os.environ.get('TERM') == 'linux':
        return True
    try:
        tty_name = os.ttyname(0)
        if re.match(r'/dev/tty\d+', tty_name):
            return True
    except (OSError, AttributeError):
        pass
    return False


def cleanup_disk_locks() -> None:
    """Release disk locks: swap, LVM volume groups, LUKS containers.

    Must be called before filesystem operations to avoid 'Device busy' errors.
    """
    # Deactivate swap on all devices
    subprocess.run(['swapoff', '--all'], stderr=subprocess.DEVNULL, check=False)

    # Deactivate LVM volume groups (if lvm2 is available)
    try:
        subprocess.run(
            ['vgchange', '-an'], stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, check=False,
        )
    except FileNotFoundError:
        pass

    # Close LUKS containers
    try:
        dm_path = Path('/dev/mapper')
        if dm_path.exists():
            for dev in dm_path.iterdir():
                if dev.name == 'control':
                    continue
                subprocess.run(
                    ['cryptsetup', 'close', str(dev)],
                    stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, check=False,
                )
    except FileNotFoundError:
        pass
