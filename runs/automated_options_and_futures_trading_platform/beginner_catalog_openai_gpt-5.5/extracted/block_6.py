from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4


@dataclass
class PaperOrder:
    id: str
    created_at: str
    underlying_symbol: str
    option_symbol: str
    expiry: str
    strike: float
    right: str
    quantity: int
    estimated_premium: float
    estimated_total_debit: float
    max_debit: float
    reason: str
    status: str


class PaperOrderStore:
    def __init__(self) -> None:
        self._orders: list[PaperOrder] = []
        self._lock = Lock()

    def create(
        self,
        underlying_symbol: str,
        option_symbol: str,
        expiry: str,
        strike: float,
        right: str,
        quantity: int,
        estimated_premium: float,
        max_debit: float,
        reason: str,
    ) -> PaperOrder:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if estimated_premium <= 0:
            raise ValueError("estimated_premium must be positive")
        if max_debit <= 0:
            raise ValueError("max_debit must be positive")

        estimated_total_debit = round(estimated_premium * 100 * quantity, 2)

        if estimated_total_debit > max_debit:
            raise ValueError(
                f"estimated debit ${estimated_total_debit} exceeds max debit ${max_debit}"
            )

        order = PaperOrder(
            id=str(uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            underlying_symbol=underlying_symbol.upper(),
            option_symbol=option_symbol,
            expiry=expiry,
            strike=float(strike),
            right=right.upper(),
            quantity=int(quantity),
            estimated_premium=float(estimated_premium),
            estimated_total_debit=estimated_total_debit,
            max_debit=float(max_debit),
            reason=reason,
            status="PAPER_FILLED",
        )

        with self._lock:
            self._orders.insert(0, order)

        return order

    def list(self) -> list[dict]:
        with self._lock:
            return [asdict(order) for order in self._orders]
