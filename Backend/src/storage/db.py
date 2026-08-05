import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from src.utils.url_help import hash_url
from src.utils.embeding_help import hash_text

DB_PATH = Path("news.db")


def _connect():
    """Open a SQLite connection with foreign-key enforcement enabled.
    SQLite doesn't enforce FK constraints by default; without this pragma they're decorative."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            url_hash TEXT NOT NULL UNIQUE,
            title TEXT,
            description TEXT,
            content TEXT,
            source TEXT,
            published_at TEXT,
            fetched_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            text_hash TEXT NOT NULL,
            model_name TEXT NOT NULL,
            vector BLOB NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (text_hash, model_name)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            superseded_by INTEGER,
            FOREIGN KEY (superseded_by) REFERENCES goals(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS similarity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            goal_id INTEGER NOT NULL,
            score REAL NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (article_id, goal_id),
            FOREIGN KEY (article_id) REFERENCES articles(id),
            FOREIGN KEY (goal_id) REFERENCES goals(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            goal_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (article_id, goal_id, model_name),
            FOREIGN KEY (article_id) REFERENCES articles(id),
            FOREIGN KEY (goal_id) REFERENCES goals(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            goal_id INTEGER NOT NULL,
            is_relevant INTEGER NOT NULL CHECK (is_relevant IN (0, 1)),
            created_at TEXT NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles(id),
            FOREIGN KEY (goal_id) REFERENCES goals(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watched (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            goal_id INTEGER NOT NULL,
            is_watched INTEGER NOT NULL CHECK (is_watched IN (0, 1)),
            created_at TEXT NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles(id),
            FOREIGN KEY (goal_id) REFERENCES goals(id)
        )
    """)
    conn.commit()
    conn.close()


def insert_article(url, title, description, source, published_at):
    """Insert an article. Returns the new article_id, or None if it already existed."""
    conn = _connect()
    fetched_at = datetime.now(timezone.utc).isoformat()
    url_hash = hash_url(url)
    try:
        cur = conn.execute("""
            INSERT INTO articles (url, url_hash, title, description, source, published_at, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (url, url_hash, title, description, source, published_at, fetched_at))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def update_article_content(url, content):
    """Fill in the full article text for an already-inserted article. Returns True if a row was updated, False if no row matched."""
    url_hash = hash_url(url)
    conn = _connect()
    try:
        cur = conn.execute("""
            UPDATE articles SET content = ? WHERE url_hash = ?
        """, (content, url_hash))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_article_content(url):
    """Return stored content for an article, or None if the article isn't stored or its content is NULL."""
    url_hash = hash_url(url)
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT content FROM articles WHERE url_hash = ?",
            (url_hash,),
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def get_article_id(url):
    """Return the id of an already-stored article, or None if the url isn't in the table."""
    url_hash = hash_url(url)
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id FROM articles WHERE url_hash = ?",
            (url_hash,),
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def get_embedding(text, model_name):
    """Return cached float32 vector for (text, model_name), or None on cache miss."""
    text_hash = hash_text(text)
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT vector FROM embeddings WHERE text_hash = ? AND model_name = ?",
            (text_hash, model_name),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return np.frombuffer(row[0], dtype=np.float32)


def save_embedding(text, vector, model_name):
    """Cache a vector. Idempotent: re-saving the same (text, model_name) is a no-op."""
    text_hash = hash_text(text)
    created_at = datetime.now(timezone.utc).isoformat()
    blob = vector.astype(np.float32).tobytes()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO embeddings (text_hash, model_name, vector, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (text_hash, model_name, blob, created_at),
        )
        conn.commit()
    finally:
        conn.close()


def insert_goal(text):
    """Insert a new goal. Returns the new goal_id."""
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO goals (text) VALUES (?)",
            (text,),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_active_goals():
    """Return [(goal_id, text), ...] for goals that have not been superseded."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, text FROM goals WHERE superseded_by IS NULL"
        ).fetchall()
    finally:
        conn.close()
    return rows


def insert_similarity(article_id, goal_id, score):
    """Store a (article, goal) similarity score. Returns True if newly inserted, False if the pair already had a score."""
    conn = _connect()
    created_at = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            """
            INSERT INTO similarity (article_id, goal_id, score, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (article_id, goal_id, score, created_at),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_summary(article_id, goal_id, model_name):
    """Return cached summary text for (article_id, goal_id, model_name), or None on cache miss."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT summary FROM summaries WHERE article_id = ? AND goal_id = ? AND model_name = ?",
            (article_id, goal_id, model_name),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return row[0]


def insert_summary(article_id, goal_id, model_name, summary):
    """Cache a summary. Idempotent: re-saving the same (article_id, goal_id, model_name) is a no-op."""
    conn = _connect()
    created_at = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO summaries (article_id, goal_id, model_name, summary, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (article_id, goal_id, model_name, summary, created_at),
        )
        conn.commit()
    finally:
        conn.close()


def get_pending_summary_pairs(threshold=0.28):
    """Return [(article_id, goal_id, score), ...] for pairs scoring above `threshold` that have no summary yet — i.e., retry candidates."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT s.article_id, s.goal_id, s.score
            FROM similarity s
            LEFT JOIN summaries sum
                ON sum.article_id = s.article_id
                AND sum.goal_id   = s.goal_id
            WHERE s.score >= ? AND sum.id IS NULL
            """,
            (threshold,),
        ).fetchall()
    finally:
        conn.close()
    return rows


def clear_pipeline_data():
    """Delete all rows from articles, embeddings, similarity, summaries. Goals are preserved; schemas are untouched.
    Dev utility for wiping pipeline state without rebuilding the DB."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM summaries")
        conn.execute("DELETE FROM similarity")
        conn.execute("DELETE FROM articles")
        conn.execute("DELETE FROM embeddings")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    insert_article(
        url="https://example.com/test-article",
        title="Test Article",
        description="A test description",
        source="test-source",
        published_at="2026-04-30T12:00:00Z",
    )
