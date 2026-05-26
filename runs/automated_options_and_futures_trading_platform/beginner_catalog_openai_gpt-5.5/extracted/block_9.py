from app.signal_logic import PriceWindow


def test_drop_signal_triggers_when_price_falls_from_window_high():
    window = PriceWindow()
    window.add(100, ts=1000)
    window.add(102, ts=1010)
    window.add(99, ts=1020)

    signal = window.evaluate(threshold_pct=2.0, lookback_seconds=300, now=1030)

    assert signal.triggered is True
    assert signal.high_price == 102
    assert signal.current_price == 99
    assert signal.drop_pct == 2.9412


def test_drop_signal_does_not_trigger_below_threshold():
    window = PriceWindow()
    window.add(100, ts=1000)
    window.add(101, ts=1010)
    window.add(100.5, ts=1020)

    signal = window.evaluate(threshold_pct=2.0, lookback_seconds=300, now=1030)

    assert signal.triggered is False


def test_old_points_are_trimmed():
    window = PriceWindow()
    window.add(200, ts=1000)
    window.add(100, ts=2000)

    signal = window.evaluate(threshold_pct=10, lookback_seconds=100, now=2000)

    assert signal.high_price == 100
    assert signal.current_price == 100
    assert signal.triggered is False
