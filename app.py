import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, request, flash, jsonify, url_for
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from forms import LoginForm, RegistrationForm, DeleteAccount
from models import db, User, Holding, Transaction, StockHistory, PortfolioHistory
from service import calculate_fifo, buy_stock, update_if_stale, fetch_and_store_history, store_portfolio_history_if_needed
from stock_validation import validate_and_fetch
from werkzeug.middleware.proxy_fix import ProxyFix
import logging


app = Flask(__name__)
CSRFProtect(app)
login = LoginManager(app)
login.login_view = 'login'
# login_manager.init_app(app)

load_dotenv(dotenv_path=".env")

_db_uri = os.getenv('DATABASE_URL') or os.getenv('SQLALCHEMY_DATABASE_URI')
_secret_key = os.getenv("SECRET_KEY")
_redis_url = os.getenv("REDIS_URL", "memory://")


if _db_uri and _db_uri.startswith("postgres://"):
    _db_uri = _db_uri.replace("postgres://", "postgresql://", 1)
if not _db_uri:
    raise RuntimeError("SQLALCHEMY_DATABASE_URI environment variable is not set.")
if not _secret_key:
    raise RuntimeError("SECRET_KEY environment variable is not set.")

app.config["SQLALCHEMY_DATABASE_URI"] = _db_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
_production = os.getenv("FLASK_ENV") == "production"
app.config["SESSION_COOKIE_SECURE"] = _production
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["REMEMBER_COOKIE_SECURE"] = _production
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["WTF_CSRF_ENABLED"] = False
app.secret_key = _secret_key
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
db.init_app(app)
migrate = Migrate(app, db)
limiter = Limiter(
    app=app, 
    key_func=lambda: str(current_user.id) if current_user.is_authenticated else get_remote_address(),
    storage_uri=_redis_url,
    storage_options={"ssl_cert_reqs": None}
    )
logging.getLogger("flask_limiter").setLevel(logging.DEBUG)

    
@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))

@app.errorhandler(429)
def rate_limit_exceeded(e):
    flash("Too many requests. Please wait before trying again.")
    return redirect(request.referrer or url_for("index"))

@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    if _production:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

@app.route("/health")
def health():
    return "", 200

#Homepage
@limiter.limit("5/minute", methods=["POST"])
@app.route("/", methods=["POST", "GET"])
@login_required
def index():    
    #Add Stock
    portfolio = Holding.query.filter(Holding.user == current_user).order_by(Holding.total_invested.desc()).all()
    active_holdings = []
    for holding in portfolio:
        if holding.shares_owned == 0:
            db.session.delete(holding)
        else:
            update_if_stale(holding.stock)
            fetch_and_store_history(holding.stock.ticker, db)
            active_holdings.append(holding)
    db.session.commit()
    store_portfolio_history_if_needed(current_user, active_holdings, db)
    db.session.commit()

    if request.method == "POST":
        try:
            order = {
                "ticker": request.form['stock'].upper(),
                "shares": float(request.form['shares']),
                "price_bought": float(request.form['price']),
                "date": datetime.fromisoformat(request.form['date'])
            }
            if order["shares"] <= 0 or order["price_bought"] <= 0:
                flash("Shares and price must be positive.")
                return redirect(url_for("index"))
        except (ValueError, KeyError):
            flash("Invalid input.")
            return redirect(url_for("index"))

        valid, current_price, error = validate_and_fetch(order["ticker"])
        if valid:
            try:
                buy_stock(current_user, active_holdings, db, order, current_price)
                db.session.commit()
                return redirect(url_for("index"))
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error: {e}")
                flash("Issue occurred when trying to buy stock.")
                return redirect(request.referrer or url_for("index"))
        else:      
            flash(error)
            return redirect(url_for("index"))
    # See portfolio
    else:
        return render_template("index.html", portfolio=active_holdings)

#Returns JSON to render portfolio performance graphics
@app.route("/portfolio-history", methods=["GET"])
@login_required
def portfolio_history_api():
    period = request.args.get("period", "1m")
    limits = {"1m": 21, "1y": 252, "5y": 1260, "all": None}
    limit = limits.get(period, 21)

    query = PortfolioHistory.query.filter_by(user_id=current_user.id).order_by(PortfolioHistory.date.desc())
    if period != "all":
        query = query.limit(limit)
    rows = query.all()
    rows.reverse()
    
    labels = [row.date.strftime("%Y-%m-%d") for row in rows]
    prices = [row.total_value for row in rows]
    return jsonify({"labels": labels, "prices": prices})

