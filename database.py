import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "smartcart.db"

def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS customers(customer_id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, password_hash TEXT, role TEXT DEFAULT 'customer', age INTEGER, gender TEXT, city TEXT, registration_date TEXT, total_purchases INTEGER DEFAULT 0, total_spending REAL DEFAULT 0, average_order_value REAL DEFAULT 0, website_visits INTEGER DEFAULT 0, segment TEXT DEFAULT 'Occasional Customer');
        CREATE TABLE IF NOT EXISTS products(product_id INTEGER PRIMARY KEY, product_name TEXT, category TEXT, price REAL CHECK(price>=0), rating REAL, stock INTEGER CHECK(stock>=0), discount REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS orders(order_id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, order_date TEXT, total REAL, payment_method TEXT, order_status TEXT, FOREIGN KEY(customer_id) REFERENCES customers(customer_id));
        CREATE TABLE IF NOT EXISTS order_items(item_id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, product_id INTEGER, quantity INTEGER, price REAL, FOREIGN KEY(order_id) REFERENCES orders(order_id), FOREIGN KEY(product_id) REFERENCES products(product_id));
        CREATE TABLE IF NOT EXISTS cart(cart_id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, product_id INTEGER, quantity INTEGER, UNIQUE(customer_id,product_id));
        CREATE TABLE IF NOT EXISTS wishlist(wishlist_id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, product_id INTEGER, UNIQUE(customer_id,product_id));
        CREATE TABLE IF NOT EXISTS customer_activity(customer_id INTEGER, product_id INTEGER, product_views INTEGER, cart_additions INTEGER, wishlist_additions INTEGER, previous_purchases INTEGER, time_spent REAL, purchased INTEGER, PRIMARY KEY(customer_id,product_id));
        ''')
