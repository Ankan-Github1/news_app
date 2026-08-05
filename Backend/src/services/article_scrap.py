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