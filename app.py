import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, request, session, flash
from flask_scss import Scss
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from flask_migrate import Migrate
from forms import LoginForm, RegistrationForm, DeleteAccount
from models import db, User, Holding, Stock, Transaction
import requests
from stock_validation import validate_ticker, get_current_price


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
    portfolio = Holding.query.filter(Holding.user == current_user).order_by(Holding.date_bought).all()
    if request.method == "POST":
        ticker = request.form['stock'].upper()
        shares = request.form['shares']
        price = request.form['price']
        date = request.form['date']
        datetime_object = datetime.fromisoformat(date)
        # 2026-01-22T15:40
        validation_result = validate_ticker(ticker)
        if validation_result[0]:
            try: 

                #### Would previously check if the STOCK was in the portfolio, if not, add this STOCK. I need to change this to see if stock 
                ## is in holdings, and also, if stock is present in stocks as well.
                stock_present = False
                for stock in portfolio:
                    if stock.ticker == ticker:
                        new_stock = stock
                        stock_present = True
                        break
                if not stock_present:
                    new_stock = Stock(ticker=ticker, user=current_user)
                db.session.add(new_stock)
                transaction = Transaction(type="BUY", shares=shares, price_per_share=price, time=datetime_object, stock=new_stock)
                db.session.add(transaction)
                db.session.commit()
                return redirect("/")
            except Exception as e:
                db.session.rollback()
                print(f"Error:{e}")
                return f"Error:{e}"
        else:
            
            flash(validation_result[1])
            return redirect('/')
    # See portfolio
    else:
        
        # current_prices = {}
        # for stock in portfolio:
        #     current_price = get_current_price(stock.ticker) 
        #     current_prices[stock.ticker] = current_price
        # pass current_prices=current_prices
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
    # user = db.session.scalar(db.select(User).where(User.username == current_user.username))
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


#Stock Info
@app.route("/info/<int:id>", methods=["GET"])
@login_required
def view(id):
    stock_view = Stock.query.get_or_404(id)
    return render_template('info.html', stock=stock_view, transactions=stock_view.transactions)


#Remove Stock
@app.route("/delete-stock/<int:id>", methods=["POST", "GET"])
@login_required
def delete_stock(id):
    stock_delete = Stock.query.get_or_404(id)
    if current_user.id == stock_delete.user_id:
        try:
            db.session.delete(stock_delete)
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
    stock_update = Stock.query.get_or_404(id)
    transaction = Transaction(stock=stock_update)
    if current_user.id == stock_update.user_id:
        if request.method == "POST":
            transaction.type = request.form['transaction_type'].upper()
            transaction.shares = request.form['shares']
            transaction.price_per_share = request.form['price_per_share']
            date = request.form['date_bought']
            transaction.date_bought = datetime.fromisoformat(date)
            if transaction.type == "SELL" and stock_update.shares_owned < transaction.shares:
                flash("Unable to sell more stocks than owned.")
            else:
                # 2026-02-03T23:56
                try:
                    db.session.add(transaction)
                    db.session.commit()
                    return redirect("/")
                except Exception as e:
                    db.session.rollback()
                    print(f"Error:{e}")
                    return f"Error:{e}"
        else:
            return render_template('transaction.html', stock=stock_update, is_transaction_edit=False)
    else:
        flash('Unable to edit stock.')
        return redirect("/")
    
# Delete Existing Transaction
@app.route("/delete-transaction/<int:id>", methods=["POST", "GET"])
@login_required
def delete_transaction(id):
    transaction_delete = Transaction.query.get_or_404(id)
    stock_id = transaction_delete.stock.id
    if current_user.id == transaction_delete.stock.user_id:
        try:
            db.session.delete(transaction_delete)
            db.session.commit()
            return redirect(f"/info/{stock_id}")
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
    if current_user.id == transaction_edit.stock.user_id:
        if request.method == "POST":
            transaction_edit.type = request.form['transaction_type'].upper()
            transaction_edit.shares = request.form['shares']
            transaction_edit.price_per_share = request.form['price_per_share']
            date = request.form['date_bought']
            # 2026-02-03T23:56
            transaction_edit.date_bought = datetime.fromisoformat(date)
            try:
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
            
    



if __name__ in "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
