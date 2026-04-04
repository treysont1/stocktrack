import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, request, session, flash, jsonify
from flask_scss import Scss
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from flask_migrate import Migrate
from forms import LoginForm, RegistrationForm, DeleteAccount
from models import db, User, Holding, Stock, Transaction, StockHistory
import requests
from service import calculate_fifo, update_if_stale, fetch_and_store_history
from stock_validation import validate_and_fetch


app = Flask(__name__)
Scss(app)
login = LoginManager(app)
login.login_view = 'login'
# login_manager.init_app(app)

load_dotenv(dotenv_path=".env")

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.secret_key = os.getenv("SECRET_KEY")
db.init_app(app)
migrate = Migrate(app, db)
#Data - Row of Data
    
@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))


#Homepage
@app.route("/", methods=["POST", "GET"])
@login_required
def index():    
    #Add Stock
    portfolio = Holding.query.filter(Holding.user == current_user).order_by(Holding.total_invested.desc()).all()
    for holding in portfolio:
        update_if_stale(holding.stock)
    db.session.commit()

    if request.method == "POST":
        ticker = request.form['stock'].upper()
        shares = float(request.form['shares'])
        price_bought = float(request.form['price'])
        date = request.form['date']
        datetime_object = datetime.fromisoformat(date)
        # 2026-01-22T15:40
        valid, current_price, error = validate_and_fetch(ticker)
        if valid:
            try:
                existing_holding = next((h for h in portfolio if h.stock.ticker == ticker), None)
                existing_stock = existing_holding.stock if existing_holding else Stock.query.filter_by(ticker=ticker).first()
                if existing_stock is None:
                    existing_stock = Stock(ticker=ticker, current_price=current_price)
                    db.session.add(existing_stock)
                if existing_holding is None:
                    existing_holding = Holding(user=current_user, stock=existing_stock)
                    db.session.add(existing_holding)
                transaction = Transaction(type="BUY", shares=shares, price_per_share=price_bought, time=datetime_object, holding=existing_holding)   
                db.session.add(transaction)
                calculate_fifo(existing_holding)
                db.session.commit()
                return redirect("/")
            except Exception as e:
                db.session.rollback()
                print(f"Error:{e}")
                return f"Error:{e}"
        else:      
            flash(error)
            return redirect('/')
    # See portfolio
    else:
        return render_template("index.html", portfolio=portfolio)
    
#Login Page
@app.route('/login', methods=["POST", "GET"])
def login():
    if current_user.is_authenticated:
        return redirect('/')
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(db.select(User).where(User.username == form.username.data))
        if user is None or not user.verify_password(form.password.data):
            flash('Invalid username or password.')
            return redirect('/login')
        login_user(user, remember=form.remember_me.data)
        flash('Login for user {}, remember_me = {}'.format(form.username.data, form.remember_me.data))
        return redirect('/')
    return render_template('login.html', form=form)

#Logout Page
@app.route('/logout')
def logout():
    logout_user()
    return redirect('/')

#Registration Page
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
                return redirect("/")
            except Exception as e:
                db.session.rollback()
                print(f"Error:{e}")
                return f"Error:{e}"
        elif username:
            flash('Username Taken')
        elif email:
            flash('Email Already In Use')
    return render_template('registration.html', form=form)

#Delete Account
@app.route('/delete-account/<int:id>', methods=["POST", "GET"])
@login_required
def delete_account(id):
    form = DeleteAccount()
    # user = db.session.scalar(db.select(User).where(User.username == current_user.username)) is new version, move to in future
    user_delete = User.query.get_or_404(id)
    if form.validate_on_submit():
        if user_delete.verify_password(form.password.data) and form.confirm.data == True:
            try:
                db.session.delete(user_delete)
                db.session.commit()
                logout_user()
                flash('Account successfully deleted.')
                return redirect('/')
            except Exception as e:
                db.session.rollback()
                print(f"Error: {e}")
                return f"Error {e}"
        else: 
            flash('Incorrect Password')
    return render_template('delete_account.html', form=form)


