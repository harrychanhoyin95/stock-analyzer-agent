"""Fallback scrapers for stock data tools.

Playwright is used for top gainers (Futunn) and stock history (Yahoo Finance).
RSS via httpx is used for stock news (Yahoo Finance RSS).

Activated automatically on yfinance errors, or forced via USE_SCRAPER=1 env var.
"""

import os
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

# Approximate trading days per period — used to slice history rows
_PERIOD_ROWS: dict[str, int] = {
    "1d": 1,
    "5d": 5,
    "1mo": 21,
    "3mo": 63,
    "6mo": 126,
    "1y": 252,
    "2y": 504,
    "5y": 1260,
    "10y": 2520,
}


def use_scraper() -> bool:
    """Return True if USE_SCRAPER env var is set to '1' or 'true'."""
    return os.environ.get("USE_SCRAPER", "").lower() in ("1", "true")


def _parse_number(s: str) -> float | None:
    """Parse a formatted number string into a float.

    Handles:
      - Sign prefix:  '+56.88%' -> 56.88,  '-3.5%' -> -3.5
      - Suffixes:     '24.89M' -> 24890000.0,  '6.33B' -> 6330000000.0
      - Plain:        '84.23'  -> 84.23
      - Missing:      '--'     -> None
    """
    if not s or s.strip() in ("--", "N/A", ""):
        return None

    s = s.strip().replace(",", "")

    multiplier = 1.0
    if s.endswith("%"):
        s = s[:-1]
    elif s.endswith("B"):
        multiplier = 1_000_000_000.0
        s = s[:-1]
    elif s.endswith("M"):
        multiplier = 1_000_000.0
        s = s[:-1]
    elif s.endswith("K"):
        multiplier = 1_000.0
        s = s[:-1]

    try:
        return float(s) * multiplier
    except ValueError:
        return None


def scrape_top_gainer() -> dict:
    """Scrape the #1 NASDAQ top gainer from Futunn using Playwright.

    Returns the same dict shape as get_top_gainers().
    """
    url = "https://www.futunn.com/en/quote/us/stock-list/nasdaq/top-gainers"

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            page.wait_for_function(
                "document.body.innerText.includes('%')", timeout=20000
            )

            rows = page.query_selector_all("table tbody tr")
            if not rows:
                return {"error": "Futunn: no rows found in gainers table"}

            cells = rows[0].query_selector_all("td")
            if len(cells) < 9:
                return {"error": f"Futunn: unexpected column count ({len(cells)})"}

            symbol = cells[1].inner_text().strip()
            name = cells[2].inner_text().strip()
            price = _parse_number(cells[3].inner_text())
            change_absolute = _parse_number(cells[4].inner_text())
            change_pct = _parse_number(cells[5].inner_text())
            volume_raw = cells[6].inner_text().strip()
            volume = _parse_number(volume_raw)
            market_cap = _parse_number(cells[8].inner_text())

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "name": name,
                "exchange": "NASDAQ",
                "price": price,
                "change_absolute": change_absolute,
                "change_pct": change_pct,
                "volume": int(volume) if volume is not None else None,
                "market_cap": market_cap,
            }

    except Exception as e:
        return {"error": f"Futunn scraper failed: {str(e)}"}
    finally:
        if browser:
            browser.close()


def scrape_stock_history(symbol: str, period: str) -> dict:
    """Scrape historical OHLCV data from Yahoo Finance using Playwright.

    Returns the same dict shape as get_stock_history().
    """
    url = (
        f"https://finance.yahoo.com/quote/{symbol.upper()}/history/"
        "?period1=0&period2=9999999999"
    )
    n_rows = _PERIOD_ROWS.get(period, 5)

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)

            table = page.query_selector("table")
            if not table:
                return {"error": f"Yahoo Finance history: no table found for {symbol}"}

            rows = table.query_selector_all("tbody tr")
            if not rows:
                return {"error": f"Yahoo Finance history: no rows for {symbol}"}

            data = {}
            for row in rows[:n_rows]:
                cells = row.query_selector_all("td")
                if len(cells) < 7:
                    continue

                date_text = cells[0].inner_text().strip()
                try:
                    date_str = datetime.strptime(date_text, "%b %d, %Y").strftime(
                        "%Y-%m-%d"
                    )
                except ValueError:
                    continue

                open_ = _parse_number(cells[1].inner_text())
                high = _parse_number(cells[2].inner_text())
                low = _parse_number(cells[3].inner_text())
                close = _parse_number(cells[4].inner_text())
                volume_raw = _parse_number(cells[6].inner_text())

                if any(v is None for v in (open_, high, low, close, volume_raw)):
                    continue

                data[date_str] = {
                    "open": round(open_, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": int(volume_raw),
                }

            if not data:
                return {"error": f"Yahoo Finance history: no parseable rows for {symbol}"}

            return {"symbol": symbol.upper(), "period": period, "data": data}

    except Exception as e:
        return {"error": f"Yahoo Finance history scraper failed: {str(e)}"}
    finally:
        if browser:
            browser.close()


def scrape_stock_news(symbol: str) -> dict:
    """Fetch recent news for a stock via Yahoo Finance news page using Playwright.

    Returns the same dict shape as get_stock_news().
    """
    url = f"https://finance.yahoo.com/quote/{symbol.upper()}/news/"

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)

            page.wait_for_selector("li h3", timeout=15000)

            items = page.query_selector_all("li:has(h3)")
            if not items:
                return {"error": f"Yahoo Finance news: no items found for {symbol}"}

            news = []
            for item in items[:10]:
                h3 = item.query_selector("h3")
                anchor = item.query_selector("a[href]")
                publishing = item.query_selector("div.publishing")

                title = h3.inner_text().strip() if h3 else None
                link = anchor.get_attribute("href") if anchor else None
                if link and link.startswith("/"):
                    link = "https://finance.yahoo.com" + link

                publisher = None
                published_at = None
                if publishing:
                    parts = [p.strip() for p in publishing.inner_text().split("•")]
                    publisher = parts[0] if parts else None
                    published_at = parts[1] if len(parts) > 1 else None

                if title:
                    news.append({
                        "title": title,
                        "publisher": publisher,
                        "published_at": published_at,
                        "url": link,
                    })

            if not news:
                return {"error": f"Yahoo Finance news: no parseable items for {symbol}"}

            return {
                "symbol": symbol.upper(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "news": news,
            }

    except Exception as e:
        return {"error": f"Yahoo Finance news scraper failed: {str(e)}"}
    finally:
        if browser:
            browser.close()
