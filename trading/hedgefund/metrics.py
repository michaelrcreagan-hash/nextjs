"""Performance metrics and benchmark comparison."""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2 or equity.iloc[0] <= 0:
        return np.nan
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0:
        return np.nan
    return (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1


def max_drawdown(equity: pd.Series) -> float:
    dd = equity / equity.cummax() - 1
    return float(dd.min())


def sharpe(equity: pd.Series) -> float:
    rets = equity.pct_change().dropna()
    if rets.std() == 0 or len(rets) < 2:
        return np.nan
    return float(rets.mean() / rets.std() * np.sqrt(TRADING_DAYS))


def sortino(equity: pd.Series) -> float:
    rets = equity.pct_change().dropna()
    downside = rets[rets < 0]
    if len(downside) < 2 or downside.std() == 0:
        return np.nan
    return float(rets.mean() / downside.std() * np.sqrt(TRADING_DAYS))


def mar(equity: pd.Series) -> float:
    dd = abs(max_drawdown(equity))
    c = cagr(equity)
    return c / dd if dd > 0 else np.nan


def trade_stats(trades: pd.DataFrame) -> dict:
    if trades is None or trades.empty:
        return {"n_trades": 0, "win_rate": np.nan, "profit_factor": np.nan}
    wins = trades[trades["pnl"] > 0]
    losses = trades[trades["pnl"] <= 0]
    gross_win = wins["pnl"].sum()
    gross_loss = abs(losses["pnl"].sum())
    return {
        "n_trades": len(trades),
        "win_rate": len(wins) / len(trades),
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else np.inf,
        "avg_win": wins["ret"].mean() if len(wins) else np.nan,
        "avg_loss": losses["ret"].mean() if len(losses) else np.nan,
    }


def summarize(name: str, equity: pd.Series, trades: pd.DataFrame | None = None) -> dict:
    out = {
        "strategy": name,
        "final_equity": float(equity.iloc[-1]),
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1),
        "cagr": cagr(equity),
        "sharpe": sharpe(equity),
        "sortino": sortino(equity),
        "max_dd": max_drawdown(equity),
        "mar": mar(equity),
    }
    if trades is not None:
        out.update(trade_stats(trades))
    return out


def buy_and_hold(close: pd.Series, start_equity: float = 100_000.0) -> pd.Series:
    close = close.dropna()
    return start_equity * close / close.iloc[0]


def comparison_table(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows).set_index("strategy")
    pct_cols = ["total_return", "cagr", "max_dd", "win_rate", "avg_win", "avg_loss"]
    for c in pct_cols:
        if c in df.columns:
            df[c] = (df[c] * 100).round(1)
    for c in ("sharpe", "sortino", "mar", "profit_factor"):
        if c in df.columns:
            df[c] = df[c].round(2)
    return df
