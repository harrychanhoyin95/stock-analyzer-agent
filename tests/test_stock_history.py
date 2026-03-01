import pandas as pd
import pytest

from tools.stock_history import get_stock_history


def _make_fake_df():
    """Return a minimal DataFrame matching what yfinance returns."""
    index = pd.to_datetime(["2025-01-01", "2025-01-02"])
    return pd.DataFrame(
        {
            "Open": [150.00, 153.00],
            "High": [155.00, 158.00],
            "Low": [149.00, 152.00],
            "Close": [153.00, 157.00],
            "Volume": [1_000_000, 1_200_000],
        },
        index=index,
    )


class TestGetStockHistoryUnit:
    def test_happy_path_returns_expected_shape(self, mocker):
        mock_ticker = mocker.patch("tools.stock_history.yf.Ticker")
        mock_ticker.return_value.history.return_value = _make_fake_df()

        result = get_stock_history.invoke({"symbol": "AAPL", "period": "5d"})

        assert result["symbol"] == "AAPL"
        assert result["period"] == "5d"
        assert len(result["data"]) == 2
        row = list(result["data"].values())[0]
        assert set(row.keys()) == {"open", "high", "low", "close", "volume"}

    def test_empty_dataframe_falls_back_to_scraper(self, mocker):
        mock_ticker = mocker.patch("tools.stock_history.yf.Ticker")
        mock_ticker.return_value.history.return_value = pd.DataFrame()

        mock_scraper = mocker.patch(
            "tools.stock_history.scrape_stock_history",
            return_value={"error": "scraper called"},
        )

        result = get_stock_history.invoke({"symbol": "AAPL", "period": "5d"})

        mock_scraper.assert_called_once_with("AAPL", "5d")
        assert result == {"error": "scraper called"}

    def test_yfinance_exception_falls_back_to_scraper(self, mocker):
        mock_ticker = mocker.patch("tools.stock_history.yf.Ticker")
        mock_ticker.return_value.history.side_effect = RuntimeError("network error")

        mock_scraper = mocker.patch(
            "tools.stock_history.scrape_stock_history",
            return_value={"error": "scraper called"},
        )

        result = get_stock_history.invoke({"symbol": "AAPL", "period": "5d"})

        mock_scraper.assert_called_once()

    def test_use_scraper_env_bypasses_yfinance(self, mocker, monkeypatch):
        monkeypatch.setenv("USE_SCRAPER", "1")

        mock_yf = mocker.patch("tools.stock_history.yf.Ticker")
        mock_scraper = mocker.patch(
            "tools.stock_history.scrape_stock_history",
            return_value={"symbol": "AAPL", "period": "5d", "data": {}},
        )

        get_stock_history.invoke({"symbol": "AAPL", "period": "5d"})

        mock_yf.assert_not_called()
        mock_scraper.assert_called_once_with("AAPL", "5d")


@pytest.mark.integration
class TestGetStockHistoryIntegration:
    def test_real_aapl_returns_data(self):
        result = get_stock_history.invoke({"symbol": "AAPL", "period": "5d"})

        assert "error" not in result
        assert result["symbol"] == "AAPL"
        assert result["period"] == "5d"
        assert len(result["data"]) > 0