#View Holding Info
@app.route("/info/<int:id>", methods=["GET"])
@login_required
def view(id):
    holding_view = Holding.query.get_or_404(id)
    update_if_stale(holding_view.stock)
    fetch_and_store_history(holding_view.stock.ticker, db)
    return render_template('info.html', holding=holding_view, transactions=holding_view.transactions)

#Returns JSON to render graphics
@app.route("/history/<ticker>", methods=["GET"])
@login_required
def history_api(ticker):
    period = request.args.get("period", "1y")
    limits = {"1m": 21, "1y": 252, "5y": 9999}
    limit = limits.get(period, 252)

    rows = StockHistory.query.filter_by(ticker=ticker.upper()).order_by(StockHistory.date.desc()).limit(limit).all()
    rows.reverse()
    
    labels = [row.date.strftime("%Y-%m-%d") for row in rows]
    prices = [row.close_price for row in rows]
    return jsonify({"labels": labels, "prices": prices})


#Remove Stock
@app.route("/delete-stock/<int:id>", methods=["POST", "GET"])
@login_required
def delete_stock(id):
    holding_delete = Holding.query.get_or_404(id)
    if current_user.id == holding_delete.user_id:
        try:
            db.session.delete(holding_delete)
            db.session.commit()
            return redirect('/')
        except Exception as e:
            db.session.rollback()
            print(f"Error:{e}")
            return f"Error:{e}"
    else:
        flash('Unable to delete stock.')
        return redirect('/')
    
#Add Transaction to Stock    
@app.route("/add-transaction/<int:id>", methods=["POST", "GET"])
@login_required
def add(id):
    holding_update = Holding.query.get_or_404(id)
    transaction = Transaction(holding=holding_update)
    if current_user.id == holding_update.user_id:
        if request.method == "POST":
            transaction.type = request.form['transaction_type'].upper()
            transaction.shares = float(request.form['shares'])
            transaction.price_per_share = float(request.form['price_per_share'])
            date = request.form['date_bought']
            transaction.time = datetime.fromisoformat(date)
            if transaction.type == "SELL" and holding_update.shares_owned < transaction.shares:
                flash("Unable to sell more stocks than owned.")
            else:
                # 2026-02-03T23:56
                try:
                    db.session.add(transaction)
                    calculate_fifo(holding_update)
                    db.session.commit()
                    return redirect("/")
                except Exception as e:
                    db.session.rollback()
                    print(f"Error:{e}")
                    return f"Error:{e}"
        else:
            return render_template('transaction.html', holding=holding_update, is_transaction_edit=False)
    else:
        flash('Unable to edit stock.')
        return redirect("/")
    
# Delete Existing Transaction
@app.route("/delete-transaction/<int:id>", methods=["POST", "GET"])
@login_required
def delete_transaction(id):
    transaction_delete = Transaction.query.get_or_404(id)
    holding_id = transaction_delete.holding_id
    if current_user.id == transaction_delete.holding.user_id:
        try:
            db.session.delete(transaction_delete)
            calculate_fifo(transaction_delete.holding)
            db.session.commit()
            return redirect(f"/info/{holding_id}")
        except Exception as e:
            db.session.rollback()
            print(f"Error:{e}")
            return f"Error:{e}"
    else:
        flash('Unable to delete transaction.')
        return redirect('/')

    
# Edit Existing Transaction
@app.route("/edit-transaction/<int:id>", methods=["POST", "GET"])
@login_required
def edit(id):
    transaction_edit = Transaction.query.get_or_404(id)
    if current_user.id == transaction_edit.holding.user_id:
        if request.method == "POST":
            transaction_edit.type = request.form['transaction_type'].upper()
            transaction_edit.shares = float(request.form['shares'])
            transaction_edit.price_per_share = float(request.form['price_per_share'])
            date = request.form['date_bought']
            # 2026-02-03T23:56
            transaction_edit.time = datetime.fromisoformat(date)
            try:
                calculate_fifo(transaction_edit.holding)
                db.session.commit()
                return redirect("/")
            except Exception as e:
                print(f"Error:{e}")
                return f"Error:{e}"
        else:
            return render_template('transaction.html', transaction=transaction_edit, is_transaction_edit=True)
    else:
        flash('Unable to edit stock.')
        return redirect("/")
            
    



if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
