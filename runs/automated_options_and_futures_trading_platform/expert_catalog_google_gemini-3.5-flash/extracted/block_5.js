require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const CircuitBreaker = require('./circuitBreaker');

const app = express();
const PORT = process.env.PORT || 3000;
const PAPER_API_URL = process.env.PAPER_API_URL || 'https://paper-api.brokerage.com';

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../public')));

// Initialize Circuit Breaker with $12,000 simulated balance
const circuitBreaker = new CircuitBreaker(12000);

// Mock index fund data
let indexFundData = {
  SPY: { price: 500.00, change: 0.5 },
  QQQ: { price: 440.00, change: -0.2 },
  IWM: { price: 200.00, change: 1.1 }
};

/**
 * Polling function that simulates fetching index fund data.
 * Respects the Circuit Breaker safety state.
 */
async function pollIndexFundData() {
  if (circuitBreaker.isTripped()) {
    console.warn(`[CIRCUIT BREAKER] Polling halted. Balance ($${circuitBreaker.getBalance()}) is below safety threshold ($10,000).`);
    return;
  }

  console.log(`[POLLER] Polling index fund data from ${PAPER_API_URL}...`);
  try {
    // Simulate slight price fluctuations
    indexFundData.SPY.price += (Math.random() - 0.5) * 2;
    indexFundData.QQQ.price += (Math.random() - 0.5) * 2;
    indexFundData.IWM.price += (Math.random() - 0.5) * 1;

    // Format decimals
    indexFundData.SPY.price = parseFloat(indexFundData.SPY.price.toFixed(2));
    indexFundData.QQQ.price = parseFloat(indexFundData.QQQ.price.toFixed(2));
    indexFundData.IWM.price = parseFloat(indexFundData.IWM.price.toFixed(2));

    console.log(`[POLLER] Updated prices: SPY=$${indexFundData.SPY.price}, QQQ=$${indexFundData.QQQ.price}`);
  } catch (error) {
    console.error('[POLLER] Error fetching data:', error.message);
  }
}

// Start polling every 5 seconds
const pollingInterval = setInterval(pollIndexFundData, 5000);

// API Endpoints
app.get('/api/status', (req, res) => {
  res.json({
    balance: circuitBreaker.getBalance(),
    isTripped: circuitBreaker.isTripped(),
    paperApiUrl: PAPER_API_URL,
    indexFundData
  });
});

app.post('/api/balance', (req, res) => {
  const { balance } = req.body;
  if (typeof balance !== 'number') {
    return res.status(400).json({ error: 'Balance must be a number' });
  }
  circuitBreaker.updateBalance(balance);
  res.json({
    message: 'Balance updated successfully',
    balance: circuitBreaker.getBalance(),
    isTripped: circuitBreaker.isTripped()
  });
});

/**
 * Mock Trade Execution Endpoint.
 * STRICTLY logs the payload and returns 200 OK.
 * Under no circumstances is an HTTP POST request to the brokerage executed.
 */
app.post('/api/trade', (req, res) => {
  const tradePayload = req.body;

  console.log('==================================================');
  console.log('[MOCK TRADE EXECUTION] Intended Trade Payload:');
  console.log(JSON.stringify(tradePayload, null, 2));
  console.log('==================================================');

  res.status(200).json({
    status: 'success',
    message: 'Trade logged successfully (MOCK MODE - NO REAL OR PAPER ORDER PLACED)',
    payload: tradePayload
  });
});

module.exports = { app, circuitBreaker, pollingInterval };

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
    console.log(`Paper Trading Endpoint: ${PAPER_API_URL}`);
  });
}
