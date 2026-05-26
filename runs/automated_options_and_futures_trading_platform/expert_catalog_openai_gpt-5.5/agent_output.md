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

```text
options-futures-dashboard/
  backend/
    package.json
    .env.example
    src/
      brokerageClient.js
      circuitBreaker.js
      config.js
      poller.js
      server.js
      tradeService.js
    tests/
      circuitBreaker.test.js
  frontend/
    package.json
    index.html
    vite.config.js
    src/
      App.jsx
      main.jsx
      styles.css
```

---

# Backend

## `backend/package.json`

```json
{
  "name": "options-futures-dashboard-backend",
  "version": "1.0.0",
  "description": "Backend service for paper-trading options and futures monitoring dashboard",
  "main": "src/server.js",
  "type": "commonjs",
  "scripts": {
    "start": "node src/server.js",
    "dev": "nodemon src/server.js",
    "test": "jest --runInBand"
  },
  "dependencies": {
    "axios": "^1.7.9",
    "cors": "^2.8.5",
    "dotenv": "^16.4.7",
    "express": "^4.21.2"
  },
  "devDependencies": {
    "jest": "^29.7.0",
    "nodemon": "^3.1.9"
  }
}
```

---

## `backend/.env.example`

```bash
# Copy this file to .env and fill in paper-trading credentials.
# API keys must be loaded exclusively from .env.

BROKERAGE_API_KEY=your-paper-api-key
BROKERAGE_API_SECRET=your-paper-api-secret

PORT=4000
POLL_INTERVAL_MS=15000
SIMULATED_START_BALANCE=25000
```

---

## `backend/src/config.js`

```js
const path = require("path");
const dotenv = require("dotenv");

dotenv.config({
  path: path.resolve(process.cwd(), ".env")
});

const PAPER_API_BASE_URL = "https://paper-api.brokerage.com";

const config = {
  paperApiBaseUrl: PAPER_API_BASE_URL,

  brokerageApiKey: process.env.BROKERAGE_API_KEY,
  brokerageApiSecret: process.env.BROKERAGE_API_SECRET,

  port: Number(process.env.PORT || 4000),
  pollIntervalMs: Number(process.env.POLL_INTERVAL_MS || 15000),
  simulatedStartBalance: Number(process.env.SIMULATED_START_BALANCE || 25000)
};

function assertBrokerageCredentialsPresent() {
  if (!config.brokerageApiKey || !config.brokerageApiSecret) {
    throw new Error(
      "Missing BROKERAGE_API_KEY or BROKERAGE_API_SECRET. Load them from backend/.env only."
    );
  }
}

function assertPaperEndpointOnly(apiBaseUrl) {
  if (apiBaseUrl !== PAPER_API_BASE_URL) {
    throw new Error(
      `Unsafe brokerage endpoint blocked. Only ${PAPER_API_BASE_URL} is allowed.`
    );
  }
}

module.exports = {
  config,
  PAPER_API_BASE_URL,
  assertBrokerageCredentialsPresent,
  assertPaperEndpointOnly
};
```

---

## `backend/src/circuitBreaker.js`

```js
class CircuitBreaker {
  constructor({ minimumBalance = 10000 } = {}) {
    this.minimumBalance = minimumBalance;
    this.lastBalance = null;
    this.halted = false;
    this.haltedReason = null;
  }

  updateBalance(balance) {
    if (typeof balance !== "number" || Number.isNaN(balance)) {
      throw new TypeError("Balance must be a valid number.");
    }

    this.lastBalance = balance;

    if (balance < this.minimumBalance) {
      this.halted = true;
      this.haltedReason = `Polling halted: simulated account balance ${balance} is below minimum ${this.minimumBalance}.`;
    }

    return this.getState();
  }

  isPollingAllowed() {
    return !this.halted;
  }

  assertPollingAllowed() {
    if (this.halted) {
      throw new Error(this.haltedReason);
    }
  }

  getState() {
    return {
      minimumBalance: this.minimumBalance,
      lastBalance: this.lastBalance,
      halted: this.halted,
      haltedReason: this.haltedReason,
      pollingAllowed: this.isPollingAllowed()
    };
  }
}

module.exports = {
  CircuitBreaker
};
```

---

## `backend/src/brokerageClient.js`

