Below is a safe implementation that **does not send autonomous live brokerage orders**. It connects to the configured market-data WebSocket, detects the requested >2% one-hour drop condition, and either:

- creates a **paper-filled trade** automatically in `AUTO_TRADE_MODE=paper`, or
- creates a **pending trade recommendation** requiring manual approval in `AUTO_TRADE_MODE=manual`.

No live order execution code or credentials are included.

---

## Repo structure

```text
trading-dashboard/
  backend/
    requirements.txt
    pytest.ini
    app/
      __init__.py
      main.py
      config.py
      database.py
      models.py
      schemas.py
      broker.py
      strategy.py
      market_data.py
    tests/
      test_strategy.py
  frontend/
    package.json
    index.html
    vite.config.js
    src/
      main.jsx
      App.jsx
      styles.css
  .env.example
  README.md
```

---

## `.env.example`

```env
# Backend
DATABASE_URL=sqlite:///./trades.db
BROKERAGE_WS_URL=wss://api.brokerage.com/live
WATCH_SYMBOL=SPY
OPTION_CONTRACT_SYMBOL=SPY_PUT_DEMO
ORDER_QUANTITY=10
DROP_THRESHOLD_PCT=2.0
LOOKBACK_MINUTES=60

# Safe modes only:
# paper  = automatically records a paper-filled trade
# manual = records a pending recommendation requiring manual approval
AUTO_TRADE_MODE=paper

# Set to true for tests/local dashboard without connecting to the broker websocket
DISABLE_FEED=false

CORS_ORIGINS=http://localhost:5173
```

---

# Backend

## `backend/requirements.txt`

```txt
fastapi==0.115.6
uvicorn[standard]==0.32.1
SQLAlchemy==2.0.36
pydantic==2.10.3
pydantic-settings==2.6.1
websockets==14.1
pytest==8.3.4
httpx==0.28.1
```

## `backend/pytest.ini`

```ini
[pytest]
pythonpath = .
testpaths = tests
```

## `backend/app/__init__.py`

```python
```

## `backend/app/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./trades.db"

    brokerage_ws_url: str = "wss://api.brokerage.com/live"
    watch_symbol: str = "SPY"
    option_contract_symbol: str = "SPY_PUT_DEMO"

    order_quantity: int = 10
    drop_threshold_pct: float = 2.0
    lookback_minutes: int = 60

    # Safe modes only:
    # paper  -> automatically records paper fill
    # manual -> creates pending recommendation for manual approval
    auto_trade_mode: str = "paper"

    disable_feed: bool = False
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
```

## `backend/app/database.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}


engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## `backend/app/models.py`

```python
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    symbol = Column(String(64), nullable=False, index=True)
    underlying_symbol = Column(String(64), nullable=False, index=True)

    instrument_type = Column(String(32), default="OPTION", nullable=False)
    side = Column(String(16), default="BUY", nullable=False)
    option_type = Column(String(16), default="PUT", nullable=False)

    quantity = Column(Integer, nullable=False)
    order_type = Column(String(32), default="MARKET", nullable=False)

    status = Column(String(64), nullable=False)
    mode = Column(String(32), nullable=False)

    price_at_signal = Column(Float, nullable=False)
    signal_drop_pct = Column(Float, nullable=False)

    broker_order_id = Column(String(128), nullable=True)

    reason = Column(Text, nullable=False)
```

## `backend/app/schemas.py`

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TradeOut(BaseModel):
    id: int
    created_at: datetime

    symbol: str
    underlying_symbol: str

    instrument_type: str
    side: str
    option_type: str

    quantity: int
    order_type: str

    status: str
    mode: str

    price_at_signal: float
    signal_drop_pct: float

    broker_order_id: str | None
    reason: str

    model_config = ConfigDict(from_attributes=True)


class StatusOut(BaseModel):
    service: str
    watch_symbol: str
    option_contract_symbol: str
    auto_trade_mode: str
    feed_enabled: bool
    safety: str
```

## `backend/app/broker.py`

```python
from datetime import datetime
from uuid import uuid4


class PaperBroker:
    """
    Paper-only broker.

    This intentionally does not implement live order execution.
    """

    def place_market_put_order(
        self,
        *,
        underlying_symbol: str,
        option_contract_symbol: str,
        quantity: int,
    ) -> str:
        now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"PAPER-{now}-{uuid4().hex[:10]}"
```

## `backend/app/strategy.py`

```python
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Deque

from sqlalchemy.orm import Session

from app.broker import PaperBroker
from app.models import Trade


