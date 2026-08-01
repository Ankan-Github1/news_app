#Services
from src.services.embedings import cosine_similarity, get_or_compute_embedding
from src.services.llm.summary import summarise_test
from src.services.fetch_news import fetch_articles

#Storage
from src.storage.db import init_db, insert_article, update_article_content, get_article_content, get_active_goals, insert_similarity, insert_summary

#Variables
from src.services.embedings import EMBED_MODEL_NAME
from src.services.llm.summary import SUMMARISE_MODEL_NAME

# get content
from newspaper import Article, ArticleException
from requests.exceptions import RequestException  

def get_article_text(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text
    except (ArticleException, RequestException) as e:
        print(f"Error fetching article from {url}: {e}")
        return None


def get_or_fetch_article_text(url):
    """Return article body. Cache hit → return stored content. Miss → fetch via newspaper3k, store, return."""
    cached = get_article_content(url)
    if cached is not None:
        return cached
    fetched = get_article_text(url)
    if fetched is not None:
        update_article_content(url, fetched)
    return fetched
    
def main_pipeline():
    raw_articles = fetch_articles()

    #Important Checks
    if not raw_articles:
        print("No articles found. Please check your API key and query parameters.")
        quit()

    init_db()  # make sure articles table exists before inserting

    articles = []
    new_count = 0
    skipped_count = 0

    for i, article in enumerate(raw_articles):
        article_id = insert_article(
            url=article['url'],
            title=article['title'],
            description=article['description'],
            source=article['source']['name'],
            published_at=article['publishedAt'],
        )
        if not article_id:
            skipped_count += 1
            continue
        new_count += 1

        article_text = f"{article['title']} {article['description']}"
        article_embedding = get_or_compute_embedding(article_text)

        for goal in get_active_goals():
            goal_embedding = get_or_compute_embedding(goal[1])

            content = None
            summary = None

            sim = cosine_similarity(goal_embedding, article_embedding)
            #Similarity
            insert_similarity(
                article_id=article_id,
                goal_id=goal[0],
                score=sim
            )
            if sim >= 0.28:
                content = get_or_fetch_article_text(article['url'])
                if content is None:
                    print(f"Skipping generating content and summary for article titled - {article['title']} due to fetch/parse error.")
                else:
                    summary = summarise_test(goal[1], content)
                    insert_summary(
                        article_id=article_id,
                        goal_id=goal[0],
                        model_name=SUMMARISE_MODEL_NAME,
                        summary=summary
                    )



            articles.append({
                "title": article['title'],
                "description": article['description'],
                "source": article['source']['name'],
                "url": article['url'],
                "content": content,
                "summary": summary
            })

    print(f"\n[storage] {new_count} new article(s) inserted, {skipped_count} already seen and skipped.")
    return articles
