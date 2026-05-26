import asyncio
import json
from datetime import datetime

import websockets

from app.config import Settings
from app.database import SessionLocal
from app.strategy import DropStrategy


def parse_market_event(raw: str) -> tuple[str, float, datetime | None] | None:
    """
    Accepts common JSON market data shapes, for example:

      {"symbol": "SPY", "price": 500.12, "timestamp": "2026-05-24T12:00:00Z"}
      {"data": {"symbol": "SPY", "last": 500.12}}
      {"type": "quote", "ticker": "SPY", "last_price": 500.12}

    Adjust this parser to match the brokerage's exact schema.
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        payload = payload["data"]

    if not isinstance(payload, dict):
        return None

    symbol = payload.get("symbol") or payload.get("ticker")
    price = (
        payload.get("price")
        or payload.get("last")
        or payload.get("last_price")
        or payload.get("close")
    )

    if symbol is None or price is None:
        return None

    ts = None
    raw_ts = payload.get("timestamp") or payload.get("time")
    if isinstance(raw_ts, str):
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            ts = None

    try:
        return str(symbol), float(price), ts
    except ValueError:
        return None


async def run_market_data_stream(settings: Settings, strategy: DropStrategy) -> None:
    """
    Reconnecting websocket market-data consumer.

    The brokerage endpoint/protocol is unknown, so this sends a generic
    subscription payload. Modify the subscribe message if the brokerage requires
    a different format.
    """
    subscribe_message = {
        "type": "subscribe",
        "symbols": [settings.watch_symbol],
    }

    while True:
        try:
            async with websockets.connect(
                settings.brokerage_ws_url,
                ping_interval=20,
                ping_timeout=20,
            ) as websocket:
                await websocket.send(json.dumps(subscribe_message))

                async for raw in websocket:
                    event = parse_market_event(raw)
                    if event is None:
                        continue

                    symbol, price, ts = event

                    db = SessionLocal()
                    try:
                        strategy.on_price(
                            db=db,
                            symbol=symbol,
                            price=price,
                            timestamp=ts,
                        )
                    finally:
                        db.close()

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"market data stream error: {exc}; reconnecting in 5s")
            await asyncio.sleep(5)
