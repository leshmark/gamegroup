import psycopg2
from psycopg2 import sql
import os
import logging
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

    def initialize_database(self):
        try:
            """Initialize the database by creating necessary tables"""
            self.logger.info("Initializing database...")
            self.create_auth_links_table()
            self.create_users_table()
            self.Initialize_users_table()
            self.create_games_table()
            self.create_games_json_table()
            self.create_game_votes_table()
            self.logger.info("Database initialization complete.")
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}", exc_info=True)
            raise

    def get_connection(self):
        """Get a database connection"""
        return psycopg2.connect(**self.db_params)

    def create_auth_links_table(self):
        """Create the auth_links table for storing one-time authentication tokens"""
        return self.definition.create_auth_links_table()

    def create_games_table(self):
        """Create the games table for storing game library information"""
        return self.definition.create_games_table()

    def create_games_json_table(self):
        """Create the games_json table for storing raw JSON data from BGG"""
        return self.definition.create_games_json_table()

    def create_users_table(self):
        """Create the users table for storing user information"""
        return self.definition.create_users_table()

    def Initialize_users_table(self):
        """Initialize the users table with default users"""
        return self.definition.Initialize_users_table()

    def create_game_votes_table(self):
        """Create the game_votes table for storing user votes on games"""
        return self.definition.create_game_votes_table()

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
            
        Raises:
            ValueError: If validation of parameters fails
        """
        # Validate parameters
        if limit is not None and (limit < 1 or limit > 1000):
            raise ValueError("Limit must be between 1 and 1000")
        if offset is not None and offset < 0:
            raise ValueError("Offset must be non-negative")
        if sort_order.upper() not in ["ASC", "DESC"] and not all(
            o.strip().upper() in ("ASC", "DESC") for o in sort_order.split(",")
        ):
            raise ValueError("Sort order must be ASC or DESC")
        
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

                #TODO: make filter_criteria safer by accepting a list of tuples of (column, operator, value) and building the WHERE clause using that information and escaping text values by encoding them as base64 and decoding them in the backend before using them in the query. This would prevent SQL injection while still allowing for flexible filtering.
                # Add WHERE clause
                if filter_criteria:
                    query += sql.SQL(" WHERE ") + sql.SQL(filter_criteria)

                # Add ORDER BY, LIMIT, OFFSET only if not count_only
                if not count_only:
                    # Add ORDER BY clause (supports comma-separated multi-column sort)
                    if sort_by:
                        sort_by_fields = [f.strip() for f in sort_by.split(",") if f.strip()]
                        sort_order_values = [o.strip().upper() for o in sort_order.split(",") if o.strip()]
                        # Pad sort_order_values if fewer than sort_by_fields
                        if len(sort_order_values) < len(sort_by_fields):
                            last = sort_order_values[-1] if sort_order_values else "ASC"
                            sort_order_values += [last] * (len(sort_by_fields) - len(sort_order_values))
                        order_clauses = []
                        for i, field in enumerate(sort_by_fields):
                            order = sort_order_values[i] if sort_order_values[i] in ("ASC", "DESC") else "ASC"
                            order_clauses.append(
                                sql.SQL("{} {}").format(sql.Identifier(field), sql.SQL(order))
                            )
                        query += sql.SQL(" ORDER BY ") + sql.SQL(", ").join(order_clauses)
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



    def upsert_records(self, table_name: str, records: list, exclude_none: bool = True) -> tuple:
        """
        Generic method for upserting records into any table.
        
        Args:
            table_name: Name of the table to upsert into
            records: List of tuples (key_fields_dict, update_fields_dict) where:
                - key_fields_dict: Dictionary of fields to locate the record (can be empty/None for insert-only)
                - update_fields_dict: Dictionary of fields to update/insert
            exclude_none: If True (default), automatically filters out None values from key_fields and update_fields.
                         If False, None values are preserved and passed to the database as NULL.
        
        Note:
            By default (exclude_none=True), None values are automatically filtered out, allowing partial updates.
            Set exclude_none=False to explicitly set fields to NULL in the database.
        
        Returns:
            Tuple of (successful_ids, errors) where:
                - successful_ids: List of IDs that were successfully upserted
                - errors: List of dicts with error details {'key_fields': {...}, 'update_fields': {...}, 'error': '...', 'id': ...}
        
        Example:
            # Update existing users by email, or insert if not found
            users = [
                ({'email': 'user@example.com'}, {'username': 'john', 'authorizations': 'admin'}),
                ({'email': 'other@example.com'}, {'username': 'jane', 'authorizations': 'contributor'})
            ]
            successful_ids, errors = db_service.upsert_records('users', users)
            
            # Insert new records without key fields
            new_games = [
                ({}, {'title': 'Chess', 'min_players': 2, 'max_players': 2}),
                ({}, {'title': 'Poker', 'min_players': 2, 'max_players': 8})
            ]
            successful_ids, errors = db_service.upsert_records('games', new_games)
        """
        successful_ids = []
        errors = []
        
        conn = self.get_connection()
        
        for record_tuple in records:
            try:
                # Validate record format
                if not isinstance(record_tuple, tuple) or len(record_tuple) != 2:
                    errors.append({
                        'record': record_tuple,
                        'error': 'Record must be a tuple of (key_fields_dict, update_fields_dict)',
                        'id': None
                    })
                    continue
                
                key_fields, update_fields = record_tuple
                
                # Conditionally filter out None values based on exclude_none parameter
                if exclude_none:
                    key_fields = {k: v for k, v in (key_fields or {}).items() if v is not None}
                    update_fields = {k: v for k, v in (update_fields or {}).items() if v is not None}
                else:
                    # Ensure we have valid dictionaries even if None was passed
                    key_fields = key_fields or {}
                    update_fields = update_fields or {}
                
                # Validate that update_fields is not empty
                if not update_fields:
                    errors.append({
                        'key_fields': key_fields,
                        'update_fields': update_fields,
                        'error': 'update_fields cannot be empty',
                        'id': None
                    })
                    continue
                
                with conn.cursor() as cursor:
                    record_id = None
                    
                    # If key_fields provided, try to find existing record
                    if key_fields:
                        # Build WHERE clause from key_fields
                        where_conditions = sql.SQL(' AND ').join([
                            sql.SQL("{} = {}").format(
                                sql.Identifier(key),
                                sql.Placeholder()
                            ) for key in key_fields.keys()
                        ])
                        
                        select_query = sql.SQL("SELECT id FROM {} WHERE {}").format(
                            sql.Identifier(table_name),
                            where_conditions
                        )
                        
                        cursor.execute(select_query, list(key_fields.values()))
                        result = cursor.fetchone()
                        
                        if result:
                            # Record exists, UPDATE it
                            record_id = result[0]
                            
                            # Build SET clause from update_fields
                            set_clause = sql.SQL(', ').join([
                                sql.SQL("{} = {}").format(
                                    sql.Identifier(key),
                                    sql.Placeholder()
                                ) for key in update_fields.keys()
                            ])
                            
                            update_query = sql.SQL("UPDATE {} SET {} WHERE id = {}").format(
                                sql.Identifier(table_name),
                                set_clause,
                                sql.Placeholder()
                            )
                            
                            cursor.execute(
                                update_query,
                                list(update_fields.values()) + [record_id]
                            )
                            
                            if cursor.rowcount == 0:
                                errors.append({
                                    'key_fields': key_fields,
                                    'update_fields': update_fields,
                                    'error': f'Update failed: No record with id {record_id} was updated',
                                    'id': record_id
                                })
                                conn.rollback()
                                continue
                            
                            conn.commit()
                            successful_ids.append(record_id)
                            self.logger.info(f"Updated record in {table_name} with ID {record_id}")
                        else:
                            # Record doesn't exist, INSERT with both key_fields and update_fields
                            combined_fields = {**key_fields, **update_fields}
                            
                            columns = sql.SQL(', ').join([
                                sql.Identifier(key) for key in combined_fields.keys()
                            ])
                            
                            placeholders = sql.SQL(', ').join([
                                sql.Placeholder() for _ in combined_fields
                            ])
                            
                            insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
                                sql.Identifier(table_name),
                                columns,
                                placeholders
                            )
                            
                            cursor.execute(insert_query, list(combined_fields.values()))
                            record_id = cursor.fetchone()[0]
                            conn.commit()
                            successful_ids.append(record_id)
                            self.logger.info(f"Inserted new record in {table_name} with ID {record_id}")
                    else:
                        # No key_fields, just INSERT with update_fields
                        columns = sql.SQL(', ').join([
                            sql.Identifier(key) for key in update_fields.keys()
                        ])
                        
                        placeholders = sql.SQL(', ').join([
                            sql.Placeholder() for _ in update_fields
                        ])
                        
                        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
                            sql.Identifier(table_name),
                            columns,
                            placeholders
                        )
                        
                        cursor.execute(insert_query, list(update_fields.values()))
                        record_id = cursor.fetchone()[0]
                        conn.commit()
                        successful_ids.append(record_id)
                        self.logger.info(f"Inserted new record in {table_name} with ID {record_id}")
                        
            except psycopg2.Error as e:
                conn.rollback()
                error_detail = {
                    'key_fields': key_fields if 'key_fields' in locals() else None,
                    'update_fields': update_fields if 'update_fields' in locals() else None,
                    'error': str(e),
                    'id': record_id if 'record_id' in locals() else None
                }
                errors.append(error_detail)
                self.logger.error(f"Error upserting record in {table_name}: {e}", exc_info=True)
            except Exception as e:
                conn.rollback()
                error_detail = {
                    'key_fields': key_fields if 'key_fields' in locals() else None,
                    'update_fields': update_fields if 'update_fields' in locals() else None,
                    'error': str(e),
                    'id': None
                }
                errors.append(error_detail)
                self.logger.error(f"Unexpected error upserting record in {table_name}: {e}", exc_info=True)
        
        conn.close()
        return (successful_ids, errors)
    
    def delete_records(self, table_name: str, records: list) -> tuple:
        """
        Generic method for deleting records from any table.
        
        Args:
            table_name: Name of the table to delete from
            records: List of record identifiers, where each can be:
                - int: The ID of the record to delete
                - dict: Key-value pairs to identify the record (e.g., {'email': 'user@example.com'})
        
        Returns:
            Tuple of (successful_ids, errors) where:
                - successful_ids: List of IDs that were successfully deleted
                - errors: List of dicts with error details {'identifier': ..., 'error': '...', 'id': ...}
        
        Example:
            # Delete users by ID
            successful_ids, errors = db_service.delete_records('users', [1, 5, 10])
            
            # Delete users by email
            successful_ids, errors = db_service.delete_records('users', [
                {'email': 'user@example.com'},
                {'email': 'other@example.com'}
            ])
            
            # Delete games by title and owner
            successful_ids, errors = db_service.delete_records('games', [
                {'title': 'Chess', 'owner': 'John'}
            ])
        """
        successful_ids = []
        errors = []
        
        conn = self.get_connection()
        
        for identifier in records:
            record_id = None
            try:
                with conn.cursor() as cursor:
                    # Handle integer ID directly
                    if isinstance(identifier, int):
                        record_id = identifier
                        
                        delete_query = sql.SQL("DELETE FROM {} WHERE id = {}").format(
                            sql.Identifier(table_name),
                            sql.Placeholder()
                        )
                        
                        cursor.execute(delete_query, [record_id])
                        
                        if cursor.rowcount == 0:
                            errors.append({
                                'identifier': identifier,
                                'error': f'No record found with id {record_id}',
                                'id': record_id
                            })
                            conn.rollback()
                            continue
                        
                        conn.commit()
                        successful_ids.append(record_id)
                        self.logger.info(f"Deleted record from {table_name} with ID {record_id}")
                    
                    # Handle dictionary of key fields
                    elif isinstance(identifier, dict):
                        if not identifier:
                            errors.append({
                                'identifier': identifier,
                                'error': 'Identifier dictionary cannot be empty',
                                'id': None
                            })
                            continue
                        
                        # First, find the record ID
                        where_conditions = sql.SQL(' AND ').join([
                            sql.SQL("{} = {}").format(
                                sql.Identifier(key),
                                sql.Placeholder()
                            ) for key in identifier.keys()
                        ])
                        
                        select_query = sql.SQL("SELECT id FROM {} WHERE {}").format(
                            sql.Identifier(table_name),
                            where_conditions
                        )
                        
                        cursor.execute(select_query, list(identifier.values()))
                        result = cursor.fetchone()
                        
                        if not result:
                            errors.append({
                                'identifier': identifier,
                                'error': f'No record found matching criteria: {identifier}',
                                'id': None
                            })
                            conn.rollback()
                            continue
                        
                        record_id = result[0]
                        
                        # Delete the record
                        delete_query = sql.SQL("DELETE FROM {} WHERE id = {}").format(
                            sql.Identifier(table_name),
                            sql.Placeholder()
                        )
                        
                        cursor.execute(delete_query, [record_id])
                        
                        if cursor.rowcount == 0:
                            errors.append({
                                'identifier': identifier,
                                'error': f'Delete failed: No record with id {record_id} was deleted',
                                'id': record_id
                            })
                            conn.rollback()
                            continue
                        
                        conn.commit()
                        successful_ids.append(record_id)
                        self.logger.info(f"Deleted record from {table_name} with ID {record_id}")
                    
                    else:
                        errors.append({
                            'identifier': identifier,
                            'error': f'Invalid identifier type: {type(identifier).__name__}. Must be int or dict',
                            'id': None
                        })
                        continue
                        
            except psycopg2.Error as e:
                conn.rollback()
                error_detail = {
                    'identifier': identifier,
                    'error': str(e),
                    'id': record_id if record_id else None
                }
                errors.append(error_detail)
                self.logger.error(f"Error deleting record from {table_name}: {e}", exc_info=True)
            except Exception as e:
                conn.rollback()
                error_detail = {
                    'identifier': identifier,
                    'error': str(e),
                    'id': None
                }
                errors.append(error_detail)
                self.logger.error(f"Unexpected error deleting record from {table_name}: {e}", exc_info=True)
        
        conn.close()
        return (successful_ids, errors)
