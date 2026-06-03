from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.broker import PaperBroker
from app.database import Base
from app.models import Trade
from app.strategy import DropStrategy, StrategyConfig


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def make_strategy(mode: str = "paper") -> DropStrategy:
    return DropStrategy(
        config=StrategyConfig(
            watch_symbol="SPY",
            option_contract_symbol="SPY_PUT_DEMO",
            order_quantity=10,
            drop_threshold_pct=2.0,
            lookback_minutes=60,
            auto_trade_mode=mode,
        ),
        broker=PaperBroker(),
    )


def test_triggers_paper_trade_on_more_than_two_percent_hourly_drop(db):
    strategy = make_strategy(mode="paper")
    start = datetime(2026, 1, 1, 10, 0, 0)

    assert strategy.on_price(db=db, symbol="SPY", price=100.00, timestamp=start) is None

    trade = strategy.on_price(
        db=db,
        symbol="SPY",
        price=97.50,
        timestamp=start + timedelta(minutes=30),
    )

    assert trade is not None
    assert trade.quantity == 10
    assert trade.side == "BUY"
    assert trade.option_type == "PUT"
    assert trade.status == "PAPER_FILLED"
    assert trade.broker_order_id.startswith("PAPER-")
    assert trade.signal_drop_pct == pytest.approx(2.5)

    saved = db.query(Trade).all()
    assert len(saved) == 1


def test_does_not_trigger_at_exactly_two_percent(db):
    strategy = make_strategy(mode="paper")
    start = datetime(2026, 1, 1, 10, 0, 0)

    strategy.on_price(db=db, symbol="SPY", price=100.00, timestamp=start)
    trade = strategy.on_price(
        db=db,
        symbol="SPY",
        price=98.00,
        timestamp=start + timedelta(minutes=15),
    )

    assert trade is None
    assert db.query(Trade).count() == 0


def test_manual_mode_creates_pending_approval_trade(db):
    strategy = make_strategy(mode="manual")
    start = datetime(2026, 1, 1, 10, 0, 0)

    strategy.on_price(db=db, symbol="SPY", price=100.00, timestamp=start)
    trade = strategy.on_price(
        db=db,
        symbol="SPY",
        price=97.00,
        timestamp=start + timedelta(minutes=10),
    )

    assert trade is not None
    assert trade.status == "PENDING_APPROVAL"
    assert trade.broker_order_id is None
    assert trade.mode == "manual"


def test_ignores_other_symbols(db):
    strategy = make_strategy(mode="paper")
    start = datetime(2026, 1, 1, 10, 0, 0)

    strategy.on_price(db=db, symbol="QQQ", price=100.00, timestamp=start)
    trade = strategy.on_price(
        db=db,
        symbol="QQQ",
        price=90.00,
        timestamp=start + timedelta(minutes=10),
    )

    assert trade is None
    assert db.query(Trade).count() == 0


def test_cooldown_prevents_repeated_trades_within_lookback_window(db):
    strategy = make_strategy(mode="paper")
    start = datetime(2026, 1, 1, 10, 0, 0)

    strategy.on_price(db=db, symbol="SPY", price=100.00, timestamp=start)

    first = strategy.on_price(
        db=db,
        symbol="SPY",
        price=97.00,
        timestamp=start + timedelta(minutes=10),
    )
    second = strategy.on_price(
        db=db,
        symbol="SPY",
        price=96.00,
        timestamp=start + timedelta(minutes=20),
    )

    assert first is not None
    assert second is None
    assert db.query(Trade).count() == 1
