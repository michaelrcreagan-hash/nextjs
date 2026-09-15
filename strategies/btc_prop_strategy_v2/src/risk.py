"""Prop-firm risk manager + ATR-based position sizing.

Enforces the internal safety buffers from config.yaml (60% of firm limits):
daily loss 3%, total drawdown 6%, 0.5% risk per trade, max 5 trades/day,
max 3 concurrent positions, leverage ceiling 3x notional/equity.
"""
from dataclasses import dataclass, field


@dataclass
class RiskConfig:
    max_daily_loss_pct: float = 3.0
    max_total_dd_pct: float = 6.0
    risk_per_trade_pct: float = 0.5
    max_trades_per_day: int = 5
    max_positions: int = 3
    max_leverage: float = 3.0


@dataclass
class RiskState:
    initial_equity: float = 50000.0
    equity: float = 50000.0
    day_start_equity: float = 50000.0
    trades_today: int = 0
    halted_total: bool = False
    halted_today: bool = False
    open_positions: int = 0
    breach_log: list = field(default_factory=list)


class RiskManager:
    def __init__(self, cfg: RiskConfig, initial_equity: float):
        self.cfg = cfg
        self.s = RiskState(initial_equity=initial_equity, equity=initial_equity,
                           day_start_equity=initial_equity)

    def new_day(self, date):
        self.s.day_start_equity = self.s.equity
        self.s.trades_today = 0
        self.s.halted_today = False

    def record_pnl(self, pnl: float, date):
        self.s.equity += pnl
        daily_loss_pct = (self.s.day_start_equity - self.s.equity) / self.s.day_start_equity * 100
        total_dd_pct = (self.s.initial_equity - self.s.equity) / self.s.initial_equity * 100
        if daily_loss_pct >= self.cfg.max_daily_loss_pct and not self.s.halted_today:
            self.s.halted_today = True
            self.s.breach_log.append((str(date), "daily_buffer_halt", round(daily_loss_pct, 2)))
        if total_dd_pct >= self.cfg.max_total_dd_pct and not self.s.halted_total:
            self.s.halted_total = True
            self.s.breach_log.append((str(date), "total_dd_halt", round(total_dd_pct, 2)))

    def can_open(self) -> bool:
        return (not self.s.halted_total and not self.s.halted_today
                and self.s.trades_today < self.cfg.max_trades_per_day
                and self.s.open_positions < self.cfg.max_positions)

    def size_position(self, entry_price: float, stop_price: float) -> float:
        """Units sized so stop-out loses risk_per_trade_pct of equity,
        capped at max_leverage x equity notional."""
        stop_dist = abs(entry_price - stop_price)
        if stop_dist <= 0:
            return 0.0
        risk_usd = self.s.equity * self.cfg.risk_per_trade_pct / 100
        units = risk_usd / stop_dist
        max_units = self.s.equity * self.cfg.max_leverage / entry_price
        return min(units, max_units)

    def opened(self):
        self.s.trades_today += 1
        self.s.open_positions += 1

    def closed(self):
        self.s.open_positions = max(0, self.s.open_positions - 1)
