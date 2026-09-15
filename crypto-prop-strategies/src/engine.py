"""
Core engine: indicators, signals, and a Breakout-prop account simulator.

Four strategies are optimized independently in this project:

    BTC long    |    BTC short
    ALT long    |    ALT short

They are separated because there is no reason to assume they share
parameters, and every prior result in this line of work suggests they do not.
BTC has 10:1 leverage on Breakout against 2-5:1 for alts, it carries the
market's beta rather than expressing a view against it, and crypto's up and
down moves have different shapes -- downside is faster and more violent, so a
short's stop and target should not automatically mirror a long's.

PROP RULES (Breakout, confirmed):
    Classic eval   $10,000  target $1,000 (10%)  maxDD $600 (6%)    daily 3%
    Turbo funded  $200,000  target $18,000 (9%)  maxDD $6,000 (3%)  daily 3%

The drawdown is STATIC and DOES NOT RESET AFTER A PAYOUT. A funded account
therefore holds a fixed number of dollars of loss, permanently -- it is a
finite resource, not a compounding vehicle. The objective is P(reach target
before breach), and expected payouts before ruin is p/(1-p).

LOOKAHEAD: every indicator is shifted one bar, so the decision at bar t uses
data through t-1. Entries fill at bar t's OPEN. Exits fill intrabar off the
bar's high/low, and when a bar's range spans both the stop and the target the
STOP is assumed to fill first.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data" / "h4"

BTC = ["BTC"]
ALTS = ["ETH", "SOL", "XRP", "DOGE", "LINK", "AVAX", "LTC"]

# Breakout's published leverage tiers.
LEVERAGE = {"BTC": 10.0, "ETH": 5.0, "SOL": 5.0, "XRP": 5.0,
            "DOGE": 3.0, "LINK": 3.0, "AVAX": 3.0, "LTC": 3.0}

TAKER_PCT = 0.035          # perp taker
SLIP_BPS = 5.0
BARS_PER_DAY = 6           # 4H
BARS_PER_MONTH = 180

PROFILES = {
    "classic_10k": dict(account=10_000.0, target_usd=1_000.0,
                        max_dd_usd=600.0, daily_loss_pct=3.0),
    "turbo_200k": dict(account=200_000.0, target_usd=18_000.0,
                       max_dd_usd=6_000.0, daily_loss_pct=3.0),
}


# ------------------------------------------------------------------ data --

def load(symbols):
    raw = {}
    for s in symbols:
        f = DATA / f"{s}_4h.csv"
        raw[s] = {int(r["ts"]): (float(r["open"]), float(r["high"]),
                                 float(r["low"]), float(r["close"]),
                                 float(r["volume"]))
                  for r in csv.DictReader(f.open())}
    grid = sorted(set.intersection(*(set(v) for v in raw.values())))
    d = {"ts": np.array(grid, dtype=np.int64), "symbols": list(symbols)}
    for k, i in (("open", 0), ("high", 1), ("low", 2), ("close", 3), ("volume", 4)):
        d[k] = np.ascontiguousarray(
            np.array([[raw[s][t][i] for s in d["symbols"]] for t in grid],
                     dtype=np.float64))
    return d


def load_with_btc_context(symbols):
    """
    Alt panels still need BTC to compute market context (regime, relative
    strength), so BTC is loaded alongside and returned separately rather than
    being made tradeable.
    """
    d = load(list(symbols) + (["BTC"] if "BTC" not in symbols else []))
    bi = d["symbols"].index("BTC")
    btc_close = d["close"][:, bi].copy()
    if "BTC" not in symbols:
        keep = [i for i, s in enumerate(d["symbols"]) if s != "BTC"]
        for k in ("open", "high", "low", "close", "volume"):
            d[k] = np.ascontiguousarray(d[k][:, keep])
        d["symbols"] = [d["symbols"][i] for i in keep]
    d["btc_close"] = btc_close
    return d


# ------------------------------------------------------------ indicators --

def ema(a, span):
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


def efficiency_ratio(close, n=20):
    out = np.full_like(close, np.nan)
    ad = np.abs(np.diff(close, axis=0))
    for t in range(n, close.shape[0]):
        tot = ad[t - n:t].sum(axis=0)
        out[t] = np.where(tot > 0, np.abs(close[t] - close[t - n]) / tot, 0.0)
    return out


def adx(high, low, close, n=14):
    up = np.zeros_like(close); dn = np.zeros_like(close)
    up[1:] = high[1:] - high[:-1]
    dn[1:] = low[:-1] - low[1:]
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    trn = ema(true_range(high, low, close), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100.0 * ema(pdm, n) / trn
        mdi = 100.0 * ema(mdm, n) / trn
        dx = 100.0 * np.abs(pdi - mdi) / np.maximum(pdi + mdi, 1e-12)
    a = ema(np.nan_to_num(dx), n)
    sl = np.zeros_like(a); sl[n:] = a[n:] - a[:-n]
    return a, sl


def shift1(a):
    out = np.full_like(a, np.nan)
    out[1:] = a[:-1]
    return out


def indicators(d, keltner_n=16, keltner_mult=1.75, atr_n=14, er_n=20):
    c, h, l = d["close"], d["high"], d["low"]
    a = ema(true_range(h, l, c), atr_n)
    basis = ema(c, keltner_n)
    av, asl = adx(h, l, c)
    ind = {
        "kelt_up": shift1(basis + keltner_mult * a),
        "kelt_dn": shift1(basis - keltner_mult * a),
        "atr": shift1(a),
        "atr_r70": shift1(a / np.maximum(ema(a, 70), 1e-12)),
        "atr_r1y": shift1(a / np.maximum(ema(a, 6 * 365), 1e-12)),
        "er": shift1(efficiency_ratio(c, er_n)),
        "adx": shift1(av),
        "adx_slope": shift1(asl),
        "ema21": shift1(ema(c, 21)),
        "ema50": shift1(ema(c, 50)),
        "ema200": shift1(ema(c, 200)),
        "prev_close": shift1(c),
    }
    if "btc_close" in d:
        b = d["btc_close"][:, None]
        ind["btc_ema50"] = shift1(ema(b, 50))[:, 0]
        ind["btc_ema200"] = shift1(ema(b, 200))[:, 0]
        ind["btc_prev"] = shift1(b)[:, 0]
        # Relative strength vs BTC over 30 bars -- the report's alt selector.
        rs = np.full_like(c, np.nan)
        n = 30
        for t in range(n, c.shape[0]):
            ar = c[t] / c[t - n] - 1.0
            br = d["btc_close"][t] / d["btc_close"][t - n] - 1.0
            rs[t] = ar - br
        ind["rs_btc"] = shift1(rs)
    return ind


def vol_regime(ind):
    """0 compression, 1 normal, 2 expansion, 3 extreme."""
    r70, r1y = ind["atr_r70"], ind["atr_r1y"]
    reg = np.full(r70.shape, 1, dtype=np.int8)
    reg[r70 < 0.85] = 0
    reg[(r70 > 1.15) & (r1y > 1.0)] = 2
    reg[r1y > 1.6] = 3
    reg[np.isnan(r70)] = 1
    return reg


# --------------------------------------------------------------- signals --

def make_signal(d, ind, direction, er_min=0.30, adx_min=25.0,
                require_adx_rising=True, require_ema200=True,
                regimes=(2,), btc_filter=False, rs_min=None):
    """
    One-directional signal. `direction` is +1 (long only) or -1 (short only).

    Separating the directions is the point of this project: a long signal and a
    short signal are not the same rule with the sign flipped, because the
    filters that qualify an uptrend do not necessarily qualify a downtrend.
    """
    c = d["close"]
    pc = ind["prev_close"]
    reg = vol_regime(ind)

    q = (ind["er"] >= er_min) & (ind["adx"] >= adx_min)
    if require_adx_rising:
        q &= ind["adx_slope"] > 0
    q &= ~np.isnan(ind["er"]) & ~np.isnan(ind["adx"])

    in_reg = np.isin(reg, regimes)

    if direction == 1:
        stack = ind["ema21"] > ind["ema50"]
        if require_ema200:
            stack &= ind["ema50"] > ind["ema200"]
        raw = in_reg & (pc > ind["kelt_up"]) & q & stack
    else:
        stack = ind["ema21"] < ind["ema50"]
        if require_ema200:
            stack &= ind["ema50"] < ind["ema200"]
        raw = in_reg & (pc < ind["kelt_dn"]) & q & stack

    # Alt-only overlays.
    if btc_filter and "btc_prev" in ind:
        btc_up = (ind["btc_prev"] > ind["btc_ema50"]) & (ind["btc_prev"] > ind["btc_ema200"])
        raw &= (btc_up[:, None] if direction == 1 else ~btc_up[:, None])
    if rs_min is not None and "rs_btc" in ind:
        raw &= (ind["rs_btc"] >= rs_min) if direction == 1 else (ind["rs_btc"] <= -rs_min)

    sig = np.zeros(c.shape, dtype=np.int8)
    sig[np.nan_to_num(raw, nan=0).astype(bool)] = direction
    return sig


# ------------------------------------------------------------- simulator --

def simulate(d, ind, sig, profile, risk_pct=0.5, atr_stop=1.5, rr=1.25,
             max_concurrent=3, start_bar=0, internal_daily_pct=1.0,
             max_bars_held=90):
    n, m = d["close"].shape
    acct = profile["account"]
    target = acct + profile["target_usd"]
    floor = acct - profile["max_dd_usd"]            # STATIC, never resets
    hard_daily = profile["daily_loss_pct"] / 100.0

    op, hi, lo, cl = d["open"], d["high"], d["low"], d["close"]
    lev = np.array([LEVERAGE.get(s, 2.0) for s in d["symbols"]])
    cost_rate = TAKER_PCT / 100.0 + SLIP_BPS / 10000.0

    equity = acct
    day_anchor = acct
    day_bar0 = start_bar
    day_locked = False
    pos, trades = {}, []
    outcome, out_bar = "open", None

    for t in range(start_bar, n):
        if (t - day_bar0) >= BARS_PER_DAY:
            day_bar0 = t
            day_anchor = equity + sum(
                p["dir"] * p["units"] * (cl[t - 1, j] - p["entry"])
                for j, p in pos.items())
            day_locked = False

        for j in list(pos):
            p = pos[j]
            dirn = p["dir"]
            hit_stop = (lo[t, j] <= p["stop"]) if dirn == 1 else (hi[t, j] >= p["stop"])
            hit_tp = (hi[t, j] >= p["tp"]) if dirn == 1 else (lo[t, j] <= p["tp"])
            timeout = (t - p["bar"]) >= max_bars_held
            if not (hit_stop or hit_tp or timeout):
                continue
            fill = p["stop"] if hit_stop else (p["tp"] if hit_tp else cl[t, j])
            cost = p["units"] * fill * cost_rate
            pnl = dirn * p["units"] * (fill - p["entry"]) - cost - p["entry_cost"]
            equity += pnl
            trades.append({"sym": d["symbols"][j], "dir": dirn, "pnl": pnl,
                           "r": pnl / max(p["risk_usd"], 1e-9),
                           "reason": "sl" if hit_stop else ("tp" if hit_tp else "time"),
                           "bars": t - p["bar"]})
            del pos[j]

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

        if not day_locked and marked <= day_anchor * (1 - internal_daily_pct / 100.0):
            for j in list(pos):
                p = pos[j]
                cost = p["units"] * cl[t, j] * cost_rate
                pnl = p["dir"] * p["units"] * (cl[t, j] - p["entry"]) - cost - p["entry_cost"]
                equity += pnl
                trades.append({"sym": d["symbols"][j], "dir": p["dir"], "pnl": pnl,
                               "r": pnl / max(p["risk_usd"], 1e-9),
                               "reason": "internal_stop", "bars": t - p["bar"]})
                del pos[j]
            day_locked = True

        if not day_locked and len(pos) < max_concurrent:
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
                          "entry_cost": ec, "bar": t}

    return {"outcome": outcome, "bar": out_bar, "trades": trades,
            "bars": (out_bar or n) - start_bar}


def evaluate(d, ind, sig, profile, n_starts=50, warmup=1300, **kw):
    n = d["close"].shape[0]
    starts = np.linspace(warmup, n - 400, n_starts).astype(int)
    res = [simulate(d, ind, sig, profile, start_bar=int(b), **kw) for b in starts]
    oc = [r["outcome"] for r in res]
    passes = np.array([o == "PASS" for o in oc], dtype=float)
    rng = np.random.default_rng(0)
    boot = np.array([rng.choice(passes, len(passes), replace=True).mean()
                     for _ in range(2000)])
    tr = [t for r in res for t in r["trades"]]
    pnl = np.array([t["pnl"] for t in tr]) if tr else np.array([0.0])
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
    bars = float(np.mean([r["bars"] for r in res]))
    pb = [r["bars"] for r in res if r["outcome"] == "PASS"]
    return {
        "pass_pct": round(100 * oc.count("PASS") / len(res), 1),
        "pass_lo": round(100 * float(np.percentile(boot, 10)), 1),
        "pass_hi": round(100 * float(np.percentile(boot, 90)), 1),
        "breach_pct": round(100 * (oc.count("breach_dd") + oc.count("breach_daily")) / len(res), 1),
        "win_pct": round(100 * len([t for t in tr if t["pnl"] > 0]) / max(len(tr), 1), 1),
        "pf": round(float(gw / gl), 2) if gl > 0 else None,
        "avg_r": round(float(np.mean([t["r"] for t in tr])), 3) if tr else 0.0,
        "t_per_mo": round(len(tr) / len(res) / max(bars / BARS_PER_MONTH, 1e-9), 1),
        "mo_to_pass": round(float(np.median(pb)) / BARS_PER_MONTH, 1) if pb else None,
        "n_trades": len(tr),
    }


HDR = (f"  {'config':<40s} {'PASS':>6s} {'  [80% CI]':>12s} {'brch':>6s} "
       f"{'win%':>6s} {'PF':>5s} {'avgR':>6s} {'t/mo':>5s} {'mo2p':>5s}")


def row(lab, r):
    pf = f"{r['pf']:>5.2f}" if r["pf"] else "    -"
    mt = f"{r['mo_to_pass']:>5.1f}" if r["mo_to_pass"] else "    -"
    return (f"  {lab:<40s} {r['pass_pct']:>5.1f}% [{r['pass_lo']:>4.1f}-{r['pass_hi']:>4.1f}] "
            f"{r['breach_pct']:>5.1f}% {r['win_pct']:>5.1f}% {pf} {r['avg_r']:>6.2f} "
            f"{r['t_per_mo']:>5.1f} {mt}")
