import requests

def validate_ticker(ticker):
    url = f"https://stockprices.dev/api/stocks/{ticker}"
    results = requests.get(url)
    if results.status_code == 200:
        return (True)
    elif results.status_code == 404:
        return (False, "Invalid Ticker.")
    return (False, "API ISSUE")

def get_current_price(ticker):
    # print("called")
    url = f"https://stockprices.dev/api/stocks/{ticker}"
    results = requests.get(url)
    if results.status_code != 200:
        return None
    stock_data = results.json()
    # print(type(stock_data), stock_data)
    return stock_data['Price']
