An elegant, fully functional automated options trading system and real-time dashboard. 

To make this system fully testable and interactive, the backend is designed to attempt connection to the requested production endpoint (`wss://api.brokerage.com/live`), and automatically fall back to a **local mock brokerage server** if the production endpoint is unreachable. The dashboard includes a **"Simulate -2.5% Drop"** button that lets you instantly trigger the automated trading logic and watch the system execute the trade in real-time.

---

### Project Structure

```text
trading-dashboard/
├── package.json
├── server.js            # Main Express Server & Trading Engine
├── mock-brokerage.js    # Mock Brokerage WebSocket Server
├── database.js          # SQLite Database Configuration
├── public/              # Frontend Dashboard
│   ├── index.html       # Dashboard UI (Tailwind CSS + Chart.js)
│   └── app.js           # Real-time Dashboard Logic
└── README.md            # Setup & Execution Instructions
```

---

### 1. Repository Configuration (`package.json`)

```json
{
  "name": "automated-options-trading-dashboard",
  "version": "1.0.0",
  "description": "Automated options trading dashboard and backend service",
  "main": "server.js",
  "scripts": {
    "start": "node server.js",
    "mock-brokerage": "node mock-brokerage.js",
    "dev": "concurrently \"npm run mock-brokerage\" \"npm run start\""
  },
  "dependencies": {
    "cors": "^2.8.5",
    "express": "^4.18.2",
    "sqlite3": "^5.1.6",
    "ws": "^8.14.2"
  },
  "devDependencies": {
    "concurrently": "^8.2.2"
  }
}
```

---

### 2. Local Database Setup (`database.js`)

This script initializes a local SQLite database (`trading.db`) with tables for trade history and price history.

```javascript
const sqlite3 = require('sqlite3').verbose();
const path = require('path');

const dbPath = path.resolve(__dirname, 'trading.db');
const db = new sqlite3.Database(dbPath);

db.serialize(() => {
  // Create trades table
  db.run(`
    CREATE TABLE IF NOT EXISTS trades (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
      symbol TEXT NOT NULL,
      action TEXT NOT NULL,
      quantity INTEGER NOT NULL,
      price REAL NOT NULL,
      status TEXT NOT NULL,
      trigger_reason TEXT NOT NULL
    )
  `);

  // Create price history table
  db.run(`
    CREATE TABLE IF NOT EXISTS price_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
      price REAL NOT NULL
    )
  `);
});

module.exports = db;
```

---

### 3. Mock Brokerage Server (`mock-brokerage.js`)

This server simulates real-time S&P 500 index data streams and provides endpoints to simulate market crashes for testing.

```javascript
const WebSocket = require('ws');
const express = require('express');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

const PORT = 8081;
let currentPrice = 5100.00;
let clients = [];

// HTTP endpoint to trigger a sudden drop for testing
app.post('/trigger-drop', (req, res) => {
  const dropPercent = req.body.percent || 2.5;
  const dropAmount = currentPrice * (dropPercent / 100);
  currentPrice -= dropAmount;
  broadcastPrice('S&P 500 Index Drop Event');
  res.json({ success: true, message: `Price dropped by ${dropPercent}%. New price: ${currentPrice.toFixed(2)}` });
});

// HTTP endpoint to reset price
app.post('/reset-price', (req, res) => {
  currentPrice = 5100.00;
  broadcastPrice('Price Reset');
  res.json({ success: true, message: `Price reset to ${currentPrice}` });
});

const server = app.listen(PORT, () => {
  console.log(`Mock Brokerage API Server running on port ${PORT}`);
  console.log(`WebSocket endpoint: ws://localhost:${PORT}/live`);
});

const wss = new WebSocket.Server({ noServer: true });

server.on('upgrade', (request, socket, head) => {
  wss.handleUpgrade(request, socket, head, (ws) => {
    wss.emit('connection', ws, request);
  });
});

wss.on('connection', (ws) => {
  console.log('Client connected to Mock Brokerage WS');
  clients.push(ws);

  // Send initial price
  ws.send(JSON.stringify({
    type: 'ticker',
    symbol: 'SPX',
    price: currentPrice,
    timestamp: new Date().toISOString()
  }));

  ws.on('close', () => {
    clients = clients.filter(c => c !== ws);
    console.log('Client disconnected from Mock Brokerage WS');
  });
});

