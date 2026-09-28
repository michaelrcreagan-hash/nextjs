"""Daily-bar backtester for btc_prop_strategy_v2.

Event loop over daily bars. Signals from bar t close execute at bar t+1 open.
Fees: taker both sides + slippage. One position per sub-strategy max.
Prop-firm internal buffers enforced via RiskManager.

Simplifications vs full spec (documented in PLAN.md): single TP at rr_ratio
instead of 50/30/20 scale-out; Funding Farmer stubbed (no data).
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd

from .indicators import enrich
from .substrategies import trend_rider_signals, range_hunter_signals, dcb_signals
from .risk import RiskConfig, RiskManager


@dataclass
class Position:
    strat: str          # 'tr' | 'rh' | 'dcb'
    direction: int      # 1 long, -1 short
    entry_price: float
    units: float
    stop: float
    target: float | None
    trail_mult: float | None  # ATR trailing multiple (trend rider)
    entry_date: object


def _fees(notional: float, fee_pct: float, slip_pct: float) -> float:
    return notional * (fee_pct + slip_pct) / 100


def run_backtest(df_raw: pd.DataFrame, params: dict, fees_cfg: dict,
                 risk_cfg: RiskConfig, initial_equity: float = 50000.0,
                 adx_threshold: float | None = None,
                 rsi_oversold: float | None = None,
                 trail_mult: float | None = None,
                 periods_per_year: int = 365) -> dict:
    p = {k: (dict(v) if isinstance(v, dict) else v) for k, v in params.items()}
    tr_cfg, rh_cfg = p["trend_rider"], p["range_hunter"]
    if adx_threshold is not None:
        tr_cfg["adx_threshold"] = adx_threshold
    if rsi_oversold is not None:
        rh_cfg["rsi_oversold"] = rsi_oversold
        rh_cfg["rsi_overbought"] = 100 - rsi_oversold
    if trail_mult is None:
        trail_mult = tr_cfg["trailing_atr_multiple"]

    df = enrich(df_raw, p)
    sig = pd.concat([
        trend_rider_signals(df, tr_cfg["adx_threshold"]),
        range_hunter_signals(df, rh_cfg["rsi_oversold"], rh_cfg["rsi_overbought"],
                             rh_cfg["adx_max"], rh_cfg["confirmation"]["volume_spike_multiple"]),
        dcb_signals(df),
    ], axis=1)

    fee_pct, slip_pct = fees_cfg["taker"], fees_cfg["slippage"]
    rr = 2.5  # take_profit rr_ratio from config
    rm = RiskManager(risk_cfg, initial_equity)
    positions: dict[str, Position] = {}
    trades, equity_curve = [], []
    last_date = None

    for i in range(1, len(df)):
        row_prev, row = df.iloc[i - 1], df.iloc[i]
        sig_prev = sig.iloc[i - 1]
        date = row["date"]
        if last_date is None or date.date() != last_date:
            rm.new_day(date)
            last_date = date.date()

        # ── manage open positions on today's bar ──
        for key in list(positions):
            pos = positions[key]
            exit_price, reason = None, None
            if pos.direction == 1:
                if row["low"] <= pos.stop:
                    exit_price, reason = pos.stop, "stop"
                elif pos.target and row["high"] >= pos.target:
                    exit_price, reason = pos.target, "target"
            else:
                if row["high"] >= pos.stop:
                    exit_price, reason = pos.stop, "stop"
                elif pos.target and row["low"] <= pos.target:
                    exit_price, reason = pos.target, "target"

            # signal exits (evaluated on prev close, executed at today's open)
            if exit_price is None:
                sig_exit = (
                    (pos.strat == "tr" and ((pos.direction == 1 and sig_prev["tr_long_exit"]) or
                                            (pos.direction == -1 and sig_prev["tr_short_exit"]))) or
                    (pos.strat == "rh" and ((pos.direction == 1 and sig_prev["rh_long_exit"]) or
                                            (pos.direction == -1 and sig_prev["rh_short_exit"]))) or
                    (pos.strat == "dcb" and sig_prev["dcb_regime_exit"])
                )
                if sig_exit:
                    exit_price, reason = row["open"], "signal"

            if exit_price is not None:
                pnl = (exit_price - pos.entry_price) * pos.units * pos.direction
                pnl -= _fees(exit_price * pos.units, fee_pct, slip_pct)
                rm.record_pnl(pnl, date)
                rm.closed()
                trades.append({"strat": pos.strat, "dir": pos.direction,
                               "entry": pos.entry_price, "exit": exit_price,
                               "pnl": pnl, "reason": reason,
                               "entry_date": pos.entry_date, "exit_date": date})
                del positions[key]
                continue

            # trailing stop update (trend rider)
            if pos.strat == "tr" and pos.trail_mult and not np.isnan(row["atr"]):
                if pos.direction == 1:
                    pos.stop = max(pos.stop, row["close"] - pos.trail_mult * row["atr"])
                else:
                    pos.stop = min(pos.stop, row["close"] + pos.trail_mult * row["atr"])

        # ── entries at today's open from yesterday's signals ──
        if not np.isnan(row_prev["atr"]):
            atr_v = row_prev["atr"]
            entries = []
            if "tr" not in positions:
                if sig_prev["tr_long_entry"]:
                    entries.append(("tr", 1, trail_mult * atr_v, None, trail_mult))
                elif sig_prev["tr_short_entry"]:
                    entries.append(("tr", -1, trail_mult * atr_v, None, trail_mult))
            if "rh" not in positions:
                if sig_prev["rh_long_entry"]:
                    entries.append(("rh", 1, rh_cfg["atr_stop_multiple"] * atr_v, None, None))
                elif sig_prev["rh_short_entry"]:
                    entries.append(("rh", -1, rh_cfg["atr_stop_multiple"] * atr_v, None, None))
            if "dcb" not in positions and sig_prev["dcb_short_entry"]:
                entries.append(("dcb", -1, 1.5 * atr_v, sig_prev["dcb_bounce_pct"], None))

            for strat, direction, stop_dist, extra, tmult in entries:
                if not rm.can_open():
                    break
                entry_price = row["open"]
                stop = entry_price - direction * stop_dist
                units = rm.size_position(entry_price, stop)
                if units <= 0:
                    continue
                if strat == "dcb":
                    # target: 38.2% retrace of the bounce below entry
                    bounce_range = entry_price * (extra / 100) / (1 + extra / 100)
                    target = entry_price - 0.382 * bounce_range - stop_dist  # extend through prior low
                elif strat == "rh":
                    target = entry_price + direction * rh_cfg["rr_min"] * stop_dist
                else:
                    target = None if tmult else entry_price + direction * rr * stop_dist
                cost = _fees(entry_price * units, fee_pct, slip_pct)
                rm.record_pnl(-cost, date)
                positions[strat] = Position(strat, direction, entry_price, units,
                                            stop, target, tmult, date)
                rm.opened()

        equity_curve.append({"date": date, "equity": rm.s.equity})
        if rm.s.halted_total:
            break

    return _metrics(trades, equity_curve, initial_equity, rm, periods_per_year)


def _metrics(trades, equity_curve, initial_equity, rm, periods_per_year=365) -> dict:
    eq = pd.DataFrame(equity_curve)
    if eq.empty or not trades:
        return {"sharpe": 0.0, "total_return_pct": 0.0, "max_dd_pct": 0.0,
                "win_rate_pct": 0.0, "trades": 0, "profit_factor": 0.0,
                "halted": rm.s.halted_total, "breaches": rm.s.breach_log,
                "trade_list": [], "equity": eq}
    eq["ret"] = eq["equity"].pct_change()
    sharpe = eq["ret"].mean() / eq["ret"].std() * np.sqrt(periods_per_year) if eq["ret"].std() > 0 else 0.0
    peak = eq["equity"].cummax()
    max_dd = ((eq["equity"] - peak) / peak).min() * 100
    tdf = pd.DataFrame(trades)
    wins = tdf[tdf["pnl"] > 0]["pnl"].sum()
    losses = -tdf[tdf["pnl"] <= 0]["pnl"].sum()
    return {
        "sharpe": round(float(sharpe), 3),
        "total_return_pct": round((eq["equity"].iloc[-1] / initial_equity - 1) * 100, 2),
        "max_dd_pct": round(float(max_dd), 2),
        "win_rate_pct": round((tdf["pnl"] > 0).mean() * 100, 1),
        "trades": len(tdf),
        "profit_factor": round(wins / losses, 2) if losses > 0 else float("inf"),
        "halted": rm.s.halted_total,
        "breaches": rm.s.breach_log,
        "trade_list": trades,
        "equity": eq,
    }


def walk_forward_windows(df: pd.DataFrame, n_windows: int = 5, oos_frac: float = 0.25):
    """Expanding-window walk-forward splits: yields (train_df, test_df)."""
    n = len(df)
    test_len = int(n * oos_frac / n_windows)
    first_train_end = n - n_windows * test_len
    for w in range(n_windows):
        train_end = first_train_end + w * test_len
        test_end = train_end + test_len
        yield df.iloc[:train_end].reset_index(drop=True), df.iloc[train_end:test_end].reset_index(drop=True)
