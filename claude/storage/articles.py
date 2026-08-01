"""Reads and writes for the articles table.

No SQL exists outside storage/. Callers ask for articles; they never see a query.
"""

import sqlite3

from storage.db import connect
from util.dates import iso_days_ago, utc_now_iso
from util.urls import hash_url


def insert(url, title, description, source, published_at):
    """Store a new article. Returns its id, or None if it was already stored.

    Returning None rather than raising is a deliberate choice about what a
    duplicate *means*. A duplicate isn't an error here — it's the dedup working.
    The caller's normal path is "have I seen this?", so the answer belongs in
    the return value, not in an exception.

    Catching sqlite3.IntegrityError specifically (not Exception) matters: the
    UNIQUE violation on url_hash is the one failure with a recovery plan. A
    disk-full error or a missing table should still explode loudly.
    """
    with connect() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO articles
                    (url, url_hash, title, description, source, published_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (url, hash_url(url), title, description, source,
                 published_at, utc_now_iso()),
            )
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def upsert(url, title, description, source, published_at):
    """Store the article if new, and return its id either way.

    `insert()` answers "was this new?". This answers "what is its id?". Two
    different questions, so two functions rather than one with a flag.

    A caller that scores articles against a goal needs this one: an article
    already in the database still has to be scored against a goal it has never
    been compared to.
    """
    article_id = insert(url, title, description, source, published_at)
    if article_id is not None:
        return article_id
    return get_id(url)


def get_id(url):
    """The stored article's id, or None if it isn't stored.

    Queries url_hash, not url. Two reasons:
      - correctness: the caller's URL may carry tracking params the stored one
        doesn't. Matching on the raw string would miss it and you'd store a
        second copy of the same article.
      - speed: url_hash is UNIQUE, so SQLite has an index on it. url does not.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM articles WHERE url_hash = ?", (hash_url(url),)
        ).fetchone()
    return row["id"] if row else None


def get_content(url):
    """Stored full text, or None if absent or never fetched.

    Note that None is doing double duty: "no such article" and "article exists
    but has no content yet". The caller does the same thing in both cases — go
    fetch it — so collapsing them costs nothing and keeps the signature simple.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT content FROM articles WHERE url_hash = ?", (hash_url(url),)
        ).fetchone()
    return row["content"] if row else None


def set_content(url, content):
    """Fill in full text after a successful fetch. True if a row was updated.

    Never store a placeholder like "Error fetching content". It reads as real
    data downstream — it would be embedded, scored, and summarised as if it were
    an article. Store nothing and let None mean nothing.
    """
    with connect() as conn:
        cur = conn.execute(
            "UPDATE articles SET content = ? WHERE url_hash = ?",
            (content, hash_url(url)),
        )
        return cur.rowcount > 0


def get(article_id):
    """A whole article row by id, or None."""
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM articles WHERE id = ?", (article_id,)
        ).fetchone()


def recent(days):
    """Articles published within the last `days`, newest first.

    Used when a new goal needs scoring against what's already stored — score a
    recent window, not the entire table. At 20k articles, rescoring everything
    for each new goal stops being reasonable, and week-old news isn't what
    anyone wants anyway.
    """
    with connect() as conn:
        return conn.execute(
            """
            SELECT * FROM articles
            WHERE published_at >= ?
            ORDER BY published_at DESC
            """,
            (iso_days_ago(days),),
        ).fetchall()
