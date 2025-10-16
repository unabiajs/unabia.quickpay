from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "quickpay_secret_key"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quickpay.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    balance = db.Column(db.Float, default=100.0)

    sent_transactions = db.relationship('Transaction', foreign_keys='Transaction.sender_id', backref='sender', lazy=True)
    received_transactions = db.relationship('Transaction', foreign_keys='Transaction.receiver_id', backref='receiver', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash("Username already exists!")
            return redirect(url_for('register'))

        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please log in.")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['username'] = user.username
            flash("Login successful!")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.")
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        flash("Please log in first.")
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()
    sent = Transaction.query.filter_by(sender_id=user.id).all()
    received = Transaction.query.filter_by(receiver_id=user.id).all()

    return render_template('dashboard.html', user=user, sent=sent, received=received)


@app.route('/send', methods=['POST'])
def send():
    if 'username' not in session:
        flash("Please log in first.")
        return redirect(url_for('login'))

    sender = User.query.filter_by(username=session['username']).first()
    recipient_username = request.form['recipient']
    amount = float(request.form['amount'])

    receiver = User.query.filter_by(username=recipient_username).first()

    if not receiver:
        flash("Recipient not found.")
        return redirect(url_for('dashboard'))

    if amount <= 0:
        flash("Amount must be greater than zero.")
        return redirect(url_for('dashboard'))

    if sender.balance < amount:
        flash("Insufficient balance.")
        return redirect(url_for('dashboard'))

    sender.balance -= amount
    receiver.balance += amount

    transaction = Transaction(sender_id=sender.id, receiver_id=receiver.id, amount=amount)
    db.session.add(transaction)
    db.session.commit()

    flash(f"Sent ${amount:.2f} to {receiver.username}")
    return redirect(url_for('dashboard'))


@app.route('/transactions')
def transactions():
    if 'username' not in session:
        flash("Please log in first.")
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()
    sent = Transaction.query.filter_by(sender_id=user.id).all()
    received = Transaction.query.filter_by(receiver_id=user.id).all()

    return render_template('transactions.html', user=user, sent=sent, received=received)


@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("You have been logged out.")
    return redirect(url_for('home'))


if __name__ == '__main__':
    if not os.path.exists('quickpay.db'):
        with app.app_context():
            db.create_all()
    app.run(debug=True)
