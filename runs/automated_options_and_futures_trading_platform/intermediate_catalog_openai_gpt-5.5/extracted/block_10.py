from datetime import datetime
from uuid import uuid4


class PaperBroker:
    """
    Paper-only broker.

    This intentionally does not implement live order execution.
    """

    def place_market_put_order(
        self,
        *,
        underlying_symbol: str,
        option_contract_symbol: str,
        quantity: int,
    ) -> str:
        now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"PAPER-{now}-{uuid4().hex[:10]}"
