"""v7.0 Unified Trading Engine."""
from .regime import Regime, detect_regime, fetch_regime_data, REGIME_MATRIX
from .composite import CompositeScorer, MODULE_WEIGHTS
from .breakout import BreakoutSignal, atr_rsi_breakout, batch_breakout
from .pullback import PullbackSignal, fib_keltner_pullback, batch_pullback
from .confluence import IAEConfluence, compute_confluence_score, batch_confluence
from .options import build_options_trade, compute_iv_rank, select_options_strategy, OptionsStrategy, OptionsTrade
from .hedge import build_hedge_portfolio, fetch_vix, get_active_hedge_signals, MacroHedge
from .scanner import LiveScanner
from .universe import FULL_UNIVERSE, AI_LAYERS, get_peers, get_sector_etf, get_tier, get_sleeve

__all__ = [
    "Regime", "detect_regime", "fetch_regime_data", "REGIME_MATRIX",
    "CompositeScorer", "MODULE_WEIGHTS",
    "BreakoutSignal", "atr_rsi_breakout", "batch_breakout",
    "PullbackSignal", "fib_keltner_pullback", "batch_pullback",
    "IAEConfluence", "compute_confluence_score", "batch_confluence",
    "OptionsStrategy", "OptionsTrade", "build_options_trade", "compute_iv_rank",
    "MacroHedge", "build_hedge_portfolio", "fetch_vix", "get_active_hedge_signals",
    "LiveScanner",
    "FULL_UNIVERSE", "AI_LAYERS", "get_peers", "get_sector_etf", "get_tier", "get_sleeve",
]
