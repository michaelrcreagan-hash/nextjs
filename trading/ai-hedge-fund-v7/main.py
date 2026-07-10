#!/usr/bin/env python3
"""
AI Hedge Fund v7.0 — Unified Top-Down Trading System
====================================================
Usage:
    python main.py --scan              Full scan
    python main.py --regime            Regime only
    python main.py --ticker NVDA       Single ticker deep dive
    python main.py --breakout          Breakout signals only
    python main.py --pullback          Pullback signals only
    python main.py --options           Options trades
    python main.py --hedge             Macro hedges
    python main.py --output report.json  Save to file
"""
import argparse
import json
import sys
from pathlib import Path

# Ensure engine is importable
sys.path.insert(0, str(Path(__file__).parent))

from src.engine.scanner import LiveScanner
from src.engine.regime import fetch_regime_data, detect_regime, REGIME_MATRIX
from src.engine.composite import CompositeScorer
from src.engine.breakout import atr_rsi_breakout
from src.engine.pullback import fib_keltner_pullback
from src.engine.options import build_options_trade
from src.engine.hedge import build_hedge_portfolio, fetch_vix
from src.engine.universe import FULL_UNIVERSE, get_peers


def cmd_scan(args):
    """Run full top-down scan."""
    scanner = LiveScanner()
    report = scanner.full_scan(limit=args.top_n)
    scanner.print_report()
    if args.output:
        scanner.to_json(args.output)
        print(f"\nReport saved to {args.output}")
    return report

def cmd_regime(args):
    """Show current macro regime."""
    data = fetch_regime_data()
    regime, score = detect_regime(
        vix=data["vix"],
        smh_above_200dma=data["smh_above_200dma"],
        breadth_pct=data.get("breadth_pct", 60.0),
        btc_trend=data.get("btc_trend", "neutral"),
    )
    alloc = REGIME_MATRIX[regime]
    print(f"Regime: {regime.value}")
    print(f"Score: {score:.1f}")
    print(f"VIX: {data['vix']:.2f}")
    print(f"SMH > 200DMA: {data['smh_above_200dma']}")
    print(f"\n4-Sleeve Allocation:")
    for k, v in alloc.items():
        print(f"  {k:12s}: {v:5.0%}")

def cmd_ticker(args):
    """Deep dive on single ticker."""
    t = args.ticker.upper()
    print(f"\n{'='*50}")
    print(f"DEEP DIVE: {t}")
    print(f"{'='*50}")

    scorer = CompositeScorer()
    peers = get_peers(t)
    comp, breakdown = scorer.score(t, peers=peers)
    print(f"\n[COMPOSITE SCORE] {comp:.1f}/100")
    for k, v in breakdown.items():
        bar = "█" * int(v / 5) + "░" * (20 - int(v / 5))
        print(f"  {k:12s}: {v:5.1f} {bar}")

    b = atr_rsi_breakout(t)
    print(f"\n[BREAKOUT] Trigger: {b.trigger}")
    if b.trigger:
        print(f"  ATR%: {b.atr_pct:.2f} | RSI: {b.rsi:.1f}")
        print(f"  Entry: ${b.close:.2f} | Stop: ${b.stop_loss:.2f} | Target: ${b.target:.2f}")
        print(f"  Risk:Reward = 1:{b.risk_reward:.2f}")

    p = fib_keltner_pullback(t)
    print(f"\n[PULLBACK] Trigger: {p.trigger}")
    if p.trigger:
        print(f"  Fib Dist: {p.fib_dist:.2f}% | Keltner Pos: {p.keltner_position:.3f}")
        print(f"  Entry: ${p.close:.2f} | Stop: ${p.stop_loss:.2f} | Target: ${p.target:.2f}")
        print(f"  Risk:Reward = 1:{p.risk_reward:.2f}")

    from src.engine.options import compute_iv_rank
    iv = compute_iv_rank(t)
    setup = "breakout" if comp > 65 else "pullback"
    from src.engine.regime import fetch_regime_data, detect_regime
    rd = fetch_regime_data()
    regime, _ = detect_regime(**{k: rd.get(k, 0 if k != "btc_trend" else "neutral") for k in ["vix", "smh_above_200dma", "breadth_pct", "btc_trend"]})
    ot = build_options_trade(t, comp, setup, regime.value)
    print(f"\n[OPTIONS] IV Rank: {iv:.0f}%")
    print(f"  Strategy: {ot.strategy.value}")
    print(f"  Direction: {ot.direction}")
    print(f"  {ot.recommendation}")
    print(f"  Sizing: {ot.sizing}")
    print(f"  Strikes: {ot.strike_suggestion}")
    print(f"  Expiry: {ot.expiration_suggestion}")

