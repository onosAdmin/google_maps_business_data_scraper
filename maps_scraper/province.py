"""
Fetch the list of villages (comuni) for an Italian province
from visureinrete.it.
"""

import re
from typing import List

import requests


_URL_TEMPLATE = (
    "https://www.visureinrete.it/anagrafe/anagrafe_provincia.asp?P={province}"
)

# Matches: <li class="regione"><a href="...">Village Name</a></li>
_VILLAGE_RE = re.compile(
    r'<li\s+class="regione">\s*<a\s+href="[^"]*">([^<]+)</a>', re.IGNORECASE
)


def fetch_villages(province: str, timeout: int = 15) -> List[str]:
    """Fetch village names for an Italian province.

    Args:
        province: Province name as it appears on the site (e.g. "Vicenza", "Verona").
        timeout: HTTP request timeout in seconds.

    Returns:
        Sorted list of village names.

    Raises:
        RuntimeError: If the page cannot be fetched or contains no villages.
    """
    url = _URL_TEMPLATE.format(province=province)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()

    # The page is encoded as iso-8859-1
    resp.encoding = "iso-8859-1"
    html = resp.text

    villages = _VILLAGE_RE.findall(html)

    if not villages:
        raise RuntimeError(
            f"No villages found for province '{province}'. "
            f"Check the spelling matches the site: {url}"
        )

    # Clean up HTML entities (e.g. &#232; -> è)
    import html as html_mod

    villages = [html_mod.unescape(v.strip()) for v in villages]

    return villages
