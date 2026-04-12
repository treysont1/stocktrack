import re
import yfinance as yf

_TICKER_RE = re.compile(r'^[A-Za-z0-9.\-]{1,10}$')

def validate_and_fetch(ticker):
    if not _TICKER_RE.match(ticker):
        return (False, None, "Invalid Ticker")
    try:
        fast = yf.Ticker(ticker).fast_info
        price = fast["lastPrice"]
        if price is None:
            return (False, None, "Invalid Ticker")
        return (True, price, None)
    except yf.exceptions.YFRateLimitError:
        return (False, None, "YFinance is receiving too many requests, try again shortly.")
    except Exception:
        return (False, None, "API error.")

    # return (True, 14, "_") in case of future changes


def get_current_price(ticker):
    try:
        return yf.Ticker(ticker).fast_info["lastPrice"]
    except Exception:
        return None
