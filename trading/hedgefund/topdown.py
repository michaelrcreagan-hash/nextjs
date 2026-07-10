"""Top-down live update — the full funnel in one command.

    python -m hedgefund.run topdown

Walks the complete decision cascade the strategy docs, backtests, and
optimization converged on, and emits a live update (markdown report +
JSON snapshot):

  L1 MACRO DESK ........ regime engine + 4yr/16.8yr/seasonal cycle + kill
                         switches (regime.py, cycles.py)
  L2 ALLOCATION ........ optimized four-sleeve targets (sleeves.py with
                         OPTIMIZATION_REPORT.md's adopted parameters)
  L3 THEME DESK ........ theme rotation ranking + leaders (themes.py)
  L4 STOCK DESK ........ conviction score x confluence x analyst-revision
                         velocity funnel (signals.py, confluence.py,
                         revision_velocity.py)
  L5 TRADE SETUPS ...... spot entries/stops/targets/sizes per the
                         backtest-validated rules (2.5xATR stop, 1% risk
                         x regime multiplier, quarter-size starts)
  L6 OPTIONS DESK ...... IV-rank structure selection with ATR strikes
                         (iv_rank.py) + SMH PMCC core status
  L7 HEDGE DESK ........ income-sleeve hedge mix (duration + gold
                         variants), portfolio-stop state, secular
                         invalidation, 88% sell composite on holdings

Data: prefers data_long/ (dividend-adjusted, usually freshest) per
symbol and falls back to data/ for names only cached there; each
symbol's last bar date is tracked so staleness is visible, not hidden.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from .confluence import latest_confluence
from .cycles import check_invalidation, cycle_signal
from .data import DATA_DIR, PricePanel, load_panel
from .indicators import ema
from .iv_rank import latest_structure_selection
from .ledger import LEDGER_PATH, load_ledger
from .regime import RegimeParams, compute_regime
from .sell_composite import latest_sell_signals
from .sleeves import (
    DATA_LONG,
    INCOME_MIX,
    INNOVATION_MEMBERS,
    MACRO_MEMBERS,
    SLEEVE_MATRIX,
    SleeveParams,
    _income_weights,
    _Precomp,
    _sleeve_internal_weights,
)
from .themes import THEME_MAP, latest_theme_ranking, theme_leaders
from .universe import ALL_SYMBOLS, CATEGORY_OF, UNIVERSE
from .workflow import screen

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
STATE_DIR = os.path.dirname(LEDGER_PATH)

# The adopted optimal configuration (strategies/four_sleeve_portfolio/
# config.yaml). sleeves.py defaults stay baseline; the live desk runs this.
OPTIMIZED = SleeveParams(
    macro_trend_gate=False,
    income_variant="both",
    innovation_top_n=4,
    momentum_window=63,
    innovation_vol_target=0.35,
)

GOLDEN_RULES = [
    "Decision order is macro -> theme -> stock -> options; never reversed.",
    "Quarter-size initial entries; full size only on follow-through.",
    "Never average down more than once; never into a broken trend gate.",
    "3+ losses in the last 5 closed trades -> half size until a win.",
    "Re-entry cooldown after a >2% loss on a name (5 trading days).",
    "12% single-name cap; 2% max risk per options spread.",
    "No naked options, ever; close debit spreads by 14 DTE.",
]


def load_merged_panel() -> tuple[PricePanel, dict[str, str]]:
    """Union of data_long/ (preferred, freshest) and data/ per symbol.
    Returns the panel plus each symbol's last-bar date for staleness."""
    symbols = sorted(set(ALL_SYMBOLS) | set(MACRO_MEMBERS)
                     | set(INNOVATION_MEMBERS) | set(INCOME_MIX["MIXED"])
                     | {"SPY", "QQQ", "SMH", "VIX", "BTCUSD", "TLT", "GLD"})
    closes, volumes, last_bar = {}, {}, {}
    for sym in symbols:
        best = None
        # Prefer whichever cache has the LATER last bar — data_long/ has
        # deeper adjusted history, but the daily CI job only refreshes
        # data/, so freshness must win over depth.
        for d in (DATA_LONG, DATA_DIR):
            path = os.path.join(d, f"{sym}.csv")
            if not os.path.exists(path):
                continue
            df = pd.read_csv(path, parse_dates=["date"]).set_index("date")
            df = df[~df.index.duplicated(keep="last")].sort_index()
            if best is None or df.index[-1] > best.index[-1]:
                best = df
        if best is not None:
            closes[sym] = best["close"]
            volumes[sym] = best.get("volume")
            last_bar[sym] = str(best.index[-1].date())
    close = pd.DataFrame(closes).sort_index()
    volume = pd.DataFrame(volumes).reindex(close.index)
    equity_cols = [c for c in close.columns if c != "BTCUSD"]
    mask = close[equity_cols].notna().any(axis=1)
    close, volume = close[mask], volume[mask]
    close = close.ffill()
    return PricePanel(close=close, volume=volume, high=None, low=None), last_bar


