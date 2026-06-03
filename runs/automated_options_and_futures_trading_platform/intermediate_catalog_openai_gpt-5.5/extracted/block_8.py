from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    symbol = Column(String(64), nullable=False, index=True)
    underlying_symbol = Column(String(64), nullable=False, index=True)

    instrument_type = Column(String(32), default="OPTION", nullable=False)
    side = Column(String(16), default="BUY", nullable=False)
    option_type = Column(String(16), default="PUT", nullable=False)

    quantity = Column(Integer, nullable=False)
    order_type = Column(String(32), default="MARKET", nullable=False)

    status = Column(String(64), nullable=False)
    mode = Column(String(32), nullable=False)

    price_at_signal = Column(Float, nullable=False)
    signal_drop_pct = Column(Float, nullable=False)

    broker_order_id = Column(String(128), nullable=True)

    reason = Column(Text, nullable=False)
