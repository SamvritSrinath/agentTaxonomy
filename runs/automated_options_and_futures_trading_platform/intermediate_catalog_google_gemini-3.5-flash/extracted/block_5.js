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
