from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
import time

app = Flask(__name__)
app.secret_key = 'quickpay_secret_key_change_me'

DB_PATH = 'quickpay.db'


class User:
    def __init__(self, db_conn):
        self.db = db_conn

    def get_user_by_email(self, email):
        sql = "SELECT * FROM users WHERE email = ?;"
        return self.db.execute_fetch_one(sql, (email,))

    def get_user_by_id(self, user_id):
        sql = "SELECT * FROM users WHERE id = ?;"
        return self.db.execute_fetch_one(sql, (user_id,))

    def create_user(self, name, email, password_hash):
        sql = "INSERT INTO users (name, email, password, balance, created_at) VALUES (?, ?, ?, 1000.00, ?);"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lastrowid = self.db.execute_insert(sql, (name, email, password_hash, timestamp))
        return lastrowid

    def get_all_users_except_self(self, current_user_id):
        sql = "SELECT id, name, email FROM users WHERE id != ? ORDER BY name;"
        return self.db.execute_fetch_all(sql, (current_user_id,))

    def update_balance(self, user_id, new_balance):
        sql = "UPDATE users SET balance = ? WHERE id = ?;"
        self.db.execute_update(sql, (new_balance, user_id))

    def update_verification_status(self, user_id, status):
        sql = "UPDATE users SET verification_status = ? WHERE id = ?;"
        self.db.execute_update(sql, (status, user_id))


class Transaction:
    def __init__(self, db_conn):
        self.db = db_conn

    def record_transaction(self, sender_id, receiver_id, amount):
        sql = "INSERT INTO transactions (sender_id, receiver_id, amount, status) VALUES (?, ?, ?, 'Completed');"
        self.db.execute_insert(sql, (sender_id, receiver_id, amount))

    def get_transactions_for_user(self, user_id):
        sql = """
            SELECT
                t.amount,
                t.timestamp,
                u_sender.name AS sender_name,
                u_receiver.name AS receiver_name,
                CASE
                    WHEN t.sender_id = ? THEN 'Sent'
                    ELSE 'Received'
                END AS type
            FROM transactions t
            JOIN users u_sender ON t.sender_id = u_sender.id
            JOIN users u_receiver ON t.receiver_id = u_receiver.id
            WHERE t.sender_id = ? OR t.receiver_id = ?
            ORDER BY t.timestamp DESC;
        """
        return self.db.execute_fetch_all(sql, (user_id, user_id, user_id))


class DatabaseConnection:
    def __init__(self, db_path):
        self.db_path = db_path
        self.connection = None
        self.cursor = None

    def __enter__(self):
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        self.connection.close()

    def execute_fetch_one(self, sql, params=()):
        self.cursor.execute(sql, params)
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def execute_fetch_all(self, sql, params=()):
        self.cursor.execute(sql, params)
        return [dict(row) for row in self.cursor.fetchall()]

    def execute_update(self, sql, params=()):
        self.cursor.execute(sql, params)

    def execute_insert(self, sql, params=()):
        self.cursor.execute(sql, params)
        return self.cursor.lastrowid


