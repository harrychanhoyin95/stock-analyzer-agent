import json
import os
import tempfile

import matplotlib
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from langchain_core.tools import tool

matplotlib.use("Agg")


@tool
def generate_chart(data: str, chart_type: str, title: str) -> dict:
    """Generate a stock chart image and save it to a temp file.

    Call this tool before send_email when the user wants a chart attached.
    Pass the output chart_path directly to send_email's chart_path argument.

    Args:
        data: JSON string in the same shape as get_stock_history output.
              Must contain a 'data' key mapping date strings to OHLCV dicts.
        chart_type: 'line' for a closing price line chart,
                    'candlestick' for an OHLC candlestick chart.
        title: Chart title string (e.g. 'AAPL 1-Month Close Price').

    Returns:
        Dict with 'chart_path' (path to the PNG file) on success,
        or 'error' on failure.
    """
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as e:
        return {"error": f"invalid data JSON: {e}"}

    ohlcv = parsed.get("data")
    if not ohlcv:
        return {"error": "data JSON missing 'data' key"}

    dates = sorted(ohlcv.keys())
    if not dates:
        return {"error": "no data points found"}

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    chart_path = tmp.name
    tmp.close()

    try:
        if chart_type == "line":
            closes = [ohlcv[d]["close"] for d in dates]

            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(dates, closes, linewidth=1.5)
            ax.set_title(title)
            ax.set_xlabel("Date")
            ax.set_ylabel("Close Price (USD)")
            ax.tick_params(axis="x", rotation=45)
            plt.tight_layout()
            fig.savefig(chart_path, dpi=150)
            plt.close(fig)

        elif chart_type == "candlestick":
            df = pd.DataFrame(
                {
                    "Open": [ohlcv[d]["open"] for d in dates],
                    "High": [ohlcv[d]["high"] for d in dates],
                    "Low": [ohlcv[d]["low"] for d in dates],
                    "Close": [ohlcv[d]["close"] for d in dates],
                    "Volume": [ohlcv[d]["volume"] for d in dates],
                },
                index=pd.DatetimeIndex(dates),
            )
            mpf.plot(
                df,
                type="candle",
                title=title,
                ylabel="Price (USD)",
                savefig=chart_path,
                style="yahoo",
                figsize=(10, 5),
            )
            plt.close("all")

        else:
            if os.path.exists(chart_path):
                os.unlink(chart_path)
            return {"error": f"unknown chart_type '{chart_type}': use 'line' or 'candlestick'"}

    except Exception as e:
        if os.path.exists(chart_path):
            os.unlink(chart_path)
        return {"error": f"chart generation failed: {e}"}

    return {"chart_path": chart_path}
