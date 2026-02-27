import csv
import io
from typing import Dict
from fastapi import HTTPException, UploadFile
from db_utils import DatabaseService


class GamesUploader:
    """Handles bulk game uploads via CSV files"""

    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self.required_columns = ["title", "owner", "min_players", "max_players"]

    async def process_csv_upload(
        self, file: UploadFile, contributor_email: str
    ) -> Dict[str, any]:
        """
        Process a CSV file upload and add games to the database.

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

                # Add game to database
                self.db_service.add_game(
                    title=row["title"],
                    owner=row["owner"],
                    min_players=min_players,
                    max_players=max_players,
                    contributor_email=contributor_email,
                    description=row.get("description"),
                    short_description=row.get("short_description"),
                    tags=row.get("tags", "").split(",") if row.get("tags") else None,
                    image_url=row.get("image_url"),
                    bgg_link=row.get("bgg_link"),
                    bgg_rating=float(row["bgg_rating"])
                    if row.get("bgg_rating")
                    else None,
                )
                games_added += 1

            except ValueError as e:
                errors.append(f"Row {row_num}: Invalid data format - {str(e)}")
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        return {
            "message": "CSV processed successfully",
            "games_added": games_added,
            "errors": errors if errors else None,
        }
