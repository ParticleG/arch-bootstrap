from __future__ import annotations

from pathlib import Path

from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.models.mirrors import CustomServer, MirrorConfiguration, MirrorRegion

from .constants import COUNTRY_NAMES, FALLBACK_MIRRORS


# =============================================================================
# Mirror resolution helpers
# =============================================================================

def resolve_mirror_regions(
    country: str | None,
    handler: MirrorListHandler,
) -> list[MirrorRegion]:
    """Return MirrorRegion objects ONLY if handler has online data.
    Returns empty list if no online data available for the country.
    """
    if country and country in COUNTRY_NAMES:
        region_name = COUNTRY_NAMES[country]
        regions = handler.get_mirror_regions()
        matching = [r for r in regions if r.name == region_name]
        if matching:
            return matching
    return []


def get_fallback_servers(country: str | None) -> list[CustomServer]:
    """Build CustomServer list from FALLBACK_MIRRORS for a country.
    Falls back to 'Worldwide' if country not in FALLBACK_MIRRORS.
    """
    key = country if country and country in FALLBACK_MIRRORS else 'Worldwide'
    urls = FALLBACK_MIRRORS.get(key, FALLBACK_MIRRORS['Worldwide'])
    return [CustomServer(url=url) for url in urls]


def build_mirror_config(
    country: str | None,
    handler: MirrorListHandler,
) -> MirrorConfiguration:
    """Build MirrorConfiguration with proper fallback handling.

    Strategy:
    - If handler has online data for country -> use MirrorRegion (regions_config works)
    - If handler has no data -> use CustomServer entries (bypasses regions_config entirely)
    """
    regions = resolve_mirror_regions(country, handler)
    if regions:
        return MirrorConfiguration(mirror_regions=regions)

    # No online data: use fallback as custom servers
    servers = get_fallback_servers(country)
    return MirrorConfiguration(custom_servers=servers)


def apply_mirrors_to_live_iso(
    country: str | None,
    handler: MirrorListHandler,
) -> int:
    """Apply mirrors to live ISO's /etc/pacman.d/mirrorlist.

    Uses speed_sort=False (archlinux.org score-sorted data is sufficient
    for the interactive wizard; full speed testing happens at install time
    via set_mirrors which hardcodes speed_sort=True).

    Returns number of servers written, or 0 if not in ISO environment.
    """
    from .detection import is_iso_environment

    if not is_iso_environment():
        return 0

    mirrorlist = Path('/etc/pacman.d/mirrorlist')
    config = build_mirror_config(country, handler)

    # Build mirrorlist content without speed testing
    parts: list[str] = []

    # Custom servers first (fallback mirrors)
    custom = config.custom_servers_config()
    if custom:
        parts.append(custom)

    # Region servers (score-sorted, no speed test)
    if config.mirror_regions:
        regions = config.regions_config(handler, speed_sort=False)
        if regions.strip():
            parts.append(regions)

    content = '\n\n'.join(parts)
    if not content.strip():
        return 0

    mirrorlist.write_text(content + '\n')

    # Count Server = lines
    return content.count('Server = ')
