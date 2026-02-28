from datetime import datetime, timezone
import yfinance as yf
from langchain_core.tools import tool
from .top_gainers import get_top_gainers

@tool
def get_stock_news(ticker: str | None = None) -> dict:
  """Fetch recent news headlines for a stock and return them for sentiment analysis.

  Use this tool when you need to find news about a specific stock or the top gainer.
  If ticker is not provided, automatically fetches news for today's top NASDAQ gainer.

  Args:
      ticker: Optional stock symbol (e.g. 'AAPL'). If omitted, uses the top gainer.

  Returns:
      Dictionary with symbol, timestamp, and a list of up to 10 news items.
      Each item contains title, publisher, published_at (ISO 8601), and url.
      Returns {'error': message} if the fetch fails.
  """

  if ticker is None:
      result = get_top_gainers.invoke({})
      if "error" in result:
          return result
      symbol = result["symbol"]
  else:
      symbol = ticker.upper()

  try:
      ticker_obj = yf.Ticker(symbol)
      raw_news = ticker_obj.news
  except Exception as e:
      return {"error": f"Failed to fetch news for {symbol}: {str(e)}"}

  if not raw_news:
      return {"error": f"No news found for {symbol}"}

  news = []
  for item in raw_news[:10]:
      content = item.get("content", {})
      news.append({
          "title": content.get("title"),
          "publisher": content.get("provider", {}).get("displayName"),
          "published_at": content.get("pubDate"),
          "url": content.get("canonicalUrl", {}).get("url"),
      })

  return {
      "symbol": symbol,
      "timestamp": datetime.now(timezone.utc).isoformat(),
      "news": news,
  }
