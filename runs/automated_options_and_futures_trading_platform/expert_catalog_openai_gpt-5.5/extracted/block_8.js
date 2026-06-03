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