def init_db():
    try:
        with DatabaseConnection(DB_PATH) as db:
            db.execute_update("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    balance REAL DEFAULT 1000.00,
                    verification_status TEXT DEFAULT 'Unverified',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            db.execute_update("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER NOT NULL,
                    receiver_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    FOREIGN KEY (sender_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (receiver_id) REFERENCES users (id) ON DELETE CASCADE
                );
            """)
    except sqlite3.Error as e:
        print(f"Database initialization FAILED: {e}")


with app.app_context():
    init_db()


@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}


def get_current_user_data(user_id):
    try:
        with DatabaseConnection(DB_PATH) as db:
            user_model = User(db)
            return user_model.get_user_by_id(user_id)
    except sqlite3.Error:
        return None


@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('welcome'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in session:
        return redirect(url_for('welcome'))

    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['new_email']
        password = request.form['new_password']

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password)

        try:
            with DatabaseConnection(DB_PATH) as db:
                user_model = User(db)

                if user_model.get_user_by_email(email):
                    flash("Email already registered. Please log in.", "warning")
                    return redirect(url_for('login'))
                else:
                    new_user_id = user_model.create_user(fullname, email, hashed_pw)

            user_data = get_current_user_data(new_user_id)
            if user_data:
                session['user'] = {'name': user_data['name'], 'id': user_data['id']}
                flash("Registration successful! You are now logged in. Please verify your account.", "success")
                return redirect(url_for('verify'))

            flash("Registration successful, but login failed. Please try logging in.", "warning")
            return redirect(url_for('login'))

        except sqlite3.Error as e:
            flash(f"Database Error: Could not register user. {e}", "danger")
            return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('welcome'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            with DatabaseConnection(DB_PATH) as db:
                user_model = User(db)
                user = user_model.get_user_by_email(email)

                if user and check_password_hash(user['password'], password):
                    session['user'] = {'name': user['name'], 'id': user['id']}
                    flash(f"Welcome back, {user['name']}!", "success")
                    return redirect(url_for('welcome'))
                else:
                    flash("Invalid email or password", "danger")
                    return redirect(url_for('login'))

        except sqlite3.Error as e:
            flash(f"Database Error during login. {e}", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('_flashes', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))


@app.route('/welcome')
def welcome():
    if 'user' not in session:
        flash("You must be logged in to access QuickPay.", "warning")
        return redirect(url_for('login'))

    user_id = session['user']['id']
    user_data = get_current_user_data(user_id)

    if not user_data:
        session.pop('user', None)
        flash("User data not found. Please log in again.", "danger")
        return redirect(url_for('login'))

    return render_template('welcome.html', user=user_data)


@app.route('/send')
def send_money():
    if 'user' not in session:
        flash("You must be logged in to send money.", "warning")
        return redirect(url_for('login'))

    user_id = session['user']['id']
    user_data = get_current_user_data(user_id)

    if not user_data:
        session.pop('user', None)
        flash("User data not found. Please log in again.", "danger")
        return redirect(url_for('login'))

    try:
        with DatabaseConnection(DB_PATH) as db:
            user_model = User(db)
            other_users = user_model.get_all_users_except_self(user_id)

        return render_template('send_money.html', user=user_data, other_users=other_users)
    except sqlite3.Error as e:
        flash(f"Database Error: Could not load recipient data. {e}", "danger")
        return render_template('send_money.html', user=user_data, other_users=[])


@app.route('/history')
def transaction_history():
    if 'user' not in session:
        flash("You must be logged in to view history.", "warning")
        return redirect(url_for('login'))

    user_id = session['user']['id']
    user_data = get_current_user_data(user_id)

    if not user_data:
        session.pop('user', None)
        flash("User data not found. Please log in again.", "danger")
        return redirect(url_for('login'))

    try:
        with DatabaseConnection(DB_PATH) as db:
            transaction_model = Transaction(db)
            history = transaction_model.get_transactions_for_user(user_id)

        return render_template('transaction_history.html', user=user_data, history=history)
    except sqlite3.Error as e:
        flash(f"Database Error: Could not load transaction history. {e}", "danger")
        return render_template('transaction_history.html', user=user_data, history=[])


@app.route('/transfer', methods=['POST'])
def transfer():
    if 'user' not in session:
        return redirect(url_for('login'))

    sender_id = session['user']['id']
    receiver_id = request.form.get('receiver_id', type=int)
    amount_str = request.form.get('amount')

    if not receiver_id or not amount_str:
        flash("Missing receiver or amount.", "danger")
        return redirect(url_for('send_money'))

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Amount must be positive.", "danger")
            return redirect(url_for('send_money'))
    except ValueError:
        flash("Invalid amount entered.", "danger")
        return redirect(url_for('send_money'))

    try:
        with DatabaseConnection(DB_PATH) as db:
            user_model = User(db)
            transaction_model = Transaction(db)

            sender = user_model.get_user_by_id(sender_id)
            receiver = user_model.get_user_by_id(receiver_id)

            if not sender or not receiver:
                flash("Invalid sender or receiver ID.", "danger")
                raise Exception("Invalid User ID in transfer attempt.")

            if sender['balance'] < amount:
                flash("Insufficient funds for this transfer.", "danger")
                return redirect(url_for('send_money'))

            new_sender_balance = sender['balance'] - amount
            user_model.update_balance(sender_id, new_sender_balance)

            new_receiver_balance = receiver['balance'] + amount
            user_model.update_balance(receiver_id, new_receiver_balance)

            transaction_model.record_transaction(sender_id, receiver_id, amount)

        flash(f"Successfully sent ${amount:.2f} to {receiver['name']}!", "success")

    except sqlite3.Error as e:
        flash(f"Transaction failed due to a database error. Funds safe. Error: {e}", "danger")
    except Exception as e:
        flash(f"Transaction failed: {e}", "danger")

    return redirect(url_for('welcome'))


@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'user' not in session:
        flash("You must be logged in to verify your account.", "warning")
        return redirect(url_for('login'))

    user_id = session['user']['id']

    try:
        with DatabaseConnection(DB_PATH) as db:
            user_model = User(db)
            user_data = user_model.get_user_by_id(user_id)

            if not user_data:
                flash("User data not found.", "danger")
                session.pop('user', None)
                return redirect(url_for('login'))

            if user_data['verification_status'] == 'Verified':
                flash("Your account is already fully Verified.", "info")
                return render_template('verify.html', user=user_data)

            if request.method == 'POST':
                user_model.update_verification_status(user_id, 'Verified')

                flash("Identity documents processed and **Verified** instantly! You now have full access.", "success")
                return redirect(url_for('welcome'))

            return render_template('verify.html', user=user_data)

    except sqlite3.Error as e:
        flash(f"Database error during verification process: {e}", "danger")
        return redirect(url_for('welcome'))


if __name__ == '__main__':
    app.run(debug=True)