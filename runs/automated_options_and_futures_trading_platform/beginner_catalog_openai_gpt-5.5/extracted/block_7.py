import asyncio
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from ib_insync import IB, Option, Stock

from app.config import settings


def _safe_float(value: Any) -> float | None:
    try:
        value = float(value)
        if math.isnan(value) or math.isinf(value) or value <= 0:
            return None
        return value
    except Exception:
        return None


class IBKRClient:
    """
    Read-only IBKR market-data client.

    This intentionally does not expose order-placement methods.
    """

    def __init__(self) -> None:
        self.ib = IB()
        self._demo_prices: dict[str, float] = {}

    async def connect(self) -> None:
        if settings.demo_mode:
            return

        if self.ib.isConnected():
            return

        await self.ib.connectAsync(
            host=settings.ib_host,
            port=settings.ib_port,
            clientId=settings.ib_client_id,
            readonly=settings.ib_readonly,
            timeout=10,
        )

        if settings.ib_delayed_data:
            # 3 = delayed market data when live subscriptions are unavailable.
            self.ib.reqMarketDataType(3)

    async def disconnect(self) -> None:
        if self.ib.isConnected():
            self.ib.disconnect()

    async def quote(self, symbol: str) -> dict:
        symbol = symbol.upper()

        if settings.demo_mode:
            base = self._demo_prices.get(symbol, 500.0)
            moved = max(1.0, base * (1 + random.uniform(-0.0025, 0.0025)))
            self._demo_prices[symbol] = moved
            return {
                "symbol": symbol,
                "price": round(moved, 2),
                "source": "demo",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        await self.connect()

        contract = Stock(symbol, "SMART", "USD")
        qualified = await self.ib.qualifyContractsAsync(contract)
        if not qualified:
            raise RuntimeError(f"Could not qualify stock contract for {symbol}")

        contract = qualified[0]
        ticker = self.ib.reqMktData(contract, "", False, False)

        await asyncio.sleep(1.5)

        price = (
            _safe_float(ticker.marketPrice())
            or _safe_float(ticker.last)
            or _safe_float(ticker.close)
            or _safe_float(ticker.bid)
            or _safe_float(ticker.ask)
        )

        self.ib.cancelMktData(contract)

        if price is None:
            raise RuntimeError(f"No market price available for {symbol}")

        return {
            "symbol": symbol,
            "price": round(price, 4),
            "source": "ibkr",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def call_option_candidate(
        self,
        symbol: str,
        otm_pct: float = 1.0,
        min_days_to_expiry: int = 7,
    ) -> dict:
        """
        Finds a basic out-of-the-money call option candidate.
        This is for display/paper simulation only.
        """
        symbol = symbol.upper()
        quote = await self.quote(symbol)
        underlying_price = float(quote["price"])

        if settings.demo_mode:
            expiry = (datetime.now(timezone.utc) + timedelta(days=14)).strftime("%Y%m%d")
            strike = round(underlying_price * (1 + otm_pct / 100.0))
            premium = max(0.25, round(underlying_price * 0.015, 2))
            return {
                "underlying_symbol": symbol,
                "underlying_price": underlying_price,
                "option_symbol": f"{symbol} {expiry} C {strike}",
                "expiry": expiry,
                "strike": strike,
                "right": "C",
                "estimated_premium": premium,
                "source": "demo",
            }

        await self.connect()

        stock = Stock(symbol, "SMART", "USD")
        qualified = await self.ib.qualifyContractsAsync(stock)
        if not qualified:
            raise RuntimeError(f"Could not qualify stock contract for {symbol}")

        stock = qualified[0]

        chains = await self.ib.reqSecDefOptParamsAsync(
            underlyingSymbol=symbol,
            futFopExchange="",
            underlyingSecType="STK",
            underlyingConId=stock.conId,
        )

        if not chains:
            raise RuntimeError(f"No option chains found for {symbol}")

        chain = next((c for c in chains if c.exchange == "SMART"), chains[0])

        min_expiry = datetime.now(timezone.utc).date() + timedelta(days=min_days_to_expiry)
        expiries = sorted(
            e for e in chain.expirations
            if datetime.strptime(e, "%Y%m%d").date() >= min_expiry
        )

        if not expiries:
            raise RuntimeError(f"No expiries found at least {min_days_to_expiry} days out")

        expiry = expiries[0]
        target_strike = underlying_price * (1 + otm_pct / 100.0)

        strikes = sorted(
            float(s) for s in chain.strikes
            if underlying_price * 0.5 <= float(s) <= underlying_price * 1.5
        )

        strike = next((s for s in strikes if s >= target_strike), strikes[-1])

        option = Option(symbol, expiry, strike, "C", "SMART", currency="USD")
        qualified_options = await self.ib.qualifyContractsAsync(option)
        if not qualified_options:
            raise RuntimeError("Could not qualify option contract")

        option = qualified_options[0]
        ticker = self.ib.reqMktData(option, "", False, False)

        await asyncio.sleep(2.0)

        premium = (
            _safe_float(ticker.marketPrice())
            or _safe_float(ticker.last)
            or _safe_float(ticker.close)
            or _safe_float(ticker.ask)
            or _safe_float(ticker.bid)
        )

        self.ib.cancelMktData(option)

        if premium is None:
            raise RuntimeError("No option premium available")

        return {
            "underlying_symbol": symbol,
            "underlying_price": round(underlying_price, 4),
            "option_symbol": option.localSymbol or f"{symbol} {expiry} C {strike}",
            "expiry": expiry,
            "strike": float(strike),
            "right": "C",
            "estimated_premium": round(float(premium), 4),
            "source": "ibkr",
        }
