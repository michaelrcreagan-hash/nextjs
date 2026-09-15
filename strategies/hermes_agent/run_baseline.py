"""
hermes_agent -- Step 5: BASELINE RUN

The bar every later step must clear. Mechanical core only: regime + momentum
entry + two-stage exit. No confluence score, no features, no ML, no LLM.

Runs four arms:
  A  regime-scaled   (the strategy)
  B  static 80%      (same entries/exits, regime engine OFF)  <- the arm that
                        can embarrass us; four_sleeve's regime matrix ADDED
                        drawdown vs a static allocation
  C  buy & hold BTC  (the goal's stated benchmark)
  D  buy & hold EW   (equal-weight all 11 names)

THE GATE (BUILD_PLAN.md step 5): if arm A fails to beat BOTH B and C/D, stop
and report. Steps 6-9 are not worth building on a core that does not work.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from backtest import (STRATEGY_DIR, load_config, run, buy_and_hold,
                      compute_metrics)
from src.exits import EXIT_NAMES
from src.regime import occupancy, REGIME_NAMES

OUT = STRATEGY_DIR / "experiments" / "baseline"


def assert_invariants(res: dict, cfg: dict) -> list[str]:
    """The three rules from backtest.py's docstring, checked rather than intended."""
    checks = []
    tr = res["trades"]
    floor = float(cfg["sizing"]["min_position_value_usd"])

    # RULE 1 -- position floor is a SKIP. Check entry notionals, reconstructed
    # from the FIRST fill of each (symbol, entry_idx) pair: a scaled-out
    # position's fills are fractions of an entry that did clear the floor.
    if len(tr):
        entries = {}
        for row in tr:
            key = (int(row[0]), int(row[1]))
            entries[key] = entries.get(key, 0.0) + row[5]
        notionals = []
        for (s, ei), qty in entries.items():
            px = next(r[3] for r in tr if int(r[0]) == s and int(r[1]) == ei)
            notionals.append(qty * px)
        below = [n for n in notionals if n < floor - 1e-6]
        checks.append(("no trade below the $%d position floor" % floor,
                       len(below) == 0,
                       f"{len(below)} of {len(notionals)} below"))

    # RULE 3 -- deployed capital never exceeds gross_exposure[t].
    dep, gross = res["deployed"], res["gross"]
    ws = res["warm_start"]
    breach = np.where(dep[ws:] > gross[ws:] + 1e-6)[0]
    checks.append(("deployed <= regime gross exposure at every bar",
                   breach.size == 0,
                   f"{breach.size} breaching bars"))

    # Equity curve stays positive and finite.
    eq = res["equity"]
    checks.append(("equity curve finite and positive",
                   bool(np.isfinite(eq).all() and (eq > 0).all()),
                   "ok" if np.isfinite(eq).all() else "non-finite values"))
    return checks


def cost_direction_check(cfg: dict) -> tuple[bool, float, float]:
    """
    A zero-cost run must be strictly better than the costed run. If it is not,
    the cost model is wired backwards -- a failure mode that would otherwise
    hide inside plausible-looking metrics.
    """
    import copy
    free = copy.deepcopy(cfg)
    vc = free["strategy_params"]["venue_costs"]
    vc["coinbase_spot"]["taker_pct"] = 0.0
    vc["coinbase_spot"]["slippage_bps"] = 0.0
    vc["merrill_ira"]["commission_usd"] = 0.0
    vc["merrill_ira"]["slippage_bps"] = 0.0
    a = run(cfg)["metrics"]["final_equity_usd"]
    b = run(free)["metrics"]["final_equity_usd"]
    return b >= a, a, b


def fmt(m: dict, name: str) -> str:
    pf = m.get("profit_factor")
    pf = f"{pf:>7.2f}" if isinstance(pf, (int, float)) else "      -"
    mar = m.get("mar")
    mar = f"{mar:>6.2f}" if isinstance(mar, (int, float)) else "     -"
    return (f"  {name:<22s} {m['cagr_pct']:>7.2f}% {m['max_drawdown_pct']:>8.2f}% "
            f"{mar} {pf} {m['sharpe']:>7.2f} {m['deflated_sharpe']:>7.3f} "
            f"{m['n_fills']:>6d} {m['final_equity_usd']:>12,.0f}")


