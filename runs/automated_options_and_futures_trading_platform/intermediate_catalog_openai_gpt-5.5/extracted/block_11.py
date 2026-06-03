from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Deque

from sqlalchemy.orm import Session

from app.broker import PaperBroker
from app.models import Trade


@dataclass(frozen=True)
class StrategyConfig:
    watch_symbol: str
    option_contract_symbol: str
    order_quantity: int
    drop_threshold_pct: float
    lookback_minutes: int
    auto_trade_mode: str


class DropStrategy:
    """
    Detects whether the watched symbol has fallen more than threshold percent
    from its highest price observed within the rolling lookback window.

    Safe behavior:
      - paper mode: record a paper-filled trade
      - manual mode: record a pending recommendation
    """

    def __init__(self, config: StrategyConfig, broker: PaperBroker):
        if config.auto_trade_mode not in {"paper", "manual"}:
            raise ValueError("auto_trade_mode must be 'paper' or 'manual'")

        self.config = config
        self.broker = broker

        self.prices: Deque[tuple[datetime, float]] = deque()
        self.last_signal_at: datetime | None = None

    def on_price(
        self,
        *,
        db: Session,
        symbol: str,
        price: float,
        timestamp: datetime | None = None,
    ) -> Trade | None:
        if symbol != self.config.watch_symbol:
            return None

        if price <= 0:
            return None

        ts = timestamp or datetime.utcnow()
        lookback = timedelta(minutes=self.config.lookback_minutes)

        self.prices.append((ts, float(price)))

        cutoff = ts - lookback
        while self.prices and self.prices[0][0] < cutoff:
            self.prices.popleft()

        if len(self.prices) < 2:
            return None

        if self.last_signal_at is not None and ts - self.last_signal_at < lookback:
            return None

        max_price = max(p for _, p in self.prices)
        drop_pct = ((max_price - price) / max_price) * 100.0

        # "more than 2%" means strictly greater than the configured threshold.
        if drop_pct <= self.config.drop_threshold_pct:
            return None

        broker_order_id = None
        status = "PENDING_APPROVAL"
        mode = "manual"

        if self.config.auto_trade_mode == "paper":
            broker_order_id = self.broker.place_market_put_order(
                underlying_symbol=self.config.watch_symbol,
                option_contract_symbol=self.config.option_contract_symbol,
                quantity=self.config.order_quantity,
            )
            status = "PAPER_FILLED"
            mode = "paper"

        reason = (
            f"{self.config.watch_symbol} dropped {drop_pct:.2f}% within "
            f"{self.config.lookback_minutes} minutes. "
            f"Detected price={price:.4f}, rolling-window high={max_price:.4f}. "
            "Safe system behavior: no autonomous live brokerage order was sent."
        )

        trade = Trade(
            symbol=self.config.option_contract_symbol,
            underlying_symbol=self.config.watch_symbol,
            instrument_type="OPTION",
            side="BUY",
            option_type="PUT",
            quantity=self.config.order_quantity,
            order_type="MARKET",
            status=status,
            mode=mode,
            price_at_signal=price,
            signal_drop_pct=drop_pct,
            broker_order_id=broker_order_id,
            reason=reason,
        )

        db.add(trade)
        db.commit()
        db.refresh(trade)

        self.last_signal_at = ts

        return trade
