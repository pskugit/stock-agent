import json
import market
from datetime import datetime
from pydantic import BaseModel, Field, computed_field, model_validator
from datetime import datetime
from typing import List, Dict

class Transaction(BaseModel):
    time: datetime = Field(default_factory=datetime.now)
    transaction_type: str
    symbol: str
    price: float = Field(ge=0)  # greater or equal to 0
    quantity: float = Field(ge=0)
    cash_after_transaction: float = Field(ge=0)
    comment: str = ""
    
    @computed_field
    @property
    def total_value(self) -> float:
        return self.price * self.quantity

    def __str__(self):
        """Return a human-readable string representation of the transaction."""
        return (f"Time: {self.time.strftime('%Y-%m-%d %H:%M:%S')} | "
                f"Action: {self.transaction_type.upper()} {self.symbol} @ "
                f"{self.price:.2f} EUR x {self.quantity:.4f} shares = {self.total_value:.2f}| "
                f"Cash after: {self.cash_after_transaction:.2f} | "
                f"Comment: {self.comment})")

class TransactionHistory(BaseModel):
    history: List[Transaction] = Field(default_factory=list)

    def log(self, transaction: Transaction = None, **kwargs):
        """
        Logs a transaction into the history.
        Allows providing either a Transaction object or individual transaction parameters.

        Parameters:
            transaction (Transaction): Optional Transaction object.
            kwargs: Individual transaction fields (type, symbol, price, quantity, cash_after_transaction, comment).
        """
        if transaction is None:
            # Create a transaction object from provided arguments
            transaction = Transaction.model_validate(kwargs)
        
        self.history.append(transaction)
        return transaction
    
    def get_history(self) -> List[Transaction]:
        """Returns the transaction history as a list of Transaction objects."""
        return self.history

    def clear(self):
        """Clears the transaction history."""
        self.history.clear()
    
    def __iter__(self):
        return (txn for txn in self.history)
    
    def __getitem__(self, item):
        return self.history[item]

    def __str__(self):
        """Returns a formatted string representation of all transactions."""
        if not self.history:
            return "No transactions recorded."
        return "\n".join(str(txn) for txn in self.history)
    
    def __len__(self):
        return len(self.history)
    

class Position(BaseModel):
    symbol: str
    buy_price: float = Field(ge=0)
    quantity: float = Field(ge=0)
    last_update_price: float = Field(ge=0)
    last_update_time: datetime = Field(default_factory=datetime.now)

    absolute_change_since_start: float = 0.0
    relative_change_since_start: float = 0.0
    absolute_change_since_update: float = 0.0
    relative_change_since_update: float = 0.0

    @computed_field
    @property
    def position_value(self) -> float:
        return self.last_update_price * self.quantity

    def update_position(self, new_price: float):
        """Update position values based on the new market price."""
        self.absolute_change_since_start = (new_price - self.buy_price) * self.quantity
        self.relative_change_since_start = (new_price - self.buy_price) / self.buy_price
        self.absolute_change_since_update = (new_price - self.last_update_price) * self.quantity
        self.relative_change_since_update = (new_price - self.last_update_price) / self.last_update_price
        self.last_update_price = new_price
        self.last_update_time = datetime.now()

    def buy(self, price: float, quantity: float):
        """Add more to the position, updating the buy price."""
        total_cost = self.buy_price * self.quantity + price * quantity
        self.quantity += quantity
        self.buy_price = total_cost / self.quantity
        self.update_position(price)

    def sell(self, price: float, quantity: float):
        """Sell part of the position."""
        if quantity > self.quantity:
            raise ValueError(f"Cannot sell {quantity} quantity; only {self.quantity} available.")
        self.quantity -= quantity
        self.update_position(price)

    def __str__(self):
        """Return a human-readable string representation of the position."""
        return (f"Symbol: {self.symbol}, Total Value: {self.position_value:.2f}, "
                f"Quantity: {self.quantity:.2f}, Last Update Price: {self.last_update_price:.2f}, "
                f"Buy-in Price: {self.buy_price:.2f}, "
                f"Abs Change Since Start: {self.absolute_change_since_start:.2f}, "
                f"Rel Change Since Start: {self.relative_change_since_start:.2%}, ")