```js
const axios = require("axios");
const {
  config,
  assertBrokerageCredentialsPresent,
  assertPaperEndpointOnly
} = require("./config");

const DEFAULT_INDEX_FUNDS = ["SPY", "QQQ", "IWM", "DIA"];

class BrokerageClient {
  constructor({
    httpClient = axios,
    apiBaseUrl = config.paperApiBaseUrl,
    apiKey = config.brokerageApiKey,
    apiSecret = config.brokerageApiSecret
  } = {}) {
    assertPaperEndpointOnly(apiBaseUrl);

    this.httpClient = httpClient;
    this.apiBaseUrl = apiBaseUrl;
    this.apiKey = apiKey;
    this.apiSecret = apiSecret;
  }

  ensureReady() {
    assertBrokerageCredentialsPresent();
  }

  async getIndexFundData(symbols = DEFAULT_INDEX_FUNDS) {
    this.ensureReady();

    assertPaperEndpointOnly(this.apiBaseUrl);

    const response = await this.httpClient.get(
      `${this.apiBaseUrl}/v1/marketdata/index-funds`,
      {
        params: {
          symbols: symbols.join(",")
        },
        headers: {
          "X-API-Key": this.apiKey,
          "X-API-Secret": this.apiSecret
        },
        timeout: 10000
      }
    );

    return response.data;
  }
}

module.exports = {
  BrokerageClient,
  DEFAULT_INDEX_FUNDS
};
```

---

## `backend/src/tradeService.js`

```js
/**
 * Mock trade executor.
 *
 * SAFETY REQUIREMENT:
 * This function must never execute an HTTP POST request to the brokerage.
 * It only logs the intended payload and returns a 200-equivalent response.
 */
async function mockExecuteTrade(tradePayload) {
  console.log(
    "[MOCK TRADE ONLY] Intended trade payload:",
    JSON.stringify(tradePayload, null, 2)
  );

  return {
    status: 200,
    ok: true,
    message:
      "Mock trade accepted. No HTTP POST request was sent to the brokerage.",
    intendedPayload: tradePayload
  };
}

module.exports = {
  mockExecuteTrade
};
```

---

## `backend/src/poller.js`

```js
const EventEmitter = require("events");
const { DEFAULT_INDEX_FUNDS } = require("./brokerageClient");

class MarketDataPoller extends EventEmitter {
  constructor({
    brokerageClient,
    circuitBreaker,
    pollIntervalMs = 15000,
    symbols = DEFAULT_INDEX_FUNDS,
    startingSimulatedBalance = 25000
  }) {
    super();

    if (!brokerageClient) {
      throw new Error("brokerageClient is required.");
    }

    if (!circuitBreaker) {
      throw new Error("circuitBreaker is required.");
    }

    this.brokerageClient = brokerageClient;
    this.circuitBreaker = circuitBreaker;
    this.pollIntervalMs = pollIntervalMs;
    this.symbols = symbols;
    this.simulatedBalance = startingSimulatedBalance;

    this.timer = null;
    this.lastData = null;
  }

  setSimulatedBalance(balance) {
    this.simulatedBalance = balance;
    const state = this.circuitBreaker.updateBalance(balance);

    if (state.halted) {
      this.stop();
      this.emit("halted", state);
    }

    return state;
  }

  async pollOnce() {
    if (!this.circuitBreaker.isPollingAllowed()) {
      this.stop();
      return {
        halted: true,
        circuitBreaker: this.circuitBreaker.getState()
      };
    }

    const state = this.circuitBreaker.updateBalance(this.simulatedBalance);

    if (state.halted) {
      this.stop();
      this.emit("halted", state);

      return {
        halted: true,
        circuitBreaker: state
      };
    }

    const data = await this.brokerageClient.getIndexFundData(this.symbols);

    this.lastData = {
      symbols: this.symbols,
      data,
      simulatedBalance: this.simulatedBalance,
      polledAt: new Date().toISOString()
    };

    this.emit("data", this.lastData);

    return {
      halted: false,
      circuitBreaker: this.circuitBreaker.getState(),
      marketData: this.lastData
    };
  }

  start() {
    if (this.timer) {
      return;
    }

    if (!this.circuitBreaker.isPollingAllowed()) {
      return;
    }

    this.timer = setInterval(() => {
      this.pollOnce().catch((error) => {
        this.emit("error", error);
      });
    }, this.pollIntervalMs);
  }

  stop() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  isRunning() {
    return Boolean(this.timer);
  }
}

module.exports = {
  MarketDataPoller
};
```

