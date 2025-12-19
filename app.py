import os
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, request
from flask_scss import Scss
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
Scss(app)


load_dotenv(dotenv_path="env/.env")

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv('SQLALCHEMY_DATABASE_URI')
db = SQLAlchemy(app)

#Data - Row of Data
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
    def __repr__(self):
        return f"Stock {self.id}"


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

#Stock Info
@app.route("/info/<int:id>", methods=["GET"])
def view():
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
def update(id):
    stock_update = Stock.query.get_or_404(id)
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



if __name__ in "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
