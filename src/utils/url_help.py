import hashlib
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

TRACKING_PARAMS = {
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src",    #gotta look here
}

def normalize_url(url: str) -> str:
    parsed = urlparse(url)

    scheme = "https"

    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    query_pairs = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    query = urlencode(query_pairs)

    fragment = ""

    return urlunparse((scheme, netloc, parsed.path, parsed.params, query, fragment))

def hash_url(url: str) -> str:
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

if __name__ == "__main__":
    test_urls = [
        "https://example.com/article",
        "https://www.example.com/article",
        "http://example.com/article",
        "https://example.com/article?utm_source=twitter&utm_medium=social",
        "https://example.com/article#section3",
        "https://EXAMPLE.com/article?fbclid=abc123",
    ]
    for u in test_urls:
        print(f"{u}\n  → {normalize_url(u)}\n  → {hash_url(u)[:16]}...\n")
