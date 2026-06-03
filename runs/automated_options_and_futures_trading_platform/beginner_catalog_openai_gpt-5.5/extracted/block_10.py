import pytest

from app.paper_store import PaperOrderStore


def test_create_paper_order():
    store = PaperOrderStore()

    order = store.create(
        underlying_symbol="SPY",
        option_symbol="SPY 20250117 C 500",
        expiry="20250117",
        strike=500,
        right="C",
        quantity=1,
        estimated_premium=2.5,
        max_debit=300,
        reason="test",
    )

    assert order.status == "PAPER_FILLED"
    assert order.estimated_total_debit == 250
    assert len(store.list()) == 1


def test_rejects_order_above_max_debit():
    store = PaperOrderStore()

    with pytest.raises(ValueError):
        store.create(
            underlying_symbol="SPY",
            option_symbol="SPY 20250117 C 500",
            expiry="20250117",
            strike=500,
            right="C",
            quantity=2,
            estimated_premium=2.5,
            max_debit=300,
            reason="test",
        )
