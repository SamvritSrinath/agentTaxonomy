import pytest
from backend.circuit_breaker import CircuitBreaker

class TestCircuitBreaker:
    THRESHOLD = 10_000.0

    def test_initial_state_active_when_balance_above_threshold(self):
        cb = CircuitBreaker(threshold=self.THRESHOLD, initial_balance=15_000.0)
        assert cb.is_active is True

    def test_initial_state_inactive_when_balance_equal_threshold(self):
        cb = CircuitBreaker(threshold=self.THRESHOLD, initial_balance=10_000.0)
        assert cb.is_active is True  # >= threshold

    def test_initial_state_inactive_when_balance_below_threshold(self):
        cb = CircuitBreaker(threshold=self.THRESHOLD, initial_balance=9_999.99)
        assert cb.is_active is False

    def test_update_balance_above_threshold_reactivates(self):
        cb = CircuitBreaker(threshold=self.THRESHOLD, initial_balance=8_000.0)
        assert cb.is_active is False
        cb.update_balance(12_000.0)
        assert cb.is_active is True

    def test_update_balance_below_threshold_deactivates(self):
        cb = CircuitBreaker(threshold=self.THRESHOLD, initial_balance=15_000.0)
        assert cb.is_active is True
        cb.update_balance(9_000.0)
        assert cb.is_active is False

    def test_balance_exactly_threshold_remains_active(self):
        cb = CircuitBreaker(threshold=self.THRESHOLD, initial_balance=10_000.0)
        assert cb.is_active is True
        cb.update_balance(10_000.0)
        assert cb.is_active is True
