"""
hermes_agent -- Step 2: Regime Engine

Classifies each bar RISK_ON / MIXED / CAUTION / RISK_OFF and emits the gross
exposure multiplier that drives both position sizing and trailing-stop width.

WHY THIS IS A PROXY, NOT macro_sector_dominance's MODEL
--------------------------------------------------------
config.strategy_params.regime.source_template points at
strategies/macro_sector_dominance's `regime_score_model`, and BUILD_PLAN.md
says to start from it rather than reinvent. That model scores five inputs:

    VIX, SMH vs 50/200-DMA, net liquidity (Fed BS - TGA - RRP), ISM new
    orders, DXY.

NONE of those five are in this panel. Data/btc_historical_data.csv carries
BTC/ETH/SOL, five spot-BTC ETFs, MSTR, SPY and TLT -- no vol index, no
semis proxy, no macro series. Wiring FRED is real separate work and
BUILD_PLAN.md marked macro series "optional for baseline".

So this is a **structural port, not a data port**: the 0-12 score, the four
labels, and the [8,12]/[5,7]/[2,4]/[0,1] bands are preserved exactly so
results stay comparable to macro_sector_dominance, while each component is
served by the closest available substitute. The substitutions, stated plainly
because they are the weakest link in this step:

  | Original          | Substitute here                  | Quality        |
  |-------------------|----------------------------------|----------------|
  | VIX               | SPY 30d realized vol, percentile | Good           |
  | SMH vs 50/200-DMA | SPY vs its own 50/200-DMA        | Good           |
  | Net liquidity     | TLT 20d trend (rates proxy)      | WEAK -- flagged|
  | ISM + DXY         | BTC vs 50/200-DMA (risk appetite)| Different thing|

The TLT substitution is the one to distrust. TLT rising means yields falling
means easing, which correlates with expanding liquidity but is not it. The
ISM/DXY slot has been repurposed rather than approximated -- crypto risk
appetite is a genuinely different signal, chosen because it is the one this
book is actually exposed to. Neither claims fidelity to the original.

Consequence for R1: a regime engine built on proxies is a weaker test of the
regime mechanism than one built on the real inputs. If the baseline fails, the
proxies are a live explanation and are the first thing to fix -- not evidence
that regime conditioning does not work.

LOOKAHEAD: every rolling statistic below is passed through shift1(). The
regime label at bar t is computable strictly from bars < t. This is the
highest-risk lookahead surface in the build; test_lookahead() proves it by
recomputing from truncated arrays.
"""

from __future__ import annotations

import numpy as np

from .data_loader import rolling_mean, rolling_std, returns, shift1

RISK_ON, MIXED, CAUTION, RISK_OFF = 0, 1, 2, 3
REGIME_NAMES = ["RISK_ON", "MIXED", "CAUTION", "RISK_OFF"]


def _rolling_percentile_rank(x: np.ndarray, window: int) -> np.ndarray:
    """
    Fraction of the trailing `window` observations that x[t] exceeds.

    Expanding-then-rolling: a fixed cutoff would have to be chosen from the
    whole sample (lookahead). config.strategy_params.regime specifies
    vol_cluster_threshold: percentile precisely to avoid that.
    """
    n = x.shape[0]
    out = np.full(n, np.nan)
    for t in range(window, n):
        w = x[t - window:t]
        w = w[~np.isnan(w)]
        if w.size >= window // 2 and not np.isnan(x[t]):
            out[t] = (w < x[t]).mean()
    return out


