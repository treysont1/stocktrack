import os
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, request, session, flash
from flask_scss import Scss
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy.orm as so
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user, login_required
from flask_migrate import Migrate
from forms import LoginForm
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
    stocks: so.WriteOnlyMapped['Stock'] = db.relationship(back_populates='user')

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
    user_id: so.Mapped[int] = db.Column(db.ForeignKey("user.id"), index=True)
    user: so.Mapped[User] = db.relationship(back_populates='stocks')

    def __repr__(self):
        return f"Stock {self.id}: {self.ticker}"
    
@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))


#Homepage
@app.route("/", methods=["POST", "GET"])
def index():    
    #Add Stock
    if request.method == "POST":
        stock = request.form['stock']
        new_stock = Stock(ticker=stock)
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
        portfolio = Stock.query.order_by(Stock.date_bought).all()
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

@app.route('/logout')
def logout():
    logout_user()
    return redirect('/')

#Stock Info
@app.route("/info/<int:id>", methods=["GET"])
def view(id):
    stock_view = Stock.query.get_or_404(id)
    return render_template('info.html', stock=stock_view)


#Remove Stock
@app.route("/delete/<int:id>", methods=["POST", "GET"])
def delete(id):
    stock_delete = Stock.query.get_or_404(id)
    try:
        db.session.delete(stock_delete)
        db.session.commit()
        return redirect('/')
    except Exception as e:
        db.session.rollback()
        print(f"Error:{e}")
        return f"Error:{e}"
    
#Edit Stock    
@app.route("/update/<int:id>", methods=["POST", "GET"])
@login_required
def update(id):
    stock_update = Stock.query.get_or_404(id)
    if request.method == "POST":
        stock_update.ticker = request.form['stock_ticker']
        stock_update.total_invested = request.form['stock_total_invested']
        stock_update.shares_owned = request.form['stock_shares']
        stock_update.current_share_price = request.form['stock_current_share_price']
        stock_update.avg_cost = float(stock_update.total_invested) / float(stock_update.shares_owned)
        stock_update.total_value = float(stock_update.shares_owned) * float(stock_update.current_share_price)
        stock_update.gain = (float(stock_update.current_share_price) - float(stock_update.avg_cost)) * float(stock_update.shares_owned)
        stock_update.gain_percentage = 100 * float(stock_update.gain) / float(stock_update.total_invested)
        print(stock_update.__dict__)
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



if __name__ in "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