#Login Page
@limiter.limit("5/minute")
@app.route('/login', methods=["POST", "GET"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(db.select(User).where(User.username == form.username.data))
        if user is None or not user.verify_password(form.password.data):
            flash('Invalid username or password.')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        flash("Logged in successfully.")
        return redirect(url_for("index"))
    return render_template('login.html', form=form)

#Logout Page
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for("index"))

#Registration Page
@limiter.limit("5/minute")
@app.route('/register', methods=["POST", "GET"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = db.session.scalar(db.select(User).where(User.username == form.username.data))
        email = db.session.scalar(db.select(User).where(User.email == form.email.data))
        if username is None and email is None and form.password.data == form.confirm_password.data:
            new_user = User(username=form.username.data, email=form.email.data, password=form.password.data)
            try:
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                return redirect(url_for("index"))
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error: {e}")
                flash("Issue with registering for account.")
                return redirect(request.referrer or url_for("index"))
        elif username:
            flash('Username Taken')
        elif email:
            flash('Email Already In Use')
    return render_template('registration.html', form=form)

#Delete Account
@app.route('/delete-account/<int:id>', methods=["GET", "POST"])
@login_required
def delete_account(id):
    if id != current_user.id:
        flash("Unauthorized.")
        return redirect(url_for("index"))
    form = DeleteAccount()
    user_delete = db.get_or_404(User, id)
    if form.validate_on_submit():
        if user_delete.verify_password(form.password.data) and form.confirm.data is True:
            try:
                db.session.delete(user_delete)
                db.session.commit()
                logout_user()
                flash('Account successfully deleted.')
                return redirect(url_for("index"))
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error: {e}")
                flash("Issue with deleting account.")
                return redirect(request.referrer or url_for("index"))
        else: 
            flash('Incorrect Password')
    return render_template('delete_account.html', form=form)


#View Holding Info
@limiter.limit("5/minute")
@app.route("/info/<int:id>", methods=["GET"])
@login_required
def view_holding(id):
    holding_view = db.get_or_404(Holding, id)
    if holding_view.user_id != current_user.id:
        flash("Unauthorized.")
        return redirect(url_for("index"))
    update_if_stale(holding_view.stock)
    fetch_and_store_history(holding_view.stock.ticker, db)
    db.session.commit()
    return render_template('info.html', holding=holding_view, transactions=holding_view.transactions)

#Returns JSON to render individual stock graphics
@app.route("/history/<ticker>", methods=["GET"])
@login_required
def stock_history_api(ticker):
    period = request.args.get("period", "1y")
    limits = {"1m": 21, "1y": 252, "5y": 1260, "all": None}
    limit = limits.get(period, 21)

    query = StockHistory.query.filter_by(ticker=ticker.upper()).order_by(StockHistory.date.desc())
    if period != "all":
        query = query.limit(limit)
    rows = query.all()
    rows.reverse()
    
    labels = [row.date.strftime("%Y-%m-%d") for row in rows]
    prices = [row.close_price for row in rows]
    return jsonify({"labels": labels, "prices": prices})


#Remove Stock
@app.route("/delete-stock/<int:id>", methods=["POST"])
@login_required
def delete_stock(id):
    holding_delete = db.get_or_404(Holding, id)
    if holding_delete.user_id != current_user.id:
        flash("Unauthorized.")
        return redirect(url_for("index"))
    try:
        db.session.delete(holding_delete)
        db.session.commit()
        return redirect(url_for("index"))
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error: {e}")
        flash("Issue with deleting stock.")
        return redirect(url_for("index"))
    
#Add Transaction to Stock    
@app.route("/add-transaction/<int:id>", methods=["POST", "GET"])
@login_required
def add_transaction(id):
    holding_update = db.get_or_404(Holding, id)
    transaction = Transaction(holding=holding_update)
    if current_user.id == holding_update.user_id:
        if request.method == "POST":
            try:
                transaction.type = request.form['transaction_type'].upper()
                transaction.shares = float(request.form['shares'])
                transaction.price_per_share = float(request.form['price_per_share'])
                date = request.form['date_bought']
                transaction.time = datetime.fromisoformat(date)
            except (ValueError, KeyError):
                flash("Invalid input.")
                return redirect(url_for("index"))
            if transaction.type == "SELL" and holding_update.shares_owned < transaction.shares:
                flash("Unable to sell more stocks than owned.")
            elif transaction.shares <= 0 or transaction.price_per_share <= 0:
                flash("Shares and price must be positive.")
            else:
                try:
                    db.session.add(transaction)
                    calculate_fifo(holding_update)
                    db.session.commit()
                    return redirect(url_for("index"))
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"Error: {e}")
                    flash("Issue with adding transaction.")
                    return redirect(request.referrer or url_for("index"))
        else:
            return render_template('transaction.html', holding=holding_update, is_transaction_edit=False)
    else:
        flash('Unable to edit stock.')
        return redirect(url_for("index"))
    
# Delete Existing Transaction
@app.route("/delete-transaction/<int:id>", methods=["POST"])
@login_required
def delete_transaction(id):
    transaction_delete = db.get_or_404(Transaction, id)
    holding_id = transaction_delete.holding_id
    if current_user.id == transaction_delete.holding.user_id:
        try:
            db.session.delete(transaction_delete)
            calculate_fifo(transaction_delete.holding)
            db.session.commit()
            return redirect(url_for("view_holding", id=holding_id))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error: {e}")
            flash("Issue with deleting transaction.")
            return redirect(request.referrer or url_for("index"))
    else:
        flash('Unable to delete transaction.')
        return redirect(url_for("index"))

    
# Edit Existing Transaction
@app.route("/edit-transaction/<int:id>", methods=["POST", "GET"])
@login_required
def edit_transaction(id):
    transaction_edit = db.get_or_404(Transaction, id)
    if current_user.id == transaction_edit.holding.user_id:
        if request.method == "POST":
            try:
                transaction_edit.type = request.form['transaction_type'].upper()
                transaction_edit.shares = float(request.form['shares'])
                transaction_edit.price_per_share = float(request.form['price_per_share'])
                date = request.form['date_bought']
                transaction_edit.time = datetime.fromisoformat(date)
            except (ValueError, KeyError):
                flash("Invalid input.")
                return redirect(url_for("index"))
            try:
                calculate_fifo(transaction_edit.holding)
                db.session.commit()
                return redirect(url_for("index"))
            except Exception as e:
                app.logger.error(f"Error: {e}")
                flash("Issue with editing transaction.")
                return redirect(request.referrer or url_for("index"))
        else:
            return render_template('transaction.html', transaction=transaction_edit, is_transaction_edit=True)
    else:
        flash('Unable to edit stock.')
        return redirect(url_for("index"))



if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
