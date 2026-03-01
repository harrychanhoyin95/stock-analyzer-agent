import pytest
from pydantic import ValidationError

from tools.validate import AnalyzerInput, StockHistoryResult, TopGainerResult


class TestStockHistoryResult:
    def test_valid(self, fake_ohlcv_response):
        result = StockHistoryResult(**fake_ohlcv_response)
        assert result.symbol == "AAPL"
        assert result.period == "5d"
        assert len(result.data) == 2

    def test_empty_data_raises(self):
        with pytest.raises(ValidationError, match="data has no rows"):
            StockHistoryResult(symbol="AAPL", period="5d", data={})

    def test_missing_symbol_raises(self, fake_ohlcv_response):
        payload = {k: v for k, v in fake_ohlcv_response.items() if k != "symbol"}
        with pytest.raises(ValidationError):
            StockHistoryResult(**payload)

    def test_invalid_ohlcv_row_raises(self):
        with pytest.raises(ValidationError):
            StockHistoryResult(
                symbol="AAPL",
                period="5d",
                data={"2025-01-01": {"open": "not_a_float", "high": 1, "low": 1, "close": 1, "volume": 100}},
            )


class TestTopGainerResult:
    def test_valid(self, fake_top_gainer_response):
        result = TopGainerResult(**fake_top_gainer_response)
        assert result.symbol == "AAPL"
        assert result.exchange == "NMS"

    def test_name_can_be_none(self, fake_top_gainer_response):
        fake_top_gainer_response["name"] = None
        result = TopGainerResult(**fake_top_gainer_response)
        assert result.name is None

    def test_market_cap_can_be_none(self, fake_top_gainer_response):
        fake_top_gainer_response["market_cap"] = None
        result = TopGainerResult(**fake_top_gainer_response)
        assert result.market_cap is None

    def test_missing_required_field_raises(self, fake_top_gainer_response):
        del fake_top_gainer_response["symbol"]
        with pytest.raises(ValidationError):
            TopGainerResult(**fake_top_gainer_response)


class TestAnalyzerInput:
    def test_accepts_extra_fields(self):
        obj = AnalyzerInput(foo="bar", baz=123)
        assert obj.foo == "bar"  # type: ignore[attr-defined]
