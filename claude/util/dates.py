"""Timestamps and date windows.

One rule, applied everywhere: times are UTC, stored as ISO 8601 strings.

Why UTC: a server in Frankfurt, a phone in Kolkata and a laptop in between must
agree on what "yesterday" means. Local time makes that a guessing game.

Why ISO strings in SQLite: SQLite has no datetime type. ISO 8601 sorts correctly
as plain text, so ORDER BY published_at works without parsing anything.
"""

from datetime import datetime, timedelta, timezone


def utc_now():
    """Timezone-aware current time. Never use datetime.now() — it's naive."""
    return datetime.now(timezone.utc)


def utc_now_iso():
    """Current UTC time as an ISO 8601 string, for storing."""
    return utc_now().isoformat()


def lookback_window(days):
    """(from_date, to_date) as YYYY-MM-DD strings, for news API date filters.

    Returns dates rather than timestamps because most news APIs take whole days.
    """
    today = utc_now().date()
    start = today - timedelta(days=days)
    return start.isoformat(), today.isoformat()


def iso_days_ago(days):
    """Full ISO timestamp for N days ago. For SQL comparisons against stored
    ISO strings, where string comparison and time comparison agree."""
    return (utc_now() - timedelta(days=days)).isoformat()
