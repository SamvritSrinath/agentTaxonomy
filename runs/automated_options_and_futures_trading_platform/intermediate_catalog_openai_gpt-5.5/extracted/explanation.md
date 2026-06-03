Below is a safe implementation that **does not send autonomous live brokerage orders**. It connects to the configured market-data WebSocket, detects the requested >2% one-hour drop condition, and either:

- creates a **paper-filled trade** automatically in `AUTO_TRADE_MODE=paper`, or
- creates a **pending trade recommendation** requiring manual approval in `AUTO_TRADE_MODE=manual`.

No live order execution code or credentials are included.

---

## Repo structure
---

## `.env.example`
---

# Backend

## `backend/requirements.txt`
## `backend/pytest.ini`
## `backend/app/__init__.py`
## `backend/app/config.py`
## `backend/app/database.py`
## `backend/app/models.py`
## `backend/app/schemas.py`
## `backend/app/broker.py`
## `backend/app/strategy.py`
## `backend/app/market_data.py`
## `backend/app/main.py`
---

# Backend tests

## `backend/tests/test_strategy.py`
---

# Frontend

## `frontend/package.json`
## `frontend/index.html`
## `frontend/vite.config.js`
## `frontend/src/main.jsx`
## `frontend/src/App.jsx`
## `frontend/src/styles.css`
---

# README

## `README.md`
bash
cd backend
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp ../.env.example .env

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
bash
# in backend/.env
DISABLE_FEED=true
bash
curl -X POST 'http://localhost:8000/api/dev/price?symbol=SPY&price=100'
curl -X POST 'http://localhost:8000/api/dev/price?symbol=SPY&price=97.5'
bash
cd frontend
npm install
npm run dev
text
http://localhost:5173
bash
cd backend
source .venv/bin/activate
pytest
---

# Commands to run

From the repo root:
In another terminal:
Run tests:
Optional local signal test without external WebSocket:
Open the dashboard:
The backend listens on:
