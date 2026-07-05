"""Crypto desk daily update: algo trader signal + investor lens.

Crypto trades seven days a week, so this section appears in EVERY
morning report (weekends included), unlike the equity ledger which
only ticks on trading days.

Two mechanical views per asset, mirroring the two LLM agents:

  Algo trader  - the walk-forward validated Turtle dual-system
                 (crypto_algo.py params): composite score, signal,
                 entry/stop/target per the N-based rules.
  Investor     - long-horizon cycle lens: trend vs 200DMA, drawdown
                 from ATH, extension, 1y return -> ACCUMULATE / HOLD /
                 TRIM / WAIT zone classification.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

from .crypto_algo import (
    CryptoParams,
    composite_score,
    compute_indicators,
    target_units,
)
from .data import DATA_DIR

CRYPTO_SYMBOLS = ["BTCUSD", "ETHUSD"]


def load_crypto(sym: str, data_dir: str = DATA_DIR) -> pd.DataFrame | None:
    """Prefer the *_full.csv OHLCV file; fall back to the plain cache if it
    carries OHLC columns (fetch_data writes full bars for crypto too)."""
    for name in (f"{sym}_full.csv", f"{sym}.csv"):
        path = os.path.join(data_dir, name)
        if os.path.exists(path):
            df = (
                pd.read_csv(path, parse_dates=["date"])
                .set_index("date")
                .sort_index()
            )
            if {"high", "low", "close", "volume"}.issubset(df.columns):
                return df[~df.index.duplicated(keep="last")]
    return None


def algo_update(df: pd.DataFrame, params: CryptoParams | None = None) -> dict:
    p = params or CryptoParams()
    ind = compute_indicators(df, p)
    row = ind.iloc[-1]
    close, atr, adx = row["close"], row["atr"], row["adx"]
    score, system = composite_score(row, p)
    vetoed = bool(adx < p.adx_veto)
    units = 0 if vetoed else target_units(score, p)

    if vetoed:
        signal = "VETO — ADX below 20, no breakout trades in a dead-trend regime"
    elif score >= p.strong_score:
        signal = "STRONG BUY"
    elif score >= p.buy_score:
        signal = "BUY"
    elif score >= p.weak_score:
        signal = "WEAK BUY"
    elif score <= -p.strong_score:
        signal = "STRONG SELL"
    elif score <= -p.buy_score:
        signal = "SELL"
    elif score <= -p.weak_score:
        signal = "WEAK SELL"
    else:
        signal = "HOLD"

    out = {
        "close": float(close),
        "score": int(score),
        "system": system,
        "adx": float(adx),
        "vetoed": vetoed,
        "signal": signal,
        "units": int(units),
        "n_atr": float(atr),
    }
    if units > 0 and not vetoed and score > 0:
        out["entry"] = float(close)
        out["stop"] = float(close - p.stop_n * atr)
        out["pyramid_at"] = float(close + p.pyramid_step_n * atr)
    return out


def investor_update(df: pd.DataFrame) -> dict:
    close = df["close"]
    last = float(close.iloc[-1])
    ma200 = float(close.rolling(200).mean().iloc[-1])
    ma50 = float(close.rolling(50).mean().iloc[-1])
    ath = float(close.max())
    dd_from_ath = last / ath - 1
    ret_1y = last / float(close.iloc[-365]) - 1 if len(close) > 365 else np.nan
    ext_200 = last / ma200 - 1

    # Cycle-zone classification mirroring the crypto_investor framework:
    # deep-value accumulation in bear troughs, hold the uptrend, trim
    # cycle-top extension, wait out downtrends that aren't cheap yet.
    if last < ma200 and dd_from_ath <= -0.50:
        zone = "ACCUMULATE"
        note = "deep-value zone: below 200DMA with >50% drawdown from ATH"
    elif last < ma200:
        zone = "WAIT"
        note = "downtrend but not deep value yet — stage in slowly or wait"
    elif ext_200 >= 0.40:
        zone = "TRIM"
        note = "extended >40% above 200DMA — cycle-top territory, take profits"
    else:
        zone = "HOLD"
        note = "uptrend intact, not extended — hold core position"

    return {
        "close": last,
        "ma200": ma200,
        "ma50": ma50,
        "vs_200dma": ext_200,
        "dd_from_ath": dd_from_ath,
        "ret_1y": ret_1y,
        "zone": zone,
        "note": note,
    }


def crypto_report_lines(data_dir: str = DATA_DIR) -> list[str]:
    """Markdown section for the morning report. Runs every day."""
    lines = ["", "## Crypto desk", ""]
    any_data = False
    for sym in CRYPTO_SYMBOLS:
        df = load_crypto(sym, data_dir)
        if df is None or len(df) < 250:
            lines.append(f"_{sym}: no OHLCV data cached_")
            continue
        any_data = True
        a = algo_update(df)
        v = investor_update(df)
        name = sym.replace("USD", "")
        lines.append(f"### {name} — ${a['close']:,.0f}")
        lines.append("")
        algo_line = (
            f"**Algo trader:** {a['signal']} (score {a['score']:+d}, "
            f"ADX {a['adx']:.0f}"
            + (f", {a['system']} breakout" if a["system"] else "")
            + ")"
        )
        if "entry" in a:
            algo_line += (
                f" — entry {a['entry']:,.0f}, stop {a['stop']:,.0f} (1.5N), "
                f"{a['units']} unit(s), pyramid at {a['pyramid_at']:,.0f}"
            )
        lines.append(algo_line)
        ret1y = f"{v['ret_1y'] * 100:+.0f}%" if np.isfinite(v["ret_1y"]) else "n/a"
        lines.append(
            f"**Investor:** {v['zone']} — {v['note']} "
            f"(vs 200DMA {v['vs_200dma'] * 100:+.0f}%, "
            f"off ATH {v['dd_from_ath'] * 100:.0f}%, 1y {ret1y})"
        )
        lines.append("")
    if not any_data:
        lines.append("_no crypto data available — run fetch_data_")
    return lines
