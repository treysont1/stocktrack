from flask import Flask, render_template, redirect, request
from flask_scss import Scss
from flask_sqlalchemy import SQLAlchemy
#from datetime import datetime

app = Flask(__name__)
Scss(app)

db = SQLAlchemy(app)

#Data - Row of Data
class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False)
    initial = db.Column(db.Integer)
    current = db.Column(db.Integer)
#datetime default=datetime.
    def __repr__(self):
        return f"Stock {self.id}"


#Homepage
@app.route("/", methods=["POST", "GET"])
def index():
    #Add stock


    #See portfolio

    return render_template("index.html")


if __name__ in "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
