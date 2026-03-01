import pytest

from tools.top_gainers import get_top_gainers


def _make_quote(symbol="AAPL", exchange="NMS", quote_type="EQUITY", change_pct=5.0):
    return {
        "symbol": symbol,
        "longName": "Apple Inc.",
        "exchange": exchange,
        "quoteType": quote_type,
        "regularMarketPrice": 153.00,
        "regularMarketChange": 5.00,
        "regularMarketChangePercent": change_pct,
        "regularMarketVolume": 1_000_000,
        "marketCap": 2_400_000_000_000,
    }


class TestGetTopGainersUnit:
    def test_happy_path_returns_top_nasdaq_equity(self, mocker):
        mocker.patch("tools.top_gainers.yf.EquityQuery")
        mocker.patch(
            "tools.top_gainers.yf.screen",
            return_value={"quotes": [_make_quote()]},
        )

        result = get_top_gainers.invoke({})

        assert result["symbol"] == "AAPL"
        assert result["exchange"] == "NMS"
        assert "error" not in result

    def test_non_nasdaq_quotes_filtered_out(self, mocker):
        mocker.patch("tools.top_gainers.yf.EquityQuery")
        mocker.patch(
            "tools.top_gainers.yf.screen",
            return_value={
                "quotes": [
                    _make_quote(symbol="NYSE_STOCK", exchange="NYQ", change_pct=10.0),
                    _make_quote(symbol="AAPL", exchange="NMS", change_pct=5.0),
                ]
            },
        )
        mock_scraper = mocker.patch("tools.top_gainers.scrape_top_gainer")

        result = get_top_gainers.invoke({})

        # NYSE stock should be filtered, AAPL returned
        assert result["symbol"] == "AAPL"
        mock_scraper.assert_not_called()

    def test_warrant_symbols_filtered_out(self, mocker):
        mocker.patch("tools.top_gainers.yf.EquityQuery")
        mocker.patch(
            "tools.top_gainers.yf.screen",
            return_value={
                "quotes": [
                    _make_quote(symbol="XYZW", exchange="NMS", change_pct=20.0),  # warrant
                    _make_quote(symbol="AAPL", exchange="NMS", change_pct=5.0),
                ]
            },
        )

        result = get_top_gainers.invoke({})

        assert result["symbol"] == "AAPL"

    def test_all_filtered_out_falls_back_to_scraper(self, mocker, fake_top_gainer_response):
        mocker.patch("tools.top_gainers.yf.EquityQuery")
        mocker.patch(
            "tools.top_gainers.yf.screen",
            return_value={
                "quotes": [
                    _make_quote(symbol="XYZW", exchange="NMS", change_pct=20.0),  # warrant, filtered
                ]
            },
        )
        mock_scraper = mocker.patch(
            "tools.top_gainers.scrape_top_gainer",
            return_value=fake_top_gainer_response,
        )

        result = get_top_gainers.invoke({})

        mock_scraper.assert_called_once()

    def test_empty_quotes_falls_back_to_scraper(self, mocker, fake_top_gainer_response):
        mocker.patch("tools.top_gainers.yf.EquityQuery")
        mocker.patch(
            "tools.top_gainers.yf.screen",
            return_value={"quotes": []},
        )
        mock_scraper = mocker.patch(
            "tools.top_gainers.scrape_top_gainer",
            return_value=fake_top_gainer_response,
        )

        get_top_gainers.invoke({})

        mock_scraper.assert_called_once()

    def test_use_scraper_env_bypasses_yfinance(self, mocker, monkeypatch, fake_top_gainer_response):
        monkeypatch.setenv("USE_SCRAPER", "1")

        mock_yf = mocker.patch("tools.top_gainers.yf.screen")
        mock_scraper = mocker.patch(
            "tools.top_gainers.scrape_top_gainer",
            return_value=fake_top_gainer_response,
        )

        get_top_gainers.invoke({})

        mock_yf.assert_not_called()
        mock_scraper.assert_called_once()


@pytest.mark.integration
class TestGetTopGainersIntegration:
    def test_real_call_returns_expected_keys(self):
        result = get_top_gainers.invoke({})

        # Either returns data or a scraper error — both are valid
        assert isinstance(result, dict)
        if "error" not in result:
            assert "symbol" in result
            assert "exchange" in result
            assert "price" in result
