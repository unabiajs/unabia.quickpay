class User:
    """
    Manages user-related database operations for QuickPay.
    Includes methods for balance and user retrieval for transactions.
    """

    def __init__(self, db_connection):
        self.db = db_connection

    def create_user(self, name, email, password_hash):
        """Inserts a new user with an initial balance of 1000.00."""
        initial_balance = 1000.00
        query = "INSERT INTO users (name, email, password, balance) VALUES (?, ?, ?, ?)"
        return self.db.execute_update(query, (name, email, password_hash, initial_balance))

    def get_user_by_email(self, email):
        """Retrieves a user's data by email address."""
        query = "SELECT id, name, email, password, balance FROM users WHERE email = ?"
        result = self.db.execute_query(query, (email,))
        return result[0] if result else None

    def get_user_by_id(self, user_id):
        """Retrieves a user's data by ID."""
        # Include email for the dashboard dropdown listing (for other users)
        query = "SELECT id, name, email, balance FROM users WHERE id = ?"
        result = self.db.execute_query(query, (user_id,))
        return result[0] if result else None

    def get_all_users_except_self(self, current_user_id):
        """Retrieves all users except the current user for payment selection."""
        query = "SELECT id, name, email FROM users WHERE id != ? ORDER BY name ASC"
        return self.db.execute_query(query, (current_user_id,))

    def update_balance(self, user_id, new_balance):
        """Updates the balance for a given user ID."""
        query = "UPDATE users SET balance = ? WHERE id = ?"
        return self.db.execute_update(query, (new_balance, user_id))