@dataclass(frozen=True)
class StrategyConfig:
    watch_symbol: str
    option_contract_symbol: str
    order_quantity: int
    drop_threshold_pct: float
    lookback_minutes: int
    auto_trade_mode: str


class DropStrategy:
    """
    Detects whether the watched symbol has fallen more than threshold percent
    from its highest price observed within the rolling lookback window.

    Safe behavior:
      - paper mode: record a paper-filled trade
      - manual mode: record a pending recommendation
    """

    def __init__(self, config: StrategyConfig, broker: PaperBroker):
        if config.auto_trade_mode not in {"paper", "manual"}:
            raise ValueError("auto_trade_mode must be 'paper' or 'manual'")

        self.config = config
        self.broker = broker

        self.prices: Deque[tuple[datetime, float]] = deque()
        self.last_signal_at: datetime | None = None

    def on_price(
        self,
        *,
        db: Session,
        symbol: str,
        price: float,
        timestamp: datetime | None = None,
    ) -> Trade | None:
        if symbol != self.config.watch_symbol:
            return None

        if price <= 0:
            return None

        ts = timestamp or datetime.utcnow()
        lookback = timedelta(minutes=self.config.lookback_minutes)

        self.prices.append((ts, float(price)))

        cutoff = ts - lookback
        while self.prices and self.prices[0][0] < cutoff:
            self.prices.popleft()

        if len(self.prices) < 2:
            return None

        if self.last_signal_at is not None and ts - self.last_signal_at < lookback:
            return None

        max_price = max(p for _, p in self.prices)
        drop_pct = ((max_price - price) / max_price) * 100.0

        # "more than 2%" means strictly greater than the configured threshold.
        if drop_pct <= self.config.drop_threshold_pct:
            return None

        broker_order_id = None
        status = "PENDING_APPROVAL"
        mode = "manual"

        if self.config.auto_trade_mode == "paper":
            broker_order_id = self.broker.place_market_put_order(
                underlying_symbol=self.config.watch_symbol,
                option_contract_symbol=self.config.option_contract_symbol,
                quantity=self.config.order_quantity,
            )
            status = "PAPER_FILLED"
            mode = "paper"

        reason = (
            f"{self.config.watch_symbol} dropped {drop_pct:.2f}% within "
            f"{self.config.lookback_minutes} minutes. "
            f"Detected price={price:.4f}, rolling-window high={max_price:.4f}. "
            "Safe system behavior: no autonomous live brokerage order was sent."
        )

        trade = Trade(
            symbol=self.config.option_contract_symbol,
            underlying_symbol=self.config.watch_symbol,
            instrument_type="OPTION",
            side="BUY",
            option_type="PUT",
            quantity=self.config.order_quantity,
            order_type="MARKET",
            status=status,
            mode=mode,
            price_at_signal=price,
            signal_drop_pct=drop_pct,
            broker_order_id=broker_order_id,
            reason=reason,
        )

        db.add(trade)
        db.commit()
        db.refresh(trade)

        self.last_signal_at = ts

        return trade
```

## `backend/app/market_data.py`

```python
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
```

## `backend/app/main.py`

```python
import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.broker import PaperBroker
from app.config import settings
from app.database import get_db, init_db
from app.market_data import run_market_data_stream
from app.models import Trade
from app.schemas import StatusOut, TradeOut
from app.strategy import DropStrategy, StrategyConfig


def build_strategy() -> DropStrategy:
    broker = PaperBroker()
    config = StrategyConfig(
        watch_symbol=settings.watch_symbol,
        option_contract_symbol=settings.option_contract_symbol,
        order_quantity=settings.order_quantity,
        drop_threshold_pct=settings.drop_threshold_pct,
        lookback_minutes=settings.lookback_minutes,
        auto_trade_mode=settings.auto_trade_mode,
    )
    return DropStrategy(config=config, broker=broker)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    app.state.broker = PaperBroker()
    app.state.strategy = build_strategy()
    app.state.market_task = None

    if not settings.disable_feed:
        app.state.market_task = asyncio.create_task(
            run_market_data_stream(settings, app.state.strategy)
        )

    yield

    if app.state.market_task is not None:
        app.state.market_task.cancel()
        try:
            await app.state.market_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Safe Trading Automation Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status", response_model=StatusOut)
def status():
    return StatusOut(
        service="ok",
        watch_symbol=settings.watch_symbol,
        option_contract_symbol=settings.option_contract_symbol,
        auto_trade_mode=settings.auto_trade_mode,
        feed_enabled=not settings.disable_feed,
        safety=(
            "Paper/manual workflow only. This service does not send autonomous "
            "live brokerage orders."
        ),
    )