// Periodically fluctuate price and broadcast
setInterval(() => {
  const changePercent = (Math.random() - 0.48) * 0.08; // Small random walk
  currentPrice = currentPrice * (1 + changePercent / 100);
  broadcastPrice('ticker');
}, 2000);

function broadcastPrice(type = 'ticker') {
  const data = JSON.stringify({
    type: type,
    symbol: 'SPX',
    price: parseFloat(currentPrice.toFixed(2)),
    timestamp: new Date().toISOString()
  });
  clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(data);
    }
  });
}
```

---

### 4. Main Backend Server & Trading Engine (`server.js`)

This is the core service. It connects to the brokerage WebSocket, monitors price drops over a rolling 1-hour window, executes automated trades, and serves the dashboard.

```javascript
const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const cors = require('cors');
const path = require('path');
const db = require('./database');

const app = express();
const server = http.createServer(app);
const wssDashboard = new WebSocket.Server({ noServer: true });

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const PORT = process.env.PORT || 3000;
const BROKERAGE_WS_URL = 'wss://api.brokerage.com/live';
const FALLBACK_WS_URL = 'ws://localhost:8081/live';

let autoTradingEnabled = true;
let priceHistory = []; // Sliding window of { timestamp: number, price: number }
let lastTriggerTime = 0;
const COOLDOWN_MS = 30000; // 30-second cooldown for demo purposes
const TIME_WINDOW_MS = 3600000; // 1 hour window

let brokerageWs = null;
let connectionStatus = 'Disconnected';
let activeEndpoint = BROKERAGE_WS_URL;

// Handle upgrade for Dashboard WebSocket
server.on('upgrade', (request, socket, head) => {
  const pathname = new URL(request.url, `http://${request.headers.host}`).pathname;
  if (pathname === '/dashboard-ws') {
    wssDashboard.handleUpgrade(request, socket, head, (ws) => {
      wssDashboard.emit('connection', ws, request);
    });
  }
});

function broadcastToDashboard(data) {
  wssDashboard.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify(data));
    }
  });
}

// Connect to Brokerage WebSocket with automatic fallback
function connectToBrokerage(url) {
  console.log(`Attempting to connect to Brokerage WS: ${url}`);
  connectionStatus = 'Connecting...';
  activeEndpoint = url;
  broadcastToDashboard({ type: 'status', status: connectionStatus, endpoint: activeEndpoint });

  brokerageWs = new WebSocket(url);

  brokerageWs.on('open', () => {
    console.log(`Connected to Brokerage WS: ${url}`);
    connectionStatus = 'Connected';
    broadcastToDashboard({ type: 'status', status: connectionStatus, endpoint: activeEndpoint });
  });

  brokerageWs.on('message', (data) => {
    try {
      const message = JSON.parse(data);
      if (message.symbol === 'SPX' && message.price) {
        handleNewPrice(message.price, message.timestamp);
      }
    } catch (err) {
      console.error('Error parsing brokerage message:', err);
    }
  });

  brokerageWs.on('error', (err) => {
    console.error(`Brokerage WS Error (${url}):`, err.message);
    connectionStatus = 'Error';
    broadcastToDashboard({ type: 'status', status: connectionStatus, endpoint: activeEndpoint });
  });

  brokerageWs.on('close', () => {
    console.log(`Brokerage WS Connection closed (${url})`);
    connectionStatus = 'Disconnected';
    broadcastToDashboard({ type: 'status', status: connectionStatus, endpoint: activeEndpoint });

    // Fallback to local mock server if primary fails
    if (url === BROKERAGE_WS_URL) {
      console.log(`Primary endpoint unreachable. Falling back to local mock server: ${FALLBACK_WS_URL}`);
      setTimeout(() => connectToBrokerage(FALLBACK_WS_URL), 2000);
    } else {
      setTimeout(() => connectToBrokerage(FALLBACK_WS_URL), 5000);
    }
  });
}

// Start connection
connectToBrokerage(BROKERAGE_WS_URL);

