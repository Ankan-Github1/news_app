"""Every tunable number, path and model name in the project.

Why one file: to answer "what are this system's settings?" you should read one
file, not grep for magic numbers. It's also the single place that reads
environment variables, so "what's different on the server?" has one answer.

Nothing here does work. Importing this file must stay cheap and side-effect free
apart from reading .env.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# --- storage -----------------------------------------------------------------
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "news.db"))

# --- sources -----------------------------------------------------------------
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
PAGE_SIZE = int(os.getenv("PAGE_SIZE", 30))
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", 7))

# --- embedding ---------------------------------------------------------------
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
EMBED_DIM = 384  # all-MiniLM-L6-v2. Changing the model changes this.

# --- ranking -----------------------------------------------------------------
# Rank, don't threshold. Cosine scores only compare within one batch, so a fixed
# cut-off means nothing once articles are fetched *for* a goal.
TOP_K = int(os.getenv("TOP_K", 8))
SCORE_FLOOR = float(os.getenv("SCORE_FLOOR", 0.15))  # safety net, not the mechanism

# --- llm ---------------------------------------------------------------------
# "ollama" | "gemini". Set LLM_BACKEND=gemini on a server that can't run torch.
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", 120))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Full articles can be enormous. Cap what reaches the model: cost and context
# limits both scale with input length, and the useful signal is near the top.
SUMMARY_INPUT_CHAR_LIMIT = int(os.getenv("SUMMARY_INPUT_CHAR_LIMIT", 12000))


def summary_model_name():
    """The model string stored alongside a cached summary.

    Summaries are cached by (article_id, goal_id, model_name). If the model
    changes, the key changes, and old summaries stay valid for the model that
    produced them instead of silently being served as if they were new.
    """
    return OLLAMA_MODEL if LLM_BACKEND == "ollama" else GEMINI_MODEL
