import os
from dotenv import load_dotenv
load_dotenv()
from newsapi import NewsApiClient
import worldnewsapi
from worldnewsapi.rest import ApiException

from datetime import datetime, timedelta
from llm_utils import query_llm


class NewsClient():
    """Base class. Shall not be instanciated"""
    def get_daily_articles(self, topic):
        raise NotImplementedError
            
    def get_daily_news_summary(self, topic):
        raw_news = self.get_daily_articles(topic)
        prompt = (f"Given this partially incomplete list of articles (or article stubs) on the keyword '{topic}', "
            f"write a summary on the news. Make sure to keep the relevant numbers and facts intact. "
            f"Focus in particular on novel potential investment opportunities and impending risks if (and only if) such are mentioned."
            f"Do stick true to the source material."
            f"Make sure to always point out the relevant stock symbols (e.g. AAPL, GOOGL, etc.)\n\n")
        prompt += raw_news
        
        summary, cost = query_llm(prompt)
        print(f"API call to LLM: {cost}$")
        return summary


class WorldNewsCustomClient(NewsClient):
    def __init__(self, api_key=None):
        api_key = os.getenv("WORLD_NEWS_API_KEY") if not api_key else api_key
        newsapi_configuration = worldnewsapi.Configuration(api_key={'apiKey': api_key})
        newsapi_configuration.api_key['headerApiKey'] = api_key
        self.newsapi_instance = worldnewsapi.NewsApi(worldnewsapi.ApiClient(newsapi_configuration))
        
    def _format_articles(self, articles) -> str:
        raw_news = ""
        for article in articles:
            raw_news += f"{article.title}: {article.publish_date}\n"
            raw_news += f"{article.summary}\n"
            raw_news += f"{article.text}\n"
            raw_news += "\n"
        return raw_news

    def get_daily_articles(self, topic):
        yesterday = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        today = datetime.today().strftime('%Y-%m-%d')
        tomorrow = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        try:
            # Fetch news articles
            response = self.newsapi_instance.search_news(
                text=topic,
                language='en',
                earliest_publish_date=yesterday,
                latest_publish_date=tomorrow,
                sort="publish-time",
                sort_direction="desc",
                number=10
            )
        except ApiException as e:
            print(f"Exception when calling NewsApi->search_news: {e}\n")
        all_articles = response.news
        raw_news = self._format_articles(all_articles)
        return raw_news
    

class NewsApiCustomClient(NewsClient):
    def __init__(self, api_key=None):
        api_key = os.getenv("NEWS_API_KEY") if not api_key else api_key
        self.news_api = NewsApiClient(api_key=api_key)
    
    def _format_articles(self, articles) -> str:
        raw_news = ""
        for art in articles["articles"]:
            raw_news += f"{art["source"]["name"]}: {art["publishedAt"]}\n"
            raw_news += f"{art["title"]}\n"
            raw_news += f"{art["description"]}\n"
            raw_news += "\n"
        return raw_news
    
    def get_daily_articles(self, topic):
        yesterday = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        today = datetime.today().strftime('%Y-%m-%d')
        tomorrow = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        all_articles = self.news_api.get_everything(q=topic,
                                                    from_param=yesterday,
                                                    to=tomorrow,
                                                    language='en',
                                                    sort_by='relevancy')
        if not all_articles["articles"]:
            return f"Today ({today}) there were no news on the topic '{topic}'"
        raw_news = self._format_articles(all_articles)
        return raw_news

            