class Transaction:
    """
    Manages transaction-related database operations for QuickPay.
    """
    def __init__(self, db_connection):
        self.db = db_connection

    def record_transaction(self, sender_id, receiver_id, amount, status="Completed"):
        """Records a new transaction."""
        query = """
            INSERT INTO transactions (sender_id, receiver_id, amount, status) 
            VALUES (?, ?, ?, ?)
        """
        return self.db.execute_update(query, (sender_id, receiver_id, amount, status))

    def get_transactions_for_user(self, user_id):
        """
        Retrieves all transactions (sent and received) for a specific user.
        Joins with the users table to get sender/receiver names.
        """
        query = """
            SELECT 
                t.id, 
                t.amount, 
                t.timestamp,
                t.status,
                sender.name AS sender_name,
                receiver.name AS receiver_name,
                CASE 
                    WHEN t.sender_id = ? THEN 'Sent' 
                    ELSE 'Received' 
                END AS type
            FROM transactions t
            JOIN users sender ON t.sender_id = sender.id
            JOIN users receiver ON t.receiver_id = receiver.id
            WHERE t.sender_id = ? OR t.receiver_id = ?
            ORDER BY t.timestamp DESC
        """
        return self.db.execute_query(query, (user_id, user_id, user_id))