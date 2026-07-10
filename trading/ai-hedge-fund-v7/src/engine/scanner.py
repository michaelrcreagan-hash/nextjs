"""
Phase 7: Live Scanner Orchestrator
Top-down: Regime -> Universe -> Composite -> Signal -> Options/Hedge
"""
from datetime import datetime
from typing import Dict, List, Optional
import json

from .regime import detect_regime, fetch_regime_data, Regime, REGIME_MATRIX
from .composite import CompositeScorer
from .breakout import atr_rsi_breakout, batch_breakout
from .pullback import fib_keltner_pullback, batch_pullback
from .confluence import compute_confluence_score, batch_confluence
from .options import build_options_trade
from .hedge import build_hedge_portfolio, fetch_vix, get_active_hedge_signals
from .universe import FULL_UNIVERSE, get_peers, get_sector_etf, get_tier, get_sleeve


class LiveScanner:
    """
    Full top-down scanner:
    1. Detect macro regime
    2. Score universe with 6-module composite
    3. Find breakout & pullback signals
    4. Build options trades
    5. Generate macro hedges
    """

    def __init__(self, universe: Optional[List[str]] = None):
        self.universe = universe or FULL_UNIVERSE
        self.scorer = CompositeScorer()
        self.results: Dict = {}

    def scan_regime(self) -> Dict:
        """Phase 1: Macro regime detection."""
        data = fetch_regime_data()
        regime, score = detect_regime(
            vix=data["vix"],
            smh_above_200dma=data["smh_above_200dma"],
            breadth_pct=data.get("breadth_pct", 60.0),
            btc_trend=data.get("btc_trend", "neutral"),
        )
        allocation = REGIME_MATRIX[regime]
        return {
            "regime": regime.value,
            "score": score,
            "vix": data["vix"],
            "allocation": allocation,
            "timestamp": datetime.now().isoformat(),
        }

    def scan_composite(self, tickers: Optional[List[str]] = None) -> List[Dict]:
        """Phase 2: 6-module composite scoring."""
        targets = tickers or self.universe
        scored = []
        for t in targets:
            peers = get_peers(t)
            composite, breakdown = self.scorer.score(t, peers=peers)
            scored.append({
                "ticker": t,
                "tier": get_tier(t),
                "sleeve": get_sleeve(t),
                "composite": round(composite, 2),
                "breakdown": {k: round(v, 2) for k, v in breakdown.items()},
            })
        scored.sort(key=lambda x: x["composite"], reverse=True)
        return scored

    def scan_signals(self, tickers: Optional[List[str]] = None) -> Dict:
        """Phase 3: Breakout & pullback signal detection."""
        targets = tickers or self.universe
        breakouts = []
        pullbacks = []
        for t in targets:
            b = atr_rsi_breakout(t)
            if b.trigger:
                breakouts.append(b.to_dict())
            p = fib_keltner_pullback(t)
            if p.trigger:
                pullbacks.append(p.to_dict())
        breakouts.sort(key=lambda x: x.get("risk_reward", 0), reverse=True)
        pullbacks.sort(key=lambda x: x.get("risk_reward", 0), reverse=True)
        return {"breakouts": breakouts, "pullbacks": pullbacks}

    def scan_confluence(self, tickers: Optional[List[str]] = None) -> List[Dict]:
        """Phase 4: IAE 8-layer technical confluence."""
        targets = tickers or self.universe
        results = []
        for t in targets:
            c = compute_confluence_score(t, sector_etf=get_sector_etf(t))
            results.append(c.to_dict())
        results.sort(key=lambda x: x["composite"], reverse=True)
        return results

    def scan_options(self, top_tickers: List[str], regime: str) -> List[Dict]:
        """Phase 5: Options trade recommendations."""
        trades = []
        for item in top_tickers:
            t = item["ticker"] if isinstance(item, dict) else item
            comp = item["composite"] if isinstance(item, dict) else 50.0
            setup = "breakout" if comp > 65 else "pullback"
            trade = build_options_trade(t, comp, setup, regime)
            trades.append(trade.to_dict())
        return trades

    def scan_hedges(self, regime: str) -> Dict:
        """Phase 6: Macro hedge portfolio."""
        vix = fetch_vix()
        hedge = build_hedge_portfolio(regime, vix)
        return hedge.to_dict()

    def full_scan(self, limit: int = 15) -> Dict:
        """
        Run complete top-down scan.
        Returns full report with regime, scores, signals, options, hedges.
        """
        print("[1/6] Detecting macro regime...")
        regime_data = self.scan_regime()
        regime = regime_data["regime"]

        print(f"[2/6] Scoring {len(self.universe)} tickers...")
        composite = self.scan_composite()
        top = [c for c in composite if c["composite"] > 50][:limit]

        print("[3/6] Finding breakout & pullback signals...")
        signals = self.scan_signals()

        print("[4/6] Computing technical confluence...")
        confluence = self.scan_confluence([c["ticker"] for c in top])

        print("[5/6] Building options trades...")
        options = self.scan_options(top, regime)

        print("[6/6] Generating macro hedges...")
        hedges = self.scan_hedges(regime)

        report = {
            "timestamp": datetime.now().isoformat(),
            "regime": regime_data,
            "top_composite": top,
            "all_composite": composite,
            "signals": signals,
            "confluence": confluence,
            "options_trades": options,
            "macro_hedges": hedges,
            "hedge_signals": get_active_hedge_signals(),
        }
        self.results = report
        return report

    def to_json(self, path: Optional[str] = None) -> str:
        """Export results to JSON."""
        data = json.dumps(self.results, indent=2, default=str)
        if path:
            with open(path, "w") as f:
                f.write(data)
        return data

    def print_report(self):
        """Print formatted scan report."""
        r = self.results
        if not r:
            print("No scan results. Run full_scan() first.")
            return

        print("=" * 60)
        print(f"  AI HEDGE FUND v7.0 — LIVE SCAN REPORT")
        print(f"  {r['timestamp']}")
        print("=" * 60)

        rd = r["regime"]
        print(f"\n[MACRO REGIME] {rd['regime']} (score: {rd['score']:.1f}, VIX: {rd['vix']:.1f})")
        alloc = rd["allocation"]
        print(f"  Sleeve Alloc: Macro {alloc['macro']:.0%} | Income {alloc['income']:.0%} | "
              f"Innov {alloc['innovation']:.0%} | Opt {alloc['options']:.0%} | Cash {alloc['cash']:.0%}")

        print(f"\n[TOP 10 COMPOSITE SCORES]")
        for i, c in enumerate(r["top_composite"][:10], 1):
            print(f"  {i:2d}. {c['ticker']:6s} T{c['tier']} | {c['sleeve']:12s} | "
                  f"Score: {c['composite']:5.1f}")

        sig = r["signals"]
        if sig["breakouts"]:
            print(f"\n[BREAKOUT SIGNALS] ({len(sig['breakouts'])} found)")
            for b in sig["breakouts"][:5]:
                print(f"  {b['ticker']:6s} ATR%:{b['atr_pct']:5.2f} RSI:{b['rsi']:4.1f} "
                      f"R:R {b['risk_reward']:.2f}")
        if sig["pullbacks"]:
            print(f"\n[PULLBACK SIGNALS] ({len(sig['pullbacks'])} found)")
            for p in sig["pullbacks"][:5]:
                print(f"  {p['ticker']:6s} FibDist:{p['fib_dist_pct']:4.2f}% "
                      f"R:R {p['risk_reward']:.2f}")

        print(f"\n[OPTIONS TRADES] ({len(r['options_trades'])})")
        for o in r["options_trades"][:5]:
            print(f"  {o['ticker']:6s} {o['strategy']:15s} | {o['direction']:8s} | "
                  f"IV:{o['iv_rank']:4.0f} | {o['sizing']}")

        h = r["macro_hedges"]
        print(f"\n[MACRO HEDGE] {h['total_hedge_allocation']} allocated | Cash: {h['cash']}")
        for hedge in h["hedges"]:
            print(f"  {hedge['instrument']:6s} {hedge['allocation_pct']:5.2f}%")

        print(f"\n{h['reasoning']}")
        print("=" * 60)
