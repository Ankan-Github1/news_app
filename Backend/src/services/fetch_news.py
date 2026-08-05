import dotenv
dotenv.load_dotenv()

import os
from newsapi import NewsApiClient

from src.utils.time_help import get_date

def fetch_articles(queries):
    """Call NewsAPI and return a list of article dicts. Nothing runs until you call this."""

    if not os.getenv('NEWS_API_KEY'):
        raise ValueError("Missing NEWS_API_KEY in environment variables. Please set it before running the code.")

    if not queries:
        raise ValueError("The 'queries' list is empty. Please provide at least one query string.")

    newsapi = NewsApiClient(api_key=os.getenv('NEWS_API_KEY'))

    response = newsapi.get_everything(q=' OR '.join(f'"{query}"' for query in queries),
        # sources='bbc-news,the-verge',
        # domains='medium.com',
        from_param=get_date()['Previous Date'],
        to=get_date()['Date'],
        language='en',
        # sort_by='relevancy',
        page_size=30,
        # page=1
    )
    return response['articles']


if __name__ == "__main__":
    queries = ["SDE", "hiring"]
    articles = fetch_articles(queries)
    print(articles)


#internet info drawing (choosing sources itself according to our needs)