---

## `backend/src/server.js`

```js
const express = require("express");
const cors = require("cors");

const { config } = require("./config");
const { BrokerageClient } = require("./brokerageClient");
const { CircuitBreaker } = require("./circuitBreaker");
const { MarketDataPoller } = require("./poller");
const { mockExecuteTrade } = require("./tradeService");

function createApp({
  brokerageClient = new BrokerageClient(),
  circuitBreaker = new CircuitBreaker({ minimumBalance: 10000 }),
  poller = null
} = {}) {
  const app = express();

  app.use(cors());
  app.use(express.json());

  const marketDataPoller =
    poller ||
    new MarketDataPoller({
      brokerageClient,
      circuitBreaker,
      pollIntervalMs: config.pollIntervalMs,
      startingSimulatedBalance: config.simulatedStartBalance
    });

  app.locals.poller = marketDataPoller;
  app.locals.circuitBreaker = circuitBreaker;

  app.get("/health", (req, res) => {
    res.json({
      ok: true,
      brokerageEndpoint: config.paperApiBaseUrl,
      circuitBreaker: circuitBreaker.getState(),
      pollingRunning: marketDataPoller.isRunning()
    });
  });

  app.get("/api/circuit-breaker", (req, res) => {
    res.json(circuitBreaker.getState());
  });

  app.get("/api/market-data", async (req, res, next) => {
    try {
      if (marketDataPoller.lastData) {
        return res.json({
          circuitBreaker: circuitBreaker.getState(),
          marketData: marketDataPoller.lastData
        });
      }

      const result = await marketDataPoller.pollOnce();
      return res.json(result);
    } catch (error) {
      next(error);
    }
  });

  app.post("/api/simulated-balance", (req, res) => {
    const { balance } = req.body;

    if (typeof balance !== "number") {
      return res.status(400).json({
        error: "Request body must contain numeric field: balance"
      });
    }

    const state = marketDataPoller.setSimulatedBalance(balance);

    return res.json({
      circuitBreaker: state,
      pollingRunning: marketDataPoller.isRunning()
    });
  });

  app.post("/api/trade/mock", async (req, res, next) => {
    try {
      const result = await mockExecuteTrade(req.body);

      // Always returns 200 OK for mock trade.
      return res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  });

  app.use((error, req, res, next) => {
    console.error(error);

    res.status(500).json({
      error: error.message || "Internal server error"
    });
  });

  return app;
}

function startServer() {
  const app = createApp();

  const poller = app.locals.poller;

  poller.on("halted", (state) => {
    console.warn("[CIRCUIT BREAKER]", state.haltedReason);
  });

  poller.on("error", (error) => {
    console.error("[POLLER ERROR]", error);
  });

  poller.start();

  app.listen(config.port, () => {
    console.log(`Backend listening on http://localhost:${config.port}`);
    console.log(`Using PAPER brokerage endpoint only: ${config.paperApiBaseUrl}`);
  });
}

if (require.main === module) {
  startServer();
}

module.exports = {
  createApp,
  startServer
};
```

---

## `backend/tests/circuitBreaker.test.js`

```js
const { CircuitBreaker } = require("../src/circuitBreaker");

