"""Turning text into vectors, and comparing them.

Sits at the top level rather than under storage/ or llm/ because it belongs to
neither: storage/embeddings.py caches vectors without knowing how they're made,
and llm/ talks to generative models, which this isn't.
"""

import numpy as np

from config import EMBED_MODEL
from storage import embeddings as cache

_model = None


def _get_model():
    """Load the sentence-transformers model once, on first use.

    Loading pulls ~90MB off disk and initialises torch — one to three seconds,
    and hundreds of MB of RAM. Doing that at import time means every process
    that touches this module pays it, including a web server that may only ever
    serve cached vectors and never embed anything.

    Caching it in a module-level variable means the cost is paid at most once
    per process. This pattern is called *lazy loading*: do expensive setup when
    something actually needs it, not when the file is read.

    The import is inside the function for the same reason — `import
    sentence_transformers` alone costs about a second of torch initialisation.
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def embed(text):
    """Vector for `text`, from cache if possible.

    Two layers of caching, and they do different jobs:
      - the DB cache survives restarts and is shared between the pipeline and
        the web app
      - the loaded model avoids re-reading 90MB on every call within a process

    Returns float32 to match what's stored, so a cache hit and a cache miss give
    you an identical array. A function whose return type depends on whether a
    cache was warm is a bug waiting to happen.
    """
    hit = cache.get(text, EMBED_MODEL)
    if hit is not None:
        return hit

    vector = _get_model().encode(text).astype(np.float32)
    cache.save(text, vector, EMBED_MODEL)
    return vector


def embed_many(texts):
    """Vectors for several texts, computing only the misses — in one batch.

    Encoding 30 texts together is much faster than 30 separate calls: the model
    processes them as one matrix instead of paying per-call overhead thirty
    times. On CPU this is often 3-5x.

    Order is preserved, so result[i] belongs to texts[i].
    """
    results = [cache.get(t, EMBED_MODEL) for t in texts]
    missing = [i for i, vec in enumerate(results) if vec is None]

    if missing:
        fresh = _get_model().encode([texts[i] for i in missing])
        for i, vector in zip(missing, fresh):
            vector = vector.astype(np.float32)
            cache.save(texts[i], vector, EMBED_MODEL)
            results[i] = vector

    return results


def cosine_similarity(a, b):
    """How aligned two vectors are: 1.0 identical direction, 0.0 unrelated.

    Cosine measures the ANGLE between vectors and ignores their length. That
    matters here because a long article and a short headline about the same
    subject point the same way but have different magnitudes — you want them to
    score as similar, and plain dot product wouldn't.

    The number is only meaningful *within one comparison set*. 0.31 is not
    "relevant"; it's "0.31 compared to whatever else is in this batch". Which is
    exactly why this project ranks instead of thresholding.
    """
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator == 0:
        # A zero vector has no direction, so the angle is undefined. Return 0.0
        # rather than letting numpy emit a nan that quietly poisons a sort.
        return 0.0
    return float(np.dot(a, b) / denominator)
