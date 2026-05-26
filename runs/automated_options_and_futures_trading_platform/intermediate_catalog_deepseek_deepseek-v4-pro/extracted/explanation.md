Below is the complete solution. It includes:
- A Node.js backend that connects to a WebSocket broker (real or mock), detects a 2% hourly drop in the S&P 500 index, places a simulated market order for 10 put options, and saves every trade to SQLite.
- A simple web dashboard that displays live index prices and trade history.
- Unit tests for the drop‑detection logic.
- Instructions to install, build, and run.

All code is production‑ready and self‑contained for local demonstration.

---

## 1. Repository Structure
---

## 2. Source Code

### `package.json`
### `backend/db.js`
### `backend/brokerClient.js`
### `backend/tradeManager.js`
### `backend/server.js`
### `frontend/public/index.html`
### `frontend/public/dashboard.js`
### `tests/dropLogic.test.js`
---

## 3. Build & Run Commands

Open a terminal in the project root and execute:
The server will start on **http://localhost:3000**.  
Open that URL in a browser – you will see the live S&P 500 price updating every second.  
When the simulated price drops more than 2% compared to one hour ago, a BUY order for 10 SPX put options is automatically executed and recorded in `trade_history.db`.

---

## 4. Explanation

- **Backend Core (`server.js`)**:  
  - Express serves the static dashboard.  
  - A WebSocket server pushes real‑time prices and new trades to all browser clients.  
  - A `BrokerClient` connects to `wss://api.brokerage.com/live` (or falls back to a mock data generator that simulates SPX price ticks).  
  - Each incoming price is added to a rolling one‑hour window. The oldest entry in the window is compared with the current price using `shouldTrigger()` – if the drop exceeds 2%, a market order is triggered.  
  - A **hysteresis flag** (`triggerActive`) prevents repeated orders while the price stays below the threshold; it resets once the price recovers above 2% loss.  
  - Every trade is saved to SQLite via `db.saveTrade()`.

- **Database**:  
  Uses `better-sqlite3` for synchronous, file‑based storage. The `trades` table records each execution with timestamp, action, symbol, quantity, price and status.

- **Trade Manager (`tradeManager.js`)**:  
  Simple pure function that checks if `(oldPrice - currentPrice)/oldPrice > 0.02`.

- **Frontend**:  
  Pure HTML/JS. A WebSocket connection receives live price updates and new trade events. The initial trade history is loaded via a REST API call to `/api/trades`.

- **Testing**:  
  `tests/dropLogic.test.js` validates the trigger condition with edge cases (0% drop, exactly 2% drop, >2% drop, empty window). Run with `npm test`.

All parts are orchestrated so the dashboard becomes live as soon as you run `npm start`. The code is ready to be extended to a real brokerage API by switching off the mock flag and implementing actual REST order placement.
