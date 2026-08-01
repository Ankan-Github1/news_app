"""What every news source must return.

This file has no logic. It writes down a shape, so nothing downstream has to
know which service an article came from.

The problem it prevents: NewsAPI returns `{"source": {"name": "..."},
"publishedAt": ...}`. Read those keys directly in the pipeline and NewsAPI's
JSON layout is now baked into your business logic. Add Hacker News later — it
has neither key — and you either fake them or write a second code path through
the whole pipeline.

Normalising at the edge means one place changes per new source, and the pipeline
never learns that more than one source exists.

This is NOT a plugin system or a class hierarchy. A source is just a function:

    fetch(query, ...) -> list[FetchedArticle]

That's the entire contract. Abstract base classes and a registry would be real
over-engineering at one source; a dataclass and a docstring are not.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FetchedArticle:
    """One article, in this project's shape rather than any vendor's.

    frozen=True makes instances immutable — assigning to a field raises. Fetched
    data is a record of what a source said at a moment in time. If something
    downstream wants it different, that's a new object, not a quiet edit to
    shared state.

    Fields:
        url          canonical link. required — it's the dedup key.
        title        headline. required.
        description  short blurb. may be None.
        source       publisher name, e.g. "The Verge". may be None.
        published_at ISO 8601 UTC string. may be None if the source omits it.
    """

    url: str
    title: str
    description: str | None = None
    source: str | None = None
    published_at: str | None = None

    def embed_text(self):
        """The text used to represent this article in vector space.

        Title plus description, not the full body. Two reasons:

        Cost — embedding a 5,000-word article means fetching it first, which is
        the slowest step in the pipeline. Title and description arrive free with
        the search result.

        Quality — an embedding is one fixed-size vector no matter how much text
        goes in. Feed it a long article and everything it's about gets averaged
        into a blur. The headline is a human-written summary of the point, which
        is usually a sharper signal than the article's own average.
        """
        parts = [self.title, self.description]
        return " ".join(p for p in parts if p)
