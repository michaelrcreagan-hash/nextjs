"""Options desk: LEAPS-diagonal (PMCC) simulation via Black-Scholes.

No historical options chains exist in this environment, so legs are priced
with Black-Scholes using an IV proxy (20-day realized vol * ``iv_premium``,
floored). This is an approximation — good for comparing structures and
management rules, not for absolute-P&L bragging rights. The ``iv_premium``
knob controls how rich sold premium is vs realized; 1.0 bakes in NO edge
from selling (conservative default for honest testing).

Structure per the options agent's embedded strategy:
  - Long deep-ITM LEAPS call, target delta ~0.80, ~18 months out,
    rolled when 12 months remain (or on 100% gain).
  - Short ~35 DTE call at target delta ~0.22, bought back at 50% profit
    or rolled at 21 DTE.
  - Regime filter: only hold the diagonal while price > 200-SMA and
    50-SMA > 200-SMA; regime break closes everything to cash.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call(s: float, k: float, t: float, sigma: float, r: float = 0.04) -> float:
    if t <= 0:
        return max(0.0, s - k)
    if sigma <= 0:
        return max(0.0, s - k * math.exp(-r * t))
    d1 = (math.log(s / k) + (r + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    return s * _ncdf(d1) - k * math.exp(-r * t) * _ncdf(d2)


def call_delta(s: float, k: float, t: float, sigma: float, r: float = 0.04) -> float:
    if t <= 0 or sigma <= 0:
        return 1.0 if s > k else 0.0
    d1 = (math.log(s / k) + (r + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
    return _ncdf(d1)


def strike_for_delta(
    s: float, t: float, sigma: float, tgt_delta: float, r: float = 0.04
) -> float:
    """Invert BS delta for the strike (exact via inverse normal approx)."""
    # d1 = ndtri(tgt_delta); use Acklam-style rational approx of probit.
    p = min(max(tgt_delta, 1e-6), 1 - 1e-6)
    # Beasley-Springer-Moro approximation
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        z = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    elif p <= phigh:
        q = p - 0.5
        rr = q * q
        z = (((((a[0] * rr + a[1]) * rr + a[2]) * rr + a[3]) * rr + a[4]) * rr + a[5]) * q / (
            ((((b[0] * rr + b[1]) * rr + b[2]) * rr + b[3]) * rr + b[4]) * rr + 1
        )
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        z = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    return s * math.exp(-(z * sigma * math.sqrt(t) - (0.04 + 0.5 * sigma**2) * t))


@dataclass
class PMCCParams:
    leaps_delta: float = 0.80
    leaps_days: int = 540          # ~18 months at initiation
    leaps_roll_days: int = 365     # roll when this many days remain
    short_delta: float = 0.22
    short_days: int = 35
    short_roll_dte: int = 21
    short_profit_take: float = 0.50
    sell_short_leg: bool = True
    use_regime: bool = True
    iv_premium: float = 1.0        # IV = HV * this (1.0 = no sell edge assumed)
    iv_floor: float = 0.15
    hv_window: int = 20
    cost_frac: float = 0.01        # per side, fraction of option premium
    # Stock-replacement sizing: hold contracts covering this fraction of
    # equity in share-equivalents (1.0 = same exposure as 100% shares).
    # The unspent cash (the structure's whole point) earns ``cash_yield``.
    exposure: float = 1.0
    cash_yield: float = 0.04
    start_equity: float = 100_000.0


def run_pmcc(
    close: pd.Series,
    params: PMCCParams | None = None,
    start: str | None = None,
    end: str | None = None,
) -> tuple[pd.Series, pd.DataFrame]:
    p = params or PMCCParams()
    close = close.dropna()
    if start:
        close = close.loc[start:]
    if end:
        close = close.loc[:end]

    logret = np.log(close / close.shift(1))
    hv = logret.rolling(p.hv_window).std() * math.sqrt(TRADING_DAYS)
    iv = (hv * p.iv_premium).clip(lower=p.iv_floor)
    ma200 = close.rolling(200).mean()
    ma50 = close.rolling(50).mean()
    regime_ok = (close > ma200) & (ma50 > ma200)

    cash = p.start_equity
    # long leg state
    l_strike = l_expiry_i = None
    l_contracts = 0.0
    # short leg state
    s_strike = s_expiry_i = None
    s_contracts = 0.0
    s_premium_in = 0.0

    equity_hist = {}
    events = []
    idx = close.index

    def leg_val(i, strike, expiry_i, sigma):
        t = max(0, (expiry_i - i)) / TRADING_DAYS
        return bs_call(close.iloc[i], strike, t, sigma)

    for i, day in enumerate(idx):
        s = close.iloc[i]
        sigma = iv.iloc[i]
        if not np.isfinite(sigma):
            equity_hist[day] = cash
            continue

        gate = regime_ok.iloc[i] if p.use_regime else True

        # --- mark ---
        lv = leg_val(i, l_strike, l_expiry_i, sigma) * l_contracts if l_contracts else 0.0
        sv = leg_val(i, s_strike, s_expiry_i, sigma) * s_contracts if s_contracts else 0.0
        equity_hist[day] = cash + lv - sv

        # --- regime break: liquidate ---
        if l_contracts and not gate:
            cash += lv * (1 - p.cost_frac)
            if s_contracts:
                cash -= sv * (1 + p.cost_frac)
            events.append({"date": day, "action": "regime_exit", "px": s})
            l_contracts = s_contracts = 0.0
            l_strike = s_strike = None
            continue

        # --- accrue cash yield (daily) ---
        cash *= 1 + p.cash_yield / TRADING_DAYS

        # --- open long leg (stock-replacement sizing) ---
        if not l_contracts and gate:
            t = p.leaps_days / TRADING_DAYS
            l_strike = strike_for_delta(s, t, sigma, p.leaps_delta)
            l_expiry_i = i + p.leaps_days
            price = bs_call(s, l_strike, t, sigma)
            nav = cash
            share_equiv = nav * p.exposure / s          # shares we'd otherwise own
            l_contracts = share_equiv                    # 1 option covers 1 share-equiv
            spend = l_contracts * price * (1 + p.cost_frac)
            if spend > cash:                             # cap at available cash
                l_contracts = cash / (price * (1 + p.cost_frac))
                spend = cash
            cash -= spend
            events.append({"date": day, "action": "open_leaps", "px": s, "strike": l_strike})

        # --- roll long leg at 12 months remaining ---
        if l_contracts and (l_expiry_i - i) <= p.leaps_roll_days:
            val = leg_val(i, l_strike, l_expiry_i, sigma) * l_contracts
            cash += val * (1 - p.cost_frac)
            t = p.leaps_days / TRADING_DAYS
            l_strike = strike_for_delta(s, t, sigma, p.leaps_delta)
            l_expiry_i = i + p.leaps_days
            price = bs_call(s, l_strike, t, sigma)
            nav = cash + 0.0
            share_equiv = nav * p.exposure / s
            l_contracts = share_equiv
            spend = l_contracts * price * (1 + p.cost_frac)
            if spend > cash:
                l_contracts = cash / (price * (1 + p.cost_frac))
                spend = cash
            cash -= spend
            events.append({"date": day, "action": "roll_leaps", "px": s, "strike": l_strike})

        # --- short leg management ---
        if s_contracts:
            sval = leg_val(i, s_strike, s_expiry_i, sigma)
            dte = s_expiry_i - i
            if (
                sval <= s_premium_in * (1 - p.short_profit_take)
                or dte <= p.short_roll_dte
            ):
                cash -= sval * s_contracts * (1 + p.cost_frac)
                won = sval <= s_premium_in * (1 - p.short_profit_take)
                events.append(
                    {"date": day, "action": "close_short", "px": s,
                     "pnl": (s_premium_in - sval) * s_contracts, "won": won}
                )
                s_contracts = 0.0
                s_strike = None

        # --- sell new short leg ---
        if p.sell_short_leg and l_contracts and not s_contracts and gate:
            t = p.short_days / TRADING_DAYS
            k = strike_for_delta(s, t, sigma, p.short_delta)
            # never strike below LEAPS breakeven zone
            k = max(k, l_strike * 1.02)
            price = bs_call(s, k, t, sigma)
            s_strike, s_expiry_i = k, i + p.short_days
            s_contracts = l_contracts  # 1:1 covered by long delta
            s_premium_in = price
            cash += price * s_contracts * (1 - p.cost_frac)
            events.append({"date": day, "action": "sell_short", "px": s, "strike": k})

    eq = pd.Series(equity_hist).sort_index()
    ev = pd.DataFrame(events)
    return eq, ev
