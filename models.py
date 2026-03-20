from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from functools import cached_property
from datetime import datetime
import sqlalchemy.orm as so
from stock_validation import get_current_price
from werkzeug.security import generate_password_hash, check_password_hash



db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(128), unique=True)
    password_hash = db.Column(db.String(128))
    stocks: so.Mapped[list['Stock']] = db.relationship("Stock", back_populates='user', cascade='all, delete-orphan')

    @property
    def password(self):
        raise AttributeError('Password is not in correct format')
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f"User {self.username}"

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(25), nullable=False) 
    total_invested = db.Column(db.Integer, default=0) 
    bought_at = db.Column(db.Integer, default=0)
    shares_owned = db.Column(db.Integer, default=0) 
    avg_cost = db.Column(db.Integer, default=0) 
    current_share_price = db.Column(db.Integer, default=0) 
    total_value = db.Column(db.Integer, default=0) 
    gain = db.Column(db.Integer, default=0) 
    gain_percentage = db.Column(db.Integer, default=0) 
    date_bought = db.Column(db.DateTime, default=datetime.now)
    user_id: so.Mapped[int] = db.Column(db.Integer, db.ForeignKey("user.id", ondelete='CASCADE'), nullable=False, index=True)
    user: so.Mapped[User] = db.relationship("User", back_populates='stocks')
    transactions: so.Mapped[list['Transaction']] = db.relationship("Transaction", back_populates='stock', cascade='all, delete-orphan', order_by='Transaction.time')

    @cached_property
    def current_price(self):
        return get_current_price(self.ticker)
    @property
    def shares_owned(self):
        remaining_shares = self._calculate_fifo()
        return sum(shares for shares, _ in remaining_shares)
    @property
    def total_invested(self):
        remaining_shares = self._calculate_fifo()
        return sum(shares * price for shares, price in remaining_shares)
    @property
    def average_cost(self):
        if self.shares_owned == 0:
            return 0
        return self.total_invested / self.shares_owned
    @property
    def current_value(self):
        if self.current_price is not None:
            return self.shares_owned * self.current_price
        return None
    @property
    def unrealized_gain(self):
        if self.current_value is not None:
            return self.current_value - self.total_invested
        return None
    @property
    def potential_gain_percent(self):
        if self.total_invested and self.unrealized_gain is not None:
            return 100 * self.unrealized_gain / self.total_invested
        return None


    def _calculate_fifo(self):
        remaining_shares = []
        for t in self.transactions:
            if t.type == "BUY":
                remaining_shares.append([t.shares, t.price_per_share])
            else:
                shares_to_sell = t.shares
                while shares_to_sell > 0 and remaining_shares:
                    first_in = remaining_shares[0]
                    if first_in[0] > shares_to_sell:
                        first_in[0] -= shares_to_sell
                        shares_to_sell = 0
                    else:
                        shares_to_sell -= first_in[0]
                        remaining_shares.pop(0)
        return remaining_shares

    def __repr__(self):
        return f"Stock {self.id}: {self.ticker}"
    
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.Enum("BUY", "SELL", name="transaction_type"), nullable=False)
    shares = db.Column(db.Float, nullable=False)
    price_per_share = db.Column(db.Float, nullable=False)
    time = db.Column(db.DateTime, default=datetime.now)
    stock_id: so.Mapped[int] = db.Column(db.Integer, db.ForeignKey("stock.id", ondelete='CASCADE'), nullable=False, index=True)
    stock: so.Mapped['Stock'] = db.relationship("Stock", back_populates='transactions')
   
class StockHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False)
    date = db.Column(db.Date, nullable=False)
    open_price = db.Column(db.Float)
    high_price = db.Column(db.Float)
    low_price = db.Column(db.Float)
    close_price = db.Column(db.Float)
    volume = db.Column(db.Integer)

    def __repr__(self):
        return f"StockHistory {self.symbol} {self.date}"