def main() -> int:
    cfg = load_config()
    OUT.mkdir(parents=True, exist_ok=True)

    print("=" * 100)
    print("hermes_agent -- STEP 5 BASELINE (mechanical core: regime + momentum + two-stage exit)")
    print("=" * 100)

    a = run(cfg, regime_scaled=True)
    panel, reg = a["panel"], a["regime"]

    print(f"\npanel      : {panel['n_bars']} bars, {panel['dates'][0]} -> {panel['dates'][-1]}")
    print(f"warm-up    : {a['warm_start']} bars flat (200-DMA is the binding constraint)")
    print(f"tradeable  : {panel['n_bars'] - a['warm_start']} bars "
          f"({(panel['n_bars'] - a['warm_start']) / 252:.2f} years)")
    print(f"regimes    : {occupancy(reg['labels'])}")
    print(f"mean gross : {a['metrics']['mean_deployed_frac']:.1%} deployed "
          f"-> {1 - a['metrics']['mean_deployed_frac']:.1%} cash")

    b = run(cfg, regime_scaled=False, static_gross=0.80)
    c = buy_and_hold(panel, cfg, "BTC-USD")
    d = buy_and_hold(panel, cfg, None)
    ctrl = run(cfg, regime_scaled=True, first_tranche_override=0.0)

    print("\n" + "-" * 100)
    print(f"  {'arm':<22s} {'CAGR':>8s} {'maxDD':>9s} {'MAR':>6s} {'PF':>7s} "
          f"{'Sharpe':>7s} {'DSR':>7s} {'fills':>6s} {'final $':>12s}")
    print("-" * 100)
    print(fmt(a["metrics"], "A regime-scaled"))
    print(fmt(b["metrics"], "B static 80%"))
    print(fmt(c["metrics"], "C buy&hold BTC"))
    print(fmt(d["metrics"], "D buy&hold equal-wt"))
    print(fmt(ctrl["metrics"], "A' no scale-out (ctrl)"))
    print("-" * 100)
    print("  DSR at n_trials=1 -- this is the PRE-SEARCH figure. Step 8's grids "
          "exceed 1,700 configs\n  and will deflate it substantially. Do not quote this number post-search.")

    # ---------------- invariants ----------------
    print("\ninvariant checks")
    all_ok = True
    for label, ok, detail in assert_invariants(a, cfg):
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:<52s} {detail}")
        all_ok &= ok
    ok, costed, free = cost_direction_check(cfg)
    print(f"  [{'PASS' if ok else 'FAIL'}] zero-cost run beats costed run"
          f"{'':<22s} ${costed:,.0f} -> ${free:,.0f}")
    all_ok &= ok

    r1 = run(cfg)["metrics"]["final_equity_usd"]
    r2 = run(cfg)["metrics"]["final_equity_usd"]
    print(f"  [{'PASS' if r1 == r2 else 'FAIL'}] determinism (re-run reproduces "
          f"exactly){'':<11s} ${r1:,.2f}")
    all_ok &= (r1 == r2)

    # ---------------- exit attribution ----------------
    tr = a["trades"]
    if len(tr):
        print("\nexit attribution (fills)")
        for code in sorted(set(int(x) for x in tr[:, 8])):
            sel = tr[tr[:, 8] == code]
            print(f"  {EXIT_NAMES[code]:<16s} n={len(sel):>4d}  "
                  f"pnl=${sel[:, 6].sum():>11,.0f}  avg=${sel[:, 6].mean():>9,.0f}")
        print(f"\ntotal costs paid : ${tr[:, 7].sum():,.0f} "
              f"({100 * tr[:, 7].sum() / cfg['account']['initial_capital']:.2f}% of initial capital)")

    # ---------------- THE GATE ----------------
    A = a["metrics"]
    beats_static = (A["mar"] or -9) > (b["metrics"]["mar"] or -9)
    beats_btc = A["cagr_pct"] > c["metrics"]["cagr_pct"]
    beats_ew = A["cagr_pct"] > d["metrics"]["cagr_pct"]

    print("\n" + "=" * 100)
    print("STEP 5 GATE")
    print("=" * 100)
    print(f"  beats static-80% arm on MAR : {str(beats_static):<5s}  "
          f"({A['mar']} vs {b['metrics']['mar']})")
    print(f"  beats buy&hold BTC on CAGR  : {str(beats_btc):<5s}  "
          f"({A['cagr_pct']}% vs {c['metrics']['cagr_pct']}%)")
    print(f"  beats equal-weight on CAGR  : {str(beats_ew):<5s}  "
          f"({A['cagr_pct']}% vs {d['metrics']['cagr_pct']}%)")

    # BUILD_PLAN.md step 5: "beat BOTH buy-and-hold AND a static allocation".
    # BOTH means AND. An earlier version of this gate read
    # `beats_static and (beats_btc or beats_ew)`, which lets the arm pass by
    # clearing the weaker of the two buy-and-hold arms -- a materially easier
    # test than the plan specifies, and one this baseline scrapes through on.
    # BTC is the buy-and-hold that counts: it is the benchmark the stated goal
    # names, and beating an equal-weight basket that itself returned 0.33% is
    # not evidence of anything.
    passed = beats_static and beats_btc
    print(f"\n  GATE: {'PASS -- proceed to step 6' if passed else 'FAIL -- STOP. Do not build steps 6-9 on this core.'}")

    payload = {
        "arms": {
            "A_regime_scaled": A,
            "B_static_80": b["metrics"],
            "C_buyhold_btc": c["metrics"],
            "D_buyhold_equalweight": d["metrics"],
            "A_control_no_scaleout": ctrl["metrics"],
        },
        "regime_occupancy_pct": occupancy(reg["labels"]),
        "warm_start_bars": int(a["warm_start"]),
        "tradeable_bars": int(panel["n_bars"] - a["warm_start"]),
        "gate": {
            "beats_static_on_mar": bool(beats_static),
            "beats_buyhold_btc_on_cagr": bool(beats_btc),
            "beats_equalweight_on_cagr": bool(beats_ew),
            "passed": bool(passed),
        },
        "invariants_passed": bool(all_ok),
        "dsr_trial_count": 1,
        "notes": [
            "ATR is a close-to-close proxy (no intraday H/L) -- stops read tighter than true-range ATR",
            "Exits fill at the breaching close, not at the stop level -- close-only data, conservative direction",
            "Regime engine uses PROXY inputs (SPY vol/trend, TLT, BTC) not macro_sector_dominance's VIX/SMH/liquidity/ISM/DXY",
            "Crypto is on the NYSE calendar in this panel -- weekend moves absent, surface as Monday gaps",
            f"Only {panel['n_bars'] - a['warm_start']} tradeable bars after the 200-DMA warm-up",
        ],
    }
    (OUT / "metrics.json").write_text(json.dumps(payload, indent=2))
    np.save(OUT / "equity_A.npy", a["equity"])
    np.save(OUT / "trades_A.npy", a["trades"])
    print(f"\nsaved: {OUT.relative_to(STRATEGY_DIR.parent.parent)}/metrics.json")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
