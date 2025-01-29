import market
import os
import json
from datetime import datetime
from pydantic_core import core_schema

class Transaction:
    def __init__(self, transaction_type: str, symbol: str, price: float, quantity: float, cash_after_transaction: float, comment: str = ""):
        """Represents a single transaction."""
        self.time = datetime.now()
        self.transaction_type = transaction_type
        self.symbol = symbol
        self.price = price
        self.quantity = quantity
        self.total_value = price * quantity
        self.cash_after_transaction = cash_after_transaction
        self.comment = comment
        
    def to_dict(self, formatted: bool = True):
        """Returns the transaction details as a dictionary."""
        return {
            'time': self.time.strftime('%Y-%m-%d %H:%M:%S') if formatted else self.time,
            'type': self.transaction_type,
            'symbol': self.symbol,
            'price': self.price,
            'quantity': self.quantity,
            'total_value': self.total_value,
            'cash_after_transaction': self.cash_after_transaction,
            'comment': self.comment
        }


    def __str__(self):
        """Return a human-readable string representation of the transaction."""
        return f"Time: {self.time.strftime('%Y-%m-%d %H:%M:%S')} | Action: {self.transaction_type.upper()} {self.symbol} @ {self.price:.2f} EUR x {self.quantity:.4f} shares | Cash after: {self.cash_after_transaction:.2f} | Comment: {self.comment})"


class TransactionHistory:
    def __init__(self):
        self.history = []

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
            transaction = Transaction(
                transaction_type=kwargs.get('transaction_type'),
                symbol=kwargs.get('symbol'),
                price=kwargs.get('price'),
                quantity=kwargs.get('quantity'),
                cash_after_transaction=kwargs.get('cash_after_transaction'),
                comment=kwargs.get('comment', "")
            )
        
        self.history.append(transaction)
        return transaction

    def get_history(self, formatted: bool = True):
        """Returns the transaction history. Optionally formats the timestamps."""
        return [tx.to_dict(formatted) for tx in self.history]

    def clear(self):
        """Clears the transaction history."""
        self.history = []

    def __str__(self):
        """Returns a formatted string representation of all transactions."""
        if not self.history:
            return "No transactions recorded."
        return "\n".join(str(txn) for txn in self.history)
    

class Position:
    def __init__(self, symbol: str, price: float, quantity: float):
        self.symbol = symbol
        self.buy_price = price
        self.quantity = quantity
        self.position_value = price * quantity
        self.last_update_price = price
        self.absolute_change_since_start = 0.0
        self.relative_change_since_start = 0.0
        self.absolute_change_since_update = 0.0
        self.relative_change_since_update = 0.0
        self.last_update_time = datetime.now()

    def update_position(self, new_price: float):
        """Update position values based on the new market price."""
        self.absolute_change_since_start = (new_price - self.buy_price) * self.quantity
        self.relative_change_since_start = ((new_price - self.buy_price) / self.buy_price)
        self.absolute_change_since_update = (new_price - self.last_update_price) * self.quantity
        self.relative_change_since_update = ((new_price - self.last_update_price) / self.last_update_price)
        self.last_update_price = new_price
        self.position_value = self.last_update_price * self.quantity
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
        if self.quantity == 0:
            self.buy_price = 0  # Reset if no quantity remain
        self.update_position(price)
        
    def __str__(self):
        """Return a human-readable string representation of the position."""
        return (f"Symbol: {self.symbol}, Total Value: {self.position_value:.2f}, "
                f"Quantity: {self.quantity:.2f}, Last Update Price: {self.last_update_price:.2f}, "
                f"Buy-in Price: {self.buy_price:.2f}, "
                f"Abs Change Since Start: {self.absolute_change_since_start:.2f}, "
                f"Rel Change Since Start: {self.relative_change_since_start:.2%}, ")


