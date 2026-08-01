import dotenv
dotenv.load_dotenv()

import os
from newsapi import NewsApiClient

from src.utils.time_help import get_date

def fetch_articles():
    """Call NewsAPI and return a list of article dicts. Nothing runs until you call this."""
    newsapi = NewsApiClient(api_key=os.getenv('NEWS_API_KEY'))

    response = newsapi.get_everything(q='"software engineering" OR "software architecture" OR "design patterns" OR "developer tools"',
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




#internet info drawing (choosing sources itself according to our needs)