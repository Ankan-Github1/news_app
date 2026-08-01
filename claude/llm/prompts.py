"""What to say to the model.

Separate from client.py because these change at completely different speeds.
You will edit this file fifty times while tuning and client.py roughly twice.
Files that change together belong together; files that don't, don't.

Each prompt is a function rather than a template string, so the caller can't
forget a variable — a missing argument is a TypeError at the call, not a prompt
containing the literal text "{goal}" sent to a model that will cheerfully
answer it anyway.
"""

from config import SUMMARY_INPUT_CHAR_LIMIT
from util.text import clip


def extract_query(goal_text):
    """Turn a goal in someone's own words into a news search query.

    "be good table tennis player and impress aunties in the TT court in my
    apartment" -> "table tennis"

    Why this needs a model rather than keyword extraction: the searchable
    subject is often not the most frequent or most prominent word. Here it's
    buried in the middle, and the loudest words ("impress", "aunties",
    "apartment") would produce a search that returns nothing useful.

    The instructions are blunt because search APIs are literal. A model that
    "helps" by returning a sentence produces a query matching zero articles.
    """
    return f"""Extract a short news search query from this personal goal.

Goal: {goal_text}

Rules:
- Reply with the search query ONLY. No explanation, no quotes, no punctuation.
- 1 to 4 words.
- Use the general subject, not the personal detail.
  "be good at table tennis and impress the aunties" -> table tennis
  "get a job at a startup building dev tools" -> developer tools
- Use words a journalist would use, not words only this person would use.

Query:"""


def summarise_for_goal(goal_text, article_title, article_text):
    """Summarise an article in terms of one specific goal.

    This is the whole product. A generic summary is something a hundred sites
    already give you; the value here is the connection between this article and
    this person's goal — including when there isn't one, which is why the model
    is explicitly allowed to say so.

    The article is clipped rather than sent whole. Cost and context limits both
    scale with input length, and the point of a news article is near the top by
    journalistic convention.
    """
    body = clip(article_text, SUMMARY_INPUT_CHAR_LIMIT)

    return f"""You are helping someone follow news relevant to a specific goal.

THEIR GOAL:
{goal_text}

ARTICLE TITLE:
{article_title}

ARTICLE:
{body}

Write 2-3 sentences explaining what this article means FOR THEIR GOAL.

Rules:
- Lead with the connection to their goal, not with what the article is about.
- Be concrete. Name the actual fact, number or event that matters.
- If the article is genuinely not relevant to their goal, say exactly that in
  one sentence. Do not invent a connection.
- No preamble. Start with the substance.
- Plain language. No bullet points, no headings.

Summary:"""