class Portfolio(BaseModel):
    initial_cash: float = 0.0
    available_cash: float = 0.0
    positions: Dict[str, Position] = Field(default_factory=dict)
    transaction_history: TransactionHistory = Field(default_factory=TransactionHistory)
    absolute_change_since_start: float = 0.0
    relative_change_since_start: float = 0.0
    absolute_change_since_update: float = 0.0
    relative_change_since_update: float = 0.0
    last_update_time: datetime = Field(default_factory=datetime.now)
    
    @computed_field
    @property
    def portfolio_value(self) -> float:
        """Calculate the total portfolio value."""
        return sum(pos.position_value for pos in self.positions.values()) + self.available_cash

    def load_cash(self, cash_amount):
        self.initial_cash += cash_amount
        self.available_cash += cash_amount
        return self.initial_cash, self.available_cash
        
    def buy(self, symbol: str, buy_value: float) -> dict:
        """Invest a specified amount into a position."""
        comment = ""
        price = market.get_price_for_symbol(symbol)
        if price is None or price <= 0:
            raise ValueError("Invalid price retrieved for the symbol.")
        shares_to_buy = buy_value / price
        if buy_value > self.available_cash:
            raise ValueError("Not enough cash to complete the transaction.")
        self.available_cash -= buy_value
        if symbol in self.positions:
            self.positions[symbol].buy(price, shares_to_buy)
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                buy_price=price,
                quantity=shares_to_buy,
                last_update_price=price
            )
            comment = "position opened"
            
        return self.transaction_history.log(
            transaction=Transaction(
                transaction_type="BUY",
                symbol=symbol,
                price=price,
                quantity=shares_to_buy,
                cash_after_transaction=self.available_cash,
                comment=comment
            )
        )
        
    def sell(self, symbol: str, sell_value: float) -> dict:
        """Sell a specified cash value from an existing position."""
        comment = ""
        if symbol not in self.positions:
            raise ValueError(f"No position found for symbol {symbol}.")
        price = market.get_price_for_symbol(symbol)
        if price is None or price <= 0:
            raise ValueError("Invalid price retrieved for the symbol.")
        position = self.positions[symbol]
        shares_to_sell = sell_value / price
        if round(shares_to_sell, 6) > round(position.quantity, 6):
            raise ValueError("Not enough quantity to complete the transaction.")
        position.sell(price, shares_to_sell)
        self.available_cash += sell_value
        if position.quantity * price < 1:
            shares_to_sell = position.quantity
            sell_value = shares_to_sell * price
            self.available_cash += sell_value
            comment = "position closed"
            del self.positions[symbol]
        return self.transaction_history.log(
                    transaction=Transaction(
                        transaction_type="SELL",
                        symbol=symbol,
                        price=price,
                        quantity=shares_to_sell,
                        cash_after_transaction=self.available_cash,
                        comment=comment
                    )
                )
        
    def close_position(self, symbol: str) -> dict:
        """Sells all shares of a position at the current market price."""
        if symbol not in self.positions:
            raise ValueError(f"No position found for symbol {symbol}.")
        position = self.positions.pop(symbol)
        price = market.get_price_for_symbol(symbol)
        self.available_cash += price * position.quantity
        return self.transaction_history.log(
                        transaction=Transaction(
                            transaction_type="SELL",
                            symbol=symbol,
                            price=price,
                            quantity=position.quantity,
                            cash_after_transaction=self.available_cash,
                            comment="position_closed"
                        )
                    )
        
    def update(self):
        """Update all positions and portfolio-level metrics."""
        previous_value = self.portfolio_value 
        for position in self.positions.values():
            new_price = market.get_price_for_symbol(position.symbol)
            if new_price and new_price > 0:
                position.update_position(new_price)
            else:
                raise ValueError("Received faulty price data")
        self.absolute_change_since_update = self.portfolio_value - previous_value
        self.relative_change_since_update = (self.portfolio_value - previous_value) / previous_value
        self.absolute_change_since_start = self.portfolio_value - self.initial_cash
        self.relative_change_since_start = (self.portfolio_value - self.initial_cash) / self.initial_cash
        self.last_update_time = datetime.now()

    def positions_to_str(self) -> str:
        """Return a summary of all current positions."""
        if not self.positions:
            return "No active positions."
        return "\n".join(str(position) for position in self.positions.values())
    
    def __str__(self):
        """Return a human-readable summary of the portfolio."""
        summary = (
            f"Portfolio Summary ({self.last_update_time.strftime('%Y-%m-%d %H:%M:%S')}):\n"
            f"Total Value: {self.portfolio_value:.2f}\n"
            f"Cash: {self.available_cash:.2f}\n"
            f"Invested: {self.portfolio_value - self.available_cash:.2f}\n"
            f"Absolute Change Since Start: {self.absolute_change_since_start:.2f}\n"
            f"Relative Change Since Start: {self.relative_change_since_start:.2%}\n"
            f"{'-' * 60}\n"
        )            
        return summary + self.positions_to_str()

    def to_file(self, filename):
        with open(filename, 'w') as f:
            f.write(self.model_dump_json())
    
    @classmethod
    def from_file(cls, filename) -> 'Portfolio':
        with open(filename, 'r') as f:
            pf_dict = json.loads(f.read())
        return cls.model_validate(pf_dict)