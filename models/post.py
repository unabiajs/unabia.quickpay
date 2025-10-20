class Post:
    """
    Manages post-related database operations.
    """
    def __init__(self, db_connection):
        self.db = db_connection

    def create_post(self, content, user_id):
        """
        Inserts a new post into the database.
        Note the use of '?' placeholder for SQLite.
        """
        query = "INSERT INTO posts (content, user_id) VALUES (?, ?)"
        return self.db.execute_update(query, (content, user_id))

    def get_post_by_id(self, post_id):
        """
        Retrieves a single post by its ID.
        """
        query = "SELECT id, content, user_id FROM posts WHERE id = ?"
        result = self.db.execute_query(query, (post_id,))
        return result[0] if result else None

    def get_all_posts(self):
        """
        Retrieves all posts, joining with user names for display.
        """
        query = """
            SELECT posts.id, posts.content, posts.user_id, users.name 
            FROM posts 
            INNER JOIN users ON posts.user_id = users.id 
            ORDER BY posts.created_at DESC
        """
        return self.db.execute_query(query)

    def delete_post(self, post_id):
        """
        Deletes a post by its ID.
        """
        query = "DELETE FROM posts WHERE id = ?"
        return self.db.execute_update(query, (post_id,))

    def update_post(self, post_id, content):
        """Updates the content of an existing post."""
        query = "UPDATE posts SET content = ? WHERE id = ?"
        return self.db.execute_update(query, (content, post_id))