def sleeve_allocation(panel: PricePanel, day) -> dict:
    """Concrete target allocation from the OPTIMIZED four-sleeve config."""
    p = OPTIMIZED
    pc = _Precomp(panel, p)
    regime = compute_regime(panel, UNIVERSE, RegimeParams())
    state = regime["state"].reindex(panel.close.index).ffill().iloc[-1]

    row = SLEEVE_MATRIX[state]
    w_macro, w_income = row["macro"], row["income"]
    w_innov, w_opt = row["innovation"], row["options"]
    cyc = cycle_signal(day, p.cycle_params)
    mult = cyc["cycle_multiplier"]
    w_macro, w_innov, w_opt = w_macro * mult, w_innov * mult, w_opt * mult
    eq_total = w_macro + w_innov + w_opt
    max_eq = 1.0 - w_income
    if eq_total > max_eq and eq_total > 0:
        s = max_eq / eq_total
        w_macro, w_innov, w_opt = w_macro * s, w_innov * s, w_opt * s

    macro_w = _sleeve_internal_weights(pc, MACRO_MEMBERS, day, p,
                                       p.macro_trend_gate, None)
    innov_w = _sleeve_internal_weights(pc, INNOVATION_MEMBERS, day, p,
                                       True, p.innovation_top_n)
    # crash guard: proxy the sleeve's trailing vol with the weighted
    # member vol so the live signal matches the backtest's behavior
    if p.innovation_vol_target and innov_w:
        rets = panel.close[list(innov_w)].pct_change().tail(21)
        port = (rets * pd.Series(innov_w)).sum(axis=1)
        realized = float(port.std() * np.sqrt(252))
        if realized > 0:
            guard = min(1.0, p.innovation_vol_target / realized)
            innov_w = {m: w * guard for m, w in innov_w.items()}
    income_w = _income_weights(pc, day, state, p.income_variant)

    positions = {}
    for m, w in macro_w.items():
        positions[m] = positions.get(m, 0) + w * w_macro
    for m, w in innov_w.items():
        positions[m] = positions.get(m, 0) + w * w_innov
    for m, w in income_w.items():
        positions[m] = positions.get(m, 0) + w * w_income
    cash = max(1.0 - sum(positions.values()) - w_opt, 0.0)

    return {
        "state": state,
        "regime_row": regime.iloc[-1].to_dict(),
        "cycle": cyc,
        "sleeve_weights": {"macro": round(w_macro, 3),
                           "income": round(w_income, 3),
                           "innovation": round(w_innov, 3),
                           "options": round(w_opt, 3),
                           "cash": round(cash, 3)},
        "positions": {m: round(w, 4) for m, w in
                      sorted(positions.items(), key=lambda kv: -kv[1])},
        "hedge_signals": {
            "tlt_below_200dma": bool(pc.tlt_below_200.iloc[-1])
            if pc.tlt_below_200 is not None else None,
            "spy_tlt_corr_126d": round(float(pc.spy_tlt_corr.iloc[-1]), 2)
            if pc.spy_tlt_corr is not None else None,
        },
    }


def spot_setup(panel: PricePanel, sym: str, regime_mult: float,
               equity: float, asymmetric: bool) -> dict:
    """Backtest-validated spot trade plan for one name."""
    close = panel.close[sym].dropna()
    px = float(close.iloc[-1])
    atr = float(panel.atr(20)[sym].dropna().iloc[-1])
    ema21 = float(ema(close, 21).iloc[-1])
    hi52 = float(close.tail(252).max())

    if asymmetric or px >= hi52 * 0.99:
        entry_lo, entry_hi, mode = px, px * 1.005, "breakout/now"
    else:
        entry_lo, entry_hi = ema21 - 0.5 * atr, ema21 + 0.5 * atr
        mode = "pullback to EMA21"
    entry = (entry_lo + entry_hi) / 2
    stop = entry - 2.5 * atr
    target = entry + 5.0 * atr          # 2R at the 2.5xATR stop
    risk_frac = 0.01 * regime_mult
    risk_dollars = equity * risk_frac
    shares_full = risk_dollars / (entry - stop) if entry > stop else 0.0
    notional_full = min(shares_full * entry, equity * 0.12)   # 12% cap
    return {
        "symbol": sym, "last": round(px, 2), "atr20": round(atr, 2),
        "mode": mode,
        "entry_zone": [round(entry_lo, 2), round(entry_hi, 2)],
        "stop": round(stop, 2), "target_2R": round(target, 2),
        "trail": "25% from peak after 1R",
        "risk_pct_equity": round(risk_frac * 100, 2),
        "starter_notional": round(notional_full * 0.25, 0),
        "full_notional": round(notional_full, 0),
    }


