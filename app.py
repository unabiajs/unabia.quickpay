from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import time
from models.user import User
from models.transaction import Transaction
from utils.dbconnection import DatabaseConnection

# Import datetime for the footer year in the template (optional, but good practice)
from datetime import datetime

app = Flask(__name__)
# IMPORTANT: Change this secret key in a production environment
app.secret_key = 'quickpay_secret_key_change_me'

# --- Database Configuration ---
DB_PATH = 'quickpay.db'


def init_db():
    """Initializes the SQLite database tables (users and transactions)."""
    print("Attempting to initialize database tables...")
    try:
        with DatabaseConnection(DB_PATH) as db:
            # Users table: Added BALANCE column
            db.execute_update("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    balance REAL DEFAULT 1000.00,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Transactions table: Replaced 'posts' with 'transactions'
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
        print("QuickPay database tables checked/created successfully.")
    except sqlite3.Error as e:
        print(f"Database initialization FAILED: {e}")


# Run database initialization when the application context is ready
with app.app_context():
    init_db()


# --- Application Routes ---

# Inject current time into all templates for footer year
@app.context_processor
def inject_now():
    """Makes the current datetime available to all templates."""
    return {'now': datetime.utcnow()}

@app.route('/')
def index():
    """Renders the main page, redirects to dashboard if logged in."""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles new user registration."""
    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['new_email']
        password = request.form['new_password']

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return redirect(url_for('index'))

        hashed_pw = generate_password_hash(password)

        try:
            with DatabaseConnection(DB_PATH) as db:
                user_model = User(db)

                if user_model.get_user_by_email(email):
                    flash("Email already registered. Please log in.", "warning")
                    return redirect(url_for('index'))
                else:
                    user_model.create_user(fullname, email, hashed_pw)

            flash("Registration successful! Initial balance: $1000.00. You can now log in.", "success")
            return redirect(url_for('index'))

        except sqlite3.Error as e:
            flash(f"Database Error: Could not register user. {e}", "danger")
            return redirect(url_for('index'))

    return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            with DatabaseConnection(DB_PATH) as db:
                user_model = User(db)
                user = user_model.get_user_by_email(email)

                if user and check_password_hash(user['password'], password):
                    # Store only non-sensitive data in the session
                    session['user'] = {'name': user['name'], 'id': user['id']}
                    flash(f"Welcome back, {user['name']}!", "success")
                    return redirect(url_for('dashboard'))
                else:
                    flash("Invalid email or password", "danger")
                    return redirect(url_for('index'))

        except sqlite3.Error as e:
            flash(f"Database Error during login. {e}", "danger")
            return redirect(url_for('index'))

    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    """Logs the user out."""
    session.pop('user', None)
    session.pop('_flashes', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    """Displays the user's balance, payment form, and transaction history."""
    if 'user' not in session:
        flash("You must be logged in to access QuickPay.", "warning")
        return redirect(url_for('index'))

    user_id = session['user']['id']
    try:
        with DatabaseConnection(DB_PATH) as db:
            user_model = User(db)
            transaction_model = Transaction(db)

            # 1. Get current user's full data (including balance)
            current_user_data = user_model.get_user_by_id(user_id)
            if not current_user_data:
                session.pop('user', None)
                flash("User data not found. Please log in again.", "danger")
                return redirect(url_for('index'))

            # 2. Get list of other users for payment dropdown
            other_users = user_model.get_all_users_except_self(user_id)

            # 3. Get transaction history
            history = transaction_model.get_transactions_for_user(user_id)

        return render_template(
            'dashboard.html',
            user=current_user_data,
            other_users=other_users,
            history=history
        )

    except sqlite3.Error as e:
        flash(f"Database Error: Could not load dashboard data. {e}", "danger")
        return render_template('dashboard.html', user={'name': session['user']['name'], 'balance': 0.00},
                               other_users=[], history=[])


@app.route('/transfer', methods=['POST'])
def transfer():
    """Handles the peer-to-peer money transfer."""
    if 'user' not in session:
        return redirect(url_for('index'))

    sender_id = session['user']['id']
    receiver_id = request.form.get('receiver_id', type=int)
    amount_str = request.form.get('amount')

    # Basic input validation
    if not receiver_id or not amount_str:
        flash("Missing receiver or amount.", "danger")
        return redirect(url_for('dashboard'))

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Amount must be positive.", "danger")
            return redirect(url_for('dashboard'))
    except ValueError:
        flash("Invalid amount entered.", "danger")
        return redirect(url_for('dashboard'))

    # Start the atomic transaction block
    try:
        with DatabaseConnection(DB_PATH) as db:
            user_model = User(db)
            transaction_model = Transaction(db)

            sender = user_model.get_user_by_id(sender_id)
            receiver = user_model.get_user_by_id(receiver_id)

            if not sender or not receiver:
                flash("Invalid sender or receiver ID.", "danger")
                # This rollback is implicit via the context manager if an exception is raised
                raise Exception("Invalid User ID in transfer attempt.")

            if sender['balance'] < amount:
                flash("Insufficient funds for this transfer.", "danger")
                # Rollback/Prevent commit
                return redirect(url_for('dashboard'))

                # 1. Update Sender's Balance (Debit)
            new_sender_balance = sender['balance'] - amount
            user_model.update_balance(sender_id, new_sender_balance)

            # 2. Update Receiver's Balance (Credit)
            new_receiver_balance = receiver['balance'] + amount
            user_model.update_balance(receiver_id, new_receiver_balance)

            # 3. Record the Transaction
            transaction_model.record_transaction(sender_id, receiver_id, amount)

        # If we reach here, the context manager commits all changes.
        flash(f"Successfully sent ${amount:.2f} to {receiver['name']}!", "success")

    except sqlite3.Error as e:
        # If any DB operation fails, the context manager rolls back.
        flash(f"Transaction failed due to a database error. Funds safe. Error: {e}", "danger")
    except Exception as e:
        # Catch custom exception for invalid user IDs, etc.
        flash(f"Transaction failed: {e}", "danger")

    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True)