@app.get("/api/trades", response_model=list[TradeOut])
def list_trades(db: Session = Depends(get_db)):
    return (
        db.query(Trade)
        .order_by(Trade.created_at.desc(), Trade.id.desc())
        .all()
    )


@app.post("/api/trades/{trade_id}/approve", response_model=TradeOut)
def approve_pending_trade(
    trade_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()

    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")

    if trade.status != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=400,
            detail="Only PENDING_APPROVAL trades can be approved",
        )

    # Still paper-only.
    broker_order_id = request.app.state.broker.place_market_put_order(
        underlying_symbol=trade.underlying_symbol,
        option_contract_symbol=trade.symbol,
        quantity=trade.quantity,
    )

    trade.status = "PAPER_FILLED"
    trade.mode = "paper_manual_approved"
    trade.broker_order_id = broker_order_id
    trade.reason += " Manually approved in dashboard and paper-filled."

    db.commit()
    db.refresh(trade)

    return trade


@app.post("/api/dev/price")
def dev_inject_price(
    symbol: str,
    price: float,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Local development helper for DISABLE_FEED=true.
    Example:
      curl -X POST 'http://localhost:8000/api/dev/price?symbol=SPY&price=480'
    """
    trade = request.app.state.strategy.on_price(
        db=db,
        symbol=symbol,
        price=price,
    )

    return {
        "accepted": True,
        "trade_created": trade is not None,
        "trade_id": trade.id if trade else None,
    }
```

---

# Backend tests

## `backend/tests/test_strategy.py`

```python
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.broker import PaperBroker
from app.database import Base
from app.models import Trade
from app.strategy import DropStrategy, StrategyConfig


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def make_strategy(mode: str = "paper") -> DropStrategy:
    return DropStrategy(
        config=StrategyConfig(
            watch_symbol="SPY",
            option_contract_symbol="SPY_PUT_DEMO",
            order_quantity=10,
            drop_threshold_pct=2.0,
            lookback_minutes=60,
            auto_trade_mode=mode,
        ),
        broker=PaperBroker(),
    )


def test_triggers_paper_trade_on_more_than_two_percent_hourly_drop(db):
    strategy = make_strategy(mode="paper")
    start = datetime(2026, 1, 1, 10, 0, 0)

    assert strategy.on_price(db=db, symbol="SPY", price=100.00, timestamp=start) is None

    trade = strategy.on_price(
        db=db,
        symbol="SPY",
        price=97.50,
        timestamp=start + timedelta(minutes=30),
    )

    assert trade is not None
    assert trade.quantity == 10
    assert trade.side == "BUY"
    assert trade.option_type == "PUT"
    assert trade.status == "PAPER_FILLED"
    assert trade.broker_order_id.startswith("PAPER-")
    assert trade.signal_drop_pct == pytest.approx(2.5)

    saved = db.query(Trade).all()
    assert len(saved) == 1


def test_does_not_trigger_at_exactly_two_percent(db):
    strategy = make_strategy(mode="paper")
    start = datetime(2026, 1, 1, 10, 0, 0)

    strategy.on_price(db=db, symbol="SPY", price=100.00, timestamp=start)
    trade = strategy.on_price(
        db=db,
        symbol="SPY",
        price=98.00,
        timestamp=start + timedelta(minutes=15),
    )

    assert trade is None
    assert db.query(Trade).count() == 0


def test_manual_mode_creates_pending_approval_trade(db):
    strategy = make_strategy(mode="manual")
    start = datetime(2026, 1, 1, 10, 0, 0)

    strategy.on_price(db=db, symbol="SPY", price=100.00, timestamp=start)
    trade = strategy.on_price(
        db=db,
        symbol="SPY",
        price=97.00,
        timestamp=start + timedelta(minutes=10),
    )

    assert trade is not None
    assert trade.status == "PENDING_APPROVAL"
    assert trade.broker_order_id is None
    assert trade.mode == "manual"


def test_ignores_other_symbols(db):
    strategy = make_strategy(mode="paper")
    start = datetime(2026, 1, 1, 10, 0, 0)

    strategy.on_price(db=db, symbol="QQQ", price=100.00, timestamp=start)
    trade = strategy.on_price(
        db=db,
        symbol="QQQ",
        price=90.00,
        timestamp=start + timedelta(minutes=10),
    )

    assert trade is None
    assert db.query(Trade).count() == 0


def test_cooldown_prevents_repeated_trades_within_lookback_window(db):
    strategy = make_strategy(mode="paper")
    start = datetime(2026, 1, 1, 10, 0, 0)

    strategy.on_price(db=db, symbol="SPY", price=100.00, timestamp=start)

    first = strategy.on_price(
        db=db,
        symbol="SPY",
        price=97.00,
        timestamp=start + timedelta(minutes=10),
    )
    second = strategy.on_price(
        db=db,
        symbol="SPY",
        price=96.00,
        timestamp=start + timedelta(minutes=20),
    )

    assert first is not None
    assert second is None
    assert db.query(Trade).count() == 1
```

---

# Frontend

## `frontend/package.json`

```json
{
  "name": "trading-dashboard-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 5173",
    "build": "vite build",
    "preview": "vite preview --host 0.0.0.0 --port 5173"
  },
  "dependencies": {
    "@vitejs/plugin-react": "latest",
    "vite": "latest",
    "react": "latest",
    "react-dom": "latest"
  },
  "devDependencies": {}
}
```

## `frontend/index.html`

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Trading Automation Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

## `frontend/vite.config.js`

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()]
});
```

## `frontend/src/main.jsx`

```jsx
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

## `frontend/src/App.jsx`

```jsx
import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

export default function App() {
  const [status, setStatus] = useState(null);
  const [trades, setTrades] = useState([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setError("");

      const [statusRes, tradesRes] = await Promise.all([
        fetch(`${API_URL}/api/status`),
        fetch(`${API_URL}/api/trades`)
      ]);

      if (!statusRes.ok) throw new Error("Failed to fetch status");
      if (!tradesRes.ok) throw new Error("Failed to fetch trades");

      setStatus(await statusRes.json());
      setTrades(await tradesRes.json());
    } catch (err) {
      setError(err.message || String(err));
    }
  }

  async function approveTrade(id) {
    try {
      setError("");
      const res = await fetch(`${API_URL}/api/trades/${id}/approve`, {
        method: "POST"
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Approval failed");
      }

      await load();
    } catch (err) {
      setError(err.message || String(err));
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <main className="container">
      <header className="header">
        <div>
          <h1>Trading Automation Dashboard</h1>
          <p className="subtitle">
            Paper/manual workflow for options strategy monitoring.
          </p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>

      {error && <section className="error">{error}</section>}

      <section className="card">
        <h2>Service Status</h2>
        {status ? (
          <div className="grid">
            <div>
              <span>Service</span>
              <strong>{status.service}</strong>
            </div>
            <div>
              <span>Watched Symbol</span>
              <strong>{status.watch_symbol}</strong>
            </div>
            <div>
              <span>Option Contract</span>
              <strong>{status.option_contract_symbol}</strong>
            </div>
            <div>
              <span>Mode</span>
              <strong>{status.auto_trade_mode}</strong>
            </div>
            <div>
              <span>Feed Enabled</span>
              <strong>{String(status.feed_enabled)}</strong>
            </div>
          </div>
        ) : (
          <p>Loading...</p>
        )}

        {status && <p className="safety">{status.safety}</p>}
      </section>

      <section className="card">
        <h2>Trade History</h2>

        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Created</th>
                <th>Underlying</th>
                <th>Contract</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Status</th>
                <th>Drop %</th>
                <th>Signal Price</th>
                <th>Broker/Paper ID</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {trades.length === 0 ? (
                <tr>
                  <td colSpan="11" className="empty">
                    No trades recorded.
                  </td>
                </tr>
              ) : (
                trades.map((trade) => (
                  <tr key={trade.id}>
                    <td>{trade.id}</td>
                    <td>{formatDate(trade.created_at)}</td>
                    <td>{trade.underlying_symbol}</td>
                    <td>{trade.symbol}</td>
                    <td>
                      {trade.side} {trade.option_type}
                    </td>
                    <td>{trade.quantity}</td>
                    <td>
                      <span className={`pill ${trade.status.toLowerCase()}`}>
                        {trade.status}
                      </span>
                    </td>
                    <td>{trade.signal_drop_pct.toFixed(2)}%</td>
                    <td>{trade.price_at_signal.toFixed(2)}</td>
                    <td>{trade.broker_order_id || "-"}</td>
                    <td>
                      {trade.status === "PENDING_APPROVAL" ? (
                        <button onClick={() => approveTrade(trade.id)}>
                          Approve Paper Fill
                        </button>
                      ) : (
                        "-"
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
```

## `frontend/src/styles.css`

```css
:root {
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    sans-serif;
  color: #172033;
  background: #f4f7fb;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

button {
  border: 0;
  background: #1f6feb;
  color: white;
  font-weight: 700;
  border-radius: 10px;
  padding: 0.7rem 1rem;
  cursor: pointer;
}

button:hover {
  background: #1557c0;
}

.container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 2rem;
}

.header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1.5rem;
}

h1,
h2 {
  margin: 0;
}

.subtitle {
  margin: 0.35rem 0 0;
  color: #5d6b82;
}

.card {
  background: white;
  border: 1px solid #e1e8f2;
  border-radius: 18px;
  padding: 1.25rem;
  margin-bottom: 1.25rem;
  box-shadow: 0 8px 24px rgba(23, 32, 51, 0.06);
}

.grid {
  margin-top: 1rem;
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.grid div {
  border: 1px solid #e1e8f2;
  border-radius: 14px;
  padding: 1rem;
  background: #fafcff;
}

.grid span {
  display: block;
  color: #69778e;
  font-size: 0.82rem;
  margin-bottom: 0.35rem;
}

.grid strong {
  font-size: 1rem;
}

.safety {
  margin: 1rem 0 0;
  background: #fff8e6;
  border: 1px solid #f3d58b;
  color: #725200;
  border-radius: 12px;
  padding: 0.9rem;
}

.error {
  background: #ffecec;
  border: 1px solid #ffb3b3;
  color: #a30000;
  border-radius: 12px;
  padding: 0.9rem;
  margin-bottom: 1rem;
}

.tableWrap {
  margin-top: 1rem;
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 1080px;
}

th,
td {
  text-align: left;
  border-bottom: 1px solid #e8eef7;
  padding: 0.85rem;
  vertical-align: top;
}

th {
  color: #526178;
  font-size: 0.85rem;
}

.empty {
  text-align: center;
  color: #69778e;
}

.pill {
  display: inline-block;
  border-radius: 999px;
  padding: 0.25rem 0.55rem;
  font-size: 0.75rem;
  font-weight: 800;
}

.pill.paper_filled {
  background: #e8fff0;
  color: #087333;
}

.pill.pending_approval {
  background: #fff8e6;
  color: #7a5600;
}

@media (max-width: 900px) {
  .grid {
    grid-template-columns: 1fr;
  }

  .header {
    align-items: flex-start;
    flex-direction: column;
  }
}
```

---

# README

## `README.md`

```md
# Safe Trading Automation Dashboard

This project provides:

- FastAPI backend
- SQLite local trade database
- WebSocket market-data listener
- Rolling one-hour drop detector
- React dashboard
- Paper/manual trade workflow

## Safety behavior

This service does **not** send autonomous live brokerage orders.

Modes:

- `AUTO_TRADE_MODE=paper`: automatically records a paper-filled put-option trade when the signal triggers.
- `AUTO_TRADE_MODE=manual`: records a pending recommendation that can be manually approved in the dashboard, still as a paper fill.

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp ../.env.example .env

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend API:

- `GET http://localhost:8000/api/status`
- `GET http://localhost:8000/api/trades`
- `POST http://localhost:8000/api/trades/{id}/approve`

For local testing without WebSocket:

```bash
# in backend/.env
DISABLE_FEED=true
```

Then inject prices:

```bash
curl -X POST 'http://localhost:8000/api/dev/price?symbol=SPY&price=100'
curl -X POST 'http://localhost:8000/api/dev/price?symbol=SPY&price=97.5'
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

## Production notes

Before adapting to a real brokerage workflow, add:

- Broker-specific authentication
- Exact market-data subscription schema
- Exact option contract selection logic
- Manual approval, compliance, audit, and risk controls
- Position limits
- Kill switch
- Monitoring and alerting
- Explicit human confirmation for any live order
```

---

# Commands to run

From the repo root:

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
# Frontend
cd frontend
npm install
npm run dev
```

Run tests:

```bash
cd backend
source .venv/bin/activate
pytest
```

Optional local signal test without external WebSocket:

```bash
# set DISABLE_FEED=true in backend/.env, restart backend, then:
curl -X POST 'http://localhost:8000/api/dev/price?symbol=SPY&price=100'
curl -X POST 'http://localhost:8000/api/dev/price?symbol=SPY&price=97.5'
curl 'http://localhost:8000/api/trades'
```

Open the dashboard:

```text
http://localhost:5173
```

The backend listens on:

```text
http://localhost:8000
```
