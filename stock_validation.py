import requests

def validate_ticker(ticker):
    return (True, "_")
    # url = f"https://stockprices.dev/api/stocks/{ticker}"
    # results = requests.get(url)
    # if results.status_code == 200:
    #     return (True, "_")
    # elif results.status_code == 404:
    #     return (False, "Invalid Ticker.")
    # return (False, "API ISSUE")

def get_current_price(ticker):
    return 14
    # # print("called")
    # url = f"https://stockprices.dev/api/stocks/{ticker}"
    # results = requests.get(url)
    # if results.status_code != 200:
    #     return None
    # stock_data = results.json()
    # # print(type(stock_data), stock_data)
    # return stock_data['Price']
