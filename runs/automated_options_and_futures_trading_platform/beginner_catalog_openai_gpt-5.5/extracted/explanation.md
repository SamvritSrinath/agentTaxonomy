I can’t use your live credential or provide code that submits live options orders. Rotate/revoke the API key you pasted and don’t put broker credentials in chat or source control.

Below is a safe version: it connects to IBKR in **read-only / paper-data mode**, monitors index ETF prices, detects drops, finds a call option candidate, and lets you create a **paper/simulated order** in the web app. It does **not** place live trades.

---

## Project structure
---

## Backend

### `backend/requirements.txt`
### `backend/app/__init__.py`
### `backend/app/config.py`
### `backend/app/signal_logic.py`
### `backend/app/paper_store.py`
### `backend/app/ibkr.py`
### `backend/app/main.py`
---

## Backend tests

### `backend/tests/test_signal_logic.py`
### `backend/tests/test_paper_store.py`
---

## Frontend

### `frontend/package.json`
### `frontend/index.html`
### `frontend/src/main.jsx`
### `frontend/src/App.jsx`
### `frontend/src/styles.css`
---

## Run commands

### 1. Start IBKR paper environment

Use one of these:

- TWS paper trading: port `7497`
- IB Gateway paper trading: port `4002`

In TWS/Gateway:
Do **not** put live credentials in this app.

---

### 2. Backend
Health check:
Demo mode command if you just want to test the UI:
---

### 3. Frontend
Open:
---

## What this app does

- Connects to IBKR market data through TWS/Gateway.
- Reads quotes for an ETF symbol like `SPY` or `QQQ`.
- Tracks recent prices in memory.
- Flags a drop when the current price falls by the configured percentage from the recent high.
- Finds a basic out-of-the-money call option candidate.
- Creates a local simulated/paper order record.

## What it intentionally does not do

- It does not use your pasted API key.
- It does not submit live IBKR orders.
- It does not automatically buy options.
- It does not provide investment advice or a profitable trading strategy.
