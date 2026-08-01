"""Text hashing and trimming."""

import hashlib


def hash_text(text):
    """sha256 of a string. The cache key for embeddings.

    The property that makes the whole embedding cache work: same text always
    gives the same hash, and any change to the text gives a different one. So a
    goal whose wording changes automatically misses the cache and gets a fresh
    vector. No invalidation logic to write, and none to get wrong.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clip(text, limit):
    """Trim text to `limit` characters, ending on a word boundary where possible.

    Cutting mid-word gives the model a fragment like 'the announcem' which reads
    as corruption. Backing up to the last space is nearly free and avoids it.
    """
    if text is None or len(text) <= limit:
        return text

    cut = text[:limit]
    last_space = cut.rfind(" ")
    # Only honour the word boundary if it isn't absurdly far back — a text with
    # no spaces in 12k characters shouldn't collapse to nothing.
    if last_space > limit * 0.9:
        cut = cut[:last_space]
    return cut.rstrip()
