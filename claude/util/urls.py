"""URL normalisation and hashing, for deduplication.

The problem: the same article reaches you as several different strings.

    https://site.com/story?utm_source=twitter
    http://www.site.com/story#comments
    https://SITE.com/story

Three strings, one article. Compare raw URLs and you store it three times.
Normalise first, hash the result, and the three collapse into one key.
"""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Params that identify *how you arrived*, not *what you're looking at*.
# Two URLs differing only in these point at the same article.
TRACKING_PARAMS = {
    "fbclid", "gclid", "dclid", "msclkid", "igshid", "twclid",
    "mc_cid", "mc_eid",
    "ref", "ref_src", "referrer", "source",
    "cmpid", "campaign_id", "at_medium", "at_campaign",
    "spm", "_hsenc", "_hsmi", "vero_id", "yclid", "wt_zmc",
}

# Whole families of params. Prefix match catches utm_source, utm_medium, and
# every utm_* someone invents next year without editing this file.
TRACKING_PREFIXES = ("utm_", "pk_", "piwik_", "matomo_", "hsa_")


def _is_tracking(key):
    lowered = key.lower()
    return lowered in TRACKING_PARAMS or lowered.startswith(TRACKING_PREFIXES)


def normalize_url(url):
    """Reduce a URL to a canonical form for comparison.

    Rules, and why each one:
      - force https      : http:// and https:// serve the same article
      - lowercase host   : hostnames are case-insensitive, paths are NOT
      - strip www.       : www.site.com and site.com are the same site
      - drop fragment    : #comments is a position on a page, not a page
      - drop tracking    : see TRACKING_PARAMS
      - sort remaining   : ?a=1&b=2 and ?b=2&a=1 are the same request
      - strip trailing / : /story and /story/ are the same article

    Deliberately NOT done: lowercasing the path. Plenty of sites serve
    different content from /Story and /story, so folding them would merge two
    real articles into one — a much worse failure than storing a duplicate.
    """
    parts = urlsplit(url.strip())

    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not _is_tracking(k)]
    query = urlencode(sorted(kept))

    path = parts.path.rstrip("/") or "/"

    return urlunsplit(("https", host, path, query, ""))


def hash_url(url):
    """sha256 of the normalised URL. This is the dedup key.

    Why hash instead of storing the URL and comparing strings: fixed length
    (indexes stay small and fast), and it's a clean UNIQUE column regardless of
    how long or strange the original URL was.
    """
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()
