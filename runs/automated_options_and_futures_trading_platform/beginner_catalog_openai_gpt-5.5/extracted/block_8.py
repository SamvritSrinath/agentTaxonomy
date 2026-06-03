from collections import defaultdict
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.ibkr import IBKRClient
from app.paper_store import PaperOrderStore
from app.signal_logic import PriceWindow


app = FastAPI(title="IBKR Paper Market Monitor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ibkr = IBKRClient()
paper_orders = PaperOrderStore()
price_windows: dict[str, PriceWindow] = defaultdict(PriceWindow)


class PaperOrderRequest(BaseModel):
    underlying_symbol: str
    option_symbol: str
    expiry: str
    strike: float
    right: str = "C"
    quantity: int = Field(ge=1, le=100)
    estimated_premium: float = Field(gt=0)
    max_debit: float = Field(gt=0)
    reason: str = ""


@app.on_event("startup")
async def startup() -> None:
    if not settings.demo_mode:
        try:
            await ibkr.connect()
        except Exception:
            # Do not fail app startup if TWS/Gateway is not running.
            # API endpoints will return connection errors until IBKR is available.
            pass


@app.on_event("shutdown")
async def shutdown() -> None:
    await ibkr.disconnect()


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "demo_mode": settings.demo_mode,
        "ib_readonly": settings.ib_readonly,
    }


@app.get("/api/market/{symbol}")
async def market(
    symbol: str,
    threshold_pct: Annotated[float, Query(gt=0, le=25)] = settings.drop_threshold_pct,
    lookback_seconds: Annotated[int, Query(ge=30, le=86400)] = settings.lookback_seconds,
) -> dict:
    try:
        quote = await ibkr.quote(symbol)
        price_windows[symbol.upper()].add(float(quote["price"]))
        signal = price_windows[symbol.upper()].evaluate(
            threshold_pct=threshold_pct,
            lookback_seconds=lookback_seconds,
        )

        return {
            "quote": quote,
            "drop_signal": {
                "triggered": signal.triggered,
                "current_price": signal.current_price,
                "high_price": signal.high_price,
                "drop_pct": signal.drop_pct,
                "threshold_pct": signal.threshold_pct,
                "lookback_seconds": signal.lookback_seconds,
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/option-candidate/{symbol}")
async def option_candidate(
    symbol: str,
    otm_pct: Annotated[float, Query(ge=0, le=25)] = 1.0,
    min_days_to_expiry: Annotated[int, Query(ge=1, le=365)] = 7,
) -> dict:
    try:
        return await ibkr.call_option_candidate(
            symbol=symbol,
            otm_pct=otm_pct,
            min_days_to_expiry=min_days_to_expiry,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/paper-orders")
async def create_paper_order(req: PaperOrderRequest) -> dict:
    try:
        order = paper_orders.create(
            underlying_symbol=req.underlying_symbol,
            option_symbol=req.option_symbol,
            expiry=req.expiry,
            strike=req.strike,
            right=req.right,
            quantity=req.quantity,
            estimated_premium=req.estimated_premium,
            max_debit=req.max_debit,
            reason=req.reason,
        )
        return {"order": order.__dict__}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/paper-orders")
async def list_paper_orders() -> dict:
    return {"orders": paper_orders.list()}
