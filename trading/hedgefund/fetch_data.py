"""Data ingest: populate hedgefund/data/*.csv with daily OHLCV.

Run anywhere with open internet access (the Claude Code sandbox blocks
finance hosts, so run this locally):

    cd trading && python -m hedgefund.fetch_data

Sources, tried in order per symbol:
  1. yfinance (no key needed)
  2. FMP stable API when FMP_API_KEY is set in the environment

Output CSV schema: date,open,high,low,close,volume — exactly what
``hedgefund.data.load_panel`` expects. Re-running refreshes in place.
"""

from __future__ import annotations

import os
import sys
import time

import pandas as pd

from .data import DATA_DIR
from .universe import ALL_SYMBOLS

START = "2019-01-01"

# cache alias -> vendor symbols
YF_SYMBOL = {"BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD", "VIX": "^VIX"}
FMP_SYMBOL = {"BTCUSD": "BTCUSD", "ETHUSD": "ETHUSD", "VIX": "^VIX"}

# Crypto desk assets fetched in addition to the equity universe. Their
# OHLCV also lands in <SYM>_full.csv, which the Turtle signals read.
CRYPTO_EXTRA = ["ETHUSD"]
CRYPTO_FULL_COPY = ["BTCUSD", "ETHUSD"]


def _drop_partial_bar(df: pd.DataFrame) -> pd.DataFrame:
    """Drop today's in-progress bar when running during market hours.

    The pre-open scheduled run must trade on the last COMPLETE session:
    yfinance includes a partial bar for the current NY date once trading
    starts, and indicators computed on it are garbage. Keep it only after
    the close (16:05 ET) when it is final.
    """
    from zoneinfo import ZoneInfo

    now_ny = pd.Timestamp.now(tz=ZoneInfo("America/New_York"))
    if df.empty:
        return df
    last_date = df["date"].iloc[-1]
    is_today = last_date.date() == now_ny.date()
    before_close = (now_ny.hour, now_ny.minute) < (16, 5)
    if is_today and before_close:
        return df.iloc[:-1]
    return df


def fetch_yfinance(symbol: str) -> pd.DataFrame | None:
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not installed (pip install yfinance)", file=sys.stderr)
        return None
    try:
        df = yf.Ticker(YF_SYMBOL.get(symbol, symbol)).history(
            start=START, auto_adjust=True
        )
        if df.empty:
            return None
        out = df.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
        out.columns = ["date", "open", "high", "low", "close", "volume"]
        out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None)
        return _drop_partial_bar(out)
    except Exception as e:
        print(f"  yfinance failed for {symbol}: {e}", file=sys.stderr)
        return None


def fetch_fmp(symbol: str) -> pd.DataFrame | None:
    api_key = os.environ.get("FMP_API_KEY")
    if not api_key:
        return None
    import requests

    url = (
        "https://financialmodelingprep.com/stable/historical-price-eod/full"
        f"?symbol={FMP_SYMBOL.get(symbol, symbol)}&from={START}&apikey={api_key}"
    )
    try:
        rows = requests.get(url, timeout=30).json()
        if not isinstance(rows, list) or not rows:
            return None
        df = pd.DataFrame(rows)[["date", "open", "high", "low", "close", "volume"]]
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date")
    except Exception as e:
        print(f"  FMP failed for {symbol}: {e}", file=sys.stderr)
        return None


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    ok, failed = [], []
    for sym in ALL_SYMBOLS + CRYPTO_EXTRA:
        print(f"fetching {sym} ...")
        df = fetch_yfinance(sym)
        if df is None:
            df = fetch_fmp(sym)
        if df is None or df.empty:
            failed.append(sym)
            continue
        df.to_csv(os.path.join(DATA_DIR, f"{sym}.csv"), index=False)
        if sym in CRYPTO_FULL_COPY:
            df.to_csv(os.path.join(DATA_DIR, f"{sym}_full.csv"), index=False)
        ok.append(sym)
        time.sleep(0.4)  # be polite to the API
    print(f"\ndone: {len(ok)} cached, {len(failed)} failed")
    if failed:
        print("failed symbols (late IPOs before listing date are expected):")
        print("  " + ", ".join(failed))


if __name__ == "__main__":
    main()
