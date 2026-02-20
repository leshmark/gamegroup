import psycopg2
import logging


class DatabaseDefinition:
    """Handles database schema creation and initialization"""
    
    def __init__(self, db_service):
        """
        Initialize database definition handler
        
        Args:
            db_service: DatabaseService instance to use for connections
        """
        self.db_service = db_service
        self.logger = logging.getLogger(__name__)
    
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
        
        conn = self.db_service.get_connection()
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
        
        conn = self.db_service.get_connection()
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
        
        conn = self.db_service.get_connection()
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
    
    def Initialize_users_table(self):
        """Initialize the users table with default users"""
        self.db_service.upsert_user(username="lesh", email="marklesh@yahoo.com", authorizations="is_contributor,is_admin,is_viewer")
        self.db_service.upsert_user(username="dlesh", email="dlesh@distributedworks.com", authorizations="is_contributor,is_viewer")
