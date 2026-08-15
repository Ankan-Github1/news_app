#Third party libraries
import json

#Services
from src.services.embedings import cosine_similarity, get_or_compute_embedding
from src.services.llm.summary import summarise_text, get_or_compute_summary
from src.services.fetch_news import fetch_articles

#Storage
from src.storage.db import get_article_id, init_db, insert_article, update_article_content, get_article_content, get_active_goals, insert_similarity, insert_summary

#Variables
from src.services.embedings import EMBED_MODEL_NAME
from src.services.llm.summary import SUMMARISE_MODEL_NAME

# get content
from src.services.article_scrap import get_article_text

# helper functions
from src.services.llm.query_gen import extract_queries



def get_or_fetch_article_text(url):
    """Return article body. Cache hit → return stored content. Miss → fetch via newspaper3k, store, return."""
    cached = get_article_content(url)
    if cached is not None:
        return cached
    fetched = get_article_text(url)
    if fetched is not None:
        update_article_content(url, fetched)
    return fetched


def rank_for_goal(goal, top_k=8, floor=0.15):
    """Fetch, score and rank articles for one goal.
    Returns a list of dicts, highest score first, at most top_k, all above floor.
    Each dict: article_id, title, description, source, url, score, summary.
    Empty list if the goal produced no articles.
    """

    all_articles = []

    goal_id, goal_text, goal_query = goal
    goal_embedding = get_or_compute_embedding(goal_text, EMBED_MODEL_NAME)

    queries = json.loads(goal_query)  # Convert the JSON string back to a list
    articles = fetch_articles(queries)

    if not articles:
        return []

    for article in articles:
        if article['title'] is None and article['description'] is None:
            print(f"Skipping article with URL {article['url']} due to missing title and description.")
            continue
        article_id = insert_article(
            url = article['url'],
            title = article['title'],
            description = article['description'],
            source = article['source']['name'],
            published_at = article['publishedAt'],
        )

        if not article_id:
            article_id = get_article_id(article['url'])
            

        article_text = f"{article['title']} {article['description']}"
        
        if article['description'] is None:
            article_text = f"{article['title']}"
        elif article['title'] is None:
            article_text = f"{article['description']}"
        article_embedding = get_or_compute_embedding(article_text, EMBED_MODEL_NAME)

        sim = cosine_similarity(goal_embedding, article_embedding)
        insert_similarity(article_id, goal_id, EMBED_MODEL_NAME, sim)

        all_articles.append({
            "article_id": article_id,
            "goal_id": goal_id,
            "goal_text": goal_text,
            "title": article['title'],
            "description": article['description'],
            "source": article['source']['name'],
            "url": article['url'],
            "score": sim,
        })

    top_articles = sorted(
        (article for article in all_articles if article["score"] >= floor),
        key=lambda article: article["score"],
        reverse=True
        )[:top_k]

    return top_articles

def present_selected_articles(articles):
    """
    Given a list of articles, return a list of dicts with title, description, source, url, score, summary. Wont share content, cause user can read it by clicking link
    """
    required_news = []

    for i, article in enumerate(articles):
        article_id = article["article_id"]
        goal_id = article["goal_id"]

        content = None
        summary = None

        content = get_or_fetch_article_text(article['url'])
        if content is None:
            if article['description'] is None:
                content = f"{article['title']}"
            elif article['title'] is None:
                content = f"{article['description']}"
            elif (article['title']) and (article['description']):
                content = f"{article['title']}. {article['description']}"

        summary = get_or_compute_summary(article_id, goal_id, SUMMARISE_MODEL_NAME, article["goal_text"], content)

        required_news.append(
            {
                "articles" : article,
                "summary" : summary
            }
        )

    return required_news
          

    # for article in articles:
    #     pass







