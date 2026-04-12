from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone
import sqlalchemy.orm as so
from werkzeug.security import generate_password_hash, check_password_hash



db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(128), unique=True)
    password_hash = db.Column(db.String(256))
    holdings: so.Mapped[list['Holding']] = db.relationship("Holding", back_populates='user', cascade='all, delete-orphan')
    # portfolio_history: so.Mapped['PortfolioHistory'] = db.relationship("PortfolioHistory", back_populates='user')

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
    
class Holding(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id: so.Mapped[int] = db.Column(db.Integer, db.ForeignKey("user.id", ondelete='CASCADE'), nullable=False, index=True)
    user: so.Mapped[User] = db.relationship("User", back_populates='holdings')

    stock_id: so.Mapped[int] = db.Column(db.Integer, db.ForeignKey("stock.id", ondelete='CASCADE'), nullable=False, index=True)
    stock: so.Mapped['Stock'] = db.relationship("Stock", back_populates='holding')

    shares_owned = db.Column(db.Float, default=0)
    average_price = db.Column(db.Float, default=0)
    total_invested = db.Column(db.Float, default=0)

    __table_args__ = (db.UniqueConstraint('user_id', 'stock_id', name='uq_holding_user_stock'),)

    transactions: so.Mapped[list['Transaction']] = db.relationship("Transaction", back_populates='holding', cascade='all, delete-orphan', order_by='Transaction.time')

    @property
    def current_value(self):
        if self.stock.current_price is not None:
            return self.shares_owned * self.stock.current_price
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

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(25), nullable=False) 
    current_price = db.Column(db.Float)
    last_updated = db.Column(db.DateTime)
    holding: so.Mapped[list['Holding']] = db.relationship("Holding", back_populates='stock', cascade='all, delete-orphan')

    def __repr__(self):
        return f"Stock {self.id}: {self.ticker}"
    
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.Enum("BUY", "SELL", name="transaction_type"), nullable=False)
    shares = db.Column(db.Float, nullable=False)
    price_per_share = db.Column(db.Float, nullable=False)
    time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    holding_id: so.Mapped[int] = db.Column(db.Integer, db.ForeignKey("holding.id", ondelete='CASCADE'), nullable=False, index=True)
    holding: so.Mapped['Holding'] = db.relationship("Holding", back_populates='transactions')
   
class StockHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    __table_args__ = (db.UniqueConstraint('ticker', 'date', name='uq_stockhistory_ticker_date'),)
    open_price = db.Column(db.Float)
    high_price = db.Column(db.Float)
    low_price = db.Column(db.Float)
    close_price = db.Column(db.Float)
    volume = db.Column(db.Integer)

    def __repr__(self):
        return f"StockHistory {self.ticker} {self.date}"

class PortfolioHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id: so.Mapped[int] = db.Column(db.Integer, db.ForeignKey("user.id", ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    total_value = db.Column(db.Float, nullable=False)