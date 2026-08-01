"""Reads and writes for the goals table.

Goals are append-only. Editing a goal's text does not UPDATE the row — it
inserts a new row and points the old one at it via superseded_by.

Why: every similarity score and every summary references a goal_id. If you edit
the text in place, those old rows now claim to be scored against text that was
never used to produce them. The scores become quietly wrong, with nothing to
show that anything happened. Appending keeps (text, embedding, score) consistent
forever, at the cost of some dead rows nobody reads.
"""

from storage.db import connect
from util.dates import utc_now_iso


def insert(text, query=None, owner_token=None):
    """Create a goal. Returns its id.

    `query` is the search string extracted from the goal text — "be good at
    table tennis and impress the aunties" becomes "table tennis". Stored rather
    than recomputed because extraction costs an LLM call, and because you want
    to see what it actually decided when results look wrong.
    """
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO goals (text, query, owner_token, created_at) VALUES (?, ?, ?, ?)",
            (text, query, owner_token, utc_now_iso()),
        )
        return cur.lastrowid


def get(goal_id):
    """One goal row by id, or None."""
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()


def active():
    """Every goal that hasn't been superseded."""
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM goals WHERE superseded_by IS NULL ORDER BY created_at DESC"
        ).fetchall()


def for_owner(owner_token):
    """This visitor's live goals, newest first.

    This is what makes the app feel personal without a login: the cookie names
    the owner, and the owner names the goals. Every page is scoped through here.

    A None token would match rows where owner_token IS NULL — the seeded demo
    goals — via a different SQL operator, and `= ?` never matches NULL anyway.
    Refusing to answer is safer than silently returning nothing or everything.
    """
    if not owner_token:
        raise ValueError("owner_token is required; use active() for all goals")

    with connect() as conn:
        return conn.execute(
            """
            SELECT * FROM goals
            WHERE owner_token = ? AND superseded_by IS NULL
            ORDER BY created_at DESC
            """,
            (owner_token,),
        ).fetchall()


def owns(goal_id, owner_token):
    """Does this visitor own this goal?

    Called before rendering a goal page. Without it, /goal/12 shows goal 12 to
    anyone who types the URL — fine for a demo, not fine the moment the content
    is worth hiding. Cheap to have now, awkward to retrofit later.
    """
    goal = get(goal_id)
    return goal is not None and goal["owner_token"] == owner_token


def supersede(old_goal_id, new_text, query=None, owner_token=None):
    """Replace a goal's text by appending a new row and linking the old one.

    Both statements share one connection, so they're atomic: either the new goal
    exists AND the old one points at it, or neither happened. A crash between
    them would otherwise leave a new goal nobody references and an old goal
    still presenting itself as current.
    """
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO goals (text, query, owner_token, created_at) VALUES (?, ?, ?, ?)",
            (new_text, query, owner_token, utc_now_iso()),
        )
        new_goal_id = cur.lastrowid
        conn.execute(
            "UPDATE goals SET superseded_by = ? WHERE id = ?",
            (new_goal_id, old_goal_id),
        )
        return new_goal_id
