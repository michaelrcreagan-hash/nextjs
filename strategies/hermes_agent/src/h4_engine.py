"""
4H strategy engine -- indicators + Breakout prop simulator.

Implements the champion architecture from the author's ChatGPT research report
(Hermes_Optimal_Crypto_Prop_Strategies_Report, 2026-08-27):

    BTC 4H Keltner expansion breakout
      + MACD histogram confirmation
      + Kaufman Efficiency Ratio >= 0.30
      + ADX >= 25 and rising
      + EMA 21/50/200 structure
      + ATR volatility-regime gate (compression / normal / expansion / extreme)
      + 2 ATR stop, ATR-sized risk

...tested against the REAL Breakout rules, including the fact the author
confirmed 2026-08-27:

    THE STATIC DRAWDOWN FLOOR DOES NOT RESET AFTER A PAYOUT.

That single fact reframes the whole problem. A funded account is not a
compounding vehicle -- it is a FINITE RESOURCE with a fixed number of dollars
of loss in it, forever. Withdraw $18,000 and the balance returns to $200,000
but the floor stays at $194,000. Every payout cycle is played with the same
3% buffer, and one breach ends the account permanently. So the objective is
not geometric return; it is P(reach target before breach), repeated. The
expected number of payouts before ruin is p/(1-p), which is why a few points
of pass rate matter more than any amount of return optimization.

LOOKAHEAD DISCIPLINE
--------------------
Every indicator is computed on closed bars and then shifted one bar, so the
decision at bar t uses information through bar t-1 only. Entries fill at bar
t's OPEN (knowable), never at its close. Stops and targets fill intrabar using
the bar's high/low, with the conservative tie-break: if a bar's range spans
both the stop and the target, the STOP is assumed to fill first.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "Data" / "h4"

# Breakout leverage tiers (from the firm's published rules, per the report:
# BTC 10x; ETH + major liquid alts 5x; some 3x; remainder 2x).
LEVERAGE = {"BTC": 10.0, "ETH": 5.0, "SOL": 5.0, "XRP": 5.0,
            "DOGE": 3.0, "LINK": 3.0, "AVAX": 3.0, "LTC": 3.0}

# Breakout is a crypto prop firm on perps; use perp-style taker + slippage.
TAKER_PCT = 0.035
SLIP_BPS = 5.0

BARS_PER_DAY = 6            # 4H bars
BARS_PER_MONTH = 180


# ---------------------------------------------------------------- data ----

def load(symbols=None):
    """Returns {sym: dict of aligned float64 arrays} on a common timestamp grid."""
    files = sorted(DATA_DIR.glob("*_4h.csv"))
    if symbols:
        files = [f for f in files if f.stem.split("_")[0] in symbols]
    raw = {}
    for f in files:
        sym = f.stem.split("_")[0]
        rows = list(csv.DictReader(f.open()))
        raw[sym] = {int(r["ts"]): (float(r["open"]), float(r["high"]),
                                   float(r["low"]), float(r["close"]),
                                   float(r["volume"])) for r in rows}
    if not raw:
        raise SystemExit("no 4h data -- run fetch_4h_panel.py first")

    grid = sorted(set.intersection(*(set(v) for v in raw.values())))
    ts = np.array(grid, dtype=np.int64)
    out = {"ts": ts, "symbols": sorted(raw)}
    for k, i in (("open", 0), ("high", 1), ("low", 2), ("close", 3), ("volume", 4)):
        out[k] = np.ascontiguousarray(
            np.array([[raw[s][t][i] for s in out["symbols"]] for t in grid],
                     dtype=np.float64))
    return out


# ---------------------------------------------------------- indicators ----

def ema(a, span):
    """Column-wise EMA. NaN-free input assumed (the grid is an intersection)."""
    alpha = 2.0 / (span + 1.0)
    out = np.empty_like(a)
    out[0] = a[0]
    for t in range(1, a.shape[0]):
        out[t] = alpha * a[t] + (1 - alpha) * out[t - 1]
    return out


def true_range(high, low, close):
    tr = np.empty_like(close)
    tr[0] = high[0] - low[0]
    pc = close[:-1]
    tr[1:] = np.maximum(high[1:] - low[1:],
                        np.maximum(np.abs(high[1:] - pc), np.abs(low[1:] - pc)))
    return tr


def atr(high, low, close, n=14):
    return ema(true_range(high, low, close), n)


def efficiency_ratio(close, n=20):
    """
    Kaufman Efficiency Ratio: |net change| / sum(|bar changes|) over n bars.

    1.0 = a perfectly straight move, 0.0 = pure chop. The report specifies
    ER >= 0.30 for breakouts, which is the single most important filter in the
    architecture: breakouts fail in sideways markets, and ER is what detects
    sideways directly rather than by proxy.
    """
    n_bars = close.shape[0]
    out = np.full_like(close, np.nan)
    absdiff = np.abs(np.diff(close, axis=0))
    for t in range(n, n_bars):
        net = np.abs(close[t] - close[t - n])
        tot = absdiff[t - n:t].sum(axis=0)
        out[t] = np.where(tot > 0, net / tot, 0.0)
    return out


def adx(high, low, close, n=14):
    """Wilder ADX plus its slope, both column-wise."""
    up = np.zeros_like(close)
    dn = np.zeros_like(close)
    up[1:] = high[1:] - high[:-1]
    dn[1:] = low[:-1] - low[1:]
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr_n = ema(true_range(high, low, close), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100.0 * ema(plus_dm, n) / tr_n
        mdi = 100.0 * ema(minus_dm, n) / tr_n
        dx = 100.0 * np.abs(pdi - mdi) / np.maximum(pdi + mdi, 1e-12)
    a = ema(np.nan_to_num(dx), n)
    slope = np.zeros_like(a)
    slope[n:] = a[n:] - a[:-n]
    return a, slope


def macd_hist(close, fast=12, slow=26, signal=9):
    line = ema(close, fast) - ema(close, slow)
    return line - ema(line, signal)


def shift1(a):
    out = np.full_like(a, np.nan)
    out[1:] = a[:-1]
    return out


def build_indicators(d, keltner_n=16, keltner_mult=1.75, atr_n=14,
                     er_n=20, adx_n=14):
    """
    All indicators, each shifted one bar so bar t sees only <= t-1.

    Returns a dict of (n_bars, n_symbols) arrays.
    """
    c, h, l = d["close"], d["high"], d["low"]
    a = atr(h, l, c, atr_n)
    basis = ema(c, keltner_n)
    adx_v, adx_s = adx(h, l, c, adx_n)

    # Volatility regime: ATR14 vs its own 70-bar and 1-year baselines, exactly
    # the comparison the report's volatility engine specifies.
    atr_70 = ema(a, 70)
    atr_1y = ema(a, 6 * 365)

    return {
        "kelt_up": shift1(basis + keltner_mult * a),
        "kelt_dn": shift1(basis - keltner_mult * a),
        "kelt_mid": shift1(basis),
        "atr": shift1(a),
        "atr_ratio_70": shift1(a / np.maximum(atr_70, 1e-12)),
        "atr_ratio_1y": shift1(a / np.maximum(atr_1y, 1e-12)),
        "er": shift1(efficiency_ratio(c, er_n)),
        "adx": shift1(adx_v),
        "adx_slope": shift1(adx_s),
        "macd_h": shift1(macd_hist(c)),
        "ema21": shift1(ema(c, 21)),
        "ema50": shift1(ema(c, 50)),
        "ema200": shift1(ema(c, 200)),
        "prev_close": shift1(c),
    }


def vol_regime(ind):
    """
    0 compression, 1 normal, 2 expansion, 3 extreme.

    The report's mapping: compression -> wait; low-vol/normal -> trend
    pullback; expansion -> breakout engine; extreme -> usually flat.
    Breakouts are only permitted in EXPANSION, which is the whole point of
    gating them: a Keltner break during compression is noise.
    """
    r70, r1y = ind["atr_ratio_70"], ind["atr_ratio_1y"]
    reg = np.full(r70.shape, 1, dtype=np.int8)
    reg[r70 < 0.85] = 0
    reg[(r70 > 1.15) & (r1y > 1.0)] = 2
    reg[(r1y > 1.6)] = 3
    reg[np.isnan(r70)] = 1
    return reg


# ------------------------------------------------------------- signals ----

def signals(d, ind, er_min=0.30, adx_min=25.0, require_adx_rising=True,
            require_macd=True, require_ema_stack=True,
            allow_short=True, engine="keltner"):
    """
    Returns (n_bars, n_symbols) int8: +1 long, -1 short, 0 flat.

    engine:
      "keltner"  -- expansion breakout through the Keltner band (champion)
      "pullback" -- EMA trend + pullback to EMA21 (report's #2, normal vol)
      "donchian" -- N-bar high/low breakout (report's #4 challenger benchmark)
    """
    c, h, l = d["close"], d["high"], d["low"]
    pc = ind["prev_close"]
    reg = vol_regime(ind)
    sig = np.zeros(c.shape, dtype=np.int8)

    quality = (ind["er"] >= er_min) & (ind["adx"] >= adx_min)
    if require_adx_rising:
        quality &= ind["adx_slope"] > 0
    quality &= ~np.isnan(ind["er"]) & ~np.isnan(ind["adx"])

    stack_long = ind["ema21"] > ind["ema50"]
    stack_short = ind["ema21"] < ind["ema50"]
    if require_ema_stack:
        stack_long &= ind["ema50"] > ind["ema200"]
        stack_short &= ind["ema50"] < ind["ema200"]

    macd_long = ind["macd_h"] > 0 if require_macd else np.ones_like(c, bool)
    macd_short = ind["macd_h"] < 0 if require_macd else np.ones_like(c, bool)

    if engine == "keltner":
        # Breakout only in the EXPANSION regime -- the gate that separates a
        # real expansion from a compression-phase false break.
        ok = reg == 2
        long_sig = ok & (pc > ind["kelt_up"]) & quality & stack_long & macd_long
        short_sig = ok & (pc < ind["kelt_dn"]) & quality & stack_short & macd_short
    elif engine == "pullback":
        # Normal / low volatility: buy the pullback INTO the EMA21 within an
        # intact trend, rather than chasing a band break.
        ok = (reg == 1) | (reg == 0)
        near21 = np.abs(pc - ind["ema21"]) < 0.5 * ind["atr"]
        long_sig = ok & near21 & (pc > ind["ema50"]) & quality & stack_long & macd_long
        short_sig = ok & near21 & (pc < ind["ema50"]) & quality & stack_short & macd_short
    elif engine == "donchian":
        n = 20
        hi = np.full_like(c, np.nan)
        lo = np.full_like(c, np.nan)
        for t in range(n + 1, c.shape[0]):
            hi[t] = h[t - n:t].max(axis=0)
            lo[t] = l[t - n:t].min(axis=0)
        long_sig = (pc > shift1(hi)) & quality & stack_long
        short_sig = (pc < shift1(lo)) & quality & stack_short
    else:
        raise ValueError(engine)

    sig[np.nan_to_num(long_sig, nan=0).astype(bool)] = 1
    if allow_short:
        sig[np.nan_to_num(short_sig, nan=0).astype(bool)] = -1
    return sig


# ------------------------------------------------------- prop simulator ----

def simulate(d, ind, sig, profile, risk_pct=0.5, atr_stop=2.0, rr=2.0,
             max_concurrent=3, start_bar=0, internal_daily_pct=1.5,
             trail_after_r=None, max_bars_held=90):
    """
    One prop run under the REAL Breakout rules.

    profile: dict(account, target_usd, max_dd_usd, daily_loss_pct)

    `internal_daily_pct` is the report's most important risk control and it is
    NOT the firm's limit: Breakout allows 3%, Hermes stops itself at 1.0-1.5%.
    Stopping voluntarily well short of the hard limit is what keeps a bad day
    from becoming a dead account -- the firm's limit is a cliff, not a target.
    """
    n, m = d["close"].shape
    acct = profile["account"]
    target = acct + profile["target_usd"]
    floor = acct - profile["max_dd_usd"]           # STATIC, never resets
    hard_daily = profile["daily_loss_pct"] / 100.0

    op, hi, lo, cl = d["open"], d["high"], d["low"], d["close"]
    lev = np.array([LEVERAGE.get(s, 2.0) for s in d["symbols"]])
    cost_rate = TAKER_PCT / 100.0 + SLIP_BPS / 10000.0

    equity = acct
    day_anchor = acct
    day_bar0 = start_bar
    day_locked = False
    pos = {}                                        # sym_idx -> dict
    trades = []
    outcome, out_bar = "open", None

    for t in range(start_bar, n):
        # New trading day at the 00:00 UTC boundary (Breakout resets 00:30).
        if (t - day_bar0) >= BARS_PER_DAY:
            day_bar0 = t
            day_anchor = equity + sum(
                p["dir"] * p["units"] * (cl[t - 1, j] - p["entry"])
                for j, p in pos.items())
            day_locked = False

        # ---- exits: intrabar, stop-first tie-break ----
        for j in list(pos):
            p = pos[j]
            dirn = p["dir"]
            hit_stop = (lo[t, j] <= p["stop"]) if dirn == 1 else (hi[t, j] >= p["stop"])
            hit_tp = (hi[t, j] >= p["tp"]) if dirn == 1 else (lo[t, j] <= p["tp"])
            timeout = (t - p["bar"]) >= max_bars_held
            if not (hit_stop or hit_tp or timeout):
                # Trail to breakeven once the trade is +trail_after_r.
                if trail_after_r is not None and not p["trailed"]:
                    mfe = dirn * (cl[t, j] - p["entry"]) / p["risk_px"]
                    if mfe >= trail_after_r:
                        p["stop"] = p["entry"]
                        p["trailed"] = True
                continue
            fill = p["stop"] if hit_stop else (p["tp"] if hit_tp else cl[t, j])
            gross = p["units"] * fill
            cost = gross * cost_rate
            pnl = dirn * p["units"] * (fill - p["entry"]) - cost - p["entry_cost"]
            equity += pnl
            trades.append({"sym": d["symbols"][j], "dir": dirn, "pnl": pnl,
                           "r": pnl / max(p["risk_usd"], 1e-9),
                           "reason": "sl" if hit_stop else ("tp" if hit_tp else "time"),
                           "bars": t - p["bar"], "bar": t})
            del pos[j]

        # ---- mark to market (floating P&L counts toward every limit) ----
        marked = equity + sum(
            p["dir"] * p["units"] * (cl[t, j] - p["entry"]) for j, p in pos.items())

        if marked >= target:
            outcome, out_bar = "PASS", t
            break
        if marked <= floor:
            outcome, out_bar = "breach_dd", t
            break
        if marked <= day_anchor * (1 - hard_daily):
            outcome, out_bar = "breach_daily", t
            break

        # Internal (self-imposed) daily stop: flatten and stand down for the
        # rest of the day. This is the control that keeps the hard limit from
        # ever being reached.
        if not day_locked and marked <= day_anchor * (1 - internal_daily_pct / 100.0):
            for j in list(pos):
                p = pos[j]
                gross = p["units"] * cl[t, j]
                cost = gross * cost_rate
                pnl = p["dir"] * p["units"] * (cl[t, j] - p["entry"]) - cost - p["entry_cost"]
                equity += pnl
                trades.append({"sym": d["symbols"][j], "dir": p["dir"], "pnl": pnl,
                               "r": pnl / max(p["risk_usd"], 1e-9),
                               "reason": "internal_stop", "bars": t - p["bar"],
                               "bar": t})
                del pos[j]
            day_locked = True

        # ---- entries: fill at THIS bar's open, on a signal from <= t-1 ----
        if not day_locked and len(pos) < max_concurrent and t + 1 < n:
            for j in range(m):
                if len(pos) >= max_concurrent or j in pos or sig[t, j] == 0:
                    continue
                a = ind["atr"][t, j]
                if not np.isfinite(a) or a <= 0:
                    continue
                entry = op[t, j]
                dirn = int(sig[t, j])
                risk_px = a * atr_stop
                risk_usd = marked * (risk_pct / 100.0)
                units = risk_usd / risk_px
                # Leverage is an exposure CEILING, not a sizing input.
                cap = marked * lev[j] / max_concurrent
                if units * entry > cap:
                    units = cap / entry
                    risk_usd = units * risk_px
                ec = units * entry * cost_rate
                equity -= ec
                pos[j] = {"dir": dirn, "entry": entry, "units": units,
                          "stop": entry - dirn * risk_px,
                          "tp": entry + dirn * risk_px * rr,
                          "risk_px": risk_px, "risk_usd": risk_usd,
                          "entry_cost": ec, "bar": t, "trailed": False}

    final = equity + sum(
        p["dir"] * p["units"] * (cl[min(out_bar or n - 1, n - 1), j] - p["entry"])
        for j, p in pos.items())
    return {"outcome": outcome, "bar": out_bar, "trades": trades,
            "final": final, "bars": (out_bar or n) - start_bar}