def run_topdown(top_setups: int = 5, fetch_revisions: bool = True) -> str:
    panel, last_bar = load_merged_panel()
    day = panel.close.index[-1]
    run_date = datetime.utcnow().strftime("%Y-%m-%d")

    # ---- L1 + L2: macro + allocation ----
    alloc = sleeve_allocation(panel, day)
    reg = alloc["regime_row"]
    inv = check_invalidation(panel, day)

    # ---- L3: themes ----
    usable = {k: v for k, v in THEME_MAP.items()
              if any(t in panel.close.columns for t in v["tickers"])}
    themes = latest_theme_ranking(panel, theme_map=usable)

    # ---- L4: stock funnel ----
    scr = screen(panel=panel)
    wl = scr["watchlist"]
    conf = latest_confluence(panel, list(wl.index))
    wl = wl.join(conf[["score", "tier"]].rename(
        columns={"score": "confluence", "tier": "conf_tier"}))

    revisions = {}
    if fetch_revisions:
        # rev_run writes state/revision_velocity.json as a side effect;
        # snapshot it so a failed fetch can't clobber good state from the
        # morning daily run with an empty payload.
        rv_path = os.path.join(STATE_DIR, "revision_velocity.json")
        rv_backup = None
        if os.path.exists(rv_path):
            with open(rv_path) as f:
                rv_backup = f.read()
        try:
            from .revision_velocity import run as rev_run
            payload = rev_run(list(wl.index[:10]))
            if not payload.get("results") and rv_backup is not None:
                with open(rv_path, "w") as f:
                    f.write(rv_backup)
            for sym_row in payload.get("results", []):
                revisions[sym_row["symbol"]] = {
                    "velocity": sym_row.get("weighted_avg"),
                    "signal": sym_row.get("signal"),
                }
            if not payload.get("results") and payload.get("errors"):
                revisions["_error"] = ("no provider reachable for "
                                       + ", ".join(payload["errors"][:5]))
        except Exception as e:                      # noqa: BLE001
            revisions = {"_error": str(e)}
            if rv_backup is not None:
                with open(rv_path, "w") as f:
                    f.write(rv_backup)

    def theme_of(sym):
        for t, cfg in THEME_MAP.items():
            if sym in cfg["tickers"]:
                return t
        return CATEGORY_OF.get(sym, "?")

    # Funnel per the top-down doctrine: REDUCE themes block new entries;
    # WATCH themes demand Gold+ conviction; INCREASE/MAINTAIN allow
    # Silver+. Confluence (close-only approximation, so scored gently)
    # hard-blocks only below 40.
    def theme_action_of(sym):
        t = theme_of(sym)
        return themes.loc[t, "action"] if t in themes.index else "UNMAPPED"

    qualified = []
    for sym, r in wl.iterrows():
        act = theme_action_of(sym)
        if act == "REDUCE" or not r["trend_gate"]:
            continue
        tier_ok = (r["tier"] in ("Platinum", "Gold")
                   or (r["tier"] == "Silver"
                       and act in ("INCREASE", "MAINTAIN", "UNMAPPED")))
        conf_ok = pd.isna(r.get("confluence")) or r["confluence"] >= 40
        if tier_ok and conf_ok:
            qualified.append(sym)

    # ---- L5: spot setups ----
    ledger = load_ledger()
    hist = ledger.get("history") or []
    equity = hist[-1]["equity"] if hist else ledger.get("start_equity", 1e5)
    setups = [spot_setup(panel, s, reg["multiplier"], equity,
                         bool(wl.loc[s, "asymmetric"]))
              for s in qualified[:top_setups]]

    # ---- L6: options structures ----
    atr_panel = panel.atr(20)
    options = []
    for s in qualified[:top_setups]:
        rec = latest_structure_selection(panel.close[s], atr_panel[s])
        rec["symbol"] = s
        options.append(rec)
    smh = panel.close["SMH"].dropna()
    pmcc_ok = bool(smh.iloc[-1] > smh.rolling(200).mean().iloc[-1]
                   and smh.rolling(50).mean().iloc[-1]
                   > smh.rolling(200).mean().iloc[-1])

    # ---- L7: hedges + exits ----
    held = list(ledger.get("positions", {}).keys())
    sell_rows = []
    if held:
        try:
            sc = latest_sell_signals(panel, held)
            sell_rows = [
                {"symbol": s, "triggers": int(r["measured_triggers"]),
                 "action": r["action"]} for s, r in sc.iterrows()]
        except Exception:                           # noqa: BLE001
            pass

    # ================= render =================
    L = [f"# Top-Down Live Update — {run_date}", ""]
    stale = {s: d for s, d in last_bar.items()
             if pd.Timestamp(d) < day - pd.Timedelta(days=3)}
    L += [f"_Data through {day.date()}"
          + (f"; {len(stale)} symbols lag (oldest {min(stale.values())})_"
             if stale else "_"), ""]

    L += ["## L1 — Macro Desk", "",
          f"**Regime:** {alloc['state']} (score {reg['score']}, gross "
          f"{reg['multiplier']:.0%}, breadth {reg['breadth']:.0%})"
          + ("  |  NO NEW LONGS (SMH<200DMA)" if reg.get("no_new_longs")
             else ""),
          f"**Cycle:** year {alloc['cycle']['year_in_cycle']}/4, "
          f"{alloc['cycle']['secular_phase']}, Q{alloc['cycle']['quarter']} "
          f"-> multiplier {alloc['cycle']['cycle_multiplier']:.2f}",
          f"**Secular invalidation:** "
          + ("TRIGGERED — " + inv["reason"] if inv.get("invalidated")
             else "clear (SPY above -20% band vs 200DMA)"), ""]

    sw = alloc["sleeve_weights"]
    L += ["## L2 — Allocation (optimized four-sleeve)", "",
          "| Sleeve | Target |", "|---|---|"]
    for k in ("macro", "income", "innovation", "options", "cash"):
        L.append(f"| {k} | {sw[k]:.1%} |")
    L += ["", "Position-level targets:", "",
          "| Ticker | Weight |", "|---|---|"]
    for m, w in alloc["positions"].items():
        L.append(f"| {m} | {w:.1%} |")
    hs = alloc["hedge_signals"]
    L += ["", f"Hedge signals: TLT below 200DMA = {hs['tlt_below_200dma']} "
          f"(duration halved when True); SPY-TLT corr(126d) = "
          f"{hs['spy_tlt_corr_126d']} (gold takes half of TLT when > 0).", ""]

    L += ["## L3 — Theme Desk", "", "| Theme | Score | Action | Leaders |",
          "|---|---|---|---|"]
    for t, r in themes.iterrows():
        lead = ", ".join(theme_leaders(panel, t, day, theme_map=usable))
        L.append(f"| {t.replace('_', ' ')} | {r['score']:.0f} "
                 f"| {r['action']} | {lead} |")
    L.append("")

    L += ["## L4 — Stock Desk (conviction x confluence x revisions)", "",
          "| Symbol | Conviction | Tier | Confluence | Trend | Theme "
          "| RevVel | Qualified |", "|---|---|---|---|---|---|---|---|"]
    for sym, r in wl.iterrows():
        rv = revisions.get(sym, {})
        L.append(
            f"| {sym} | {r['score']} | {r['tier']} "
            f"| {r.get('confluence', float('nan')):.0f} ({r.get('conf_tier', '?')}) "
            f"| {'Y' if r['trend_gate'] else 'N'} "
            f"| {theme_action_of(sym)} "
            f"| {rv.get('velocity', '—')}"
            f"{(' ' + rv['signal']) if rv.get('signal') else ''} "
            f"| {'YES' if sym in qualified else ''} |")
    if "_error" in revisions:
        L.append(f"\n_Revision velocity unavailable: "
                 f"{revisions['_error'][:120]}_")
    L.append("")

    L += ["## L5 — Spot Trade Setups (validated rules)", ""]
    for s in setups:
        L += [f"### {s['symbol']} — {s['mode']}",
              f"- Last {s['last']}, ATR20 {s['atr20']}",
              f"- Entry zone: {s['entry_zone'][0]} - {s['entry_zone'][1]}",
              f"- Stop: {s['stop']} (2.5xATR)  |  2R target: "
              f"{s['target_2R']}  |  then trail {s['trail']}",
              f"- Risk {s['risk_pct_equity']}% of equity -> starter "
              f"${s['starter_notional']:,.0f} (quarter size), full "
              f"${s['full_notional']:,.0f} (12% cap applied)", ""]
    if not setups:
        L += ["(no names currently clear the full funnel)", ""]

    L += ["## L6 — Options Desk", "",
          f"**SMH PMCC core:** {'ON — regime intact (price>200DMA, 50>200)' if pmcc_ok else 'OFF — regime broken, close/roll diagonals'}"
          " | long 0.75-0.80d LEAPS 12-24m, short 30-45 DTE 0.20-0.25d,"
          " skip the short leg on hyper-momentum names.", "",
          "| Symbol | HV-rank | Structure | Legs (ATR strikes) |",
          "|---|---|---|---|"]
    for o in options:
        legs = {k: v for k, v in o.items()
                if k.endswith(("_call", "_put")) or "strike" in k}
        legs_s = ", ".join(f"{k}={v}" for k, v in legs.items()) or "—"
        L.append(f"| {o['symbol']} | {o.get('rank', float('nan')):.0f} "
                 f"| {o.get('structure', '?')} | {legs_s} |")
    L.append("")

    L += ["## L7 — Hedge Desk & Exits", "",
          f"- Income/hedge sleeve at {sw['income']:.0%}: "
          + ", ".join(f"{m} {w:.1%}" for m, w in alloc["positions"].items()
                      if m in ("TLT", "GLD", "PFF", "GDXJ")),
          f"- Cash buffer: {sw['cash']:.0%}",
          "- Portfolio stop: reduce equity sleeves to ~30% at -20% from "
          "peak; release at -10% (regime matrix usually de-risks first).",
          ]
    if sell_rows:
        L += ["", "Open-position sell composite:", "",
              "| Symbol | Triggers (of 3 measurable) | Action |", "|---|---|---|"]
        L += [f"| {r['symbol']} | {r['triggers']} | {r['action']} |"
              for r in sell_rows]
    L += ["", "## Golden Rules", ""]
    L += [f"- {g}" for g in GOLDEN_RULES]

    report = "\n".join(L) + "\n"
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"topdown-{run_date}.md")
    with open(path, "w") as f:
        f.write(report)

    snapshot = {
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds"),
        "as_of": str(day.date()),
        "regime": alloc["state"],
        "cycle_multiplier": alloc["cycle"]["cycle_multiplier"],
        "sleeve_weights": sw,
        "position_targets": alloc["positions"],
        "themes": [{"theme": t, "score": float(r["score"]),
                    "action": r["action"]} for t, r in themes.iterrows()],
        "qualified": qualified,
        "setups": setups,
        "options": [{k: (float(v) if isinstance(v, (int, float, np.floating))
                         else v) for k, v in o.items()} for o in options],
        "hedge_signals": alloc["hedge_signals"],
        "pmcc_core_on": pmcc_ok,
        "invalidated": bool(inv.get("invalidated")),
    }
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(os.path.join(STATE_DIR, "topdown.json"), "w") as f:
        json.dump(snapshot, f, indent=2, default=str)

    print(report)
    print(f"[topdown report written to {path}]")
    return path
