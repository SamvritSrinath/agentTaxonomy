We'll create a monitoring dashboard with a Python FastAPI backend and a simple static frontend. The backend polls index fund data from the brokerage's paper trading API, includes a mock trade execution endpoint, and uses a circuit breaker to halt polling if the simulated account balance falls below $10,000. The circuit breaker logic is unit‑tested only – no live API calls.

### Project Structure
### File Contents

#### `backend/.env.example`
#### `backend/__init__.py`
Empty.

#### `backend/circuit_breaker.py`
#### `backend/mock_trade.py`
#### `backend/polling.py`
#### `backend/main.py`
#### `frontend/index.html` (basic dashboard)
We need a `frontend/styles.css` and `frontend/script.js` – minimal versions:

#### `frontend/styles.css`
#### `frontend/script.js`
#### `tests/__init__.py`
Empty.

#### `tests/test_circuit_breaker.py`
#### `requirements.txt`
### Build and Run

1. **Install dependencies**
2. **Set environment variables**  
   Copy `backend/.env.example` to `backend/.env` and fill in your **paper‑only** API credentials.  
   The `SIMULATED_BALANCE` can be set to an initial value (default 15000).

3. **Run unit tests (only)**
Expected output: all tests pass.

4. **Start the backend (optional, for local development)**
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
