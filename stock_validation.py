import re
import yfinance as yf

_TICKER_RE = re.compile(r'^[A-Za-z0-9.\-]{1,10}$')

def validate_and_fetch(ticker):
    if not _TICKER_RE.match(ticker):
        return (False, None, "Invalid Ticker")
    try:
        info = yf.Ticker(ticker).info
        price = info.get("regularMarketPrice")
        if price is None or "regularMarketPrice" not in info:
            return (False, None, "Invalid Ticker")
        return (True, price, None)
    except Exception:
        return (False, None, "API error.")

    # return (True, 14, "_") in case of future changes


def get_current_price(ticker):
    try:
        return yf.Ticker(ticker).fast_info["lastPrice"]
    except Exception:
        return None
