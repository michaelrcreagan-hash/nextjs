"""
Goal asks #2, #3, #4 -- the "buy the 4-year low" crypto spot strategy.

  #2  "focus on spot investing and buying the btc, eth and top 25 by market
       cap altcoins at the 4 year low"
  #3  "allocate 20% to leverage or micro cap satellite trades"
  #4  "...outperform btc by a more than 3 to 1 multiple"

Runs on Data/crypto_panel_5y.csv (5.01 years, 1831 daily bars, 25 names,
Coinbase). Costs are Coinbase spot: 0.60% taker + 10bps slippage, per
config.strategy_params.venue_costs -- the real venue, not an approximation.

⚠ SURVIVORSHIP BIAS -- READ BEFORE BELIEVING ANY NUMBER BELOW
--------------------------------------------------------------
The universe is the top names by market cap **as of today**. That silently
excludes every coin that was top-25 in 2021 and then collapsed -- LUNA, FTT,
and others that went to roughly zero. A "buy the multi-year low" rule is
exactly the rule that would have bought those on the way down and held to zero.
So this backtest is biased UPWARD, and the bias is largest for precisely the
strategy being tested. Treat every result as an optimistic bound, not an
estimate. Fixing it needs a point-in-time market-cap universe, which is a
paid data product.

LOOKBACK HANDLING
-----------------
A literal 1460-day (4y) trailing low on a 1831-bar panel leaves only ~371
tradeable bars. Instead the trailing low is an EXPANDING minimum that grows to
the requested window (min 365 bars of warm-up), so it means "the lowest price
in up to the last N years, using all history available at the time". That is
trailing-only and carries no lookahead. Shorter windows are run as sensitivity.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

STRATEGY_DIR = Path(__file__).resolve().parent
PANEL = STRATEGY_DIR / "Data" / "crypto_panel_5y.csv"
OUT = STRATEGY_DIR / "experiments" / "crypto_low"

TAKER_PCT = 0.60          # Coinbase spot taker
SLIP_BPS = 10.0
WARMUP_MIN = 365

CORE = ["BTC", "ETH"]     # the goal names these explicitly


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


def trailing_low(px: np.ndarray, window: int) -> np.ndarray:
    """
    Expanding-then-rolling minimum of prices strictly BEFORE bar t.

    Shifted by one bar: the low available for the decision at bar t uses bars
    [max(0, t-window) .. t-1]. Never includes bar t itself.
    """
    n, m = px.shape
    out = np.full((n, m), np.nan)
    for j in range(m):
        col = px[:, j]
        for t in range(1, n):
            lo_i = max(0, t - window)
            w = col[lo_i:t]
            w = w[~np.isnan(w)]
            if w.size >= WARMUP_MIN or (lo_i == 0 and w.size >= WARMUP_MIN):
                out[t, j] = w.min()
    return out


def run(dates, syms, px, lookback, proximity_pct, satellite_pct,
        capital=100_000.0, max_positions=10):
    """
    Buy any name trading within `proximity_pct` of its trailing low, hold spot.

    Allocation: (100 - satellite_pct)% to the CORE names (BTC/ETH), the rest
    to satellites -- the goal's ask #3, implemented as a capital split rather
    than as leverage. Leverage is deliberately NOT used: config.yaml disables
    it, and a levered "buy the low" rule on a survivorship-biased universe
    would compound the bias rather than test it.
    """
    n, m = px.shape
    low = trailing_low(px, lookback)
    core_idx = {syms.index(s) for s in CORE if s in syms}

    core_budget = capital * (100 - satellite_pct) / 100.0
    sat_budget = capital * satellite_pct / 100.0

    cash_core, cash_sat = core_budget, sat_budget
    units = np.zeros(m)
    n_buys = 0
    total_cost = 0.0
    equity = np.zeros(n)
    buys = []

    # Per-name budget: core split across the core names, satellites across
    # up to max_positions of the rest.
    per_core = core_budget / max(1, len(core_idx))
    per_sat = sat_budget / max_positions
    spent_core = {j: 0.0 for j in core_idx}
    spent_sat = {}

    for t in range(n):
        p = px[t]
        for j in range(m):
            if np.isnan(p[j]) or np.isnan(low[t, j]):
                continue
            # signal: within proximity_pct of the trailing low
            if p[j] > low[t, j] * (1.0 + proximity_pct / 100.0):
                continue

            is_core = j in core_idx
            if is_core:
                # Core accumulates in 10 tranches across the whole history.
                tranche = per_core / 10.0
                if spent_core[j] + tranche > per_core or cash_core < tranche:
                    continue
                spent_core[j] += tranche
                cash_core -= tranche
            else:
                if j not in spent_sat and len(spent_sat) >= max_positions:
                    continue
                tranche = per_sat / 5.0
                spent_sat.setdefault(j, 0.0)
                if spent_sat[j] + tranche > per_sat or cash_sat < tranche:
                    continue
                spent_sat[j] += tranche
                cash_sat -= tranche

            cost = tranche * (TAKER_PCT / 100.0 + SLIP_BPS / 10000.0)
            total_cost += cost
            units[j] += (tranche - cost) / p[j]
            n_buys += 1
            buys.append((dates[t], syms[j], round(tranche, 2), round(p[j], 6)))

        held = np.nansum(units * np.nan_to_num(p, nan=0.0))
        equity[t] = cash_core + cash_sat + held

    return {"equity": equity, "n_buys": n_buys, "cost": total_cost,
            "units": units, "buys": buys,
            "deployed": capital - (cash_core + cash_sat)}


def run_dca(dates, syms, px, satellite_pct, capital=100_000.0,
            max_positions=10, every=26):
    """
    CONTROL ARM: plain dollar-cost averaging into the same universe, same
    80/20 core/satellite split, same costs -- but NO low-buying signal at all.

    This is the control the whole ask #2 hypothesis needs. If "buy the 4-year
    low" cannot beat blindly averaging in on a fixed schedule, then the edge
    is the universe and the deployment schedule, not the signal -- and the
    signal is decoration. `every` is set so the number of buys lands near the
    strategy's ~70, making the comparison like-for-like on turnover.
    """
    n, m = px.shape
    core_idx = [syms.index(s) for s in CORE if s in syms]
    sat_idx = [j for j in range(m) if j not in core_idx][:max_positions]

    core_budget = capital * (100 - satellite_pct) / 100.0
    sat_budget = capital * satellite_pct / 100.0
    cash = capital
    units = np.zeros(m)
    n_buys = 0
    total_cost = 0.0
    equity = np.zeros(n)

    core_tranches = 10
    sat_tranches = 5
    per_core_tranche = core_budget / max(1, len(core_idx)) / core_tranches
    per_sat_tranche = sat_budget / max(1, len(sat_idx)) / sat_tranches
    core_done = {j: 0 for j in core_idx}
    sat_done = {j: 0 for j in sat_idx}

    for t in range(n):
        if t >= WARMUP_MIN and t % every == 0:
            for j in core_idx:
                if core_done[j] < core_tranches and not np.isnan(px[t, j]):
                    tr = per_core_tranche
                    if cash >= tr:
                        c = tr * (TAKER_PCT / 100.0 + SLIP_BPS / 10000.0)
                        cash -= tr; total_cost += c
                        units[j] += (tr - c) / px[t, j]
                        core_done[j] += 1; n_buys += 1
            for j in sat_idx:
                if sat_done[j] < sat_tranches and not np.isnan(px[t, j]):
                    tr = per_sat_tranche
                    if cash >= tr:
                        c = tr * (TAKER_PCT / 100.0 + SLIP_BPS / 10000.0)
                        cash -= tr; total_cost += c
                        units[j] += (tr - c) / px[t, j]
                        sat_done[j] += 1; n_buys += 1
        equity[t] = cash + np.nansum(units * np.nan_to_num(px[t], nan=0.0))
    return {"equity": equity, "n_buys": n_buys, "cost": total_cost,
            "deployed": capital - cash}


def metrics(eq, dates, label):
    eq = np.asarray(eq, dtype=float)
    valid = eq > 0
    eq = eq[valid]
    d0 = np.datetime64(dates[0]); d1 = np.datetime64(dates[-1])
    years = (d1 - d0).astype(int) / 365.25
    total = eq[-1] / eq[0] - 1.0
    cagr = (eq[-1] / eq[0]) ** (1 / years) - 1.0
    r = np.diff(eq) / eq[:-1]
    sharpe = r.mean() / r.std() * np.sqrt(365) if r.std() > 0 else 0.0
    dd = (eq / np.maximum.accumulate(eq) - 1.0).min()
    return {"label": label, "total_return_pct": round(100 * total, 1),
            "cagr_pct": round(100 * cagr, 2), "max_dd_pct": round(100 * dd, 2),
            "sharpe": round(float(sharpe), 3),
            "mar": round(float(cagr / abs(dd)), 3) if dd < 0 else None,
            "final": round(float(eq[-1]), 2), "years": round(years, 2)}


def main():
    dates, syms, px = load_panel()
    cap = 100_000.0
    print("=" * 92)
    print(f"CRYPTO 'BUY THE MULTI-YEAR LOW' -- {len(dates)} bars, {len(syms)} names, "
          f"{dates[0]} -> {dates[-1]}")
    print("=" * 92)

    # --- benchmark: BTC buy & hold ---
    b = px[:, syms.index("BTC")]
    btc_eq = cap * b / b[0]
    mb = metrics(btc_eq, dates, "BTC buy & hold")

    # --- benchmark: equal-weight top-25 buy & hold (first bar each is valid) ---
    ew = np.zeros(len(dates))
    per = cap / len(syms)
    u = np.zeros(len(syms))
    seeded = np.zeros(len(syms), dtype=bool)
    for t in range(len(dates)):
        for j in range(len(syms)):
            if not seeded[j] and not np.isnan(px[t, j]):
                u[j] = per / px[t, j]; seeded[j] = True
        ew[t] = np.nansum(u * np.nan_to_num(px[t], nan=0.0)) + per * (~seeded).sum()
    mew = metrics(ew, dates, "equal-weight 25 B&H")

    hdr = (f"  {'arm':<40s} {'CAGR':>8s} {'total':>9s} {'maxDD':>9s} "
           f"{'MAR':>6s} {'Sharpe':>7s} {'buys':>6s} {'final $':>12s}")

    results = []
    print("\n" + "-" * 92)
    print(hdr)
    print("-" * 92)
    for m in (mb, mew):
        print(f"  {m['label']:<40s} {m['cagr_pct']:>7.2f}% {m['total_return_pct']:>8.1f}% "
              f"{m['max_dd_pct']:>8.2f}% {m['mar'] or 0:>6.2f} {m['sharpe']:>7.2f} "
              f"{'-':>6s} {m['final']:>12,.0f}")
        results.append(m)

    # --- CONTROL: dollar-cost averaging, no signal ---
    dca = run_dca(dates, syms, px, satellite_pct=20.0, capital=cap)
    mdca = metrics(dca["equity"], dates, "DCA control (NO low signal)")
    mdca["n_buys"] = dca["n_buys"]
    print(f"  {mdca['label']:<40s} {mdca['cagr_pct']:>7.2f}% {mdca['total_return_pct']:>8.1f}% "
          f"{mdca['max_dd_pct']:>8.2f}% {mdca['mar'] or 0:>6.2f} {mdca['sharpe']:>7.2f} "
          f"{dca['n_buys']:>6d} {mdca['final']:>12,.0f}")
    results.append(mdca)

    # --- the strategy grid ---
    print("-" * 92)
    grid = []
    for lookback in (365, 730, 1095, 1460):
        for prox in (0.0, 5.0, 10.0, 20.0):
            r = run(dates, syms, px, lookback, prox, satellite_pct=20.0, capital=cap)
            m = metrics(r["equity"], dates,
                        f"low {lookback}d, within {prox:.0f}%")
            m["n_buys"] = r["n_buys"]; m["cost_usd"] = round(r["cost"], 2)
            m["deployed_usd"] = round(r["deployed"], 2)
            m["lookback_days"] = lookback; m["proximity_pct"] = prox
            grid.append(m)
            print(f"  {m['label']:<40s} {m['cagr_pct']:>7.2f}% {m['total_return_pct']:>8.1f}% "
                  f"{m['max_dd_pct']:>8.2f}% {m['mar'] or 0:>6.2f} {m['sharpe']:>7.2f} "
                  f"{r['n_buys']:>6d} {m['final']:>12,.0f}")
    print("-" * 92)

    best = max(grid, key=lambda m: m["cagr_pct"])
    ratio = ((1 + best["total_return_pct"] / 100)
             / (1 + mb["total_return_pct"] / 100))

    print(f"\n  trials run: {len(grid)}  (Deflated Sharpe must be computed "
          f"against n={len(grid)}, not n=1)")
    print(f"  best arm  : {best['label']}  CAGR {best['cagr_pct']}%  "
          f"deployed ${best['deployed_usd']:,.0f} of ${cap:,.0f}")

    print("\n" + "=" * 92)
    print("ASK #4 GATE -- 'outperform btc by a more than 3 to 1 multiple'")
    print("=" * 92)
    print(f"  BTC total return over 5.01y     : {mb['total_return_pct']:>8.1f}%  "
          f"(${mb['final']:,.0f} from ${cap:,.0f})")
    print(f"  best strategy total return      : {best['total_return_pct']:>8.1f}%  "
          f"(${best['final']:,.0f})")
    print(f"  terminal-wealth multiple vs BTC : {ratio:>8.2f}x   "
          f"(need > 3.00x)")
    tr_ratio = (best["total_return_pct"] / mb["total_return_pct"]
                if mb["total_return_pct"] > 0 else float("nan"))
    print(f"  total-RETURN multiple vs BTC    : {tr_ratio:>8.2f}x   "
          f"(the looser reading of '3 to 1')")
    passed = ratio > 3.0
    print(f"\n  VERDICT: {'PASS' if passed else 'FAIL'} on terminal wealth"
          f"{'' if passed else ' -- see the survivorship warning above before reading this as a real miss'}")

    print("\n" + "=" * 92)
    print("THE CONTROL THAT MATTERS -- does the low signal beat just averaging in?")
    print("=" * 92)
    edge = best["cagr_pct"] - mdca["cagr_pct"]
    print(f"  best low-buying arm : CAGR {best['cagr_pct']:>6.2f}%  "
          f"maxDD {best['max_dd_pct']:>7.2f}%  MAR {best['mar']:>5.2f}  "
          f"{best['n_buys']:>3d} buys")
    print(f"  DCA control         : CAGR {mdca['cagr_pct']:>6.2f}%  "
          f"maxDD {mdca['max_dd_pct']:>7.2f}%  MAR {mdca['mar']:>5.2f}  "
          f"{mdca['n_buys']:>3d} buys")
    print(f"  edge from the signal: {edge:>+6.2f}pp CAGR")
    if edge <= 0:
        print("  -> THE SIGNAL ADDS NOTHING. The return is the universe and the")
        print("     deployment schedule, not 'buying the 4-year low'.")
    elif edge < 3:
        print("  -> Marginal. Within the noise of a 16-trial grid on one 5y sample.")
    else:
        print("  -> The signal earns its place, subject to the survivorship caveat.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps({
        "panel": {"bars": len(dates), "symbols": syms,
                  "range": [str(dates[0]), str(dates[-1])], "years": 5.01,
                  "source": "Coinbase Exchange daily candles"},
        "costs": {"taker_pct": TAKER_PCT, "slippage_bps": SLIP_BPS,
                  "venue": "coinbase_spot"},
        "benchmarks": [mb, mew, mdca],
        "dca_control": {"cagr_pct": mdca["cagr_pct"], "max_dd_pct": mdca["max_dd_pct"],
                        "mar": mdca["mar"], "n_buys": mdca["n_buys"],
                        "signal_edge_pp": round(best["cagr_pct"] - mdca["cagr_pct"], 2)},
        "grid": grid,
        "trials": len(grid),
        "best": best,
        "ask4_gate": {"terminal_wealth_multiple_vs_btc": round(ratio, 3),
                      "total_return_multiple_vs_btc": round(tr_ratio, 3),
                      "threshold": 3.0, "passed": bool(passed)},
        "caveats": [
            "SURVIVORSHIP BIAS: universe is today's top names; excludes LUNA/FTT-style collapses that a buy-the-low rule would have bought. Results are an optimistic bound.",
            "satellite sleeve implemented as a 20% capital split, NOT leverage (config leverage.enabled:false)",
            f"grid ran {len(grid)} trials -- deflate any Sharpe accordingly",
            "trailing low is expanding-then-rolling, shifted 1 bar, never includes the current bar",
        ],
    }, indent=2))
    with (OUT / "buys.csv").open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "symbol", "usd", "price"])
        best_run = run(dates, syms, px, best["lookback_days"],
                       best["proximity_pct"], 20.0, cap)
        w.writerows(best_run["buys"])
    print(f"\nsaved: experiments/crypto_low/results.json, buys.csv")


if __name__ == "__main__":
    main()
