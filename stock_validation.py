import requests
import yfinance as yf

def validate_and_fetch(ticker):
    # return (True, 14, "_")


    try:
        info = yf.Ticker(ticker).info
        price = info.get("regularMarketPrice")
        if price is None:
            return (False, None, "Invalid Ticker")
        return (True, price, None)
    except Exception:
        return (False, None, "API error.")



# NOT BEING USED RIGHT NOW
# def get_current_price(ticker):
#     try:
#         info = yf.Ticker(ticker).info
#         return info.get("regularMarketPrice")
#     except Exception:
#         return None
