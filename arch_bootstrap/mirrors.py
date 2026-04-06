from __future__ import annotations

from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.models.mirrors import MirrorRegion

from .constants import COUNTRY_NAMES, FALLBACK_MIRRORS


# =============================================================================
# Mirror resolution helper
# =============================================================================

def resolve_mirror_regions(
    country: str | None,
    mirror_list_handler: MirrorListHandler,
) -> list[MirrorRegion]:
    """Resolve mirror regions for a country, with fallback to hardcoded pools.

    1. Try MirrorListHandler's online data (reflector-backed).
    2. Fall back to FALLBACK_MIRRORS for the country.
    3. Fall back to FALLBACK_MIRRORS['Worldwide'].
    """
    if country and country in COUNTRY_NAMES:
        region_name = COUNTRY_NAMES[country]
        regions = mirror_list_handler.get_mirror_regions()
        matching = [r for r in regions if r.name == region_name]
        if matching:
            return matching

    # Fallback to hardcoded mirrors
    country_key = country if country and country in FALLBACK_MIRRORS else 'Worldwide'
    urls = FALLBACK_MIRRORS.get(country_key, FALLBACK_MIRRORS['Worldwide'])
    region_name = COUNTRY_NAMES.get(country, 'Worldwide') if country else 'Worldwide'
    return [MirrorRegion(name=region_name, urls=urls)]
