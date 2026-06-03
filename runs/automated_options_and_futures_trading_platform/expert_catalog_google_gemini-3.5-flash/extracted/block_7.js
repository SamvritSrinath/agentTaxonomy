const CircuitBreaker = require('../src/circuitBreaker');

describe('Circuit Breaker Safety System', () => {
  test('should initialize with correct balance and not be tripped if balance >= 10000', () => {
    const cb = new CircuitBreaker(12000);
    expect(cb.getBalance()).toBe(12000);
    expect(cb.isTripped()).toBe(false);
  });

  test('should trip if initialized with balance below 10000', () => {
    const cb = new CircuitBreaker(9500);
    expect(cb.getBalance()).toBe(9500);
    expect(cb.isTripped()).toBe(true);
  });

  test('should trip when balance is updated to below 10000', () => {
    const cb = new CircuitBreaker(15000);
    expect(cb.isTripped()).toBe(false);

    cb.updateBalance(9999);
    expect(cb.getBalance()).toBe(9999);
    expect(cb.isTripped()).toBe(true);
  });

  test('should reset trip status if balance is updated back to >= 10000', () => {
    const cb = new CircuitBreaker(8000);
    expect(cb.isTripped()).toBe(true);

    cb.updateBalance(10000);
    expect(cb.isTripped()).toBe(false);
  });
});
