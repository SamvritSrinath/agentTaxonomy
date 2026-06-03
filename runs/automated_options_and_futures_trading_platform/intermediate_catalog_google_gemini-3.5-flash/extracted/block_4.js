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
