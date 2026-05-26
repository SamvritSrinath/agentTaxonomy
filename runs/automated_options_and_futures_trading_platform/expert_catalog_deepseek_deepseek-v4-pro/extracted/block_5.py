import asyncio
import os
import logging
import httpx
from .circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

PAPER_BASE = os.getenv("PAPER_API_BASE_URL", "https://paper-api.brokerage.com")
API_KEY = os.getenv("PAPER_API_KEY", "")
API_SECRET = os.getenv("PAPER_API_SECRET", "")

INDEX_SYMBOLS = ["SPX", "NDX", "RUT"]  # example index funds (paper market data)

async def poll_index_data(circuit_breaker: CircuitBreaker):
    """
    Periodically fetch index fund quotes from the paper trading API.
    Respects the circuit breaker – polling stops if balance < threshold.
    """
    async with httpx.AsyncClient() as client:
        while True:
            if not circuit_breaker.is_active:
                logger.warning("Circuit breaker open – polling suspended.")
                await asyncio.sleep(30)  # check again after a while
                continue

            try:
                # Example: fetch quotes for each index symbol
                for symbol in INDEX_SYMBOLS:
                    url = f"{PAPER_BASE}/v2/stocks/{symbol}/quotes/latest"
                    headers = {
                        "APCA-API-KEY-ID": API_KEY,
                        "APCA-API-SECRET-KEY": API_SECRET
                    }
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    logger.debug(f"Polled {symbol}: {data}")

                    # In a real system you would store this data for the frontend
                    # For scaffolding, we simply log it.

                # Simulated balance update – could come from an account endpoint
                # Here we keep the existing balance unchanged.
                # In production: fetch balance from /v2/account and call
                # circuit_breaker.update_balance(account_data['cash'])

            except Exception as e:
                logger.error(f"Polling error: {e}")

            await asyncio.sleep(60)  # poll every minute
