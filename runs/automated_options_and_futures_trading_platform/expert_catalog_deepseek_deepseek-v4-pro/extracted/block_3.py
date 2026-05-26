class CircuitBreaker:
    """
    Halts polling when simulated account balance drops below a configurable threshold.
    """
    def __init__(self, threshold: float = 10_000.0, initial_balance: float = 15_000.0):
        self.threshold = threshold
        self.balance = initial_balance
        self._active = True

    @property
    def is_active(self) -> bool:
        """Check if polling is currently allowed."""
        self._active = self.balance >= self.threshold
        return self._active

    def update_balance(self, new_balance: float):
        """Update the simulated balance and re-evaluate circuit state."""
        self.balance = new_balance
        _ = self.is_active  # force re-evaluation
