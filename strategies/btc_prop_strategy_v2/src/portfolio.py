"""Multi-asset Donchian portfolio: shared equity pool, concurrent positions per asset.

Rationale (MC finding): single-asset BTC drawdown risk forces risk/trade down to
~0.35-0.5% to keep P(hit -10% firm limit) acceptable, capping CAGR at 7-10%.
Diversifying across imperfectly-correlated crypto majors should lower portfolio
drawdown for the same per-trade risk, raising the survivable risk ceiling.

Each asset trades the same validated rules (Donchian 20 / ATR-trail 2.5 / trend
filter). Position sizing is risk% of *shared* current equity per position.
"""
import numpy as np
import pandas as pd

from .donchian import DonchianParams, prepare


def run_portfolio(dfs: dict[str, pd.DataFrame], p: DonchianParams,
                  initial_equity: float = 50000.0,
                  max_concurrent: int | None = None) -> dict:
    prepped = {sym: prepare(df, p).set_index("date") for sym, df in dfs.items()}
    all_dates = sorted(set().union(*[set(d.index) for d in prepped.values()]))

    equity = initial_equity
    positions: dict[str, dict] = {}
    trades, curve = [], []
    fees = lambda notional: notional * (p.fee_pct + p.slip_pct) / 100

    prev_row = {}
    for date in all_dates:
        # manage open positions
        for sym in list(positions):
            if date not in prepped[sym].index:
                continue
            row = prepped[sym].loc[date]
            pos = positions[sym]
            exit_price = None
            if pos["direction"] == 1 and row["low"] <= pos["stop"]:
                exit_price = min(pos["stop"], row["open"])
            elif pos["direction"] == -1 and row["high"] >= pos["stop"]:
                exit_price = max(pos["stop"], row["open"])
            if exit_price is not None:
                pnl = (exit_price - pos["entry"]) * pos["units"] * pos["direction"]
                pnl -= fees(exit_price * pos["units"])
                equity += pnl
                trades.append({"sym": sym, "dir": pos["direction"], "entry": pos["entry"],
                               "exit": exit_price, "pnl": pnl, "entry_eq": pos["entry_eq"],
                               "entry_date": pos["entry_date"], "exit_date": date})
                del positions[sym]
            else:
                if pos["direction"] == 1:
                    pos["stop"] = max(pos["stop"], row["close"] - p.trail_atr_mult * row["atr"])
                else:
                    pos["stop"] = min(pos["stop"], row["close"] + p.trail_atr_mult * row["atr"])

        # entries
        for sym, pdf in prepped.items():
            if sym in positions or date not in pdf.index:
                continue
            if max_concurrent and len(positions) >= max_concurrent:
                break
            prev = prev_row.get(sym)
            if prev is None or np.isnan(prev.get("atr", np.nan)) or np.isnan(prev.get("don_high", np.nan)):
                continue
            row = pdf.loc[date]
            bull = (not p.daily_filter) or prev["close"] > prev["trend_ema"]
            bear = (not p.daily_filter) or prev["close"] < prev["trend_ema"]
            direction = 0
            if prev["close"] > prev["don_high"] and bull:
                direction = 1
            elif prev["close"] < prev["don_low"] and bear:
                direction = -1
            if direction:
                entry = row["open"]
                stop_dist = p.trail_atr_mult * prev["atr"]
                units = (equity * p.risk_per_trade_pct / 100) / stop_dist
                units = min(units, equity * p.max_leverage / entry)
                if units > 0:
                    equity -= fees(entry * units)
                    positions[sym] = {"direction": direction, "entry": entry, "units": units,
                                      "stop": entry - direction * stop_dist,
                                      "entry_date": date, "entry_eq": equity}

        for sym, pdf in prepped.items():
            if date in pdf.index:
                prev_row[sym] = pdf.loc[date]
        curve.append((date, equity))

    eq = pd.DataFrame(curve, columns=["date", "equity"])
    return _metrics(trades, eq, initial_equity)


def _metrics(trades, eq, initial_equity, ppy=365 * 6):
    if eq.empty or not trades:
        return {"sharpe": 0.0, "cagr_pct": 0.0, "max_dd_pct": 0.0, "trades": 0,
                "equity": eq, "trade_list": trades}
    eq = eq.copy()
    eq["ret"] = eq["equity"].pct_change()
    sharpe = eq["ret"].mean() / eq["ret"].std() * np.sqrt(ppy) if eq["ret"].std() > 0 else 0.0
    peak = eq["equity"].cummax()
    max_dd = ((eq["equity"] - peak) / peak).min() * 100
    years = len(eq) / ppy
    total = eq["equity"].iloc[-1] / initial_equity
    tdf = pd.DataFrame(trades)
    wins, losses = tdf[tdf.pnl > 0].pnl.sum(), -tdf[tdf.pnl <= 0].pnl.sum()
    return {
        "sharpe": round(float(sharpe), 3),
        "cagr_pct": round((total ** (1 / years) - 1) * 100, 2) if years > 0 else 0.0,
        "total_return_pct": round((total - 1) * 100, 2),
        "max_dd_pct": round(float(max_dd), 2),
        "win_rate_pct": round((tdf.pnl > 0).mean() * 100, 1),
        "trades": len(tdf),
        "profit_factor": round(wins / losses, 2) if losses > 0 else float("inf"),
        "equity": eq, "trade_list": trades,
    }
