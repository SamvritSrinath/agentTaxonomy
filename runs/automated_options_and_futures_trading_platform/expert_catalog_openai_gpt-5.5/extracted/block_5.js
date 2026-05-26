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