# def main_pipeline():
#     TOP_K = 8 
#     FLOOR_SIMILARITY = 0.15

    # ---- preflight: fail fast, before spending time or API quota ----
    #init_db()
    #check ollama is reachable. if not, raise HERE - don't find out 40s later

    #results = {}    # goal_id -> list of article dicts

    #loop through get_active_goals()    (unpack as goal_id, goal_text)

        # ---- setup for this goal ----
        #goal_embedding = get_or_compute_embedding(goal_text)   <- once per goal, NOT per article
        #queries = extract_queries(goal_text)
        #raw_articles = fetch_articles(queries)                 <- page_size 100 now, not 30
        #if nothing came back: log it, results[goal_id] = [], move on to the next goal

        # ---- pass 1: cheap. runs on all ~100 articles ----
        #scored = []
        #for each raw article:

            #insert-or-get the id:
                #article_id = insert_article(...)
                #if that came back None -> article_id = get_article_id(article['url'])
                #NO `continue` here. a seen-before article still gets scored and can still win.

            #text to embed = title + description
                #description can be None from NewsAPI -> use '' instead
                #otherwise you embed the literal word "None" into the vector

            #article_embedding = get_or_compute_embedding(that text)
            #sim = cosine_similarity(goal_embedding, article_embedding)
            #insert_similarity(article_id, goal_id, sim)    <- every score, winners and losers
                #returns False if the pair already had a score. that's fine, not an error.

            #scored.append( (sim, article_id, article) )

        # ---- select ----
        #sort `scored` by sim, highest first
        #drop anything below FLOOR_SIMILARITY
        #keep the first TOP_K

        # ---- pass 2: expensive. runs on ~8 articles ----
        #for each survivor:

            #summary = get_summary(article_id, goal_id, SUMMARISE_MODEL_NAME)
            #if that's None (cache miss), do the work:
                #content = get_or_fetch_article_text(article['url'])
                #source_text = content if we got it, else article['description']
                    #NOT article['content'] - that's NewsAPI's 214-char stub ending in "[+2269 chars]"
                #summary = summarise_test(goal_text, source_text)
                #if we got one -> insert_summary(article_id, goal_id, SUMMARISE_MODEL_NAME, summary)

            #if this ONE article fails: log which step it failed at, leave summary as None, keep going
                #never store a placeholder string. None means "no summary".
                #the frontend decides what None looks like, not this file.

            #results[goal_id].append({title, description, source, url, summary, score})

    #return results     <- OUTSIDE the goal loop, after every goal is done


    # imports still needed at the top of this file:
    #   from src.storage.db import get_summary, get_article_id
    #   from src.services.llm.query_gen import extract_queries
    











    



























# def main_pipeline():
    # raw_articles = fetch_articles()

    # #Important Checks
    # if not raw_articles:
    #     print("No articles found. Please check your API key and query parameters.")
    #     return []

    # init_db()  # make sure articles table exists before inserting

    # articles = []
    # new_count = 0
    # skipped_count = 0

    # for i, article in enumerate(raw_articles):
    #     article_id = insert_article(
    #         url=article['url'],
    #         title=article['title'],
    #         description=article['description'],
    #         source=article['source']['name'],
    #         published_at=article['publishedAt'],
    #     )


    #     if not article_id:
    #         skipped_count += 1
    #         continue
    #     new_count += 1

        

    #     article_text = f"{article['title']} {article['description']}"
    #     article_embedding = get_or_compute_embedding(article_text)

    #     for goal in get_active_goals():
    #         goal_embedding = get_or_compute_embedding(goal[1])

    #         content = None
    #         summary = None

    #         sim = cosine_similarity(goal_embedding, article_embedding)
    #         #Similarity
    #         insert_similarity(
    #             article_id=article_id,
    #             goal_id=goal[0],
    #             score=sim
    #         )
    #         if sim >= 0.28:
    #             content = get_or_fetch_article_text(article['url'])
    #             if content is None:
    #                 print(f"Skipping generating content and summary for article titled - {article['title']} due to fetch/parse error.")
    #             else:
    #                 summary = summarise_test(goal[1], content)
    #                 insert_summary(
    #                     article_id=article_id,
    #                     goal_id=goal[0],
    #                     model_name=SUMMARISE_MODEL_NAME,
    #                     summary=summary
    #                 )



    #         articles.append({
    #             "title": article['title'],
    #             "description": article['description'],
    #             "source": article['source']['name'],
    #             "url": article['url'],
    #             "content": content,
    #             "summary": summary
    #         })

    # print(f"\n[storage] {new_count} new article(s) inserted, {skipped_count} already seen and skipped.")
    # return articles
