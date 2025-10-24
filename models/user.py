class User:
    """
    Manages user-related database operations for QuickPay.
    Includes methods for balance, user retrieval, and verification status.
    """

    def __init__(self, db_connection):
        self.db = db_connection

    def create_user(self, name, email, password_hash):
        """Inserts a new user with an initial balance of 1000.00 and 'Unverified' status."""
        initial_balance = 1000.00
        verification_status = 'Unverified'
        query = "INSERT INTO users (name, email, password, balance, verification_status) VALUES (?, ?, ?, ?, ?)"
        return self.db.execute_update(query, (name, email, password_hash, initial_balance, verification_status))

    def get_user_by_email(self, email):
        """Retrieves a user's data by email address."""
        # Ensure 'verification_status' is selected here too for complete user object
        query = "SELECT id, name, email, password, balance, verification_status FROM users WHERE email = ?"
        result = self.db.execute_query(query, (email,))
        return result[0] if result else None

    def get_user_by_id(self, user_id):
        """Retrieves a user's data by ID, including verification status."""
        query = "SELECT id, name, email, balance, verification_status FROM users WHERE id = ?"
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

    def update_verification_status(self, user_id, status):
        """Updates the user's verification status."""
        query = "UPDATE users SET verification_status = ? WHERE id = ?"
        return self.db.execute_update(query, (status, user_id))