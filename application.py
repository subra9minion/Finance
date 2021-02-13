import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    rows = db.execute("SELECT * FROM users WHERE id=:ID", ID=session["user_id"])
    username = rows[0]["username"]
    cash = float("{:.2f}".format(rows[0]["cash"]))

    rows = db.execute("SELECT * FROM stocks WHERE username=:username", username=username)

    records = []
    gtprice = cash

    for row in rows:
        row_dict = {}
        row_dict["symbol"] = row["stock"]
        row_dict["name"] = lookup(row["stock"])["name"]
        row_dict["shares"] = row["shares"]
        row_dict["price"] = float("{:.2f}".format(lookup(row["stock"])["price"]))
        row_dict["tprice"] = float("{:.2f}".format(lookup(row["stock"])["price"] * row["shares"]))
        gtprice += lookup(row["stock"])["price"] * row["shares"]
        records.append(row_dict)

    return render_template("index.html", records=records, cash=cash, gtprice=float("{:.2f}".format(gtprice)))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # GET method
    if request.method == "GET":
        return render_template("buy.html")

    # POST method
    else:

        # username currently logged in
        rows = db.execute("SELECT * FROM users WHERE id=:ID", ID=session["user_id"])
        username = rows[0]["username"]

        if not request.form.get("shares").isdigit():
            return apology("Invalid number of shares")

        # user input
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        # error checking
        if shares < 1:
            return apology("Invalid number of shares")

        if lookup(symbol) == None:
            return apology("Invalid symbol")

        # getting current cash of user
        rows = db.execute("SELECT * FROM users WHERE username=:username", username=username)
        cash = rows[0]["cash"]

        # calculating new cash of user
        new_cash = cash - shares * lookup(symbol)["price"]

        # error checking
        if new_cash < 0:
            return apology("You don't have enough cash")

        # buying shares - making changes in database

        # updating users cash after buying
        db.execute("UPDATE users SET cash=:new_cash WHERE username=:username", new_cash=new_cash, username=username)

        # updating user's stocks
        rows = db.execute("SELECT * FROM stocks WHERE username=:username AND stock=:stock", username=username, stock=symbol)

        # if he does not own any of the stock
        if len(rows) == 0:
            db.execute("INSERT INTO stocks (username, stock, shares) VALUES (:username, :stock, :shares)",
                        username=username, stock=symbol, shares=shares)

        # if he already owns some of the stock
        else:
            current_shares = rows[0]["shares"]

            new_shares = shares + current_shares

            db.execute("UPDATE stocks SET shares=:new_shares WHERE username=:username AND stock=:stock",
                        new_shares=new_shares, username=username, stock=symbol)

        # adding it to the transaction record
        db.execute("INSERT INTO transactions (username, stock, shares, price, action, dot) VALUES (:username, :stock, :shares, :price, :action, :dot)",
                    username=username, stock=symbol, shares=shares, price=lookup(symbol)["price"], action='B', dot=datetime.now())

        return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    rows = db.execute("SELECT * FROM users WHERE id=:ID", ID=session["user_id"])
    username = rows[0]["username"]

    rows = db.execute("SELECT * FROM transactions WHERE username=:username", username=username)

    return render_template("history.html", rows=rows)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # method is GET
    if request.method == "GET":
        return render_template("quote.html")

    else:

        # looking up user input
        symbol = request.form.get("symbol")

        if lookup(symbol) == None:
            return apology("Invalid Symbol")

        # displaying the quote
        return render_template("quoted.html", lookup=lookup(symbol))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # method is GET
    if request.method == "GET":
        return render_template("register.html")

    # method is POST
    else:
        # if empty username
        if not request.form.get("username"):
            return apology("You need to create a username.")

        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        if len(rows) != 0:
            return apology("The username already exists. Please try a different username")

        # if empty password
        if not request.form.get("password"):
            return apology("You need to create a new password.")

        # if passwords don't match
        if request.form.get("confirm-password") != request.form.get("password"):
            return apology("Your passwords don't match. Please try again.")

        db.execute("INSERT into users (username, hash) values (:username, :password)",
        username=request.form.get("username"), password=generate_password_hash(request.form.get("password")))

        return redirect("/")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    rows = db.execute("SELECT * FROM users WHERE id=:ID", ID=session["user_id"])
    username = rows[0]["username"]
    cash = rows[0]["cash"]

    if request.method == "GET":

        rows = db.execute("SELECT * FROM stocks WHERE username=:username", username=username)
        return render_template("sell.html", rows=rows)

    else:

        if not request.form.get("shares").isdigit():
            return apology("Invalid number of shares")

        stock = request.form.get("stock")
        shares = int(request.form.get("shares"))

        rows = db.execute("SELECT * FROM stocks WHERE username=:username AND stock=:stock", username=username, stock=stock)
        current_shares = rows[0]["shares"]

        if shares > current_shares:
            return apology("You don't have enough shares")

        if shares < 1:
            return apology("Invalid number of shares to sell")

        price = lookup(stock)["price"]
        new_cash = cash + price * shares

        db.execute("UPDATE users SET cash=:new_cash WHERE username=:username", new_cash=new_cash, username=username)

        if shares == current_shares:
            db.execute("DELETE FROM stocks WHERE username=:username AND stock=:stock", username=username, stock=stock)

        else:
            db.execute("UPDATE stocks SET shares=:shares WHERE username=:username", shares=current_shares-shares, username=username)

        shares = -shares

        db.execute("INSERT INTO transactions VALUES (:username, :stock, :shares, :price, :action, :dot)",
                 username=username, stock=stock, shares=shares, price=price, action='S', dot=datetime.now())

        return redirect("/")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
