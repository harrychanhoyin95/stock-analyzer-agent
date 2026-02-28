from typing import Literal

import yfinance as yf
from langchain_core.tools import tool


@tool
def get_stock_history(
    symbol: str,
    period: Literal["1d", "5d", "1m", "1y"] = "5d",
) -> dict:
    """Fetch historical OHLCV data for a stock symbol.

    Use this tool when you need historical price data for a stock.
    Returns Open, High, Low, Close, and Volume for each day.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL', 'TSLA')
        period: Time period to fetch - '1d', '5d' (default), '1m', or '1y'

    Returns:
        Dictionary with symbol, period, and OHLCV data indexed by date.
        Returns {'error': message} if the symbol is invalid or data unavailable.
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        df = ticker.history(period=period)

        if df.empty:
            return {"error": f"No data found for symbol: {symbol}"}

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

        return {"symbol": symbol.upper(), "period": period, "data": data}

    except Exception as e:
        return {"error": f"Failed to fetch data: {str(e)}"}