def compute_regime(panel: dict, params: dict) -> dict:
    """
    Returns dict with:
        score           float64 (n_bars,)  0-12, NaN while warming up
        labels          int8    (n_bars,)  RISK_ON..RISK_OFF; RISK_OFF while warm-up
        gross_exposure  float64 (n_bars,)  fraction 0.0-0.8
        trail_pct       float64 (n_bars,)  regime-scaled trailing distance, %
    """
    close = panel["close"]
    symbols = panel["symbols"]
    n = panel["n_bars"]

    rp = params["strategy_params"]["regime"]
    vol_lb = int(rp["vol_lookback_days"])
    vol_p = float(rp["vol_percentile"])

    i_spy = symbols.index("SPY")
    i_tlt = symbols.index("TLT")
    i_btc = symbols.index("BTC-USD")

    rets = returns(close)

    # --- Component 1: volatility regime (0-3), replaces VIX --------------
    # shift1 first, so the vol at bar t uses returns through t-1 only.
    spy_vol = rolling_std(shift1(rets[:, i_spy:i_spy + 1]), vol_lb)[:, 0]
    vol_rank = _rolling_percentile_rank(spy_vol, 120)

    c_vol = np.full(n, np.nan)
    calm = vol_rank < (vol_p - 0.25)          # e.g. < 0.50
    mid = (vol_rank >= (vol_p - 0.25)) & (vol_rank < vol_p)
    hot = vol_rank >= vol_p                    # e.g. >= 0.75 -> vol cluster
    c_vol[calm] = 3.0
    c_vol[mid] = 1.0
    c_vol[hot] = 0.0

    # --- Component 2: equity trend (-2..4), replaces SMH vs DMAs ---------
    spy = close[:, i_spy:i_spy + 1]
    spy_50 = shift1(rolling_mean(spy, 50))[:, 0]
    spy_200 = shift1(rolling_mean(spy, 200))[:, 0]
    spy_prev = shift1(spy)[:, 0]

    c_trend = np.full(n, np.nan)
    ok = ~np.isnan(spy_50) & ~np.isnan(spy_200) & ~np.isnan(spy_prev)
    above50 = ok & (spy_prev > spy_50)
    above200 = ok & (spy_prev > spy_200)
    c_trend[ok] = -2.0
    c_trend[above200] = 2.0
    c_trend[above50 & above200] = 4.0

    # --- Component 3: liquidity proxy (0-2), replaces net liquidity ------
    # WEAK SUBSTITUTION -- see module docstring.
    tlt = close[:, i_tlt:i_tlt + 1]
    tlt_20 = shift1(rolling_mean(tlt, 20))[:, 0]
    tlt_prev = shift1(tlt)[:, 0]
    c_liq = np.full(n, np.nan)
    okl = ~np.isnan(tlt_20) & ~np.isnan(tlt_prev)
    c_liq[okl] = 0.0
    c_liq[okl & (tlt_prev > tlt_20)] = 2.0
    c_liq[okl & (np.abs(tlt_prev / tlt_20 - 1.0) < 0.005)] = 1.0

    # --- Component 4: crypto risk appetite (0-3), repurposed ISM/DXY slot -
    btc = close[:, i_btc:i_btc + 1]
    btc_50 = shift1(rolling_mean(btc, 50))[:, 0]
    btc_200 = shift1(rolling_mean(btc, 200))[:, 0]
    btc_prev = shift1(btc)[:, 0]
    c_btc = np.full(n, np.nan)
    okb = ~np.isnan(btc_50) & ~np.isnan(btc_200) & ~np.isnan(btc_prev)
    c_btc[okb] = 0.0
    c_btc[okb & (btc_prev > btc_200)] = 1.5
    c_btc[okb & (btc_prev > btc_50) & (btc_prev > btc_200)] = 3.0

    # --- Score and labels -------------------------------------------------
    score = c_vol + c_trend + c_liq + c_btc          # max 3+4+2+3 = 12
    score = np.clip(score, 0.0, 12.0)

    labels = np.full(n, RISK_OFF, dtype=np.int8)
    warm = ~np.isnan(score)
    labels[warm & (score >= 8.0)] = RISK_ON
    labels[warm & (score >= 5.0) & (score < 8.0)] = MIXED
    labels[warm & (score >= 2.0) & (score < 5.0)] = CAUTION
    labels[warm & (score < 2.0)] = RISK_OFF
    # During warm-up the strategy is flat, not guessing: RISK_OFF -> 0% gross.
    labels[~warm] = RISK_OFF

    ge_cfg = params["regime_gross_exposure"]
    gross = np.array([ge_cfg[name] / 100.0 for name in REGIME_NAMES])[labels]

    ts_cfg = params["strategy_params"]["trailing_stop_by_regime"]
    trail = np.array([float(ts_cfg[name]) for name in REGIME_NAMES])[labels]

    return {
        "score": score,
        "labels": labels,
        "gross_exposure": np.ascontiguousarray(gross, dtype=np.float64),
        "trail_pct": np.ascontiguousarray(trail, dtype=np.float64),
        "warm": warm,
    }


def occupancy(labels: np.ndarray) -> dict:
    n = labels.shape[0]
    return {REGIME_NAMES[i]: round(100.0 * float((labels == i).sum()) / n, 1)
            for i in range(4)}


def test_lookahead(panel: dict, params: dict, probes: tuple = (250, 350, 450)) -> bool:
    """
    Truncated-array recompute test.

    The regime label at bar t computed from the FULL array must equal the label
    at bar t computed from only bars [0:t+1]. If it does not, something in the
    chain is reading forward. This is the check that actually catches a missing
    shift1() -- a visual code review does not.
    """
    full = compute_regime(panel, params)
    ok = True
    for t in probes:
        if t >= panel["n_bars"]:
            continue
        trunc_panel = dict(panel)
        trunc_panel["close"] = np.ascontiguousarray(panel["close"][:t + 1])
        trunc_panel["dates"] = panel["dates"][:t + 1]
        trunc_panel["n_bars"] = t + 1
        tr = compute_regime(trunc_panel, params)
        same_label = tr["labels"][t] == full["labels"][t]
        s_a, s_b = tr["score"][t], full["score"][t]
        same_score = (np.isnan(s_a) and np.isnan(s_b)) or np.isclose(s_a, s_b)
        if not (same_label and same_score):
            ok = False
            print(f"  LOOKAHEAD at t={t}: truncated "
                  f"label={tr['labels'][t]} score={s_a} vs "
                  f"full label={full['labels'][t]} score={s_b}")
    return ok


if __name__ == "__main__":
    import yaml
    from pathlib import Path
    from .data_loader import load_panel

    cfg = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.yaml").read_text())
    p = load_panel(start_date=cfg["time"]["start_date"])
    r = compute_regime(p, cfg)

    print("regime occupancy (%):", occupancy(r["labels"]))
    print(f"warm-up bars (flat)  : {int((~r['warm']).sum())} of {p['n_bars']}")
    print(f"mean gross exposure  : {r['gross_exposure'].mean():.3f} "
          f"-> mean cash {100 * (1 - r['gross_exposure'].mean()):.1f}%")
    print(f"mean gross (post-warm): "
          f"{r['gross_exposure'][r['warm']].mean():.3f}")
    print("lookahead recompute test:",
          "PASS" if test_lookahead(p, cfg) else "FAIL")
