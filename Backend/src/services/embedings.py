from sentence_transformers import SentenceTransformer
from sentence_transformers import util

from src.storage.db import get_embedding, save_embedding

EMBED_MODEL_NAME = 'all-MiniLM-L6-v2'
model = SentenceTransformer(EMBED_MODEL_NAME)  # downloads once, ~80MB

def embed(text):
    return model.encode(text).tolist()

def embed_many(texts):
    return model.encode(texts).tolist()

def cosine_similarity(vec1, vec2):
    score = util.cos_sim(vec1, vec2).item()
    return score

def get_or_compute_embedding(text, model_name):
    """Return the vector for `text` under EMBED_MODEL_NAME. Cache hit → returned as-is; miss → compute, cache, return.
    Returns a float32 numpy array on both paths."""
    cached = get_embedding(text, model_name)
    if cached is not None:
        return cached
    vector = model.encode([text])[0]
    save_embedding(text, vector, model_name)
    return vector