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
