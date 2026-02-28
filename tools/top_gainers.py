from datetime import datetime, timezone

import yfinance as yf
from langchain_core.tools import tool

from ._playwright_scraper import scrape_top_gainer, use_scraper
from pydantic import ValidationError
from .validate import TopGainerResult

_NASDAQ_EXCHANGES = {"NMS", "NGM", "NCM"}


@tool
def get_top_gainers() -> dict:
    """Fetch the #1 top gaining stock on NASDAQ right now.

    Use this tool when you need to find the best performing NASDAQ stock today.
    Queries Yahoo Finance screener filtered to NASDAQ exchanges (NMS, NGM, NCM),
    then re-filters client-side to guard against server-side leakage.
    Falls back to Playwright scraping (Futunn) if yfinance fails or USE_SCRAPER=1.

    Returns:
        Dictionary with timestamp and the top gainer's data including symbol,
        name, exchange, price, change, change_pct, volume, market_cap.
        Returns {'error': message} if the query fails or no NASDAQ gainers found.
    """
    if use_scraper():
        return scrape_top_gainer()

    try:
        query = yf.EquityQuery("and", [
            yf.EquityQuery("is-in", ["exchange", "NMS", "NGM", "NCM"]),
            yf.EquityQuery("gte", ["percentchange", 3]),
        ])
        response = yf.screen(
            query,
            sortField="percentchange",
            sortAsc=False,
            size=250,
        )
    except Exception:
        return scrape_top_gainer()

    quotes = response.get("quotes", [])
    if not quotes:
        return scrape_top_gainer()

    # Client-side filter: guard against server-side leakage (yfinance issue #2218)
    # Also exclude warrants (W), rights (R), units (U) — quoteType check alone isn't always reliable
    nasdaq_quotes = [
        q for q in quotes
        if q.get("exchange") in _NASDAQ_EXCHANGES
        and q.get("quoteType") == "EQUITY"
        and not q.get("symbol", "").endswith(("W", "R", "U"))
    ]

    if not nasdaq_quotes:
        return scrape_top_gainer()

    # Already sorted by percentchange descending — take the top one
    top = nasdaq_quotes[0]

    result = {
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
    try:
        TopGainerResult(**result)
        return result
    except ValidationError as e:
        messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
        return {"error": "validation failed: " + ", ".join(messages)}
