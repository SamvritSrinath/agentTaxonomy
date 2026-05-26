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
