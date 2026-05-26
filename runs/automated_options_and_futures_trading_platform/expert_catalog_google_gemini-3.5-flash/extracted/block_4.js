/**
 * CircuitBreaker safety mechanism.
 * Halts polling if simulated account balance drops below $10,000.
 */
class CircuitBreaker {
  constructor(initialBalance = 12000) {
    this.balance = initialBalance;
    this.tripped = false;
    this.checkLimit();
  }

  updateBalance(newBalance) {
    this.balance = newBalance;
    this.checkLimit();
  }

  checkLimit() {
    if (this.balance < 10000) {
      this.tripped = true;
    } else {
      this.tripped = false;
    }
  }

  isTripped() {
    return this.tripped;
  }

  getBalance() {
    return this.balance;
  }
}

module.exports = CircuitBreaker;
