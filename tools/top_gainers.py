from datetime import datetime, timezone

import yfinance as yf
from langchain_core.tools import tool

_NASDAQ_EXCHANGES = {"NMS", "NGM", "NCM"}


@tool
def get_top_gainers() -> dict:
    """Fetch the #1 top gaining stock on NASDAQ right now.

    Use this tool when you need to find the best performing NASDAQ stock today.
    Queries Yahoo Finance screener filtered to NASDAQ exchanges (NMS, NGM, NCM),
    then re-filters client-side to guard against server-side leakage.

    Returns:
        Dictionary with timestamp and the top gainer's data including symbol,
        name, exchange, price, change, change_pct, volume, market_cap.
        Returns {'error': message} if the query fails or no NASDAQ gainers found.
    """
    try:
        query = yf.EquityQuery("and", [
            yf.EquityQuery("is-in", ["exchange", "NMS", "NGM", "NCM"]),
            yf.EquityQuery("gte", ["percentchange", 3]),
            yf.EquityQuery("gte", ["intradaymarketcap", 2_000_000_000]),
            yf.EquityQuery("gte", ["intradayprice", 5]),
            yf.EquityQuery("gte", ["dayvolume", 15_000]),
        ])
        response = yf.screen(
            query,
            sortField="percentchange",
            sortAsc=False,
            size=250,
        )
    except Exception as e:
        return {"error": f"Failed to query Yahoo Finance screener: {str(e)}"}

    quotes = response.get("quotes", [])
    if not quotes:
        return {"error": "No results returned from screener"}

    # Client-side filter: guard against server-side leakage (yfinance issue #2218)
    # Also exclude warrants (W), rights (R), units (U) — quoteType check alone isn't always reliable
    nasdaq_quotes = [
        q for q in quotes
        if q.get("exchange") in _NASDAQ_EXCHANGES
        and q.get("quoteType") == "EQUITY"
        and not q.get("symbol", "").endswith(("W", "R", "U"))
    ]

    if not nasdaq_quotes:
        return {"error": "No NASDAQ stocks found in screener results"}

    # Already sorted by percentchange descending — take the top one
    top = nasdaq_quotes[0]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": top.get("symbol"),
        "name": top.get("longName") or top.get("shortName"),
        "exchange": top.get("exchange"),
        "price": top.get("regularMarketPrice"),
        "change_absolute": top.get("regularMarketChange"),
        "change_pct": top.get("regularMarketChangePercent"),
        "volume": top.get("regularMarketVolume"),
        "market_cap": top.get("marketCap"),
    }
