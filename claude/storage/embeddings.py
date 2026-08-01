"""The vector cache.

Embedding text is the slowest CPU work in the pipeline. The same goal text gets
embedded on every run, and the same article appears under several goals. Caching
turns all of that into one lookup.

The key is (sha256(text), model_name):
  - hashing the text means identical text always hits, and any edit
    automatically misses. There is no invalidation code, so there is no
    invalidation bug.
  - including the model name means swapping models can never serve you vectors
    produced by the old one. Different models put text in different spaces;
    comparing across them gives numbers that look fine and mean nothing.
"""

import numpy as np

from storage.db import connect
from util.dates import utc_now_iso
from util.text import hash_text


def get(text, model_name):
    """Cached vector as float32, or None on a miss.

    Vectors are stored as raw BLOBs, not JSON. 384 floats as JSON is ~4KB of
    text that must be parsed on every read; as float32 bytes it's 1536 bytes
    copied straight into a numpy array. Roughly 3x smaller and far faster.

    float32 rather than float64 halves the size again. The precision lost is far
    below anything that changes a ranking.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT vector FROM embeddings WHERE text_hash = ? AND model_name = ?",
            (hash_text(text), model_name),
        ).fetchone()

    if row is None:
        return None
    return np.frombuffer(row["vector"], dtype=np.float32)


def save(text, vector, model_name):
    """Cache a vector. Re-saving the same key is a no-op.

    INSERT OR IGNORE makes this *idempotent* — calling it twice has the same
    effect as calling it once. Two runs racing to embed the same text both
    succeed instead of one crashing on a duplicate key.
    """
    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO embeddings (text_hash, model_name, vector, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (hash_text(text), model_name,
             vector.astype(np.float32).tobytes(), utc_now_iso()),
        )
