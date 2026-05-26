from collections import deque
from dataclasses import dataclass
from time import time


@dataclass
class DropSignal:
    triggered: bool
    current_price: float
    high_price: float
    drop_pct: float
    threshold_pct: float
    lookback_seconds: int


class PriceWindow:
    def __init__(self) -> None:
        self._points: deque[tuple[float, float]] = deque()

    def add(self, price: float, ts: float | None = None) -> None:
        if price <= 0:
            return
        self._points.append((ts or time(), float(price)))

    def evaluate(self, threshold_pct: float, lookback_seconds: int, now: float | None = None) -> DropSignal:
        now = now or time()
        cutoff = now - lookback_seconds

        while self._points and self._points[0][0] < cutoff:
            self._points.popleft()

        if not self._points:
            return DropSignal(False, 0.0, 0.0, 0.0, threshold_pct, lookback_seconds)

        current_price = self._points[-1][1]
        high_price = max(price for _, price in self._points)

        if high_price <= 0:
            drop_pct = 0.0
        else:
            drop_pct = ((high_price - current_price) / high_price) * 100.0

        return DropSignal(
            triggered=drop_pct >= threshold_pct,
            current_price=current_price,
            high_price=high_price,
            drop_pct=round(drop_pct, 4),
            threshold_pct=threshold_pct,
            lookback_seconds=lookback_seconds,
        )
