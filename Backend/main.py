from time import perf_counter

from src.core.filter_logic import rank_for_goal, present_selected_articles
from src.storage.db import get_active_goals

LINE = "=" * 78
THIN = "-" * 78


def since(t):
    """Seconds elapsed since `t`, as a float."""
    return perf_counter() - t


def clip(text, limit=160):
    """Trim long text to one readable line."""
    if not text:
        return "(none)"
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 3] + "..."


run_start = perf_counter()
goals = get_active_goals()
print(f"\n{LINE}\n {len(goals)} active goal(s)\n{LINE}")

for goal in goals:
    goal_id, goal_text, _ = goal
    print(f"\n{LINE}")
    print(f" GOAL {goal_id}: {clip(goal_text, 200)}")
    print(LINE)

    t = perf_counter()
    top_articles = rank_for_goal(goal)
    rank_time = since(t)

    if not top_articles:
        print(f"\n  no articles matched.   [rank {rank_time:.1f}s]")
        continue

    print(f"\n  RANKED {len(top_articles)} article(s)   [rank {rank_time:.1f}s]\n")
    for n, article in enumerate(top_articles, 1):
        print(f"  {n}. [{article['score']:.3f}] {clip(article['title'], 90)}")
        print(f"     {article['source']}  |  {article['url']}")
        print(f"     {clip(article['description'])}\n")

    t = perf_counter()
    required_news = present_selected_articles(top_articles)
    summary_time = since(t)

    print(THIN)
    print(f"  SUMMARIES   [{summary_time:.1f}s total, "
          f"{summary_time / len(required_news):.1f}s avg]")
    print(THIN)

    for n, news in enumerate(required_news, 1):
        print(f"\n  --- {n}. {clip(news['articles']['title'], 90)} ---\n")
        print(news['summary'] or "  (no summary - fetch or LLM failed)")

    print(f"\n{THIN}")
    print(f"  goal {goal_id} done in {rank_time + summary_time:.1f}s "
          f"(rank {rank_time:.1f}s, summaries {summary_time:.1f}s)")
    print(THIN)

print(f"\n{LINE}")
print(f" RUN COMPLETE - {since(run_start):.1f}s for {len(goals)} goal(s)")
print(f"{LINE}\n")
