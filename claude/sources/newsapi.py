"""NewsAPI, normalised into FetchedArticle.

The only file in the project that knows what NewsAPI's JSON looks like.
"""

from newsapi import NewsApiClient

from config import LOOKBACK_DAYS, NEWS_API_KEY, PAGE_SIZE
from sources.base import FetchedArticle
from util.dates import lookback_window

NAME = "newsapi"


def _client():
    """Build a client, failing clearly if the key is missing.

    Built per call rather than once at import. Constructing it is free — no
    network happens here — but it raises when the key is absent, and an
    exception at import time cannot be caught by anything: it kills the process
    before your code runs. On a server that means the site is down because an
    environment variable is missing, with a traceback pointing at an import.

    Same reason the fetch below is a function and not module-level code. If a
    network call sits at module level it fires on import — every server start,
    every autoreload — burning free-tier quota nobody asked to spend, and taking
    the whole process down if it fails.
    """
    if not NEWS_API_KEY:
        raise RuntimeError("NEWS_API_KEY is not set. Add it to .env or the environment.")
    return NewsApiClient(api_key=NEWS_API_KEY)


def fetch(query, page_size=PAGE_SIZE, days=LOOKBACK_DAYS, language="en"):
    """Search NewsAPI and return FetchedArticles, newest first.

    `query` comes from a goal, so each goal pulls news about its own subject
    instead of everything scoring against one shared pool.

    Returns [] rather than raising when the search simply found nothing — an
    empty result is an answer, not a failure. A bad key or a dead network still
    raises, because those need fixing rather than handling.
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")

    from_date, to_date = lookback_window(days)

    response = _client().get_everything(
        q=query,
        from_param=from_date,
        to=to_date,
        language=language,
        page_size=page_size,
        sort_by="publishedAt",
    )

    return [_normalise(raw) for raw in response.get("articles", []) if raw.get("url")]


def _normalise(raw):
    """One NewsAPI dict -> one FetchedArticle. The vendor shape stops here.

    NewsAPI marks removed articles with the literal string "[Removed]" in every
    field. That is a sentinel — a normal-looking value that actually means
    "no value". Left alone it gets stored, embedded and summarised as though it
    were an article, so it's converted to None here, at the edge.
    """
    return FetchedArticle(
        url=raw["url"],
        title=_clean(raw.get("title")),
        description=_clean(raw.get("description")),
        source=_clean((raw.get("source") or {}).get("name")),
        published_at=raw.get("publishedAt"),
    )


def _clean(value):
    """NewsAPI's placeholders and blanks become None."""
    if not value or value == "[Removed]":
        return None
    return value.strip()
