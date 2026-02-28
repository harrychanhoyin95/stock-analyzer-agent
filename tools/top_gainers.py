from datetime import datetime, timezone

from langchain_core.tools import tool
from playwright.sync_api import sync_playwright, ElementHandle

@tool
def get_top_gainers() -> dict:
    """Fetch real-time top gaining stocks from Yahoo Finance.
    Use this tool when you need to find which stocks are gaining the most today.
    Scrapes Yahoo Finance screener for top gainers with extended data.
    Returns:
        Dictionary with timestamp, count, and list of top gainers.
        Each gainer includes: symbol, name, price, change, change_pct,
        volume, avg_vol_3m, market_cap, pe_ratio.
        Returns {'error': message} if scraping fails.
    """

    url = "https://finance.yahoo.com/screener/predefined/day_gainers"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="load", timeout=30000)
                # Wait for actual row with data-testid
                page.wait_for_selector('tr[data-testid="data-table-v2-row"]', timeout=15000)

                # Get all table rows
                rows = page.query_selector_all("tbody tr")

                gainers = []
                for row in rows:
                    cells = row.query_selector_all("td")
                    if len(cells) < 10:
                        continue
                    parsed = parse_gainers_data(cells)
                    if parsed:
                        gainers.append(parsed)

                return {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "count": len(gainers),
                    "data": gainers,
                }
            finally:
                browser.close()

    except Exception as e:
        return {"error": f"Failed to scrape top gainers: {str(e)}"}


def parse_number(text: str) -> float | None:
    """Strip $, +, commas, % and return float, or None for N/A / empty."""
    cleaned = text.strip().lstrip('+').replace('$', '').replace(',', '').replace('%', '')
    if not cleaned or cleaned in ('N/A', '-', '--'):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


_VOLUME_SUFFIXES = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000, 'T': 1_000_000_000_000}


def parse_volume(text: str) -> int | None:
    """Parse volume strings like '1.23M', '987.65K', '4.5B' into ints."""
    text = text.strip()
    if not text or text in ('N/A', '-', '--'):
        return None
    multiplier = _VOLUME_SUFFIXES.get(text[-1].upper(), 1)
    if multiplier != 1:
        text = text[:-1]
    value = parse_number(text)
    return int(value * multiplier) if value is not None else None


def parse_gainers_data(cells: list[ElementHandle]) -> dict | None:
    """Parse raw table cells into a typed gainer record.

    Yahoo Finance column layout (0-indexed):
      0: row number | 1: symbol+name (ticker on last line) | 2: name
      3: chart | 4: price | 5: change | 6: change% | 7: volume
      8: avg vol 3m | 9: market cap | 10: PE ratio
    """
    def cell_text(idx: int) -> str:
        return cells[idx].inner_text().strip() if idx < len(cells) else ""

    # Ticker is on the last line of the combined symbol+name cell
    symbol_raw = cell_text(1)
    symbol = symbol_raw.split('\n')[-1].strip()
    if not symbol:
        return None

    return {
        "symbol": symbol,
        "name": cell_text(2),
        "price_intraday": parse_number(cell_text(4)),
        "change_absolute": parse_number(cell_text(5)),
        "change_percentage": parse_number(cell_text(6)),
        "volume": parse_volume(cell_text(7)),
        "avg_vol_3m": parse_volume(cell_text(8)),
        "market_cap": parse_volume(cell_text(9)),
        "pe_ratio": parse_number(cell_text(10)),
    }