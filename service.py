from datetime import datetime, timedelta, date, timezone
import yfinance as yf
from stock_validation import get_current_price
from models import StockHistory, PortfolioHistory, Transaction, Holding, Stock
_history_checked_today: set = set()
_history_checked_date: date = date.min
_portfolio_history_checked_today: dict = {}
_portfolio_history_checked_date: date = date.min

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
            holding.total_invested = 0

def buy_stock(user, portfolio, db, order, current_price):
    existing_holding = next((h for h in portfolio if h.stock.ticker == order["ticker"]), None)
    existing_stock = existing_holding.stock if existing_holding else Stock.query.filter_by(ticker=order["ticker"]).first()
    if existing_stock is None:
        existing_stock = Stock(ticker=order["ticker"], current_price=current_price)
        db.session.add(existing_stock)
    if existing_holding is None:
        existing_holding = Holding(user=user, stock=existing_stock)
        db.session.add(existing_holding)
    transaction = Transaction(type="BUY", shares=order["shares"], price_per_share=order["price_bought"], time=order["date"], holding=existing_holding)   
    db.session.add(transaction)
    calculate_fifo(existing_holding)

# threshold will be datetime.timedelta(days=1)
threshold = timedelta(days=1)
def is_stale(stock):
    if not stock.last_updated or stock.current_price is None:
        return True
    return stock.last_updated.date() + threshold <= datetime.now(timezone.utc).date()

def update_if_stale(stock):
    if is_stale(stock):
        price = get_current_price(stock.ticker)
        if price is not None:
            stock.current_price = price
            stock.last_updated = datetime.now(timezone.utc)

# If is stale, call yfinance + update time last updated

def fetch_and_store_history(ticker, db):
    global _history_checked_today, _history_checked_date
    today = date.today()

    if _history_checked_date != today:
        _history_checked_today = set()
        _history_checked_date = today
    
    if ticker in _history_checked_today:
        return

    latest = StockHistory.query.filter_by(ticker=ticker).order_by(StockHistory.date.desc()).first()
    if latest and latest.date == today:
        _history_checked_today.add(ticker)
        return
    
    try:
        if latest:
            history = yf.Ticker(ticker).history(start=latest.date.isoformat())
        else:
            history = yf.Ticker(ticker).history(period="max")
    except Exception:
        return

    if history.empty:
        return

    existing_dates = set()
    if latest:
        existing_dates = {row.date for row in StockHistory.query.filter_by(ticker=ticker).with_entities(StockHistory.date)}
    
    for row in history.itertuples():
        row_date = row.Index.date()
        if row_date in existing_dates:
            continue
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
    _history_checked_today.add(ticker)

def invalidate_portfolio_history(user, db, from_date):
    global _portfolio_history_checked_today
    _portfolio_history_checked_today.pop(user.id, None)
    PortfolioHistory.query.filter_by(user_id=user.id).filter(PortfolioHistory.date >= from_date).delete()

def store_portfolio_history_if_needed(user, holdings, db):
    global _portfolio_history_checked_today, _portfolio_history_checked_date
    today = date.today()

    if _portfolio_history_checked_date != today:
        _portfolio_history_checked_today = {}
        _portfolio_history_checked_date = today

    if user.id in _portfolio_history_checked_today:
        return

    latest = PortfolioHistory.query.filter_by(user_id=user.id).order_by(PortfolioHistory.date.desc()).first()
    if latest and latest.date == today:
        _portfolio_history_checked_today[user.id] = True
        return
    elif latest:
        start_date = latest.date + timedelta(days=1)
    else:
        first_transaction = Transaction.query.join(Holding).filter(Holding.user_id == user.id).order_by(Transaction.time.asc()).first()
        start_date = first_transaction.time.date() if first_transaction else date.today()

    current = start_date

    tickers = [holding.stock.ticker for holding in holdings]
    price_rows = StockHistory.query.filter(StockHistory.ticker.in_(tickers), StockHistory.date >= start_date).all()
    price_map = {(row.ticker, row.date): row.close_price for row in price_rows}

    holding_transactions = {
        holding.id: sorted(holding.transactions, key=lambda t: t.time.date())
        for holding in holdings
    }
    shares_owned = {holding.id: 0 for holding in holdings}
    transaction_index = {holding.id: 0 for holding in holdings}

    # pre-populate shares owned from transactions before start_date
    for holding in holdings:
        for t in holding_transactions[holding.id]:
            if t.time.date() < start_date:
                if t.type == "BUY":
                    shares_owned[holding.id] += t.shares
                else:
                    shares_owned[holding.id] -= t.shares
                transaction_index[holding.id] += 1
            else:
                break

    while current <= date.today():
        total_value = 0
        for holding in holdings:
            while transaction_index[holding.id] < len(holding_transactions[holding.id]) and holding_transactions[holding.id][transaction_index[holding.id]].time.date() <= current:
                transaction = holding_transactions[holding.id][transaction_index[holding.id]]
                if transaction.type == "BUY":
                    shares_owned[holding.id] += transaction.shares
                else:
                    shares_owned[holding.id] -= transaction.shares
                transaction_index[holding.id] += 1
            close_price = price_map.get((holding.stock.ticker, current))
            if close_price:
                total_value += shares_owned[holding.id] * close_price
        
        if total_value > 0:
            entry = PortfolioHistory(user_id=user.id, date=current, total_value=total_value)
            db.session.add(entry)
        current += timedelta(days=1)
    _portfolio_history_checked_today[user.id] = True
