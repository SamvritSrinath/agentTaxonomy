import asyncio
import logging
import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from .circuit_breaker import CircuitBreaker
from .mock_trade import execute_mock_trade
from .polling import poll_index_data

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Options & Futures Monitor (Paper)")

# Serve static frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Global circuit breaker instance – reads initial balance from env
simulated_balance = float(os.getenv("SIMULATED_BALANCE", 15000))
circuit_breaker = CircuitBreaker(threshold=10000.0, initial_balance=simulated_balance)

@app.on_event("startup")
async def start_polling():
    """Start the background polling task."""
    logger.info("Starting background polling task...")
    asyncio.create_task(poll_index_data(circuit_breaker))

@app.get("/")
async def read_root():
    """Serve the dashboard HTML."""
    return FileResponse("frontend/index.html")

@app.post("/execute_trade")
async def execute_trade_endpoint(payload: dict):
    """
    Mock trade endpoint – logs payload and returns 200 OK.
    The actual POST to the brokerage is NEVER made.
    """
    result = execute_mock_trade(payload)
    return result

@app.get("/circuit_status")
async def get_circuit_status():
    """Return the current state of the circuit breaker."""
    return {
        "active": circuit_breaker.is_active,
        "balance": circuit_breaker.balance,
        "threshold": circuit_breaker.threshold
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
