from datetime import datetime, timedelta
import yfinance as yf
from stock_validation import get_current_price

#Important Functions

def calculate_fifo(holding):
        lots = []
        for t in holding.transactions:
            if t.type == "BUY":
                lots.append((t.shares, t.price_per_share))
            else:
                shares_to_sell = t.shares
                while shares_to_sell > 0 and lots:
                    lot = lots[0]
                    if lot[0] > shares_to_sell:
                        lots[0] = (lot[0] - shares_to_sell, lot[1])
                        shares_to_sell = 0
                    else:
                        shares_to_sell -= lot[0]
                        lots.pop(0)

        holding.shares_owned = sum(lot[0] for lot in lots)
        if holding.shares_owned > 0:
            holding.total_invested = sum(lot[0] * lot[1] for lot in lots)
            holding.average_price = holding.total_invested / holding.shares_owned
        else:
            holding.average_price = 0

# threshold will be datetime.timedelta(days=1)
threshold = timedelta(days=1)
def is_stale(stock):
    if not stock.last_updated:
        return True
    return stock.last_updated.date() + threshold < datetime.now().date()

def update_if_stale(stock):
    if is_stale(stock):
        stock.current_price = get_current_price(stock.ticker)
        stock.last_updated = datetime.now()

# If is stale, call yfinance + update time last updated

def fetch_and_store_history(ticker, db):
    from models import StockHistory

    latest = StockHistory.query.filter_by(ticker=ticker).order_by(StockHistory.date.desc()).first()
    if latest and latest.date == datetime.today():
        return

    history = yf.Ticker(ticker).history(period="1y")
    if history.empty:
        return
    
    StockHistory.query.filter_by(ticker=ticker).delete()

    for row in history.itertuples():
        entry = StockHistory(
            ticker=ticker,
            date = row.Index.date(),
            open_price = row.Open,
            high_price = row.High,
            low_price = row.Low,
            close_price = row.Close,
            volume=int(row.Volume)
        )
        db.session.add(entry)
    db.session.commit()
