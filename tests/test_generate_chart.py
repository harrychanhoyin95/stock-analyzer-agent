import json
import os

from tools.generate_chart import generate_chart


class TestGenerateChart:
    def test_line_chart_creates_png(self, fake_ohlcv_response):
        data_str = json.dumps(fake_ohlcv_response)

        result = generate_chart.invoke(
            {"data": data_str, "chart_type": "line", "title": "AAPL Test"}
        )

        assert "error" not in result
        assert "chart_path" in result
        assert result["chart_path"].endswith(".png")
        assert os.path.exists(result["chart_path"])

    def test_candlestick_chart_creates_png(self, fake_ohlcv_response):
        data_str = json.dumps(fake_ohlcv_response)

        result = generate_chart.invoke(
            {"data": data_str, "chart_type": "candlestick", "title": "AAPL Candles"}
        )

        assert "error" not in result
        assert "chart_path" in result
        assert os.path.exists(result["chart_path"])

    def test_invalid_json_returns_error(self):
        result = generate_chart.invoke(
            {"data": "{not valid", "chart_type": "line", "title": "X"}
        )

        assert "error" in result
        assert "invalid data JSON" in result["error"]

    def test_missing_data_key_returns_error(self):
        result = generate_chart.invoke(
            {"data": json.dumps({"symbol": "AAPL"}), "chart_type": "line", "title": "X"}
        )

        assert "error" in result
        assert "missing 'data' key" in result["error"]

    def test_unknown_chart_type_returns_error(self, fake_ohlcv_response):
        result = generate_chart.invoke(
            {"data": json.dumps(fake_ohlcv_response), "chart_type": "bar", "title": "X"}
        )

        assert "error" in result
        assert "unknown chart_type" in result["error"]