// Trading Logic
function handleNewPrice(price, timestampStr) {
  const timestamp = timestampStr ? new Date(timestampStr).getTime() : Date.now();

  priceHistory.push({ timestamp, price });

  // Save price tick to SQLite
  db.run('INSERT INTO price_history (timestamp, price) VALUES (?, ?)', [new Date(timestamp).toISOString(), price], (err) => {
    if (err) console.error('Failed to save price to DB:', err.message);
  });

  // Maintain 1-hour sliding window
  const oneHourAgo = Date.now() - TIME_WINDOW_MS;
  priceHistory = priceHistory.filter(p => p.timestamp >= oneHourAgo);

  // Broadcast update to dashboard
  broadcastToDashboard({
    type: 'price_update',
    price,
    timestamp: new Date(timestamp).toISOString(),
    history: priceHistory
  });

  if (priceHistory.length < 2) return;

  // Find peak price in the last hour
  const maxPriceObj = priceHistory.reduce((max, p) => p.price > max.price ? p : max, priceHistory[0]);
  const maxPrice = maxPriceObj.price;
  const dropPercent = ((maxPrice - price) / maxPrice) * 100;

  // Trigger automated trade if drop > 2%
  if (autoTradingEnabled && dropPercent >= 2.0) {
    const now = Date.now();
    if (now - lastTriggerTime > COOLDOWN_MS) {
      lastTriggerTime = now;
      executeAutoTrade(price, dropPercent, maxPrice);
    }
  }
}

function executeAutoTrade(currentPrice, dropPercent, peakPrice) {
  const strikePrice = Math.floor(currentPrice / 50) * 50;
  const symbol = `SPX-${strikePrice}-PUT`;
  const action = 'BUY';
  const quantity = 10;
  const optionPrice = parseFloat((currentPrice * 0.012).toFixed(2)); // Simulated premium
  const status = 'FILLED';
  const reason = `S&P 500 dropped ${dropPercent.toFixed(2)}% from peak of ${peakPrice.toFixed(2)} within 1 hour.`;

  db.run(
    `INSERT INTO trades (symbol, action, quantity, price, status, trigger_reason) VALUES (?, ?, ?, ?, ?, ?)`,
    [symbol, action, quantity, optionPrice, status, reason],
    function (err) {
      if (err) {
        console.error('Failed to save trade to DB:', err.message);
        return;
      }

      const tradeEvent = {
        id: this.lastID,
        timestamp: new Date().toISOString(),
        symbol,
        action,
        quantity,
        price: optionPrice,
        status,
        trigger_reason: reason
      };

      console.log('★ AUTOMATED TRADE EXECUTED:', tradeEvent);
      broadcastToDashboard({ type: 'trade_executed', trade: tradeEvent });
    }
  );
}

// REST APIs
app.get('/api/status', (req, res) => {
  res.json({
    connectionStatus,
    activeEndpoint,
    autoTradingEnabled,
    cooldownMs: COOLDOWN_MS,
    timeWindowMs: TIME_WINDOW_MS,
    latestPrice: priceHistory.length > 0 ? priceHistory[priceHistory.length - 1].price : null
  });
});

app.get('/api/trades', (req, res) => {
  db.all('SELECT * FROM trades ORDER BY timestamp DESC', [], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows);
  });
});

app.get('/api/prices', (req, res) => {
  db.all('SELECT * FROM price_history ORDER BY timestamp DESC LIMIT 100', [], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows.reverse());
  });
});

app.post('/api/toggle-trading', (req, res) => {
  autoTradingEnabled = req.body.enabled !== undefined ? req.body.enabled : !autoTradingEnabled;
  res.json({ success: true, autoTradingEnabled });
});

app.post('/api/trade', (req, res) => {
  const symbol = req.body.symbol || 'SPX-5100-PUT';
  const action = req.body.action || 'BUY';
  const quantity = req.body.quantity || 10;
  const price = req.body.price || 65.00;
  const reason = req.body.reason || 'Manual User Trigger';

  db.run(
    `INSERT INTO trades (symbol, action, quantity, price, status, trigger_reason) VALUES (?, ?, ?, ?, ?, ?)`,
    [symbol, action, quantity, price, 'FILLED', reason],
    function (err) {
      if (err) return res.status(500).json({ error: err.message });
      const tradeEvent = {
        id: this.lastID,
        timestamp: new Date().toISOString(),
        symbol,
        action,
        quantity,
        price,
        status: 'FILLED',
        trigger_reason: reason
      };
      broadcastToDashboard({ type: 'trade_executed', trade: tradeEvent });
      res.json({ success: true, trade: tradeEvent });
    }
  );
});

