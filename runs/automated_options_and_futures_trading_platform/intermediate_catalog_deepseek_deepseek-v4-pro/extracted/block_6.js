const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const path = require('path');
const BrokerClient = require('./brokerClient');
const { initDB, saveTrade, getRecentTrades } = require('./db');
const { shouldTrigger } = require('./tradeManager');

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

const db = initDB();

// Serve static dashboard
app.use(express.static(path.join(__dirname, '..', 'frontend', 'public')));

// REST endpoint for initial trade history
app.get('/api/trades', (req, res) => {
  res.json(getRecentTrades(50));
});

// WebSocket for dashboard clients
wss.on('connection', (ws) => {
  console.log('Dashboard client connected');
  ws.on('close', () => console.log('Dashboard client disconnected'));
});

// Broadcast to all dashboard WS clients
function broadcast(type, data) {
  const msg = JSON.stringify({ type, data });
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(msg);
    }
  });
}

// Trade execution (mock)
async function executeBuy(order) {
  // Simulate API call – in reality would POST to brokerage REST endpoint
  const executionPrice = order.price + (Math.random() - 0.5) * 2; // simulated fill
  const trade = {
    timestamp: new Date().toISOString(),
    action: 'BUY',
    symbol: order.symbol,
    quantity: order.quantity,
    price: Math.round(executionPrice * 100) / 100,
    status: 'FILLED'
  };
  saveTrade(trade);
  console.log('✅ Executed trade:', trade);
  broadcast('newTrade', trade);
  return trade;
}

// ---------- Main trading logic ----------
const windowPrices = [];         // {price, timestamp}
let triggerActive = false;      // avoid firing repeatedly in the same event

const broker = new BrokerClient('wss://api.brokerage.com/live', true);

broker.on('price', async (data) => {
  const now = new Date(data.timestamp);
  windowPrices.push({ price: data.price, timestamp: now });

  // Purge entries older than 1 hour
  const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
  while (windowPrices.length > 0 && windowPrices[0].timestamp < oneHourAgo) {
    windowPrices.shift();
  }

  const currentPrice = data.price;
  const exceeded = shouldTrigger(currentPrice, windowPrices);

  // Crossing trigger logic
  if (exceeded && !triggerActive) {
    triggerActive = true;
    console.log('⚠️  Alert: S&P 500 dropped >2% in the last hour!');

    // Auto-execute: buy 10 put options
    await executeBuy({
      symbol: 'SPX PUT',
      quantity: 10,
      price: currentPrice
    });
  } else if (!exceeded) {
    triggerActive = false;
  }

  // Broadcast current price to dashboard
  broadcast('price', { price: currentPrice, timestamp: data.timestamp });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`🚀 Trading dashboard running on http://localhost:${PORT}`);
});
