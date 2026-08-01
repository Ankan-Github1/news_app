"""Connection handling and schema. Nothing in here knows what an article is.

This file is the only place that opens a SQLite connection. Every other storage
module borrows one from `connect()`. Keeping that in one place means the two
easy-to-forget things — foreign keys and closing the connection — are impossible
to forget.
"""

import sqlite3
from contextlib import contextmanager

from config import DB_PATH


@contextmanager
def connect():
    """Open a connection, commit on success, roll back on failure, always close.

    A *context manager* is an object you use with `with`. Python guarantees the
    cleanup half runs no matter how the block exits — normally, by `return`, or
    by an exception.

        with connect() as conn:
            conn.execute("INSERT ...")
        # committed and closed here, even if the insert raised

    Why this beats a plain open/close pair in every function:

      1. It cannot leak. Compare the manual version:

             conn = sqlite3.connect(DB_PATH)   # line 1
             rows = conn.execute(...)          # line 2 raises
             conn.close()                      # never runs

         The connection stays open until the garbage collector notices. Do that
         in a web server under load and you run out of file handles.

      2. Multi-statement writes become atomic. Two inserts in one `with` block
         either both land or neither does. Without it, a crash between them
         leaves the database half-updated — a row with no matching row.

      3. PRAGMA foreign_keys is applied every time. SQLite defaults it OFF, and
         it is per-connection, not per-database. Forget it once and every
         declared FOREIGN KEY on that connection is decorative.

    The broad `except Exception` here is deliberate and is not the "swallowing
    errors" anti-pattern: it does not silence anything. It performs a recovery
    action (rollback) and re-raises, so the traceback is unchanged.
    """
    conn = sqlite3.connect(DB_PATH)
    # Rows come back as objects you index by column name: row["title"] instead
    # of row[3]. Positional access breaks silently the day someone reorders a
    # SELECT; name access doesn't.
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS articles (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        url          TEXT NOT NULL,
        url_hash     TEXT NOT NULL UNIQUE,
        title        TEXT,
        description  TEXT,
        content      TEXT,
        source       TEXT,
        published_at TEXT,
        fetched_at   TEXT NOT NULL
    )
    """,
    # owner_token: identity without a login. A random string in a visitor's
    # cookie. Nullable, because seeded demo goals belong to nobody.
    """
    CREATE TABLE IF NOT EXISTS goals (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        text          TEXT NOT NULL,
        query         TEXT,
        owner_token   TEXT,
        superseded_by INTEGER,
        created_at    TEXT NOT NULL,
        FOREIGN KEY (superseded_by) REFERENCES goals(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS embeddings (
        text_hash  TEXT NOT NULL,
        model_name TEXT NOT NULL,
        vector     BLOB NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (text_hash, model_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS similarity (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER NOT NULL,
        goal_id    INTEGER NOT NULL,
        score      REAL NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (article_id, goal_id),
        FOREIGN KEY (article_id) REFERENCES articles(id),
        FOREIGN KEY (goal_id)    REFERENCES goals(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS summaries (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER NOT NULL,
        goal_id    INTEGER NOT NULL,
        model_name TEXT NOT NULL,
        summary    TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (article_id, goal_id, model_name),
        FOREIGN KEY (article_id) REFERENCES articles(id),
        FOREIGN KEY (goal_id)    REFERENCES goals(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS interactions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id  INTEGER NOT NULL,
        goal_id     INTEGER NOT NULL,
        is_relevant INTEGER NOT NULL CHECK (is_relevant IN (0, 1)),
        created_at  TEXT NOT NULL,
        FOREIGN KEY (article_id) REFERENCES articles(id),
        FOREIGN KEY (goal_id)    REFERENCES goals(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watched (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER NOT NULL,
        goal_id    INTEGER NOT NULL,
        is_watched INTEGER NOT NULL CHECK (is_watched IN (0, 1)),
        created_at TEXT NOT NULL,
        FOREIGN KEY (article_id) REFERENCES articles(id),
        FOREIGN KEY (goal_id)    REFERENCES goals(id)
    )
    """,
]

# Indexes are separate from table creation because they answer a different
# question: not "what shape is the data" but "which lookups must be fast".
#
# Every one of these exists because a real query needs it. An index you don't
# query is not free — it costs disk and slows every write that touches the table.
INDEXES = [
    # "the best articles for this goal" — the main page query
    "CREATE INDEX IF NOT EXISTS idx_similarity_goal_score ON similarity(goal_id, score DESC)",
    # "which goals belong to this visitor"
    "CREATE INDEX IF NOT EXISTS idx_goals_owner ON goals(owner_token)",
    # "recent articles first"
    "CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC)",
]


def init_db():
    """Create tables and indexes if they don't exist. Safe to call repeatedly.

    Every statement is IF NOT EXISTS, which makes this *idempotent*: running it
    once and running it ten times leave the database in the same state. That's
    what lets it sit at the top of an entry point without a "have I already set
    up?" flag to get wrong.

    What this does NOT handle: changing an existing table. Adding a column to a
    live table needs a migration, not CREATE TABLE IF NOT EXISTS — the create is
    skipped and the new column silently never appears.
    """
    with connect() as conn:
        for statement in SCHEMA + INDEXES:
            conn.execute(statement)