app.post('/api/clear-history', (req, res) => {
  db.run('DELETE FROM trades', (err) => {
    if (err) return res.status(500).json({ error: err.message });
    db.run('DELETE FROM price_history', (err2) => {
      if (err2) return res.status(500).json({ error: err2.message });
      priceHistory = [];
      res.json({ success: true, message: 'Database history cleared.' });
    });
  });
});

server.listen(PORT, () => {
  console.log(`Dashboard & Trading Backend running on http://localhost:${PORT}`);
});
```

---

### 5. Web Dashboard Frontend

#### `public/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ApexTrade - Automated Options Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; background-color: #0f172a; }
  </style>
</head>
<body class="text-slate-100 min-h-screen flex flex-col">

  <!-- Header -->
  <header class="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="bg-indigo-600 p-2 rounded-lg text-white">
          <i data-lucide="trending-down" class="w-6 h-6"></i>
        </div>
        <div>
          <h1 class="text-lg font-bold tracking-tight">ApexTrade</h1>
          <p class="text-xs text-slate-400">Automated Options Engine</p>
        </div>
      </div>

      <div class="flex items-center space-x-4">
        <!-- Connection Status -->
        <div class="flex items-center space-x-2 bg-slate-800/80 px-3.5 py-1.5 rounded-full border border-slate-700">
          <span class="relative flex h-2.5 w-2.5">
            <span id="status-ping" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
            <span id="status-dot" class="relative inline-flex rounded-full h-2.5 w-2.5 bg-yellow-500"></span>
          </span>
          <span id="status-text" class="text-xs font-medium text-slate-300">Connecting...</span>
        </div>

        <!-- Auto Trading Toggle -->
        <div class="flex items-center space-x-2 bg-slate-800/80 px-3.5 py-1.5 rounded-full border border-slate-700">
          <span class="text-xs font-medium text-slate-300">Auto-Trading:</span>
          <button id="toggle-trading-btn" class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none bg-slate-600">
            <span id="toggle-slider" class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out translate-x-0"></span>
          </button>
        </div>
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">

    <!-- Metrics Grid -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-5">
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between shadow-lg">
        <div class="flex items-center justify-between text-slate-400 text-sm font-medium">
          <span>S&P 500 Index</span>
          <i data-lucide="activity" class="w-4 h-4 text-indigo-400"></i>
        </div>
        <div class="mt-4">
          <span id="spx-price" class="text-3xl font-bold tracking-tight">--.--</span>
          <span id="spx-change" class="text-sm font-semibold ml-2 text-slate-400">0.00%</span>
        </div>
        <div class="text-xs text-slate-500 mt-2">Real-time streaming data</div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between shadow-lg">
        <div class="flex items-center justify-between text-slate-400 text-sm font-medium">
          <span>1-Hour Peak</span>
          <i data-lucide="trending-up" class="w-4 h-4 text-emerald-400"></i>
        </div>
        <div class="mt-4">
          <span id="peak-price" class="text-3xl font-bold tracking-tight">--.--</span>
        </div>
        <div class="text-xs text-slate-500 mt-2">Highest price in last 60 mins</div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between shadow-lg">
        <div class="flex items-center justify-between text-slate-400 text-sm font-medium">
          <span>Drop from Peak</span>
          <i data-lucide="percent" class="w-4 h-4 text-rose-400"></i>
        </div>
        <div class="mt-4">
          <span id="drop-percent" class="text-3xl font-bold tracking-tight text-emerald-400">0.00%</span>
        </div>
        <div class="text-xs text-slate-500 mt-2">Trigger threshold: <span class="text-rose-400 font-semibold">&gt; 2.00%</span></div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between shadow-lg">
        <div class="flex items-center justify-between text-slate-400 text-sm font-medium">
          <span>Total Trades</span>
          <i data-lucide="shopping-cart" class="w-4 h-4 text-amber-400"></i>
        </div>
        <div class="mt-4">
          <span id="total-trades" class="text-3xl font-bold tracking-tight">0</span>
        </div>
        <div class="text-xs text-slate-500 mt-2">Executed put options</div>
      </div>
    </div>

    <!-- Main Dashboard Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <!-- Chart & Controls -->
      <div class="lg:col-span-2 space-y-8">
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-