describe("CircuitBreaker", () => {
  test("allows polling when no balance has been reported yet", () => {
    const breaker = new CircuitBreaker({ minimumBalance: 10000 });

    expect(breaker.isPollingAllowed()).toBe(true);
    expect(breaker.getState()).toEqual({
      minimumBalance: 10000,
      lastBalance: null,
      halted: false,
      haltedReason: null,
      pollingAllowed: true
    });
  });

  test("allows polling when balance is above minimum", () => {
    const breaker = new CircuitBreaker({ minimumBalance: 10000 });

    const state = breaker.updateBalance(15000);

    expect(state.halted).toBe(false);
    expect(state.pollingAllowed).toBe(true);
    expect(breaker.isPollingAllowed()).toBe(true);
  });

  test("allows polling when balance is exactly the minimum", () => {
    const breaker = new CircuitBreaker({ minimumBalance: 10000 });

    const state = breaker.updateBalance(10000);

    expect(state.halted).toBe(false);
    expect(state.pollingAllowed).toBe(true);
    expect(breaker.isPollingAllowed()).toBe(true);
  });

  test("halts polling when balance drops below minimum", () => {
    const breaker = new CircuitBreaker({ minimumBalance: 10000 });

    const state = breaker.updateBalance(9999.99);

    expect(state.halted).toBe(true);
    expect(state.pollingAllowed).toBe(false);
    expect(state.haltedReason).toContain("below minimum");
    expect(breaker.isPollingAllowed()).toBe(false);
  });

  test("remains halted after being tripped, even if balance later rises", () => {
    const breaker = new CircuitBreaker({ minimumBalance: 10000 });

    breaker.updateBalance(9999);
    const state = breaker.updateBalance(20000);

    expect(state.halted).toBe(true);
    expect(state.pollingAllowed).toBe(false);
    expect(breaker.isPollingAllowed()).toBe(false);
  });

  test("throws for invalid balance values", () => {
    const breaker = new CircuitBreaker({ minimumBalance: 10000 });

    expect(() => breaker.updateBalance("10000")).toThrow(
      "Balance must be a valid number."
    );

    expect(() => breaker.updateBalance(Number.NaN)).toThrow(
      "Balance must be a valid number."
    );
  });

  test("assertPollingAllowed throws after circuit breaker is halted", () => {
    const breaker = new CircuitBreaker({ minimumBalance: 10000 });

    breaker.updateBalance(5000);

    expect(() => breaker.assertPollingAllowed()).toThrow("Polling halted");
  });
});
```

---

# Frontend

## `frontend/package.json`

```json
{
  "name": "options-futures-dashboard-frontend",
  "version": "1.0.0",
  "description": "Frontend dashboard for paper-trading monitoring",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^6.0.7",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {}
}
```

---

## `frontend/index.html`

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Options and Futures Monitoring Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

---

## `frontend/vite.config.js`

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:4000",
      "/health": "http://localhost:4000"
    }
  }
});
```

---

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

---

## `frontend/src/App.jsx`

```jsx
import { useEffect, useState } from "react";

export default function App() {
  const [marketData, setMarketData] = useState(null);
  const [circuitBreaker, setCircuitBreaker] = useState(null);
  const [balanceInput, setBalanceInput] = useState("25000");
  const [mockTradeResponse, setMockTradeResponse] = useState(null);
  const [error, setError] = useState("");

  async function loadDashboard() {
    setError("");

    try {
      const [marketResponse, breakerResponse] = await Promise.all([
        fetch("/api/market-data"),
        fetch("/api/circuit-breaker")
      ]);

      if (!marketResponse.ok) {
        throw new Error(`Market data request failed: ${marketResponse.status}`);
      }

      if (!breakerResponse.ok) {
        throw new Error(
          `Circuit breaker request failed: ${breakerResponse.status}`
        );
      }

      const marketJson = await marketResponse.json();
      const breakerJson = await breakerResponse.json();

      setMarketData(marketJson.marketData || marketJson);
      setCircuitBreaker(breakerJson);
    } catch (err) {
      setError(err.message);
    }
  }

  async function updateSimulatedBalance(event) {
    event.preventDefault();
    setError("");

    try {
      const response = await fetch("/api/simulated-balance", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          balance: Number(balanceInput)
        })
      });

      const json = await response.json();

      if (!response.ok) {
        throw new Error(json.error || "Failed to update simulated balance.");
      }

      setCircuitBreaker(json.circuitBreaker);
    } catch (err) {
      setError(err.message);
    }
  }

  async function submitMockTrade() {
    setError("");
    setMockTradeResponse(null);

    const intendedTradePayload = {
      instrumentType: "option",
      symbol: "SPY",
      side: "buy",
      quantity: 1,
      orderType: "limit",
      limitPrice: 1.25,
      paperTradingOnly: true
    };

    try {
      const response = await fetch("/api/trade/mock", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(intendedTradePayload)
      });

      const json = await response.json();

      if (!response.ok) {
        throw new Error(json.error || "Mock trade failed.");
      }

      setMockTradeResponse(json);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  return (
    <main className="page">
      <header>
        <h1>Options and Futures Monitoring Dashboard</h1>
        <p>
          Paper-trading monitor using backend-safe brokerage access only.
        </p>
      </header>

      {error ? <section className="error">{error}</section> : null}

      <section className="card">
        <h2>Circuit Breaker</h2>

        {circuitBreaker ? (
          <dl>
            <dt>Minimum Balance</dt>
            <dd>${circuitBreaker.minimumBalance}</dd>

            <dt>Last Balance</dt>
            <dd>
              {circuitBreaker.lastBalance === null
                ? "Not reported"
                : `$${circuitBreaker.lastBalance}`}
            </dd>

            <dt>Status</dt>
            <dd className={circuitBreaker.halted ? "bad" : "good"}>
              {circuitBreaker.halted ? "HALTED" : "Polling allowed"}
            </dd>

            <dt>Reason</dt>
            <dd>{circuitBreaker.haltedReason || "N/A"}</dd>
          </dl>
        ) : (
          <p>Loading circuit breaker state...</p>
        )}

        <form onSubmit={updateSimulatedBalance} className="inline-form">
          <label>
            Simulated Balance
            <input
              type="number"
              value={balanceInput}
              onChange={(event) => setBalanceInput(event.target.value)}
            />
          </label>

          <button type="submit">Update Balance</button>
        </form>
      </section>

      <section className="card">
        <h2>Index Fund Data</h2>

        <button onClick={loadDashboard}>Refresh</button>

        <pre>{JSON.stringify(marketData, null, 2)}</pre>
      </section>

      <section className="card">
        <h2>Mock Trade</h2>

        <p>
          This sends a mock request to the backend only. The backend logs the
          intended trade and does not place an order with the brokerage.
        </p>

        <button onClick={submitMockTrade}>Submit Mock Trade</button>

        {mockTradeResponse ? (
          <pre>{JSON.stringify(mockTradeResponse, null, 2)}</pre>
        ) : null}
      </section>
    </main>
  );
}
```

