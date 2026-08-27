"""
Fidelity sleeve analysis -- goal ask #1
("focus on the high beta investments, yield/income investments, options trades
 and macro hedge trades in fidelity")

Reads the Aug-23-2026 position export and maps the live book onto the four
sleeves the goal names, so the sleeves are sized against what is actually
held rather than against an assumed allocation.

Classification is by instrument, in priority order: a position is assigned to
the FIRST sleeve it matches, so an option on a macro hedge (a VIX call, a TLT
call) counts as a macro hedge rather than as generic options exposure -- the
sleeve is about what the position is FOR, not what wrapper it uses.

Run: python3 analyze_fidelity.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

STRATEGY_DIR = Path(__file__).resolve().parent
SRC = STRATEGY_DIR / "Data" / "real_accounts" / "fidelity_positions.csv"
OUT = STRATEGY_DIR / "experiments" / "fidelity"

# --- sleeve definitions ---------------------------------------------------

# Yield / income: instruments held for a coupon or distribution, not price.
YIELD_SYMBOLS = {"STRC", "SATA", "FIAT"}
YIELD_HINTS = ("PFD", "PREFERRED", "VAR RAT", "VAR RT", "YIELDMAX")

# Macro hedge: expresses a view on rates, the dollar, gold, vol, or oil, or is
# an explicit short/inverse. These are the positions meant to PAY when the
# high-beta sleeve is losing.
MACRO_SYMBOLS = {
    "PFIX",   # interest-rate volatility
    "UUP",    # dollar
    "GLDM",   # gold
    "TLT", "IEF",  # duration
    "SOXS",   # inverse semis, 3x
    "BNO", "DBO", "IYE",  # oil / energy
    "VIX",
}

# Underlyings whose options are macro hedges regardless of direction.
MACRO_OPTION_UNDERLYINGS = {"VIX", "TLT", "IEF"}

# Crypto-linked: broken out inside high-beta because the goal treats crypto
# separately, and because it overlaps the Coinbase/Hyperliquid sleeves --
# double-counting crypto beta across accounts is a real risk here.
CRYPTO_SYMBOLS = {
    "MSTR", "IBIT", "BITO", "BKCH", "WGMI", "HECO", "CLSK", "CORZ", "HIVE",
    "IREN", "WULF", "GLXY", "BMNR", "PURR", "HOOD", "SOFI",
}


def parse_option(symbol: str) -> str | None:
    """'-IBIT260918C41' -> 'IBIT'. Returns None for non-options."""
    if not symbol.startswith("-"):
        return None
    body = symbol[1:]
    out = []
    for ch in body:
        if ch.isdigit():
            break
        out.append(ch)
    return "".join(out)


def classify(symbol: str, description: str) -> tuple[str, str]:
    """Returns (sleeve, note)."""
    sym = symbol.strip()
    desc = (description or "").upper()
    underlying = parse_option(sym)
    base = underlying if underlying else sym

    # 1. Macro hedge wins over the options wrapper.
    if base in MACRO_OPTION_UNDERLYINGS or base in MACRO_SYMBOLS:
        return "macro_hedge", f"macro instrument ({base})"

    # 2. Yield / income.
    if base in YIELD_SYMBOLS or any(h in desc for h in YIELD_HINTS):
        return "yield_income", "coupon/distribution instrument"

    # 3. Remaining options.
    if underlying:
        tag = "crypto-linked" if base in CRYPTO_SYMBOLS else "equity"
        return "options", f"option on {base} ({tag})"

    # 4. Everything else is the high-beta sleeve.
    tag = "crypto-linked" if base in CRYPTO_SYMBOLS else "equity/ETF"
    return "high_beta", tag


def main() -> None:
    rows = list(csv.DictReader(SRC.open()))
    for r in rows:
        for k in ("qty", "current_value", "cost_basis", "gain_loss", "pct_of_account"):
            r[k] = float(r[k]) if r[k] not in ("", "None", None) else None
        r["sleeve"], r["note"] = classify(r["symbol"], r["description"])

    PENDING = -8590.93          # unsettled activity from the export
    net_positions = sum(r["current_value"] for r in rows if r["current_value"])
    equity = net_positions + PENDING

    print("=" * 78)
    print("FIDELITY (Z34628250 Joint WROS) -- sleeve analysis, export 2026-08-23")
    print("=" * 78)
    print(f"  gross long        ${sum(r['current_value'] for r in rows if r['current_value'] > 0):>12,.2f}")
    print(f"  short option value${sum(r['current_value'] for r in rows if r['current_value'] < 0):>12,.2f}")
    print(f"  pending activity  ${PENDING:>12,.2f}")
    print(f"  NET EQUITY        ${equity:>12,.2f}")
    print(f"  positions         {len(rows):>13d}")
    print(f"  avg position      ${net_positions / len(rows):>12,.2f}")

    print("\n" + "-" * 78)
    print(f"  {'sleeve':<16s} {'n':>4s} {'value':>12s} {'% net eq':>9s} "
          f"{'cost basis':>12s} {'unreal P/L':>11s}")
    print("-" * 78)
    sleeves = {}
    for name in ("high_beta", "yield_income", "options", "macro_hedge"):
        sel = [r for r in rows if r["sleeve"] == name]
        val = sum(r["current_value"] for r in sel if r["current_value"])
        cb = sum(r["cost_basis"] for r in sel if r["cost_basis"])
        gl = sum(r["gain_loss"] for r in sel if r["gain_loss"])
        sleeves[name] = {"n": len(sel), "value": round(val, 2),
                         "pct_of_equity": round(100 * val / equity, 1),
                         "cost_basis": round(cb, 2), "unrealized": round(gl, 2)}
        print(f"  {name:<16s} {len(sel):>4d} {val:>12,.2f} {100 * val / equity:>8.1f}% "
              f"{cb:>12,.2f} {gl:>11,.2f}")
    print("-" * 78)
    print(f"  {'TOTAL':<16s} {len(rows):>4d} {net_positions:>12,.2f} "
          f"{100 * net_positions / equity:>8.1f}%")
    print(f"\n  Gross positions are {100 * net_positions / equity:.0f}% of net equity because "
          f"${-PENDING:,.0f} of\n  unsettled activity is financed -- this book is running on margin.")

    # --- crypto double-count exposure ---
    crypto = [r for r in rows
              if (parse_option(r["symbol"]) or r["symbol"]) in CRYPTO_SYMBOLS]
    cv = sum(r["current_value"] for r in crypto if r["current_value"])
    print(f"\n  crypto-linked inside Fidelity: {len(crypto)} positions, ${cv:,.2f} "
          f"({100 * cv / equity:.1f}% of net equity)")
    print("  -> this is BETA THE COINBASE AND HYPERLIQUID SLEEVES ALREADY CARRY.")
    print("     Any portfolio-level risk number must net it, not add it.")

    # --- concentration ---
    print("\n" + "-" * 78)
    print("  top 10 positions by |value|")
    print("-" * 78)
    for r in sorted(rows, key=lambda r: -abs(r["current_value"] or 0))[:10]:
        print(f"  {r['symbol']:<16s} {r['sleeve']:<13s} {r['current_value']:>10,.2f} "
              f"{100 * r['current_value'] / equity:>6.1f}%  {r['note']}")

    # --- the capacity problem, again ---
    small = [r for r in rows if r["current_value"] and 0 < r["current_value"] < 200]
    sv = sum(r["current_value"] for r in small)
    print("\n" + "-" * 78)
    print("  CAPACITY")
    print("-" * 78)
    print(f"  positions under $200 : {len(small)} of {len(rows)}  "
          f"(${sv:,.0f}, {100 * sv / equity:.1f}% of equity)")
    print(f"  This is the SAME failure mode as the Merrill book (69 positions")
    print(f"  averaging ~$143). config.yaml's min_position_value_usd of $1,000")
    print(f"  would forbid {len(small)} of the {len(rows)} positions actually held here.")
    print(f"  Barber-Odean (2000) measured 6.5pp/yr of cost drag on exactly this")
    print(f"  structure -- and it is now confirmed in TWO of the four accounts.")

    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "Portfolio_Positions_Aug232026.xlsx",
        "account": "Z34628250 Joint WROS (taxable brokerage, margin)",
        "as_of": "2026-08-23",
        "net_equity_usd": round(equity, 2),
        "gross_position_value_usd": round(net_positions, 2),
        "pending_activity_usd": PENDING,
        "n_positions": len(rows),
        "avg_position_usd": round(net_positions / len(rows), 2),
        "sleeves": sleeves,
        "crypto_linked": {"n": len(crypto), "value_usd": round(cv, 2),
                          "pct_of_equity": round(100 * cv / equity, 1),
                          "warning": "overlaps Coinbase + Hyperliquid sleeves; net, do not add"},
        "capacity": {"positions_under_200usd": len(small),
                     "value_usd": round(sv, 2),
                     "pct_of_equity": round(100 * sv / equity, 1)},
    }
    (OUT / "sleeve_analysis.json").write_text(json.dumps(payload, indent=2))

    with (OUT / "positions_by_sleeve.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sleeve", "symbol", "description", "current_value",
                    "cost_basis", "gain_loss", "note"])
        for r in sorted(rows, key=lambda r: (r["sleeve"], -abs(r["current_value"] or 0))):
            w.writerow([r["sleeve"], r["symbol"], r["description"],
                        r["current_value"], r["cost_basis"], r["gain_loss"], r["note"]])

    print(f"\nsaved: experiments/fidelity/sleeve_analysis.json")
    print(f"saved: experiments/fidelity/positions_by_sleeve.csv")


if __name__ == "__main__":
    main()
