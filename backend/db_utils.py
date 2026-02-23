import psycopg2
from psycopg2 import sql
import os
import logging
from datetime import datetime
from db_definition import DatabaseDefinition


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
            "port": os.getenv("DB_PORT", "5432"),
        }
        self.definition = DatabaseDefinition(self)

    def get_connection(self):
        """Get a database connection"""
        return psycopg2.connect(**self.db_params)

    def create_auth_links_table(self):
        """Create the auth_links table for storing one-time authentication tokens"""
        return self.definition.create_auth_links_table()

    def create_games_table(self):
        """Create the games table for storing game library information"""
        return self.definition.create_games_table()

    def create_users_table(self):
        """Create the users table for storing user information"""
        return self.definition.create_users_table()

    def Initialize_users_table(self):
        """Initialize the users table with default users"""
        return self.definition.Initialize_users_table()

    # TODO: Harden this method against SQL injection by validating table_name and filter_criteria inputs
    def read_table(
        self,
        table_name: str,
        filter_criteria: str = None,
        columns: list = None,
        sort_by: str = None,
        sort_order: str = "ASC",
        limit: int = None,
        offset: int = None,
        count_only: bool = False,
    ):
        """
        Read data from a specified table with optional filter criteria, sorting, and pagination

        Args:
            table_name: Name of the database table to read from
            filter_criteria: Optional SQL WHERE clause to filter results (e.g. "id > 10")
            columns: Optional list of column names to retrieve (defaults to all columns)
            sort_by: Optional column name to sort by
            sort_order: Sort order, either "ASC" or "DESC" (default: "ASC")
            limit: Maximum number of rows to return (optional)
            offset: Number of rows to skip (optional)
            count_only: If True, return only the count of matching rows

        Returns:
            List of dictionaries representing rows from the table or count of matching rows if count_only is True
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                # Build SELECT clause
                if count_only:
                    query = sql.SQL("SELECT COUNT(*) FROM {}").format(
                        sql.Identifier(table_name)
                    )
                elif columns:
                    column_list = sql.SQL(", ").join(
                        [sql.Identifier(col) for col in columns]
                    )
                    query = sql.SQL("SELECT {} FROM {}").format(
                        column_list, sql.Identifier(table_name)
                    )
                else:
                    query = sql.SQL("SELECT * FROM {}").format(
                        sql.Identifier(table_name)
                    )

                # Add WHERE clause
                if filter_criteria:
                    query += sql.SQL(" WHERE ") + sql.SQL(filter_criteria)

                # Add ORDER BY, LIMIT, OFFSET only if not count_only
                if not count_only:
                    # Add ORDER BY clause
                    if sort_by:
                        order = "DESC" if sort_order.upper() == "DESC" else "ASC"
                        query += sql.SQL(" ORDER BY {} {}").format(
                            sql.Identifier(sort_by), sql.SQL(order)
                        )
                    # Add LIMIT clause
                    if limit is not None:
                        query += sql.SQL(" LIMIT {}").format(sql.Literal(limit))
                    # Add OFFSET clause
                    if offset is not None:
                        query += sql.SQL(" OFFSET {}").format(sql.Literal(offset))

                # Log the final query for debugging
                self.logger.debug(f"Executing query: {query.as_string(cursor)}")
                cursor.execute(query)
                if count_only:
                    count = cursor.fetchone()[0]
                    return count
                else:
                    columns = [desc[0] for desc in cursor.description]
                    results = cursor.fetchall()
                    return [dict(zip(columns, row)) for row in results]
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
                    (token, email, expires_at),
                )
                conn.commit()
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
                    (token,),
                )
                conn.commit()
        finally:
            conn.close()

    def add_game(
        self,
        title: str,
        owner: str,
        min_players: int,
        max_players: int,
        contributor_email: str,
        description: str = None,
        tags: list = None,
        image_url: str = None,
        bgg_link: str = None,
        bgg_rating: float = None,
    ):
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
                    (
                        title,
                        owner,
                        min_players,
                        max_players,
                        description,
                        tags,
                        image_url,
                        bgg_link,
                        bgg_rating,
                        contributor_email,
                    ),
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

    def update_game_image_url(self, game_id: int, image_url: str):
        """
        Update the image_url for a specific game

        Args:
            game_id: The ID of the game to update
            image_url: The new image URL
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE games 
                    SET image_url = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (image_url, game_id),
                )
                conn.commit()
                self.logger.info(f"Updated image_url for game ID {game_id}")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error updating game image: {e}", exc_info=True)
            raise
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
                    (username, email, authorizations),
                )
                user_id = cursor.fetchone()[0]
                conn.commit()
                self.logger.info(
                    f"User '{username}' created or updated successfully with ID {user_id}"
                )
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
                    (authorizations, email),
                )
                conn.commit()
                self.logger.info(f"User '{email}' authorizations updated successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error updating user authorizations: {e}", exc_info=True)
            raise
        finally:
            conn.close()
