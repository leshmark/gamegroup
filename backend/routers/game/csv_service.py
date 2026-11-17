import csv
import io
from typing import Dict, List
from fastapi import HTTPException, UploadFile
from database_service import DatabaseService
from .helpers import replace_games_users_role, add_games_users_contributor


class CSVService:
    """Handles bulk game uploads via CSV files"""

    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self.required_columns = ["title", "owner", "min_players", "max_players"]

    async def process_csv_upload(
        self, file: UploadFile, contributor_email: str
    ) -> Dict[str, any]:
        """
        Process a CSV file upload and add games to the database.

        The ``owner`` column lands in the ``games_users`` junction table (role
        'owner') rather than on the ``games`` row, which no longer has any user
        columns.  Rows are upserted keyed on ``title``.

        Args:
            file: The uploaded CSV file
            contributor_email: Email of the user uploading the games

        Returns:
            Dict containing message, games_added count, and any errors

        Raises:
            HTTPException: If file validation or processing fails
        """
        # Validate file type
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="File must be a CSV")

        # Read file content
        content = await file.read()
        decoded_content = content.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(decoded_content))

        # Validate required columns
        if not all(col in csv_reader.fieldnames for col in self.required_columns):
            raise HTTPException(
                status_code=400,
                detail=f"CSV must contain columns: {', '.join(self.required_columns)}",
            )

        # Process each row
        games_added = 0
        errors = []

        for row_num, row in enumerate(
            csv_reader, start=2
        ):  # start=2 because row 1 is header
            try:
                # Validate and convert data
                min_players = int(row["min_players"])
                max_players = int(row["max_players"])

                if min_players > max_players:
                    errors.append(
                        f"Row {row_num}: min_players cannot be greater than max_players"
                    )
                    continue

                data_fields = {
                    "title": row["title"],
                    "min_players": min_players,
                    "max_players": max_players,
                    "description": row.get("description") or None,
                    "short_description": row.get("short_description") or None,
                    "tags": (
                        [t.strip() for t in row["tags"].split(",") if t.strip()]
                        if row.get("tags")
                        else None
                    ),
                    "image_url": row.get("image_url") or None,
                    "bgg_link": row.get("bgg_link") or None,
                    "bgg_rating": float(row["bgg_rating"])
                    if row.get("bgg_rating")
                    else None,
                }

                successful_ids, upsert_errors = self.db_service.upsert_records(
                    "games", [({"title": row["title"]}, data_fields)]
                )
                if upsert_errors:
                    errors.append(f"Row {row_num}: {upsert_errors[0]['error']}")
                    continue

                game_id = successful_ids[0]
                if row.get("owner"):
                    replace_games_users_role(
                        self.db_service, game_id, "owner", [row["owner"]]
                    )
                add_games_users_contributor(
                    self.db_service, game_id, contributor_email
                )
                games_added += 1

            except ValueError as e:
                errors.append(f"Row {row_num}: Invalid data format - {str(e)}")
            except HTTPException as e:
                errors.append(f"Row {row_num}: {e.detail}")
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        return {
            "message": "CSV processed successfully",
            "games_added": games_added,
            "errors": errors if errors else None,
        }

    def generate_csv_download(self, games: List[Dict]) -> str:
        """
        Generate CSV content from a list of games.

        Args:
            games: List of game dictionaries from the database

        Returns:
            CSV content as a string
        """
        if not games:
            return ""

        # Define column order for CSV export (external GUID7 id, not internal PK)
        columns = [
            "external_id",
            "title",
            "owner",
            "min_players",
            "max_players",
            "description",
            "short_description",
            "tags",
            "image_url",
            "bgg_link",
            "bgg_rating",
            "created_at",
            "updated_at",
            "favorited_by",
        ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()

        for game in games:
            # Convert arrays to comma-separated strings for CSV
            game_copy = game.copy()
            if game_copy.get("tags") and isinstance(game_copy["tags"], list):
                game_copy["tags"] = ",".join(game_copy["tags"])
            if game_copy.get("favorited_by") and isinstance(game_copy["favorited_by"], list):
                game_copy["favorited_by"] = ",".join(game_copy["favorited_by"])
            
            writer.writerow(game_copy)

        return output.getvalue()
