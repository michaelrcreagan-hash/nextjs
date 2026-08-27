"""
Goal ask #5 -- bull/bear crypto strategy for a Breakout-style prop account.

  "seperately create a bull market and bear market prop trading strategy for
   crypto via the breakout prop trading firm ... the goal is to make 70k a
   year 4% or more per month on a 100k crypto prop account"

Runs on Data/crypto_panel_5y.csv (5.01y, 25 names, Coinbase daily).

PROP RULES: REAL, CONFIRMED (supplied by the author 2026-08-27)
---------------------------------------------------------------
Supersedes the assumed rule set this file previously modelled. Two profiles,
matching Breakout's published Classic and Turbo 1-Step programs:

    CLASSIC eval    $10,000   target $1,000 (10%)   maxDD $600 (6%)    daily 3%
    TURBO funded   $200,000   target $18,000 (9%)   maxDD $6,000 (3%)  daily 3%

THE DRAWDOWN IS **STATIC**, not trailing: it is computed from the starting
balance and never moves. That is the SOFTER variant, and it inverts the
conclusion the previous (trailing) model reached -- under a trailing floor
every new equity high raises the bar forever; under a static floor the
constraint binds only until a cushion is built, after which it stops binding
at all. Breakout sets the threshold from the balance at 00:30 UTC and then
monitors CURRENT EQUITY against it, so floating/unrealized P&L counts toward
a breach.

Other confirmed rules: no time limit, no minimum trading days, no consistency
rule. Leverage 5:1 on BTC/ETH, 2:1 on altcoins. Profit split 80% default,
90% upgradeable. Reaching the target ENDS the run as a PASS.

⚠ ONE STRUCTURAL TRAP IN THE TURBO PROFILE: its daily loss limit (3% =
$6,000) EQUALS its total max drawdown ($6,000). A single maximum-daily-loss
day therefore does not just cost the day -- it ends the account outright.
There is no such overlap in Classic ($300 daily vs $600 total).

WHAT THE MONTE CARLO SAID THIS NEEDS (GOAL_RECONCILIATION.md)
--------------------------------------------------------------
4%/month is reachable at PF ~1.3-1.8 IF frequency is 20-40 trades/month, and
per-trade risk dominates survival: at PF 2.0, moving 1% -> 2% risk cuts
12-month survival from 91.7% to 25.0%. So the design target is small risk,
high frequency. This script measures whether a real breakout rule on real
crypto data actually delivers that PF -- rather than assuming it.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

STRATEGY_DIR = Path(__file__).resolve().parent
PANEL = STRATEGY_DIR / "Data" / "crypto_panel_5y.csv"
OUT = STRATEGY_DIR / "experiments" / "crypto_prop"

# Real Breakout profiles (see module docstring).
PROFILES = {
    "classic_eval_10k": dict(account=10_000.0, target_usd=1_000.0,
                             max_dd_usd=600.0, daily_loss_pct=3.0),
    "turbo_funded_200k": dict(account=200_000.0, target_usd=18_000.0,
                              max_dd_usd=6_000.0, daily_loss_pct=3.0),
}
TRAILING_DD = False          # CONFIRMED static, from the starting balance

# Leverage caps, per Breakout's published limits.
LEV_MAJOR = 5.0              # BTC, ETH
LEV_ALT = 2.0                # everything else
MAJORS = {"BTC", "ETH"}

# Costs: Breakout is a crypto prop firm, so perp-style taker fees apply,
# not Coinbase spot. Using the Hyperliquid figures from config.yaml's
# venue_costs as the closest real reference the project has.
TAKER_PCT = 0.035
SLIP_BPS = 5.0


def load_panel():
    rows = list(csv.DictReader(PANEL.open()))
    syms = [c for c in rows[0] if c != "Date"]
    dates = np.array([r["Date"] for r in rows])
    px = np.full((len(rows), len(syms)), np.nan)
    for i, r in enumerate(rows):
        for j, s in enumerate(syms):
            v = r[s]
            if v not in ("", "None", None):
                px[i, j] = float(v)
    return dates, syms, px


def rolling_extreme(px, window, kind):
    """Trailing max/min over `window` bars, ending at t-1 (never includes t)."""
    n, m = px.shape
    out = np.full((n, m), np.nan)
    f = np.nanmax if kind == "max" else np.nanmin
    allnan = np.isnan(px)
    for t in range(window + 1, n):
        w = px[t - window:t]
        # Skip all-NaN columns rather than letting nanmax warn on them; a name
        # that has not listed yet must produce NaN, not a spurious extreme.
        ok = ~allnan[t - window:t].all(axis=0)
        if ok.any():
            out[t, ok] = f(w[:, ok], axis=0)
    return out


def atr_proxy(px, window=14):
    n, m = px.shape
    tr = np.zeros_like(px)
    tr[1:] = np.abs(px[1:] - px[:-1])
    out = np.full((n, m), np.nan)
    allnan = np.isnan(px)
    for t in range(window + 1, n):
        ok = ~allnan[t - window:t].all(axis=0)
        if ok.any():
            out[t, ok] = np.nanmean(tr[t - window:t][:, ok], axis=0)
    return out


def regime(btc, fast=50, slow=200):
    """
    BULL when BTC is above both MAs, BEAR when below both, else NEUTRAL (flat).

    Both MAs are shifted one bar. The neutral band matters: a prop account
    cannot afford to be positioned during the chop between regimes, where a
    trend rule whipsaws and the daily-loss limit does the rest.
    """
    n = len(btc)
    r = np.zeros(n, dtype=np.int8)      # 0 neutral, 1 bull, -1 bear
    for t in range(slow + 1, n):
        p = btc[t - 1]
        f = np.nanmean(btc[t - 1 - fast:t - 1])
        s = np.nanmean(btc[t - 1 - slow:t - 1])
        if p > f and p > s:
            r[t] = 1
        elif p < f and p < s:
            r[t] = -1
    return r


def run(dates, syms, px, profile, breakout_n=20, risk_pct=0.75, atr_mult=2.5,
        max_concurrent=5, rr=2.0, allow_short=True, start_bar=None):
    """
    One prop run. Ends at PASS (target reached) or BREACH (dd / daily loss).

    `start_bar` lets the same rules be replayed from many different start
    dates, which is the only honest way to estimate a pass rate: a single
    5-year path is one sample, and prop accounts are bought on a date the
    trader picks, not at the start of history.
    """
    n, m = px.shape
    acct = profile["account"]
    target = acct + profile["target_usd"]
    floor = acct - profile["max_dd_usd"]          # STATIC, never moves
    daily_pct = profile["daily_loss_pct"] / 100.0

    hi = rolling_extreme(px, breakout_n, "max")
    lo = rolling_extreme(px, breakout_n, "min")
    atr = atr_proxy(px)
    reg = regime(px[:, syms.index("BTC")])
    lev = np.array([LEV_MAJOR if s in MAJORS else LEV_ALT for s in syms])

    t0 = start_bar if start_bar is not None else 0
    equity = acct
    day_start_eq = acct
    open_pos, trades = {}, []
    outcome, out_bar = "open", None

    for t in range(t0, n):
        # ---- manage open positions ----
        for j in list(open_pos):
            p = px[t, j]
            if np.isnan(p):
                continue
            pos = open_pos[j]
            d = pos["dir"]
            if (d == 1 and (p <= pos["stop"] or p >= pos["tp"])) or \
               (d == -1 and (p >= pos["stop"] or p <= pos["tp"])):
                gross = pos["units"] * p
                cost = gross * (TAKER_PCT / 100.0 + SLIP_BPS / 10000.0)
                pnl = d * pos["units"] * (p - pos["entry"]) - cost - pos["entry_cost"]
                equity += pnl
                won = pnl > 0
                trades.append({"sym": syms[j], "dir": d, "pnl": pnl,
                               "reason": "tp" if won else "sl", "bar": t})
                del open_pos[j]

        # ---- mark to market (floating P&L counts toward breaches) ----
        marked = equity
        for j, pos in open_pos.items():
            p = px[t, j]
            if not np.isnan(p):
                marked += pos["dir"] * pos["units"] * (p - pos["entry"])

        if marked >= target:
            outcome, out_bar = "PASS", t
            break
        if marked <= floor:
            outcome, out_bar = "breach_max_dd", t
            break
        if marked <= day_start_eq * (1 - daily_pct):
            outcome, out_bar = "breach_daily", t
            break

        # ---- entries ----
        direction = reg[t]
        if direction != 0 and len(open_pos) < max_concurrent:
            cands = []
            for j in range(m):
                if j in open_pos or np.isnan(px[t, j]) or np.isnan(atr[t, j]) \
                        or atr[t, j] <= 0:
                    continue
                if direction == 1 and not np.isnan(hi[t, j]) and px[t, j] > hi[t, j]:
                    cands.append((px[t, j] / hi[t, j], j))
                elif direction == -1 and allow_short and not np.isnan(lo[t, j]) \
                        and px[t, j] < lo[t, j]:
                    cands.append((lo[t, j] / px[t, j], j))
            cands.sort(reverse=True)
            for _, j in cands[:max_concurrent - len(open_pos)]:
                p = px[t, j]
                stop_dist = atr[t, j] * atr_mult
                if stop_dist <= 0:
                    continue
                units = (marked * (risk_pct / 100.0)) / stop_dist
                # Per-asset leverage cap: 5:1 majors, 2:1 alts.
                max_notional = marked * lev[j] / max_concurrent
                if units * p > max_notional:
                    units = max_notional / p
                notional = units * p
                entry_cost = notional * (TAKER_PCT / 100.0 + SLIP_BPS / 10000.0)
                open_pos[j] = {"dir": direction, "entry": p, "units": units,
                               "stop": p - direction * stop_dist,
                               "tp": p + direction * stop_dist * rr,
                               "entry_cost": entry_cost, "bar": t}
                equity -= entry_cost

        day_start_eq = marked

    return {"outcome": outcome, "bar": out_bar, "trades": trades,
            "final": marked if out_bar else equity,
            "bars": (out_bar - t0) if out_bar else (n - t0)}


def sweep(dates, syms, px, profile, n_starts=40, **kw):
    """Replay the same rules from many start dates -> an honest pass rate."""
    n = px.shape[0]
    first, last = 260, n - 200          # leave warm-up and room to resolve
    starts = np.linspace(first, last, n_starts).astype(int)
    res = [run(dates, syms, px, profile, start_bar=int(b), **kw) for b in starts]
    passes = [r for r in res if r["outcome"] == "PASS"]
    dd = [r for r in res if r["outcome"] == "breach_max_dd"]
    dl = [r for r in res if r["outcome"] == "breach_daily"]
    op = [r for r in res if r["outcome"] == "open"]
    ntr = [len(r["trades"]) for r in res]
    return {
        "n_starts": len(res),
        "pass_pct": round(100 * len(passes) / len(res), 1),
        "breach_dd_pct": round(100 * len(dd) / len(res), 1),
        "breach_daily_pct": round(100 * len(dl) / len(res), 1),
        "unresolved_pct": round(100 * len(op) / len(res), 1),
        "median_bars_to_pass": int(np.median([r["bars"] for r in passes])) if passes else None,
        "median_trades": int(np.median(ntr)),
        "trades_per_month": round(float(np.mean(ntr)) / (float(np.mean([r["bars"] for r in res])) / 30.4), 1),
    }


def main():
    dates, syms, px = load_panel()
    reg = regime(px[:, syms.index("BTC")])
    print("=" * 96)
    print("BREAKOUT PROP -- REAL RULES (Classic $10k eval, Turbo $200k funded)")
    print("=" * 96)
    print(f"  panel  : {len(dates)} bars, {len(syms)} names, {dates[0]} -> {dates[-1]}")
    print(f"  regime : bull {100*(reg==1).mean():.1f}%  bear {100*(reg==-1).mean():.1f}%  "
          f"neutral {100*(reg==0).mean():.1f}%")
    print(f"  drawdown is STATIC from the starting balance -- it never moves.")

    grid = [
        ("risk 0.25%", dict(risk_pct=0.25)),
        ("risk 0.50%", dict(risk_pct=0.50)),
        ("risk 0.75%", dict(risk_pct=0.75)),
        ("risk 1.00%", dict(risk_pct=1.00)),
        ("risk 0.50% long-only", dict(risk_pct=0.50, allow_short=False)),
        ("risk 0.50% rr3", dict(risk_pct=0.50, rr=3.0)),
    ]

    out = {}
    for pname, profile in PROFILES.items():
        print("\n" + "-" * 96)
        print(f"  {pname}   account ${profile['account']:,.0f}   "
              f"target ${profile['target_usd']:,.0f} "
              f"({100*profile['target_usd']/profile['account']:.0f}%)   "
              f"maxDD ${profile['max_dd_usd']:,.0f} "
              f"({100*profile['max_dd_usd']/profile['account']:.0f}%)   "
              f"daily {profile['daily_loss_pct']:.0f}%")
        if profile["max_dd_usd"] <= profile["account"] * profile["daily_loss_pct"] / 100.0:
            print(f"  ⚠ daily limit (${profile['account']*profile['daily_loss_pct']/100:,.0f}) "
                  f">= total maxDD (${profile['max_dd_usd']:,.0f}): ONE bad day ends the account")
        print("-" * 96)
        print(f"  {'arm':<24s} {'PASS':>7s} {'dd breach':>10s} {'daily breach':>13s} "
              f"{'unresolved':>11s} {'med trades':>11s} {'t/mo':>6s}")
        print("-" * 96)
        rows = []
        for label, kw in grid:
            r = sweep(dates, syms, px, profile, **kw)
            r["arm"] = label
            rows.append(r)
            print(f"  {label:<24s} {r['pass_pct']:>6.1f}% {r['breach_dd_pct']:>9.1f}% "
                  f"{r['breach_daily_pct']:>12.1f}% {r['unresolved_pct']:>10.1f}% "
                  f"{r['median_trades']:>11d} {r['trades_per_month']:>6.1f}")
        out[pname] = rows
        best = max(rows, key=lambda r: r["pass_pct"])
        print(f"\n  best: {best['arm']} -> {best['pass_pct']}% pass across "
              f"{best['n_starts']} start dates")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results_real_rules.json").write_text(json.dumps({
        "rules_source": "author-supplied 2026-08-27, cross-checked against Breakout published Classic/Turbo",
        "profiles": PROFILES,
        "static_drawdown": True,
        "leverage": {"majors": LEV_MAJOR, "alts": LEV_ALT},
        "costs": {"taker_pct": TAKER_PCT, "slippage_bps": SLIP_BPS},
        "method": "same rules replayed from 40 start dates per arm; pass = target reached first",
        "results": out,
    }, indent=2))
    print(f"\nsaved: experiments/crypto_prop/results_real_rules.json")


if __name__ == "__main__":
    main()
