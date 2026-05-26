from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TradeOut(BaseModel):
    id: int
    created_at: datetime

    symbol: str
    underlying_symbol: str

    instrument_type: str
    side: str
    option_type: str

    quantity: int
    order_type: str

    status: str
    mode: str

    price_at_signal: float
    signal_drop_pct: float

    broker_order_id: str | None
    reason: str

    model_config = ConfigDict(from_attributes=True)


class StatusOut(BaseModel):
    service: str
    watch_symbol: str
    option_contract_symbol: str
    auto_trade_mode: str
    feed_enabled: bool
    safety: str
