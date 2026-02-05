import psycopg2
from psycopg2 import sql
import os
import logging
from datetime import datetime


class DatabaseService:
    """Service for managing database connections and operations"""
    
    def __init__(self):
        """Initialize database service with configuration from environment variables"""
        self.logger = logging.getLogger(__name__)
        self.db_params = {
            "host": os.getenv("DB_HOST", "localhost"),
            "database": os.getenv("DB_NAME", "gamegroup"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", ""),
            "port": os.getenv("DB_PORT", "5432")
        }
    

    def get_connection(self):
        """Get a database connection"""
        return psycopg2.connect(**self.db_params)
    

    def create_auth_links_table(self):
        """Create the auth_links table for storing one-time authentication tokens"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS auth_links (
            id SERIAL PRIMARY KEY,
            token VARCHAR(255) UNIQUE NOT NULL,
            email VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            used_at TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_auth_links_token ON auth_links(token);
        CREATE INDEX IF NOT EXISTS idx_auth_links_email ON auth_links(email);
        CREATE INDEX IF NOT EXISTS idx_auth_links_expires_at ON auth_links(expires_at);
        """
        
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                self.logger.info("auth_links table created successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error creating auth_links table: {e}", exc_info=True)
            raise
        finally:
            conn.close()
    

    def store_auth_token(self, email: str, token: str, expires_at: datetime):
        """
        Store authentication token in the database
        
        Args:
            email: User's email address
            token: Generated authentication token
            expires_at: Token expiration timestamp
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO auth_links (token, email, expires_at) VALUES (%s, %s, %s)",
                    (token, email, expires_at)
                )
                conn.commit()
        finally:
            conn.close()
    

    def get_auth_token(self, token: str):
        """
        Retrieve authentication token details from database
        
        Args:
            token: Authentication token to look up
        
        Returns:
            Dictionary with token details or None if not found
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT email, expires_at, used FROM auth_links WHERE token = %s",
                    (token,)
                )
                result = cursor.fetchone()
                if result:
                    return {
                        "email": result[0],
                        "expires_at": result[1],
                        "used": result[2]
                    }
                return None
        finally:
            conn.close()
    

    def mark_token_as_used(self, token: str):
        """
        Mark authentication token as used
        
        Args:
            token: Authentication token to mark as used
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE auth_links SET used = TRUE, used_at = CURRENT_TIMESTAMP WHERE token = %s",
                    (token,)
                )
                conn.commit()
        finally:
            conn.close()
    

    def create_games_table(self):
        """Create the games table for storing game library information"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS games (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            owner VARCHAR(255) NOT NULL,
            min_players INTEGER NOT NULL,
            max_players INTEGER NOT NULL,
            description TEXT,
            tags TEXT[],
            image_url VARCHAR(25000),
            bgg_link VARCHAR(500),
            bgg_rating DECIMAL(3, 2),
            contributor_email VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_games_title ON games(title);
        CREATE INDEX IF NOT EXISTS idx_games_owner ON games(owner);
        CREATE INDEX IF NOT EXISTS idx_games_contributor ON games(contributor_email);
        CREATE INDEX IF NOT EXISTS idx_games_tags ON games USING GIN(tags);
        """
        
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                self.logger.info("games table created successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error creating games table: {e}", exc_info=True)
            raise
        finally:
            conn.close()
    

    def add_game(self, title: str, owner: str, min_players: int, max_players: int,
                 contributor_email: str, description: str = None, tags: list = None,
                 image_url: str = None, bgg_link: str = None, bgg_rating: float = None):
        """
        Add a new game to the library
        
        Args:
            title: Game title
            owner: Game owner name
            min_players: Minimum number of players
            max_players: Maximum number of players
            contributor_email: Email of the user adding the game
            description: Game description (optional)
            tags: List of game tags (optional)
            image_url: URL to game image (optional)
            bgg_link: BoardGameGeek link (optional)
            bgg_rating: BoardGameGeek rating (optional)
        
        Returns:
            The ID of the newly created game record
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO games (title, owner, min_players, max_players, description,
                                     tags, image_url, bgg_link, bgg_rating, contributor_email)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (title, owner, min_players, max_players, description,
                     tags, image_url, bgg_link, bgg_rating, contributor_email)
                )
                game_id = cursor.fetchone()[0]
                conn.commit()
                self.logger.info(f"Game '{title}' added successfully with ID {game_id}")
                return game_id
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error adding game: {e}", exc_info=True)
            raise
        finally:
            conn.close()


    def get_games(self, limit: int = 20, offset: int = 0, sort_by: str = None):
        """
        Retrieve games from the library with pagination
        
        Args:
            limit: Maximum number of games to return (default: 20)
            offset: Number of games to skip (default: 0)
            sort_by: Field to sort by (title, owner, min_players, max_players, bgg_rating, created_at)
        
        Returns:
            Dictionary with games list and total count
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                # Build query with optional sorting
                order_clause = "ORDER BY created_at DESC"
                if sort_by:
                    allowed_sorts = ['title', 'owner', 'min_players', 'max_players', 'bgg_rating', 'created_at']
                    if sort_by in allowed_sorts:
                        order_clause = f"ORDER BY {sort_by} ASC, title ASC"
                
                # Get total count
                cursor.execute("SELECT COUNT(*) FROM games")
                total_count = cursor.fetchone()[0]
                
                # Get paginated games
                cursor.execute(
                    f"""
                    SELECT id, title, owner, min_players, max_players, description,
                           tags, image_url, bgg_link, bgg_rating, contributor_email, created_at
                    FROM games
                    {order_clause}
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset)
                )
                results = cursor.fetchall()
                games = []
                for result in results:
                    games.append({
                        "id": result[0],
                        "title": result[1],
                        "owner": result[2],
                        "min_players": result[3],
                        "max_players": result[4],
                        "description": result[5],
                        "tags": result[6],
                        "image_url": result[7],
                        "bgg_link": result[8],
                        "bgg_rating": result[9],
                        "contributor_email": result[10],
                        "created_at": result[11].isoformat() if result[11] else None
                    })
                
                return {
                    "games": games,
                    "total": total_count,
                    "limit": limit,
                    "offset": offset
                }
        finally:
            conn.close()


    def create_users_table(self):
        """Create the users table for storing user information"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            authorizations TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        """
        
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                self.logger.info("users table created successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error creating users table: {e}", exc_info=True)
            raise
        finally:
            conn.close()
    

    def get_user_by_email(self, email: str):
        """
        Retrieve user information by email
        
        Args:
            email: User's email address
        
        Returns:
            Dictionary with user details or None if not found
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, username, email, authorizations, created_at, updated_at
                    FROM users WHERE email = %s
                    """,
                    (email,)
                )
                result = cursor.fetchone()
                if result:
                    return {
                        "id": result[0],
                        "username": result[1],
                        "email": result[2],
                        "authorizations": result[3],
                        "created_at": result[4],
                        "updated_at": result[5]
                    }
                return None
        finally:
            conn.close()


    def upsert_user(self, username: str, email: str, authorizations: str = None):
        """
        Create a new user in the database
        
        Args:
            username: Desired username
            email: User's email address
            authorizations: Comma-separated string of user roles/permissions (optional)
        
        Returns:
            The ID of the newly created user record
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (username, email, authorizations)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (email) DO UPDATE
                    SET username = EXCLUDED.username,
                        authorizations = EXCLUDED.authorizations,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                    """,
                    (username, email, authorizations)
                )
                user_id = cursor.fetchone()[0]
                conn.commit()
                self.logger.info(f"User '{username}' created or updated successfully with ID {user_id}")
                return user_id
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error creating or updating user: {e}", exc_info=True)
            raise
        finally:
            conn.close()


    def update_user_authorizations(self, email: str, authorizations: str):
        """
        Update user authorizations
        
        Args:
            email: User's email address
            authorizations: Comma-separated string of user roles/permissions
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE users SET authorizations = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE email = %s
                    """,
                    (authorizations, email)
                )
                conn.commit()
                self.logger.info(f"User '{email}' authorizations updated successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error updating user authorizations: {e}", exc_info=True)
            raise
        finally:
            conn.close()


    def get_all_users(self):
        """
        Retrieve all users from the database
        
        Returns:
            List of dictionaries containing user details
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, username, email, authorizations, created_at, updated_at
                    FROM users
                    ORDER BY created_at DESC
                    """
                )
                results = cursor.fetchall()
                users = []
                for result in results:
                    users.append({
                        "id": result[0],
                        "username": result[1],
                        "email": result[2],
                        "authorizations": result[3],
                        "created_at": result[4].isoformat() if result[4] else None,
                        "updated_at": result[5].isoformat() if result[5] else None
                    })
                return users
        finally:
            conn.close()


    def Initialize_users_table(self):
        """Initialize the users table on service startup"""
        self.upsert_user(username="lesh", email="marklesh@yahoo.com", authorizations="is_contributor,is_admin,is_viewer")