def cmd_breakout(args):
    """Scan for breakout signals."""
    from src.engine.breakout import batch_breakout
    print("Scanning for ATR+RSI breakout signals...")
    signals = batch_breakout(FULL_UNIVERSE)
    print(f"\nFound {len(signals)} breakout signals:")
    for s in signals[:15]:
        print(f"  {s.ticker:6s} ATR%:{s.atr_pct:5.2f} RSI:{s.rsi:4.1f} "
              f"Close:${s.close:7.2f} R:R 1:{s.risk_reward:.2f}")

def cmd_pullback(args):
    """Scan for pullback signals."""
    from src.engine.pullback import batch_pullback
    print("Scanning for Fib 61.8%+Keltner Lower pullback signals...")
    signals = batch_pullback(FULL_UNIVERSE)
    print(f"\nFound {len(signals)} pullback signals:")
    for s in signals[:15]:
        print(f"  {s.ticker:6s} FibDist:{s.fib_dist:5.2f}% "
              f"Close:${s.close:7.2f} R:R 1:{s.risk_reward:.2f}")

def cmd_options(args):
    """Generate options trades for top composite scorers."""
    scanner = LiveScanner()
    regime_data = scanner.scan_regime()
    composite = scanner.scan_composite()
    top = [c for c in composite if c["composite"] > 50][:15]
    trades = scanner.scan_options(top, regime_data["regime"])
    print(f"Regime: {regime_data['regime']} | VIX: {regime_data['vix']:.1f}\n")
    for t in trades:
        print(f"{t['ticker']:6s} {t['strategy']:15s} | {t['direction']:8s} | "
              f"IV:{t['iv_rank']:4.0f} | {t['sizing']}")
        print(f"         {t['recommendation']}")
        print(f"         Strikes: {t['strike']} | Exp: {t['expiration']}\n")

def cmd_hedge(args):
    """Show macro hedge recommendations."""
    from src.engine.regime import fetch_regime_data, detect_regime, REGIME_MATRIX
    from src.engine.hedge import get_active_hedge_signals
    rd = fetch_regime_data()
    regime, score = detect_regime(
        vix=rd["vix"],
        smh_above_200dma=rd["smh_above_200dma"],
        breadth_pct=rd.get("breadth_pct", 60.0),
        btc_trend=rd.get("btc_trend", "neutral"),
    )
    hedge = build_hedge_portfolio(regime.value, rd["vix"])
    print(f"Regime: {regime.value} (score: {score:.1f})")
    print(f"VIX: {rd['vix']:.2f}")
    print(f"\nHedge Allocation: {hedge.total_allocation:.1f}%")
    print(f"Cash: {hedge.cash_pct:.1f}%")
    print(f"\n{hedge.reasoning}\n")
    for h in hedge.hedges:
        print(f"  {h['instrument']:6s} {h['allocation_pct']:5.2f}% = ${h['dollar_amount']:,.0f}")
    print(f"\nActive Hedge Signals:")
    for sig in get_active_hedge_signals():
        print(f"  [{sig['action']}] {sig['sizing']}")


def main():
    parser = argparse.ArgumentParser(
        description="AI Hedge Fund v7.0 — Unified Trading System"
    )
    parser.add_argument("--scan", action="store_true", help="Full top-down scan")
    parser.add_argument("--regime", action="store_true", help="Regime detection only")
    parser.add_argument("--ticker", type=str, help="Single ticker deep dive")
    parser.add_argument("--breakout", action="store_true", help="Breakout signals")
    parser.add_argument("--pullback", action="store_true", help="Pullback signals")
    parser.add_argument("--options", action="store_true", help="Options trades")
    parser.add_argument("--hedge", action="store_true", help="Macro hedges")
    parser.add_argument("--top-n", type=int, default=15, help="Number of top tickers")
    parser.add_argument("--output", type=str, help="Save JSON report to file")

    args = parser.parse_args()

    if args.regime:
        cmd_regime(args)
    elif args.ticker:
        cmd_ticker(args)
    elif args.breakout:
        cmd_breakout(args)
    elif args.pullback:
        cmd_pullback(args)
    elif args.options:
        cmd_options(args)
    elif args.hedge:
        cmd_hedge(args)
    else:
        # Default: full scan
        cmd_scan(args)


if __name__ == "__main__":
    main()
