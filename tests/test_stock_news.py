import pytest

from tools.stock_news import get_stock_news


def _make_fake_news_item(title="Stock rises"):
    return {
        "content": {
            "title": title,
            "provider": {"displayName": "Reuters"},
            "pubDate": "2025-01-01T10:00:00Z",
            "canonicalUrl": {"url": "https://example.com/news/1"},
        }
    }


class TestGetStockNewsUnit:
    def test_happy_path_with_ticker(self, mocker):
        mock_ticker = mocker.patch("tools.stock_news.yf.Ticker")
        mock_ticker.return_value.news = [_make_fake_news_item("AAPL rises")]

        result = get_stock_news.invoke({"ticker": "AAPL"})

        assert result["symbol"] == "AAPL"
        assert len(result["news"]) == 1
        assert result["news"][0]["title"] == "AAPL rises"
        assert result["news"][0]["publisher"] == "Reuters"

    def test_no_ticker_fetches_top_gainer_first(self, mocker, fake_top_gainer_response):
        mock_top_gainers = mocker.patch("tools.stock_news.get_top_gainers")
        mock_top_gainers.invoke.return_value = fake_top_gainer_response

        mock_ticker = mocker.patch("tools.stock_news.yf.Ticker")
        mock_ticker.return_value.news = [_make_fake_news_item()]

        result = get_stock_news.invoke({})

        assert result["symbol"] == "AAPL"  # symbol from fake_top_gainer_response

    def test_top_gainer_error_propagates(self, mocker):
        mock_top_gainers = mocker.patch("tools.stock_news.get_top_gainers")
        mock_top_gainers.invoke.return_value = {"error": "top gainer failed"}

        result = get_stock_news.invoke({})

        assert result == {"error": "top gainer failed"}

    def test_yfinance_exception_falls_back_to_scraper(self, mocker):
        mock_ticker = mocker.patch("tools.stock_news.yf.Ticker")
        mock_ticker.return_value.news = None
        mock_ticker.side_effect = RuntimeError("network error")

        mock_scraper = mocker.patch(
            "tools.stock_news.scrape_stock_news",
            return_value={"symbol": "AAPL", "timestamp": "now", "news": []},
        )

        get_stock_news.invoke({"ticker": "AAPL"})

        mock_scraper.assert_called_once_with("AAPL")

    def test_empty_news_falls_back_to_scraper(self, mocker):
        mock_ticker = mocker.patch("tools.stock_news.yf.Ticker")
        mock_ticker.return_value.news = []

        mock_scraper = mocker.patch(
            "tools.stock_news.scrape_stock_news",
            return_value={"symbol": "AAPL", "timestamp": "now", "news": []},
        )

        get_stock_news.invoke({"ticker": "AAPL"})

        mock_scraper.assert_called_once_with("AAPL")

    def test_news_item_with_empty_content_returns_none_fields(self, mocker):
        mock_ticker = mocker.patch("tools.stock_news.yf.Ticker")
        mock_ticker.return_value.news = [{"content": {}}]

        result = get_stock_news.invoke({"ticker": "AAPL"})

        assert "error" not in result
        assert len(result["news"]) == 1
        item = result["news"][0]
        assert item["title"] is None
        assert item["publisher"] is None
        assert item["published_at"] is None
        assert item["url"] is None

    def test_use_scraper_env_bypasses_yfinance(self, mocker, monkeypatch):
        monkeypatch.setenv("USE_SCRAPER", "1")

        mock_yf = mocker.patch("tools.stock_news.yf.Ticker")
        mock_scraper = mocker.patch(
            "tools.stock_news.scrape_stock_news",
            return_value={"symbol": "AAPL", "timestamp": "now", "news": []},
        )

        get_stock_news.invoke({"ticker": "AAPL"})

        mock_yf.assert_not_called()
        mock_scraper.assert_called_once_with("AAPL")


@pytest.mark.integration
class TestGetStockNewsIntegration:
    def test_real_aapl_news_returns_items(self):
        result = get_stock_news.invoke({"ticker": "AAPL"})

        assert "error" not in result
        assert result["symbol"] == "AAPL"
        assert len(result["news"]) > 0
        assert "title" in result["news"][0]
