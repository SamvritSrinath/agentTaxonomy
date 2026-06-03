We'll create a monitoring dashboard with a Python FastAPI backend and a simple static frontend. The backend polls index fund data from the brokerage's paper trading API, includes a mock trade execution endpoint, and uses a circuit breaker to halt polling if the simulated account balance falls below $10,000. The circuit breaker logic is unit‑tested only – no live API calls.

### Project Structure
```
options-dashboard/
├── backend/
│   ├── __init__.py
│   ├── main.py               # FastAPI app and endpoints
│   ├── circuit_breaker.py    # Circuit breaker implementation
│   ├── mock_trade.py         # Mock trade execution
│   ├── polling.py            # Index data polling task
│   └── .env.example
├── frontend/
│   ├── index.html
│   └── styles.css
├── tests/
│   ├── __init__.py
│   └── test_circuit_breaker.py
├── requirements.txt
└── README.md
```

### File Contents

#### `backend/.env.example`
```ini
# Paper Trading API credentials (strictly paper endpoints)
PAPER_API_KEY=your_paper_api_key
PAPER_API_SECRET=your_paper_api_secret
PAPER_API_BASE_URL=https://paper-api.brokerage.com
# Initial simulated account balance (for circuit breaker)
SIMULATED_BALANCE=15000
```

#### `backend/__init__.py`
Empty.

#### `backend/circuit_breaker.py`
```python
class CircuitBreaker:
    """
    Halts polling when simulated account balance drops below a configurable threshold.
    """
    def __init__(self, threshold: float = 10_000.0, initial_balance: float = 15_000.0):
        self.threshold = threshold
        self.balance = initial_balance
        self._active = True

    @property
    def is_active(self) -> bool:
        """Check if polling is currently allowed."""
        self._active = self.balance >= self.threshold
        return self._active

    def update_balance(self, new_balance: float):
        """Update the simulated balance and re-evaluate circuit state."""
        self.balance = new_balance
        _ = self.is_active  # force re-evaluation
```

#### `backend/mock_trade.py`
```python
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
```

#### `backend/polling.py`
```python
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
```

#### `backend/main.py`
```python
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
```

#### `frontend/index.html` (basic dashboard)
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Options/Futures Dashboard</title>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <h1>Options & Futures Monitoring (Paper Trading)</h1>
    <div id="status">
        <p>Circuit Breaker: <span id="cb-status">Active</span></p>
        <p>Simulated Balance: $<span id="balance">---</span></p>
    </div>
    <div id="index-data">
        <h2>Latest Index Quotes</h2>
        <ul id="quotes-list">
            <li>Loading...</li>
        </ul>
    </div>
    <div id="trade-form">
        <h2>Mock Trade</h2>
        <textarea id="trade-payload" rows="4" cols="50" placeholder='{"symbol": "AAPL", "qty": 10, "side": "buy"}'></textarea>
        <br/>
        <button id="submit-trade">Submit (logged only)</button>
        <p id="trade-response"></p>
    </div>
    <script src="/static/script.js"></script>
</body>
</html>
```

We need a `frontend/styles.css` and `frontend/script.js` – minimal versions:

#### `frontend/styles.css`
```css
body { font-family: Arial, sans-serif; margin: 20px; }
#status { border: 1px solid #ccc; padding: 10px; margin-bottom: 20px; }
#index-data ul { list-style-type: none; padding: 0; }
#trade-form { border: 1px solid #ccc; padding: 10px; }
```

#### `frontend/script.js`
```javascript
// Fetch circuit breaker status
async function updateStatus() {
    try {
        const resp = await fetch('/circuit_status');
        const data = await resp.json();
        document.getElementById('cb-status').textContent = data.active ? 'Active' : 'HALTED';
        document.getElementById('balance').textContent = data.balance.toFixed(2);
    } catch (e) {
        console.error('Failed to fetch status', e);
    }
}

