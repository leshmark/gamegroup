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

    def initialize(self):
        """Create all database tables and seed initial data"""
        self.logger.info("Initializing database schema...")
        self.create_auth_links_table()
        self.create_users_table()
        self.add_pin_hash_column_if_missing()
        self.Initialize_users_table()
        self.create_games_table()
        self.create_games_json_table()
        self.create_game_votes_table()
        self.create_play_log_sessions_table()
        self.logger.info("Database schema initialization complete.")

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
            used_at TIMESTAMP,
            one_time_link BOOLEAN DEFAULT TRUE
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
            short_description VARCHAR(2000),
            tags TEXT[],
            image_url VARCHAR(25000),
            bgg_link VARCHAR(500),
            bgg_rating DECIMAL(3, 2) DEFAULT 0.0,
            next_play_vote_count INTEGER DEFAULT 0,
            last_played_at TIMESTAMP,
            favorited_by TEXT[],
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

    def create_games_json_table(self):
        """Create the games_json table for storing raw JSON data from BGG"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS games_json (
            id SERIAL PRIMARY KEY,
            bgg_id INTEGER UNIQUE NOT NULL,
            title VARCHAR(255) NOT NULL,
            json_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                self.logger.info("games_json table created successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error creating game_json table: {e}", exc_info=True)
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

    def add_pin_hash_column_if_missing(self):
        """Add pin_hash column to users table if it doesn't already exist (migration)"""
        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS pin_hash TEXT;
                """)
                conn.commit()
                self.logger.info("pin_hash column ensured on users table")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error adding pin_hash column: {e}", exc_info=True)
            raise
        finally:
            conn.close()

    def Initialize_users_table(self):
        """Initialize the users table with default users"""
        # Format: List of tuples (key_fields, update_fields)
        # key_fields are used to find existing records (email is unique)
        # update_fields contain the values to insert/update
        users = [
            (
                {"email": "marklesh@yahoo.com"},  # key fields to locate record
                {
                    "username": "lesh",
                    "authorizations": "is_contributor,is_admin,is_viewer",
                },
            ),
            (
                {"email": "dlesh@distributedworks.com"},
                {
                    "username": "dlesh",
                    "authorizations": "is_contributor,is_viewer",
                },
            ),
            (
                {"email": "mer.alialy@gmail.com"},
                {
                    "username": "mer",
                    "authorizations": "is_contributor,is_viewer",
                },
            ),
        ]
        successful_ids, errors = self.db_service.upsert_records("users", users)

        if errors:
            self.logger.warning(f"Errors during user initialization: {errors}")

        self.logger.info(f"Initialized {len(successful_ids)} users successfully")

    def create_game_votes_table(self):
        """Create the game_votes table for storing user votes on games"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS game_votes (
            id SERIAL PRIMARY KEY,
            game_id INTEGER NOT NULL,
            user_email VARCHAR(255) NOT NULL,
            vote INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_game
                FOREIGN KEY(game_id)
                REFERENCES games(id)
                ON DELETE CASCADE
        );
        
        CREATE INDEX IF NOT EXISTS idx_game_votes_game_id ON game_votes(game_id);
        CREATE INDEX IF NOT EXISTS idx_game_votes_user_email ON game_votes(user_email);
        CREATE INDEX IF NOT EXISTS idx_game_votes_created_at ON game_votes(created_at);
        """

        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                self.logger.info("game_votes table created successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error creating game_votes table: {e}", exc_info=True)
            raise
        finally:
            conn.close()

    def create_play_log_sessions_table(self):
        """Create the play_log_sessions table for recording when games were played"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS play_log_sessions (
            id SERIAL PRIMARY KEY,
            session_date TIMESTAMP NOT NULL,
            location VARCHAR(500),
            games_played INTEGER[],
            notes TEXT,
            logged_by VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_play_log_sessions_date ON play_log_sessions(session_date);
        CREATE INDEX IF NOT EXISTS idx_play_log_sessions_logged_by ON play_log_sessions(logged_by);
        """

        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                self.logger.info("play_log_sessions table created successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(
                f"Error creating play_log_sessions table: {e}", exc_info=True
            )
            raise
        finally:
            conn.close()
