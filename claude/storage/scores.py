"""Similarity scores and cached summaries — the derived data.

Both tables hang off (article_id, goal_id). Together they answer the only
question the web layer ever asks: "what should this goal's page show?"
"""

import sqlite3

from storage.db import connect
from util.dates import iso_days_ago, utc_now_iso


# --- similarity --------------------------------------------------------------

def record_score(article_id, goal_id, score):
    """Store one (article, goal) score. True if new, False if already scored.

    Every score gets written, not just good ones. Two reasons:
      - the near-misses section needs them
      - you cannot tune ranking on data you threw away. Keeping the whole
        distribution is what lets you look back and ask whether a floor of 0.15
        is sane, instead of guessing.
    """
    with connect() as conn:
        try:
            conn.execute(
                "INSERT INTO similarity (article_id, goal_id, score, created_at) VALUES (?, ?, ?, ?)",
                (article_id, goal_id, score, utc_now_iso()),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def record_scores(pairs):
    """Store many scores in one transaction. `pairs` is [(article_id, goal_id, score), ...].

    One connection and one commit for the whole batch instead of one per row.
    Each commit is a disk flush, so 30 separate calls means 30 flushes; this is
    the difference between "instant" and "noticeably slow" at a few hundred rows.

    INSERT OR IGNORE rather than a try/except, because in a batch a duplicate is
    routine and shouldn't abort the other 29 rows.
    """
    now = utc_now_iso()
    with connect() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO similarity (article_id, goal_id, score, created_at)
            VALUES (?, ?, ?, ?)
            """,
            [(a, g, s, now) for a, g, s in pairs],
        )


def scored_article_ids(goal_id):
    """Every article already scored against this goal, as a set.

    Lets a caller skip work it has already done, without a per-article query.
    One round trip, then membership checks in memory.
    """
    with connect() as conn:
        rows = conn.execute(
            "SELECT article_id FROM similarity WHERE goal_id = ?", (goal_id,)
        ).fetchall()
    return {row["article_id"] for row in rows}


# --- the page query ----------------------------------------------------------

def top_for_goal(goal_id, model_name, limit, floor, days=None):
    """The goal page, in one query: best articles with their summaries.

    Returns rows with the article columns plus `score` and `summary`.

    Three things worth reading in the SQL below:

    LEFT JOIN on summaries, not JOIN. A plain JOIN drops any article that has no
    summary yet — so a page rendered mid-run would silently hide its own best
    results. LEFT JOIN keeps the article and leaves summary as NULL, which the
    template can render as "summary on the way".

    ORDER BY score DESC + LIMIT is the ranking. No threshold in the WHERE clause
    beyond a low floor: cosine scores are only comparable within one batch, so
    "top 8" is a question the data can answer and "above 0.28" isn't.

    The floor is a safety net, not the mechanism. If genuinely nothing matches,
    better to show three weak results than eight irrelevant ones.
    """
    sql = """
        SELECT a.*, s.score, sm.summary
        FROM similarity s
        JOIN articles a
            ON a.id = s.article_id
        LEFT JOIN summaries sm
            ON sm.article_id = s.article_id
           AND sm.goal_id    = s.goal_id
           AND sm.model_name = ?
        WHERE s.goal_id = ? AND s.score >= ?
    """
    params = [model_name, goal_id, floor]

    if days is not None:
        sql += " AND a.published_at >= ?"
        params.append(iso_days_ago(days))

    sql += " ORDER BY s.score DESC LIMIT ?"
    params.append(limit)

    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def near_misses(goal_id, limit, floor, ceiling):
    """Articles that scored below the cut — the "you might disagree" section.

    Worth showing: it's the only honest way to see what the ranking is throwing
    away, and it's where you notice the scoring is wrong.
    """
    with connect() as conn:
        return conn.execute(
            """
            SELECT a.*, s.score
            FROM similarity s
            JOIN articles a ON a.id = s.article_id
            WHERE s.goal_id = ? AND s.score >= ? AND s.score < ?
            ORDER BY s.score DESC
            LIMIT ?
            """,
            (goal_id, floor, ceiling, limit),
        ).fetchall()


# --- summaries ---------------------------------------------------------------

def get_summary(article_id, goal_id, model_name):
    """Cached summary, or None.

    Call this before asking the model for anything. A summary costs seconds and
    is deterministic enough to reuse; regenerating one you already have is the
    single most expensive mistake this pipeline can make.
    """
    with connect() as conn:
        row = conn.execute(
            """
            SELECT summary FROM summaries
            WHERE article_id = ? AND goal_id = ? AND model_name = ?
            """,
            (article_id, goal_id, model_name),
        ).fetchone()
    return row["summary"] if row else None


def save_summary(article_id, goal_id, model_name, summary):
    """Cache a summary. Idempotent.

    model_name is part of the key, so switching from llama3.1 to Gemini produces
    a fresh summary rather than serving the old model's work under the new one's
    name. It also means you can compare two models on the same article.
    """
    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO summaries
                (article_id, goal_id, model_name, summary, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (article_id, goal_id, model_name, summary, utc_now_iso()),
        )


def missing_summaries(goal_id, model_name, limit, floor):
    """Top-scoring pairs for this goal that have no summary yet.

    The retry list. If a summarisation run dies halfway, this is what's left to
    do — no bookkeeping table needed, because the absence of a row already says
    it. Derived state beats a status column you have to keep correct.
    """
    with connect() as conn:
        return conn.execute(
            """
            SELECT s.article_id, s.goal_id, s.score
            FROM similarity s
            LEFT JOIN summaries sm
                ON sm.article_id = s.article_id
               AND sm.goal_id    = s.goal_id
               AND sm.model_name = ?
            WHERE s.goal_id = ? AND s.score >= ? AND sm.id IS NULL
            ORDER BY s.score DESC
            LIMIT ?
            """,
            (model_name, goal_id, floor, limit),
        ).fetchall()
