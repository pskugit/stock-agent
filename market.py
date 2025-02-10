import yfinance as yf

class Sensors:
    def __init__(self, tickers):
        self.tickers = tickers  # List of stock symbols to monitor

    def get_stock_data(self):
        data = {}
        for ticker in self.tickers:
            stock = yf.Ticker(ticker)
            info = stock.history(period="1d")  # Get today's data
            if not info.empty:
                latest = info.iloc[-1]
                data[ticker] = {
                    "price": latest["Close"],
                    "volume": latest["Volume"]
                }
        return data

def get_price_for_symbol(symbol: str):
    print(f"API CALL: yfinance - requesting price for {symbol}")
    stock = yf.Ticker(symbol)
    try:
        price = stock.info['currentPrice']
    except KeyError:
        return None
    if price <= 0:
        raise ValueError(f"Negative market price {price} for symbol {symbol}.")
    print(f"Price is {price}")
    return price

"""
# Example usage
sensors = Sensors(["AAPL", "GOOGL", "MSFT"])
environment_data = sensors.get_stock_data()
print(environment_data)


apple = yf.Ticker("AAPL")
print(apple)
print(apple.info)

recent_data = yf.download("AAPL", period="5d")
print(recent_data)

data = yf.download("AAPL", start="2020-01-01", end="2021-01-01", auto_adjust=True)
print(data['Close'])  # This will show the adjusted close prices



screener = yf.Screener(session=None, proxy=None)
screener.set_predefined_body('day_gainers')

result = screener.response
quotes = [quote for quote in result['quotes']]
symbols = [quote['symbol'] for quote in quotes]

print(quotes[0])

"""