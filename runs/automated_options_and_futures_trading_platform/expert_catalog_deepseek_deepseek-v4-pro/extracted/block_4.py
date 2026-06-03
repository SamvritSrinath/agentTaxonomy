import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

def execute_mock_trade(payload: dict) -> dict:
    """
    Log the trade payload and return a 200 OK response.
    Never makes an actual HTTP POST to the brokerage.
    """
    logger.info(f"Mock trade payload: {payload}")
    # Simulated validations could be added here
    return {"status": "ok", "message": "Trade logged (not submitted)"}
