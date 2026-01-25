import os
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, request, session, flash
from flask_scss import Scss
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy.orm as so
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user, login_required
from flask_migrate import Migrate
from forms import LoginForm, RegistrationForm, DeleteAccount
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
Scss(app)
login = LoginManager(app)
login.login_view = 'login'
# login_manager.init_app(app)

load_dotenv(dotenv_path="env/.env")

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.secret_key = os.getenv("SECRET_KEY")
db = SQLAlchemy(app)
migrate = Migrate(app, db)
#Data - Row of Data

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(128), unique=True)
    password_hash = db.Column(db.String(128))
    stocks: so.Mapped['Stock'] = db.relationship("Stock", back_populates='user', cascade='all, delete-orphan')

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
    shares_owned = db.Column(db.Integer, default=0) 
    avg_cost = db.Column(db.Integer, default=0) 
    current_share_price = db.Column(db.Integer, default=0) 
    total_value = db.Column(db.Integer, default=0) 
    gain = db.Column(db.Integer, default=0) 
    gain_percentage = db.Column(db.Integer, default=0) 
    date_bought = db.Column(db.DateTime, default=datetime.now)
    user_id: so.Mapped[int] = db.Column(db.Integer, db.ForeignKey("user.id", ondelete='CASCADE'), nullable=False, index=True)
    user: so.Mapped[User] = db.relationship(User, back_populates='stocks')

    @so.validates('shares_owned', 'total_invested', "current_share_price")
    def update_calculatons(self, key, value):
        # setattr(self, key, value)
        self.__dict__[key] = value

        self.avg_cost = float(self.total_invested) / float(self.shares_owned) if self.shares_owned else 0
        self.total_value = float(self.shares_owned) * float(self.current_share_price)
        self.gain = (float(self.current_share_price) - float(self.avg_cost)) * float(self.shares_owned)
        self.gain_percentage = 100 * float(self.gain) / float(self.total_invested) if self.total_invested else 0
        return value


    def __repr__(self):
        return f"Stock {self.id}: {self.ticker}"
    
@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))


#Homepage
@app.route("/", methods=["POST", "GET"])
@login_required
def index():    
    #Add Stock
    if request.method == "POST":
        stock = request.form['stock']
        new_stock = Stock(ticker=stock, user=current_user)
        try: 
            db.session.add(new_stock)
            db.session.commit()
            return redirect("/")
        except Exception as e:
            db.session.rollback()
            print(f"Error:{e}")
            return f"Error:{e}"
    # See portfolio
    else:
        portfolio = Stock.query.filter(Stock.user == current_user).order_by(Stock.date_bought).all()
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
            flash('Invalid username or password')
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
    return render_template('info.html', stock=stock_view)


#Remove Stock
@app.route("/delete/<int:id>", methods=["POST", "GET"])
@login_required
def delete(id):
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
    
#Edit Stock    
@app.route("/update/<int:id>", methods=["POST", "GET"])
@login_required
def update(id):
    stock_update = Stock.query.get_or_404(id)
    if current_user.id == stock_update.user_id:
        if request.method == "POST":
            stock_update.ticker = request.form['stock_ticker']
            stock_update.total_invested = request.form['stock_total_invested']
            stock_update.shares_owned = request.form['stock_shares']
            stock_update.current_share_price = request.form['stock_current_share_price']
            # print("HERE IS DATETIME")
            # print(type(request.form['date_bought']))
            # stock_update.date_bought = datetime(request.form['date_bought'])
            try:
                db.session.commit()
                return redirect("/")
            except Exception as e:
                print(f"Error:{e}")
                return f"Error:{e}"
        else:
            return render_template('update.html', stock=stock_update)
    else:
        flash('Unable to edit stock.')
        return redirect("/")



if __name__ in "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
