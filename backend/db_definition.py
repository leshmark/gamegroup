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
        # external_id columns must exist before the junction tables reference
        # games(external_id) and before the legacy-column migrations run.
        self.add_external_id_columns_if_missing()
        # Game groups (seeded before the game_group_id backfill so legacy rows
        # land in the Default group deterministically).
        self.create_game_groups_table()
        self.Initialize_game_groups_table()
        self.create_game_group_users_table()
        self.create_game_votes_table()
        self.create_game_night_sessions_table()
        self.create_game_night_comments_table()
        self.create_games_users_table()
        self.migrate_game_votes_to_external_game_ref()
        self.drop_game_votes_fk_if_exists()
        self.migrate_games_played_to_external_ids()
        self.migrate_timestamp_columns_to_timestamptz()
        # game_group_id soft-link columns + backfill existing rows to Default.
        default_group_id = self.get_default_game_group_id()
        self.add_game_group_id_columns_if_missing(default_group_id)
        # Move owner / contributor_email / favorited_by off games into games_users.
        self.migrate_game_user_links_to_games_users()
        # Read-compatibility view exposing the moved user fields alongside games.
        self.create_games_with_users_view()
        self.logger.info("Database schema initialization complete.")

    def create_auth_links_table(self):
        """Create the auth_links table for storing one-time authentication tokens"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS auth_links (
            id SERIAL PRIMARY KEY,
            external_id UUID NOT NULL UNIQUE DEFAULT uuidv7(),
            token VARCHAR(255) UNIQUE NOT NULL,
            email VARCHAR(255) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMPTZ NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            used_at TIMESTAMPTZ,
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
            external_id UUID NOT NULL UNIQUE DEFAULT uuidv7(),
            title VARCHAR(255) NOT NULL,
            min_players INTEGER NOT NULL,
            max_players INTEGER NOT NULL,
            description TEXT,
            short_description VARCHAR(2000),
            tags TEXT[],
            image_url VARCHAR(25000),
            bgg_link VARCHAR(500),
            rules_link VARCHAR(500),
            bgg_rating DECIMAL(3, 2) DEFAULT 0.0,
            last_played_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP

        );
        
        CREATE INDEX IF NOT EXISTS idx_games_title ON games(title);
        CREATE INDEX IF NOT EXISTS idx_games_bgg_link ON games(bgg_link);
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
            external_id UUID NOT NULL UNIQUE DEFAULT uuidv7(),
            bgg_id INTEGER UNIQUE NOT NULL,
            title VARCHAR(255) NOT NULL,
            json_data TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
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
            external_id UUID NOT NULL UNIQUE DEFAULT uuidv7(),
            username VARCHAR(255) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            authorizations TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
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
            external_id UUID NOT NULL UNIQUE DEFAULT uuidv7(),
            game_external_id UUID NOT NULL,
            user_email VARCHAR(255) NOT NULL,
            vote INTEGER NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_game_votes_user_email ON game_votes(user_email);
        CREATE INDEX IF NOT EXISTS idx_game_votes_created_at ON game_votes(created_at);
        """

        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                # On a pre-existing (legacy) game_votes table the CREATE TABLE is a
                # no-op and game_external_id does not exist yet, so only build this
                # index once the column is present.  The migration below creates it
                # when it converts the legacy game_id reference.
                cursor.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'game_votes'
                      AND column_name = 'game_external_id'
                    """
                )
                if cursor.fetchone():
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_game_votes_game_external_id "
                        "ON game_votes(game_external_id)"
                    )
                conn.commit()
                self.logger.info("game_votes table created successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error creating game_votes table: {e}", exc_info=True)
            raise
        finally:
            conn.close()

    def create_game_night_sessions_table(self):
        """Create the game_night_sessions table for recording when games were played"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS game_night_sessions (
            id SERIAL PRIMARY KEY,
            external_id UUID NOT NULL UNIQUE DEFAULT uuidv7(),
            session_date TIMESTAMPTZ NOT NULL,
            location VARCHAR(500),
            games_played UUID[],
            notes TEXT,
            logged_by VARCHAR(255) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_game_night_sessions_date ON game_night_sessions(session_date);
        CREATE INDEX IF NOT EXISTS idx_game_night_sessions_logged_by ON game_night_sessions(logged_by);
        """

        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                self.logger.info("game_night_sessions table created successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(
                f"Error creating game_night_sessions table: {e}", exc_info=True
            )
            raise
        finally:
            conn.close()

    def create_game_night_comments_table(self):
        """Create the game_night_comments table for upcoming session discussion posts"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS game_night_comments (
            id SERIAL PRIMARY KEY,
            external_id UUID NOT NULL UNIQUE DEFAULT uuidv7(),
            comment_text TEXT NOT NULL,
            author_email VARCHAR(255) NOT NULL,
            display_name VARCHAR(255) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_game_night_comments_author ON game_night_comments(author_email);
        CREATE INDEX IF NOT EXISTS idx_game_night_comments_created_at ON game_night_comments(created_at);
        """

        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                self.logger.info("game_night_comments table created successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(
                f"Error creating game_night_comments table: {e}", exc_info=True
            )
            raise
        finally:
            conn.close()

    def create_game_groups_table(self):
        """Create the game_groups table.

        ``game_groups`` is an addressable entity, so it keeps the
        ``id SERIAL`` + ``external_id`` (uuidv7) pattern used by every other
        entity table.  There is deliberately no ``is_default`` flag: the Default
        group is just a row seeded by name (see Initialize_game_groups_table),
        and ``UNIQUE(name)`` makes that seed an idempotent upsert.
        """
        create_table_query = """
        CREATE TABLE IF NOT EXISTS game_groups (
            id SERIAL PRIMARY KEY,
            external_id UUID NOT NULL UNIQUE DEFAULT uuidv7(),
            name VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_game_groups_name ON game_groups(name);
        """

        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                self.logger.info("game_groups table created successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error creating game_groups table: {e}", exc_info=True)
            raise
        finally:
            conn.close()

    def Initialize_game_groups_table(self):
        """Seed the game_groups table with the Default group.

        Mirrors Initialize_users_table(): the group is looked up by its UNIQUE
        ``name``, so re-running initialize() never creates a duplicate.  The
        Default group is the deterministic home for pre-existing (global) votes,
        sessions and comments once add_game_group_id_columns_if_missing() runs.
        """
        groups = [
            (
                {"name": "Default"},  # key field to locate record (UNIQUE name)
                {"description": "Default game group for pre-existing records"},
            ),
        ]
        successful_ids, errors = self.db_service.upsert_records(
            "game_groups", groups
        )

        if errors:
            self.logger.warning(f"Errors during game group initialization: {errors}")

        self.logger.info(
            f"Initialized {len(successful_ids)} game groups successfully"
        )

    def get_default_game_group_id(self):
        """Return the internal id of the Default game group.

        Must be called after create_game_groups_table() +
        Initialize_game_groups_table(); the migration helper needs the id to
        backfill legacy rows deterministically.
        """
        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM game_groups WHERE name = %s", ("Default",)
                )
                row = cursor.fetchone()
                if not row:
                    raise RuntimeError(
                        "Default game group is missing; "
                        "Initialize_game_groups_table() must run first"
                    )
                return row[0]
        finally:
            conn.close()

    def create_game_group_users_table(self):
        """Create the game_group_users junction table (group membership).

        A membership row has no identity beyond the association, so there is no
        ``id``/``external_id`` surrogate: the composite primary key
        ``(game_group_id, user_email)`` *is* the identity and the dedup rule.
        ``game_group_id`` is a soft link to game_groups.id and ``user_email`` a
        soft link to users.email — no FK constraints anywhere.  Insert-or-delete
        only, so there is no ``updated_at``.
        """
        create_table_query = """
        CREATE TABLE IF NOT EXISTS game_group_users (
            game_group_id INTEGER NOT NULL,
            user_email VARCHAR(255) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (game_group_id, user_email)
        );

        CREATE INDEX IF NOT EXISTS idx_game_group_users_user_email
            ON game_group_users(user_email);
        """

        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                self.logger.info("game_group_users table created successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(
                f"Error creating game_group_users table: {e}", exc_info=True
            )
            raise
        finally:
            conn.close()

    def create_games_users_table(self):
        """Create the games_users junction table (game <-> user associations).

        Composite primary key ``(game_external_id, user_email, role)`` with no
        surrogate id/external_id.  ``role`` absorbs the user links that used to
        be denormalized on ``games`` (owner / contributor_email / favorited_by[]),
        so one user can be owner AND contributor AND have favorited the same
        game.  There is no game_group_id: an association applies across groups.
        """
        create_table_query = """
        CREATE TABLE IF NOT EXISTS games_users (
            game_external_id UUID NOT NULL,
            user_email VARCHAR(255) NOT NULL,
            role VARCHAR(32) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (game_external_id, user_email, role),
            CONSTRAINT chk_games_users_role
                CHECK (role IN ('owner', 'contributor', 'favorite'))
        );

        CREATE INDEX IF NOT EXISTS idx_games_users_user_email
            ON games_users(user_email);
        CREATE INDEX IF NOT EXISTS idx_games_users_role
            ON games_users(game_external_id, role);
        """

        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                self.logger.info("games_users table created successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(
                f"Error creating games_users table: {e}", exc_info=True
            )
            raise
        finally:
            conn.close()

    def drop_game_votes_fk_if_exists(self):
        """Drop the legacy ``fk_game`` FK on game_votes (Next ERD note 1).

        All cross-table relationships are soft links now, so PostgreSQL
        enforces no referential integrity and deleting a game no longer
        cascades — GameRouter deletes dependent rows in code instead.
        Idempotent: ``DROP CONSTRAINT IF EXISTS`` is a no-op when absent.
        """
        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("ALTER TABLE game_votes DROP CONSTRAINT IF EXISTS fk_game")
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(f"Error dropping game_votes fk_game: {e}", exc_info=True)
            raise
        finally:
            conn.close()

    def add_game_group_id_columns_if_missing(self, default_group_id: int):
        """Add the ``game_group_id`` soft-link column to the three Game Night
        tables and backfill existing (global) rows with the Default group's id.

        Mirrors add_pin_hash_column_if_missing().  The default group id is
        passed in as a parameter rather than discovered via an is_default flag,
        so legacy rows land in Default deterministically.  The column is left
        with a DEFAULT of the Default group id so that existing inserts (which
        predate group functionality) keep working and land in Default; per-group
        selection is out of scope for this change.
        """
        tables = ["game_votes", "game_night_sessions", "game_night_comments"]

        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                for table in tables:
                    cursor.execute(
                        f"""
                        ALTER TABLE {table}
                        ADD COLUMN IF NOT EXISTS game_group_id INTEGER
                        """
                    )
                    cursor.execute(
                        f"""
                        UPDATE {table}
                        SET game_group_id = %s
                        WHERE game_group_id IS NULL
                        """,
                        (default_group_id,),
                    )
                    cursor.execute(
                        f"""
                        ALTER TABLE {table}
                        ALTER COLUMN game_group_id SET DEFAULT {int(default_group_id)}
                        """
                    )
                    cursor.execute(
                        f"""
                        ALTER TABLE {table}
                        ALTER COLUMN game_group_id SET NOT NULL
                        """
                    )
                    cursor.execute(
                        f"""
                        CREATE INDEX IF NOT EXISTS idx_{table}_game_group_id
                        ON {table}(game_group_id)
                        """
                    )
                    self.logger.info(f"game_group_id column ensured on {table} table")

                # One vote per user per game per group.  Vote toggling used to be
                # a read-then-insert race in vote_service, so legacy data can hold
                # duplicate rows for the same (group, user, game); collapse those
                # to the most recent vote before the UNIQUE can be created.
                cursor.execute(
                    """
                    DELETE FROM game_votes v
                    USING game_votes newer
                    WHERE newer.game_group_id = v.game_group_id
                      AND newer.user_email = v.user_email
                      AND newer.game_external_id = v.game_external_id
                      AND (newer.created_at, newer.id) > (v.created_at, v.id)
                    """
                )
                collapsed = cursor.rowcount
                if collapsed:
                    self.logger.info(
                        f"Collapsed {collapsed} duplicate game_votes rows before "
                        "adding the group/user/game UNIQUE constraint"
                    )
                cursor.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS
                        idx_game_votes_group_user_game
                        ON game_votes(game_group_id, user_email, game_external_id)
                    """
                )
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(
                f"Error adding game_group_id columns: {e}", exc_info=True
            )
            raise
        finally:
            conn.close()

    def migrate_game_user_links_to_games_users(self):
        """Move the user links off ``games`` into the ``games_users`` junction table.

        Backfills one row per (game, user, role) from the legacy columns —
        ``owner`` → role 'owner', ``contributor_email`` → role 'contributor',
        ``unnest(favorited_by)`` → role 'favorite' — then drops the legacy
        columns and their indexes, leaving ``games`` with no user columns at all.

        Idempotent: guarded on the legacy ``owner`` column still existing.
        """
        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'games'
                      AND column_name = 'owner'
                    """
                )
                if not cursor.fetchone():
                    return

                cursor.execute(
                    """
                    INSERT INTO games_users (game_external_id, user_email, role)
                    SELECT external_id, owner, 'owner'
                    FROM games
                    WHERE owner IS NOT NULL AND owner <> ''
                    ON CONFLICT (game_external_id, user_email, role) DO NOTHING
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO games_users (game_external_id, user_email, role)
                    SELECT external_id, contributor_email, 'contributor'
                    FROM games
                    WHERE contributor_email IS NOT NULL AND contributor_email <> ''
                    ON CONFLICT (game_external_id, user_email, role) DO NOTHING
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO games_users (game_external_id, user_email, role)
                    SELECT g.external_id, fav.email, 'favorite'
                    FROM games g
                    CROSS JOIN LATERAL unnest(g.favorited_by) AS fav(email)
                    WHERE fav.email IS NOT NULL AND fav.email <> ''
                    ON CONFLICT (game_external_id, user_email, role) DO NOTHING
                    """
                )

                cursor.execute(
                    """
                    ALTER TABLE games
                        DROP COLUMN IF EXISTS owner,
                        DROP COLUMN IF EXISTS contributor_email,
                        DROP COLUMN IF EXISTS favorited_by
                    """
                )
                cursor.execute("DROP INDEX IF EXISTS idx_games_owner")
                cursor.execute("DROP INDEX IF EXISTS idx_games_contributor")
                conn.commit()
                self.logger.info(
                    "Migrated games.owner/contributor_email/favorited_by into games_users"
                )
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(
                f"Error migrating game user links to games_users: {e}", exc_info=True
            )
            raise
        finally:
            conn.close()

    def create_games_with_users_view(self):
        """Create/replace the ``games_with_users`` read view.

        ``games`` no longer stores owner / contributor_email / favorited_by, so
        the read side of the REST layer resolves them from ``games_users`` here.
        The view keeps the existing API shape (scalar ``owner`` /
        ``contributor_email``, array ``favorited_by`` / ``contributors``) while
        the junction table stays the single source of truth.  Reads go through
        the view; writes still target ``games`` + ``games_users`` directly.
        """
        create_view_query = """
        CREATE OR REPLACE VIEW games_with_users AS
        SELECT
            g.*,
            (
                SELECT gu.user_email
                FROM games_users gu
                WHERE gu.game_external_id = g.external_id
                  AND gu.role = 'owner'
                ORDER BY gu.created_at, gu.user_email
                LIMIT 1
            ) AS owner,
            (
                SELECT array_agg(gu.user_email ORDER BY gu.created_at, gu.user_email)
                FROM games_users gu
                WHERE gu.game_external_id = g.external_id
                  AND gu.role = 'favorite'
            ) AS favorited_by,
            (
                SELECT array_agg(gu.user_email ORDER BY gu.created_at, gu.user_email)
                FROM games_users gu
                WHERE gu.game_external_id = g.external_id
                  AND gu.role = 'contributor'
            ) AS contributors,
            (
                SELECT gu.user_email
                FROM games_users gu
                WHERE gu.game_external_id = g.external_id
                  AND gu.role = 'contributor'
                ORDER BY gu.created_at DESC, gu.user_email
                LIMIT 1
            ) AS contributor_email
        FROM games g
        """

        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(create_view_query)
                conn.commit()
                self.logger.info("games_with_users view created successfully")
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(
                f"Error creating games_with_users view: {e}", exc_info=True
            )
            raise
        finally:
            conn.close()

    def add_external_id_columns_if_missing(self):
        """Add GUID7 external_id columns to all tables (migration).

        The internal SERIAL ``id`` stays the primary key and FK target; the
        ``external_id`` UUID (generated with Postgres 18's ``uuidv7()``) is the
        identifier exposed by the REST API.  ``ADD COLUMN ... NOT NULL DEFAULT
        uuidv7()`` backfills existing rows automatically.
        """
        tables = [
            "auth_links",
            "users",
            "games",
            "games_json",
            "game_votes",
            "game_night_sessions",
            "game_night_comments",
        ]
        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                for table in tables:
                    cursor.execute(
                        f"""
                        ALTER TABLE {table}
                        ADD COLUMN IF NOT EXISTS external_id UUID NOT NULL
                            DEFAULT uuidv7();
                        CREATE UNIQUE INDEX IF NOT EXISTS
                            idx_{table}_external_id
                            ON {table}(external_id);
                        """
                    )
                    self.logger.info(f"external_id column ensured on {table} table")
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(
                f"Error adding external_id columns: {e}", exc_info=True
            )
            raise
        finally:
            conn.close()

    def migrate_game_votes_to_external_game_ref(self):
        """Convert game_votes.game_id (internal INTEGER FK) to game_external_id (UUID FK).

        Idempotent: runs only while the legacy ``game_id`` column still exists.
        Existing votes are backfilled from the joined game's external_id, then the
        legacy column, its FK and its index are dropped.
        """
        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'game_votes'
                      AND column_name = 'game_id'
                    """
                )
                if not cursor.fetchone():
                    return

                cursor.execute(
                    """
                    ALTER TABLE game_votes
                        ADD COLUMN IF NOT EXISTS game_external_id UUID;

                    UPDATE game_votes v
                    SET game_external_id = g.external_id
                    FROM games g
                    WHERE g.id = v.game_id
                      AND v.game_external_id IS NULL;

                    ALTER TABLE game_votes
                        ALTER COLUMN game_external_id SET NOT NULL;

                    ALTER TABLE game_votes DROP CONSTRAINT IF EXISTS fk_game;
                    ALTER TABLE game_votes DROP COLUMN IF EXISTS game_id;
                    DROP INDEX IF EXISTS idx_game_votes_game_id;

                    CREATE INDEX IF NOT EXISTS
                        idx_game_votes_game_external_id
                        ON game_votes(game_external_id);
                    """
                )
                conn.commit()
                self.logger.info(
                    "Migrated game_votes.game_id to game_external_id (UUID)"
                )
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(
                f"Error migrating game_votes game reference to external_id: {e}",
                exc_info=True,
            )
            raise
        finally:
            conn.close()

    def migrate_games_played_to_external_ids(self):
        """Convert game_night_sessions.games_played from INTEGER[] (internal game
        ids) to UUID[] (external game ids), preserving element order.

        Idempotent: runs only while the column is still an integer array.
        """
        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT udt_name FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'game_night_sessions'
                      AND column_name = 'games_played'
                    """
                )
                row = cursor.fetchone()
                if not row or row[0] != "_int4":
                    return

                cursor.execute(
                    """
                    ALTER TABLE game_night_sessions
                        ADD COLUMN IF NOT EXISTS games_played_external UUID[];

                    UPDATE game_night_sessions s
                    SET games_played_external = (
                        SELECT array_agg(g.external_id ORDER BY played.ord)
                        FROM unnest(s.games_played)
                            WITH ORDINALITY AS played(gid, ord)
                        JOIN games g ON g.id = played.gid
                    )
                    WHERE s.games_played IS NOT NULL;

                    ALTER TABLE game_night_sessions
                        DROP COLUMN IF EXISTS games_played;
                    ALTER TABLE game_night_sessions
                        RENAME COLUMN games_played_external TO games_played;
                    """
                )
                conn.commit()
                self.logger.info(
                    "Migrated game_night_sessions.games_played to UUID[] external ids"
                )
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(
                f"Error migrating games_played to external ids: {e}", exc_info=True
            )
            raise
        finally:
            conn.close()

    def migrate_timestamp_columns_to_timestamptz(self):
        """Migrate any legacy TIMESTAMP (without time zone) columns to TIMESTAMPTZ.

        Existing naive values are assumed to already represent UTC wall-clock
        time (the app's connections pin session timezone to UTC), so the
        conversion preserves the same instant while making it unambiguous.
        """
        columns_by_table = {
            "auth_links": ["created_at", "expires_at", "used_at"],
            "games": ["last_played_at", "created_at", "updated_at"],
            "games_json": ["created_at", "updated_at"],
            "users": ["created_at", "updated_at"],
            "game_votes": ["created_at"],
            "game_night_sessions": ["session_date", "created_at", "updated_at"],
            "game_night_comments": ["created_at"],
        }

        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND data_type = 'timestamp without time zone'
                    """
                )
                naive_columns = {(row[0], row[1]) for row in cursor.fetchall()}

                for table, columns in columns_by_table.items():
                    for column in columns:
                        if (table, column) not in naive_columns:
                            continue
                        cursor.execute(
                            f"""
                            ALTER TABLE {table}
                            ALTER COLUMN {column} TYPE TIMESTAMPTZ
                            USING {column} AT TIME ZONE 'UTC'
                            """
                        )
                        self.logger.info(
                            f"Migrated {table}.{column} to TIMESTAMPTZ"
                        )
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            self.logger.error(
                f"Error migrating timestamp columns to TIMESTAMPTZ: {e}",
                exc_info=True,
            )
            raise
        finally:
            conn.close()
