import pytest
from portfolio import Portfolio, Position  # Assuming the code is saved in portfolio.py

# Test cases for Position
def test_position_initialization():
    pos = Position(symbol="AAPL", initial_price=150.0, initial_amount=10)
    assert pos.symbol == "AAPL"
    assert pos.buy_price == 150.0
    assert pos.amount == 10
    assert pos.last_update_price == 150.0

def test_position_update():
    pos = Position(symbol="AAPL", initial_price=150.0, initial_amount=10)
    pos.update_position(new_price=160.0)
    assert pos.absolute_change_since_start == 100.0
    assert pos.relative_change_since_start == pytest.approx(0.0666, 0.01)
    assert pos.absolute_change_since_update == 100.0
    assert pos.relative_change_since_update == pytest.approx(0.0666, 0.01)

def test_position_buy():
    pos = Position(symbol="AAPL", initial_price=150.0, initial_amount=10)
    pos.buy(price=160.0, amount=5)
    assert pos.amount == 15
    assert pos.buy_price == pytest.approx((150 * 10 + 160 * 5) / 15, 0.001)

def test_position_sell():
    pos = Position(symbol="AAPL", initial_price=150.0, initial_amount=10)
    pos.sell(price=160.0, amount=5)
    assert pos.amount == 5
    with pytest.raises(ValueError):
        pos.sell(price=160.0, amount=10)  # Selling more than available

# Test cases for Portfolio
def test_portfolio_initialization():
    portfolio = Portfolio(initial_cash=10000)
    assert portfolio.total_cash == 10000
    assert portfolio.get_portfolio_value() == 10000
    assert portfolio.show_positions() == []
    assert portfolio.show_transaction_history() == []

def test_portfolio_add_symbol():
    portfolio = Portfolio(initial_cash=10000)
    portfolio.buy("AAPL", price=150.0, amount=10)
    assert portfolio.total_cash == 8500.0
    assert len(portfolio.positions) == 1
    assert portfolio.positions["AAPL"].amount == 10
    assert portfolio.positions["AAPL"].buy_price == 150.0

def test_portfolio_remove_symbol():
    portfolio = Portfolio(initial_cash=10000)
    portfolio.buy("AAPL", price=150.0, amount=10)
    portfolio.sell("AAPL", price=160.0, amount=5)
    assert portfolio.total_cash == 9300.0
    assert portfolio.positions["AAPL"].amount == 5
    with pytest.raises(ValueError):
        portfolio.sell("AAPL", price=160.0, amount=10)  # Selling more than available

def test_portfolio_update(monkeypatch):
    monkeypatch.setattr("market.get_price_for_symbol", lambda symbol: 200)
    portfolio = Portfolio(initial_cash=10000)
    portfolio.buy("AAPL", price=150.0, amount=10)
    portfolio.buy("GOOGL", price=2800.0, amount=2)
    portfolio.update()
    metrics = portfolio.show_metrics()
    assert metrics["absolute_change_since_update"] == pytest.approx(500 - 5200, 0.001)
    assert metrics["relative_change_since_update"] < 0

def test_portfolio_transaction_history():
    portfolio = Portfolio(initial_cash=10000)
    portfolio.buy("AAPL", price=150.0, amount=10)
    portfolio.sell("AAPL", price=160.0, amount=5)
    history = portfolio.show_transaction_history()
    assert len(history) == 2
    assert history[0]["type"] == "buy"
    assert history[1]["type"] == "sell"