class Portfolio:
    def __init__(self, initial_cash: float):
        self.initial_cash = initial_cash
        self.total_cash = initial_cash
        self.positions = {}
        self.transaction_history = TransactionHistory()
        self.portfolio_value = initial_cash
        self.absolute_change_since_start = 0.0
        self.relative_change_since_start = 0.0
        self.absolute_change_since_update = 0.0
        self.relative_change_since_update = 0.0
        self.last_update_time = datetime.now()
    
    def __get_pydantic_core_schema__(self, handler):
        """
        Define how Pydantic should serialize and validate this class.
        """
        return core_schema.typed_dict(
            {
                "initial_cash": core_schema.float_schema(),
                "total_cash": core_schema.float_schema(),
                "positions": core_schema.dict_schema(),
                "portfolio_value": core_schema.float_schema(),
                "absolute_change_since_start": core_schema.float_schema(),
                "relative_change_since_start": core_schema.float_schema(),
                "absolute_change_since_update": core_schema.float_schema(),
                "relative_change_since_update": core_schema.float_schema(),
                "last_update_time": core_schema.str_schema(),  # Store as ISO format string
            }
        )
    
    def buy(self, symbol: str, investment_amount: float) -> dict:
        """Invest a specified amount into a position, automatically determining the price and quantity."""
        comment = ""
        price = market.get_price_for_symbol(symbol)
        if price is None or price <= 0 or not isinstance(price, (int, float)):
            raise ValueError("Invalid price retrieved for the symbol.")
        shares_to_buy = investment_amount / price
        if investment_amount > self.total_cash:
            raise ValueError("Not enough cash to complete the transaction.")
        self.total_cash -= investment_amount
        if symbol in self.positions:
            self.positions[symbol].buy(price, shares_to_buy)
        else:
            self.positions[symbol] = Position(symbol, price, shares_to_buy)
            comment = "position opened"
        
        return self.transaction_history.log(transaction_type='BUY',
                                            symbol = symbol,
                                            price = price,
                                            quantity = shares_to_buy, 
                                            cash_after_transaction = self.total_cash,
                                            comment = comment)

    def sell(self, symbol: str, liquidation_amount: float) -> dict:
        """Sell a specified cash value from an existing position, automatically determining the price and quantity."""
        comment = ""
        if symbol not in self.positions:
            raise ValueError(f"No position found for symbol {symbol}.")
        
        price = market.get_price_for_symbol(symbol)
        if price is None or price <= 0 or not isinstance(price, (int, float)):
            raise ValueError("Invalid price retrieved for the symbol.")
        
        position = self.positions[symbol]
        shares_to_sell = liquidation_amount / price
        if shares_to_sell > position.quantity:
            raise ValueError("Not enough quantity to complete the transaction.")
        
        position.sell(price, shares_to_sell)
        self.total_cash += liquidation_amount
        
        if position.quantity * price < 1:
            del self.positions[symbol]  # Remove the position if it is fully sold
            self.total_cash += position.quantity * price
            comment = "position closed"
            shares_to_sell = position.quantity

        return self.transaction_history.log(transaction_type='SELL',
                                            symbol = symbol,
                                            price = price,
                                            quantity = shares_to_sell, 
                                            cash_after_transaction = self.total_cash,
                                            comment = comment)

    def close_position(self, symbol):
        """Sells all shares of a position at the current market price."""
        if symbol not in self.positions:
            raise ValueError(f"No position found for symbol {symbol}.")

        quantity = self.positions[symbol].quantity
        price = market.get_price_for_symbol(symbol)
        
        self.total_cash += price * quantity
        del self.positions[symbol]
        
        return self.transaction_history.log(transaction_type='SELL',
                                    symbol = symbol,
                                    price = price,
                                    quantity = quantity, 
                                    cash_after_transaction = self.total_cash,
                                    comment = "position closed")

    def update(self):
        """Update all positions and portfolio-level metrics."""
        for position in self.positions.values():
            position.update_position(market.get_price_for_symbol(position.symbol))  # Assuming prices are updated externally
        new_portfolio_value = self._get_portfolio_value()
        if self.portfolio_value > 0:
            self.absolute_change_since_update = new_portfolio_value - self.portfolio_value
            self.relative_change_since_update = ((new_portfolio_value - self.portfolio_value) / self.portfolio_value)
            self.absolute_change_since_start = new_portfolio_value - self.initial_cash
            self.relative_change_since_start = (new_portfolio_value - self.initial_cash) / self.initial_cash
        else:
            self.absolute_change_since_update = 0.0
            self.relative_change_since_update = 0.0
        self.portfolio_value = new_portfolio_value
        self.last_update_time = datetime.now()

    def _get_portfolio_value(self) -> float:
        """Calculate the total portfolio value."""
        total_investment_value = sum(pos.position_value for pos in self.positions.values())
        return total_investment_value + self.total_cash

    def positions_to_str(self):
        """Return a summary of all current positions."""
        return "\n".join(str(position) for position in self.positions.values())

    def metrics_to_dict(self):
        """Return portfolio-level metrics."""
        return {
            "total_portfolio_value": self.portfolio_value,
            "total_cash": self.total_cash,
            "invested_amount": self.portfolio_value - self.total_cash,
            "absolute_change_since_start": self.absolute_change_since_start,
            "relative_change_since_start": self.relative_change_since_start,
            "absolute_change_since_update": self.absolute_change_since_update,
            "relative_change_since_update": self.relative_change_since_update,
            "last_update_time": self.last_update_time,
        }

    def show_transaction_history(self):
        """Return the transaction history."""
        return self.transaction_history.get_history(formatted=True)

    def __str__(self):
        """Return a human-readable string representation of the portfolio."""
        metrics = self.metrics_to_dict()
        header = (f"Portfolio Summary - {metrics['last_update_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Total Value: {metrics['total_portfolio_value']:.2f}\n"
                f"Total Cash: {metrics['total_cash']:.2f}\n"
                f"Invested Amount: {metrics['invested_amount']:.2f}\n"
                f"Absolute Change Since Start: {metrics['absolute_change_since_start']:.2f}\n"
                f"Relative Change Since Start: {metrics['relative_change_since_start']:.2%}\n"
                f"{'-' * 50}\n"
                f"Positions:\n")

        positions_str = "\n".join(str(position) for position in self.positions.values())

        return header + (positions_str if positions_str else "No active positions")

    
    def to_json(self, filepath: str = None) -> str:
        """
        Serialize the portfolio state to JSON format.
        If filepath is provided, saves to file. Otherwise returns JSON string.
        """
        def convert_transaction(tx):
            """Helper to convert transaction datetime to string"""
            tx_dict = tx.copy()
            if isinstance(tx_dict['time'], datetime):
                tx_dict['time'] = tx_dict['time'].isoformat()
            return tx_dict

        portfolio_state = {
            'initial_cash': self.initial_cash,
            'total_cash': self.total_cash,
            'portfolio_value': self.portfolio_value,
            'absolute_change_since_start': self.absolute_change_since_start,
            'relative_change_since_start': self.relative_change_since_start,
            'absolute_change_since_update': self.absolute_change_since_update,
            'relative_change_since_update': self.relative_change_since_update,
            'last_update_time': self.last_update_time.isoformat(),
            'positions': {
                symbol: {
                    'symbol': pos.symbol,
                    'buy_price': pos.buy_price,
                    'quantity': pos.quantity,
                    'position_value': pos.position_value,
                    'last_update_price': pos.last_update_price,
                    'absolute_change_since_start': pos.absolute_change_since_start,
                    'relative_change_since_start': pos.relative_change_since_start,
                    'absolute_change_since_update': pos.absolute_change_since_update,
                    'relative_change_since_update': pos.relative_change_since_update,
                    'last_update_time': pos.last_update_time.isoformat()
                } for symbol, pos in self.positions.items()
            },
            'transaction_history': [convert_transaction(tx) for tx in self.transaction_history.get_history(formatted=False)]
        }
        
        if filepath:
            with open(filepath, 'w') as f:
                json.dump(portfolio_state, f, indent=2)
            return filepath
        
        return json.dumps(portfolio_state, indent=2)
    
    @classmethod
    def from_json(cls, json_input: str) -> 'Portfolio':
        """
        Create a Portfolio instance from JSON data.
        json_input can be either a file path or a JSON string.
        """
        # Check if input is a filepath (ends with .json)
        if isinstance(json_input, str) and json_input.lower().endswith('.json'):
            if not os.path.exists(json_input):
                raise FileNotFoundError(f"JSON file not found: {json_input}")
            with open(json_input, 'r') as f:
                data = json.load(f)
        else:
            # Treat as JSON string
            try:
                data = json.loads(json_input)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON string provided: {str(e)}")
        
        # Create new portfolio instance
        portfolio = cls(data['initial_cash'])
        
        # Restore portfolio state
        portfolio.total_cash = data['total_cash']
        portfolio.portfolio_value = data['portfolio_value']
        portfolio.absolute_change_since_start = data['absolute_change_since_start']
        portfolio.relative_change_since_start = data['relative_change_since_start']
        portfolio.absolute_change_since_update = data['absolute_change_since_update']
        portfolio.relative_change_since_update = data['relative_change_since_update']
        portfolio.last_update_time = datetime.fromisoformat(data['last_update_time'])
        
        # Restore positions
        for symbol, pos_data in data['positions'].items():
            position = Position(
                symbol=pos_data['symbol'],
                price=pos_data['buy_price'],
                quantity=pos_data['quantity']
            )
            position.position_value = pos_data['position_value']
            position.last_update_price = pos_data['last_update_price']
            position.absolute_change_since_start = pos_data['absolute_change_since_start']
            position.relative_change_since_start = pos_data['relative_change_since_start']
            position.absolute_change_since_update = pos_data['absolute_change_since_update']
            position.relative_change_since_update = pos_data['relative_change_since_update']
            position.last_update_time = datetime.fromisoformat(pos_data['last_update_time'])
            portfolio.positions[symbol] = position
        
        # Restore transaction history
        for tx in data['transaction_history']:
            # Convert ISO format string back to datetime before creating transaction
            tx_time = datetime.fromisoformat(tx['time'])
            portfolio.transaction_history.log(
                transaction_type=tx['type'],
                symbol=tx['symbol'],
                price=tx['price'],
                quantity=tx['quantity'],
                cash_after_transaction=tx['cash_after_transaction'],
                comment=tx['comment']
            )
            # Update the transaction time to match the original
            portfolio.transaction_history.history[-1].time = tx_time
        
        return portfolio