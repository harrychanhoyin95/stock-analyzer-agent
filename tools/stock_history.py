from typing import Literal

import yfinance as yf
from langchain_core.tools import tool

from ._playwright_scraper import scrape_stock_history, use_scraper
from pydantic import ValidationError

from .validate import StockHistoryResult


@tool
def get_stock_history(
    symbol: str,
    period: Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y"] = "5d",
) -> dict:
    """Fetch historical OHLCV data for a stock symbol.

    Use this tool when you need historical price data for a stock.
    Returns Open, High, Low, Close, and Volume for each day.
    Falls back to Playwright scraping (Yahoo Finance) if yfinance fails or USE_SCRAPER=1.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL', 'TSLA')
        period: Time period to fetch - '1d', '5d' (default), '1mo', or '1y'

    Returns:
        Dictionary with symbol, period, and OHLCV data indexed by date.
        Returns {'error': message} if the symbol is invalid or data unavailable.
    """
    if use_scraper():
        return scrape_stock_history(symbol, period)

    try:
        ticker = yf.Ticker(symbol.upper())
        df = ticker.history(period=period)

        if df.empty:
            return scrape_stock_history(symbol, period)

        data = {}
        for date, row in df.iterrows():
            date_str = date.strftime("%Y-%m-%d")
            data[date_str] = {
                "open": float(round(row["Open"], 2)),
                "high": float(round(row["High"], 2)),
                "low": float(round(row["Low"], 2)),
                "close": float(round(row["Close"], 2)),
                "volume": int(row["Volume"]),
            }

        result = {"symbol": symbol.upper(), "period": period, "data": data}
        try:
            StockHistoryResult(**result)
            return result
        except ValidationError as e:
            messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
            return {"error": "validation failed: " + ", ".join(messages)}

    except Exception:
        return scrape_stock_history(symbol, period)