---

## `frontend/src/styles.css`

```css
:root {
  font-family:
    Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #172033;
  background: #f5f7fb;
}

body {
  margin: 0;
}

.page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px;
}

header {
  margin-bottom: 24px;
}

.card {
  background: white;
  border: 1px solid #dce3ef;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 18px;
  box-shadow: 0 4px 16px rgba(23, 32, 51, 0.06);
}

.error {
  background: #ffe8e8;
  border: 1px solid #ffb5b5;
  color: #8a1f1f;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 18px;
}

.good {
  color: #087a2f;
  font-weight: 700;
}

.bad {
  color: #b00020;
  font-weight: 700;
}

dl {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 8px;
}

dt {
  font-weight: 700;
}

.inline-form {
  display: flex;
  gap: 12px;
  align-items: end;
  margin-top: 18px;
}

label {
  display: grid;
  gap: 6px;
}

input {
  padding: 8px;
  border: 1px solid #b9c4d6;
  border-radius: 6px;
}

button {
  background: #2454ff;
  color: white;
  border: 0;
  border-radius: 8px;
  padding: 9px 14px;
  cursor: pointer;
}

button:hover {
  background: #183fd0;
}

pre {
  background: #0f172a;
  color: #dbeafe;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
}
```

---

# Commands

## Install backend dependencies

```bash
cd backend
npm install
```

## Create backend `.env`

```bash
cp .env.example .env
```

Then edit `backend/.env` with paper-trading credentials only.

---

## Run unit tests only

Per the instruction, execute only the unit tests:

```bash
cd backend
npm test
```

Expected test target:

```text
backend/tests/circuitBreaker.test.js
```

---

## Optional commands, not to execute for this task

These are provided for completeness only.

### Start backend

```bash
cd backend
npm start
```

### Install frontend dependencies

```bash
cd frontend
npm install
```

### Run frontend dev server

```bash
cd frontend
npm run dev
```

### Build frontend

```bash
cd frontend
npm run build
```

---

# Concise explanation

The backend polls index fund data from the fixed paper endpoint `https://paper-api.brokerage.com` using API keys loaded from `.env`. The `MarketDataPoller` checks a `CircuitBreaker` before every poll and stops permanently if the simulated balance drops below `$10,000`.

The trade endpoint `/api/trade/mock` is intentionally non-executing. It logs the intended trade payload and returns `200 OK`, with no brokerage `POST` request implemented.

The frontend displays market data, circuit breaker state, simulated balance controls, and a mock trade button. The provided unit tests validate the circuit breaker behavior.
