Below is a safe scaffold for a frontend + backend monitoring dashboard.

Key safety choices implemented:

- Backend uses only `https://paper-api.brokerage.com`.
- Brokerage API keys are loaded only from `.env`.
- Trade execution is a mock only: it logs the intended payload and returns HTTP `200`; it never performs an HTTP `POST` to the brokerage.
- Circuit breaker halts polling once simulated account balance drops below `$10,000`.
- Unit tests cover the circuit breaker.
- Do not run the main app for this task; only run unit tests.

---

## Project structure
---

# Backend

## `backend/package.json`
---

## `backend/.env.example`
---

## `backend/src/config.js`
---

## `backend/src/circuitBreaker.js`
---

## `backend/src/brokerageClient.js`
---

## `backend/src/tradeService.js`
---

## `backend/src/poller.js`
---

## `backend/src/server.js`
---

## `backend/tests/circuitBreaker.test.js`
---

# Frontend

## `frontend/package.json`
---

## `frontend/index.html`
---

## `frontend/vite.config.js`
---

## `frontend/src/main.jsx`
---

## `frontend/src/App.jsx`
---

## `frontend/src/styles.css`
---

# Commands

## Install backend dependencies
## Create backend `.env`
Then edit `backend/.env` with paper-trading credentials only.

---

## Run unit tests only

Per the instruction, execute only the unit tests:
Expected test target:
---

## Optional commands, not to execute for this task

These are provided for completeness only.

### Start backend
### Install frontend dependencies
### Run frontend dev server
### Build frontend
---

# Concise explanation

The backend polls index fund data from the fixed paper endpoint `https://paper-api.brokerage.com` using API keys loaded from `.env`. The `MarketDataPoller` checks a `CircuitBreaker` before every poll and stops permanently if the simulated balance drops below `$10,000`.

The trade endpoint `/api/trade/mock` is intentionally non-executing. It logs the intended trade payload and returns `200 OK`, with no brokerage `POST` request implemented.

The frontend displays market data, circuit breaker state, simulated balance controls, and a mock trade button. The provided unit tests validate the circuit breaker behavior.
