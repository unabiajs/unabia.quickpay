import sqlite3

class DatabaseConnection:
    """
    A context manager class to handle SQLite database connections.
    It automatically opens and closes the connection and cursor.
    """
    def __init__(self, db_path):
        # db_path is the file path to your SQLite database (e.g., 'minisocial.db')
        self.db_path = db_path
        self.connection = None
        self.cursor = None

    def __enter__(self):
        """Connect to the database and return the cursor."""
        try:
            # Added isolation_level=None for autocommit/explicit transactions via context manager
            self.connection = sqlite3.connect(self.db_path, isolation_level=None)
            # Use sqlite3.Row to allow fetching results by column name (dictionary-like)
            self.connection.row_factory = sqlite3.Row
            self.cursor = self.connection.cursor()
            # Begin a transaction explicitly
            self.cursor.execute("BEGIN")
            return self
        except sqlite3.Error as e:
            print(f"SQLite connection error: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Commit changes or rollback, and close the connection."""
        if self.connection:
            if exc_type is None:
                # Commit if no exception occurred
                self.connection.commit()
            else:
                # Rollback if an exception occurred
                self.connection.rollback()
            self.cursor.close()
            self.connection.close()
        # Do not suppress exceptions
        return False

    def execute_query(self, query, params=()):
        """Executes a SELECT query and returns the result as a list of dictionaries."""
        self.cursor.execute(query, params)
        # Convert sqlite3.Row objects to standard dictionaries
        return [dict(row) for row in self.cursor.fetchall()]

    def execute_update(self, query, params=()):
        """Executes an INSERT, UPDATE, or DELETE query and returns the row count."""
        self.cursor.execute(query, params)
        # Returns the row ID for INSERTs, otherwise row count
        return self.cursor.lastrowid if 'INSERT' in query.upper() else self.cursor.rowcount