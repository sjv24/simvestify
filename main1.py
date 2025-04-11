import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
import streamlit as st
import sqlite3
import json
from abc import ABC, abstractmethod

# ---------------- SQLite Functions ---------------- #
def create_table():
    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolios (
            email TEXT PRIMARY KEY,
            name TEXT,
            password TEXT,
            balance REAL,
            stocks_owned TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_user_data(user):
    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()
    
    stocks_data = {ticker: {"quantity": data["quantity"], "price": data["price"]} for ticker, data in user.stocks_owned.items()}
    
    cursor.execute('''
        REPLACE INTO portfolios (email, name, password, balance, stocks_owned)
        VALUES (?, ?, ?, ?, ?)
    ''', (user.email, user.name, user.password, user.balance, json.dumps(stocks_data)))
    conn.commit()
    conn.close()


def load_user_data(email, password):
    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM portfolios WHERE email=?", (email,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row[2] == password:
        stock_quantities = json.loads(row[4]) 
        print(f"Loaded stocks data: {stock_quantities}")
        
        stocks_owned = {}
        for ticker, qty in stock_quantities.items():
            if isinstance(qty, dict):
                stocks_owned[ticker] = {
                    "stock": Stock(ticker),
                    "quantity": qty.get("quantity", 0),
                    "price": qty.get("price", 0)
                }
            else:
                print(f"Warning: Invalid data for {ticker}, expected dictionary, got {type(qty)}")
        
        return {
            "name": row[1],
            "email": row[0],
            "password": row[2],
            "balance": row[3],
            "stocks_owned": stocks_owned
        }
    return None


def delete_user(email):
    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM portfolios WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    print(f"Deleted user with email: {email}")

def user_exists(email):
    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM portfolios WHERE email=?", (email,))
    exists = cursor.fetchone()
    conn.close()
    return bool(exists)

# ---------------- Observer Pattern ---------------- #
class StockObserver(ABC):
    @abstractmethod
    def stock_notify(self, message):
        pass

class User(StockObserver):
    def __init__(self, name, email, password, balance=1000, stocks_owned=None):
        self.name = name
        self.email = email
        self.password = password
        self.balance = balance
        self.stocks_owned = stocks_owned or {}

    def stock_notify(self, message):
        st.toast(message, icon="📢")

    def buy_stock(self, stock, quantity):
        price = stock.get_current_price()
        total_price = price * quantity
        if self.balance >= total_price:
            if stock.ticker in self.stocks_owned:
                self.stocks_owned[stock.ticker]["quantity"] += quantity
            else:
                self.stocks_owned[stock.ticker] = {"stock": stock, "quantity": quantity, "price": price}  # Add price when buying new stock
            self.balance -= total_price
            st.success(f"✅ Bought {quantity} shares of {stock} at ${price:.2f} each.")
        else:
            st.error(f"❌ Not enough balance. Needed ${total_price:.2f}, but you have ${self.balance:.2f}")

    def sell_stock(self, stock, quantity):
        if stock.ticker in self.stocks_owned:
            if self.stocks_owned[stock.ticker]["quantity"] >= quantity:
                price = stock.get_current_price()
                self.stocks_owned[stock.ticker]["quantity"] -= quantity
                self.balance += price * quantity
                st.success(f"✅ Sold {quantity} shares of {stock} at ${price:.2f} each.")
                if self.stocks_owned[stock.ticker]["quantity"] == 0:
                    del self.stocks_owned[stock.ticker]
            else:
                st.warning(f"⚠️ You only own {self.stocks_owned[stock.ticker]['quantity']} shares of {stock}")
        else:
            st.warning(f"⚠️ You don't own any shares of {stock}")

    def show_portfolio(self):
        st.markdown("---")
        st.subheader("📊 Portfolio Overview")
        if not self.stocks_owned:
            st.info("You currently don't own any stocks.")
        else:
            for ticker, data in self.stocks_owned.items():
                stock = data["stock"]
                quantity = data["quantity"]
                purchase_price = data.get("price", None)  

                if purchase_price is None:
                    st.warning(f"⚠️ No purchase price found for {ticker}.")
                else:
                    formatted_purchase_price = f"${purchase_price:.2f}"
                    st.markdown(f"📈 **{stock}** — {quantity} shares bought @ {formatted_purchase_price} each")

            st.markdown(f"**💼 Remaining Balance:** ${self.balance:.2f}")

# ---------------- Stock Class ---------------- #
class Stock:
    def __init__(self, ticker):
        self.ticker = ticker.upper()
        self.stock_data = None

    def __str__(self):
        return self.ticker

    def fetch_data(self):
        stock = yf.Ticker(self.ticker)
        self.stock_data = stock.history(period="5d")
        if self.stock_data.empty:
            st.error(f"❌ No data found for '{self.ticker}'")
        return self.stock_data

    def get_current_price(self):
        if self.stock_data is None or self.stock_data.empty:
            return 0
        return self.stock_data['Close'].iloc[-1]

    def plot_price(self):
        if self.stock_data is None or self.stock_data.empty:
            return
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=self.stock_data.index, y=self.stock_data['Close'], mode='lines+markers'))
        fig.update_layout(title=f"{self.ticker} Stock Trend", xaxis_title="Date", yaxis_title="Price", template="plotly_dark")
        return fig

# ---------------- Streamlit UI ---------------- #
st.set_page_config(page_title="Simvestify", layout="centered")
create_table()
st.title("💹 Simvestify - Simulation & Investing")

if "user_created" not in st.session_state:
    user_type = st.radio("Are you a new user or existing user?", ["New User", "Existing User"])

    if user_type == "New User":
        with st.form("register_form"):
            name = st.text_input("Name")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Create Account 🚀")

            if submit:
                if user_exists(email):
                    st.warning("🚫 This email is already registered. Try logging in.")
                elif name and email and password:
                    new_user = User(name, email, password)
                    save_user_data(new_user)
                    st.session_state.user = new_user
                    st.session_state.user_created = True
                    st.success(f"Account created! Welcome, {name} 🎉")
                    st.rerun()
                else:
                    st.warning("Please fill out all fields.")

    else:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")

            if submit:
                user_data = load_user_data(email, password)
                if user_data:
                    loaded_user = User(**user_data)
                    st.session_state.user = loaded_user
                    st.session_state.user_created = True
                    st.success(f"Welcome back, {loaded_user.name}! 💰")
                    st.rerun()
                else:
                    st.error("Invalid email or password.")

# ---------------- Main App ---------------- #
if st.session_state.get("user_created"):
    user = st.session_state.user
    st.markdown("---")
    ticker = st.text_input("🔎 Enter a stock ticker (e.g., AAPL, TSLA)")

    if ticker:
        stock = Stock(ticker)
        stock.fetch_data()
        if stock.stock_data is not None and not stock.stock_data.empty:
            st.plotly_chart(stock.plot_price(), use_container_width=True)
            st.markdown(f"**📍 Current Price:** ${stock.get_current_price():.2f}")
            quantity = st.number_input("🔢 Shares:", min_value=1, value=1)
            action = st.radio("Choose Action", ["Buy", "Sell"], horizontal=True)
            if st.button("💼 Confirm"):
                if action == "Buy":
                    user.buy_stock(stock, quantity)
                else:
                    user.sell_stock(stock, quantity)
                save_user_data(user)

    user.show_portfolio()

    st.markdown("---")
    st.subheader("⚠️ Delete Account")
    if st.checkbox("I understand this will permanently delete my data."):
        if st.button("🗑️ Delete My Account"):
            delete_user(user.email)
            st.success("Your account has been deleted.")
            st.session_state.clear()
            st.rerun()
