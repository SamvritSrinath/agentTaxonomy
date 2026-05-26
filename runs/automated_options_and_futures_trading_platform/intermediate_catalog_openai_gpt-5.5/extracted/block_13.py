import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.broker import PaperBroker
from app.config import settings
from app.database import get_db, init_db
from app.market_data import run_market_data_stream
from app.models import Trade
from app.schemas import StatusOut, TradeOut
from app.strategy import DropStrategy, StrategyConfig


def build_strategy() -> DropStrategy:
    broker = PaperBroker()
    config = StrategyConfig(
        watch_symbol=settings.watch_symbol,
        option_contract_symbol=settings.option_contract_symbol,
        order_quantity=settings.order_quantity,
        drop_threshold_pct=settings.drop_threshold_pct,
        lookback_minutes=settings.lookback_minutes,
        auto_trade_mode=settings.auto_trade_mode,
    )
    return DropStrategy(config=config, broker=broker)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    app.state.broker = PaperBroker()
    app.state.strategy = build_strategy()
    app.state.market_task = None

    if not settings.disable_feed:
        app.state.market_task = asyncio.create_task(
            run_market_data_stream(settings, app.state.strategy)
        )

    yield

    if app.state.market_task is not None:
        app.state.market_task.cancel()
        try:
            await app.state.market_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Safe Trading Automation Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status", response_model=StatusOut)
def status():
    return StatusOut(
        service="ok",
        watch_symbol=settings.watch_symbol,
        option_contract_symbol=settings.option_contract_symbol,
        auto_trade_mode=settings.auto_trade_mode,
        feed_enabled=not settings.disable_feed,
        safety=(
            "Paper/manual workflow only. This service does not send autonomous "
            "live brokerage orders."
        ),
    )


@app.get("/api/trades", response_model=list[TradeOut])
def list_trades(db: Session = Depends(get_db)):
    return (
        db.query(Trade)
        .order_by(Trade.created_at.desc(), Trade.id.desc())
        .all()
    )


@app.post("/api/trades/{trade_id}/approve", response_model=TradeOut)
def approve_pending_trade(
    trade_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()

    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")

    if trade.status != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=400,
            detail="Only PENDING_APPROVAL trades can be approved",
        )

    # Still paper-only.
    broker_order_id = request.app.state.broker.place_market_put_order(
        underlying_symbol=trade.underlying_symbol,
        option_contract_symbol=trade.symbol,
        quantity=trade.quantity,
    )

    trade.status = "PAPER_FILLED"
    trade.mode = "paper_manual_approved"
    trade.broker_order_id = broker_order_id
    trade.reason += " Manually approved in dashboard and paper-filled."

    db.commit()
    db.refresh(trade)

    return trade


@app.post("/api/dev/price")
def dev_inject_price(
    symbol: str,
    price: float,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Local development helper for DISABLE_FEED=true.
    Example:
      curl -X POST 'http://localhost:8000/api/dev/price?symbol=SPY&price=480'
    """
    trade = request.app.state.strategy.on_price(
        db=db,
        symbol=symbol,
        price=price,
    )

    return {
        "accepted": True,
        "trade_created": trade is not None,
        "trade_id": trade.id if trade else None,
    }