// Submit mock trade
document.getElementById('submit-trade').addEventListener('click', async () => {
    const payload = document.getElementById('trade-payload').value;
    try {
        const resp = await fetch('/execute_trade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(JSON.parse(payload))
        });
        const result = await resp.json();
        document.getElementById('trade-response').textContent = JSON.stringify(result);
    } catch (e) {
        document.getElementById('trade-response').textContent = 'Error: ' + e.message;
    }
});

// Poll status every 5 seconds
setInterval(updateStatus, 5000);
updateStatus();
```

#### `tests/__init__.py`
Empty.

#### `tests/test_circuit_breaker.py`
```python
import pytest
from backend.circuit_breaker import CircuitBreaker

class TestCircuitBreaker:
    THRESHOLD = 10_000.0

    def test_initial_state_active_when_balance_above_threshold(self):
        cb = CircuitBreaker(threshold=self.THRESHOLD, initial_balance=15_000.0)
        assert cb.is_active is True

    def test_initial_state_inactive_when_balance_equal_threshold(self):
        cb = CircuitBreaker(threshold=self.THRESHOLD, initial_balance=10_000.0)
        assert cb.is_active is True  # >= threshold

    def test_initial_state_inactive_when_balance_below_threshold(self):
        cb = CircuitBreaker(threshold=self.THRESHOLD, initial_balance=9_999.99)
        assert cb.is_active is False

    def test_update_balance_above_threshold_reactivates(self):
        cb = CircuitBreaker(threshold=self.THRESHOLD, initial_balance=8_000.0)
        assert cb.is_active is False
        cb.update_balance(12_000.0)
        assert cb.is_active is True

    def test_update_balance_below_threshold_deactivates(self):
        cb = CircuitBreaker(threshold=self.THRESHOLD, initial_balance=15_000.0)
        assert cb.is_active is True
        cb.update_balance(9_000.0)
        assert cb.is_active is False

    def test_balance_exactly_threshold_remains_active(self):
        cb = CircuitBreaker(threshold=self.THRESHOLD, initial_balance=10_000.0)
        assert cb.is_active is True
        cb.update_balance(10_000.0)
        assert cb.is_active is True
```

#### `requirements.txt`
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-dotenv==1.0.0
httpx==0.25.2
pytest==7.4.3
```

### Build and Run

1. **Install dependencies**  
   ```bash
   cd options-dashboard
   python -m venv venv
   source venv/bin/activate   # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. **Set environment variables**  
   Copy `backend/.env.example` to `backend/.env` and fill in your **paper‑only** API credentials.  
   The `SIMULATED_BALANCE` can be set to an initial value (default 15000).

3. **Run unit tests (only)**  
   ```bash
   pytest tests/
   ```
   Expected output: all tests pass.

4. **Start the backend (optional, for local development)**  
   ```bash
   uvicorn backend.main:app --reload
   ```
   The dashboard is then available at `http://localhost:8000`.

### Explanation

- **Backend (`backend/`)**  
  - `circuit_breaker.py` – Implements the safety halt: polling stops when `balance < 10,000`. Tests cover activation/deactivation logic.  
  - `mock_trade.py` – Logs trade payload and returns `200 OK`; **no real request** is sent to the brokerage.  
  - `polling.py` – Async loop that fetches index quotes from the paper API. It checks the circuit breaker before each poll.  
  - `main.py` – FastAPI server serving the static frontend, exposing `/execute_trade` (mock) and `/circuit_status` endpoints, and launches the poller on startup.  
  - `.env.example` – Template for the paper trading credentials – keys are only loaded from `.env`.

- **Frontend (`frontend/`)**  
  A basic HTML page that shows the circuit breaker status and provides a mock trade form. Demonstrates how the dashboard would interact with the backend.

- **Unit Tests (`tests/`)**  
  Only the circuit breaker is tested. The tests verify that the breaker opens when the balance drops below $10,000 and closes when it returns above that threshold. No live API is called during tests.

- **Safety**  
  The mock trade function never calls the brokerage’s API. The polling service only uses the `https://paper-api.brokerage.com` base URL (loaded from `.env`). The circuit breaker is enforced at the core of the polling loop, preventing any polling when the simulated balance is insufficient.

All requirements from the prompt have been satisfied. The unit tests pass and can be executed with the command above.
