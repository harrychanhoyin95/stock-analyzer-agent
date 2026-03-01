import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration (requires network/Docker)",
    )


@pytest.fixture
def fake_ohlcv_response():
    return {
        "symbol": "AAPL",
        "period": "5d",
        "data": {
            "2025-01-01": {
                "open": 150.00,
                "high": 155.00,
                "low": 149.00,
                "close": 153.00,
                "volume": 1000000,
            },
            "2025-01-02": {
                "open": 153.00,
                "high": 158.00,
                "low": 152.00,
                "close": 157.00,
                "volume": 1200000,
            },
        },
    }


@pytest.fixture
def fake_top_gainer_response():
    return {
        "timestamp": "2025-01-01T00:00:00+00:00",
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "exchange": "NMS",
        "price": 153.00,
        "change_absolute": 5.00,
        "change_pct": 3.38,
        "volume": 1000000,
        "market_cap": 2400000000000,
    }
