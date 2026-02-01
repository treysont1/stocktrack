import requests

def validate_ticker(ticker):
    url = f"https://stockprices.dev/api/stocks/{ticker}"
    results = requests.get(url)
    if results.status_code == 200:
        return True
    elif results.status_code == 404:
        return False
    return None

def get_current_price(ticker):
    url = f"https://stockprices.dev/api/stocks/{ticker}"
    results = requests.get(url)
    stock_data = results.json()
    return stock_data['Price']