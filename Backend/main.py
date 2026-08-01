# from src.core.filter_logic import articles
# print(articles)

from src.core.filter_logic import main_pipeline
articles = main_pipeline()

for article in articles:
    print(f"Title: {article['title']}")
    print(f"Description: {article['description']}")
    print(f"Source: {article['source']}")
    print(f"URL: {article['url']}")
    content = article['content']
    print(f"Content: {content[:100] + '...' if content else 'N/A'}")
    print(f"Summary: {article['summary'] or 'N/A'}\n")

print(len(articles))