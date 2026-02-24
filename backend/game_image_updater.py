from typing import Dict
from db_utils import DatabaseService
from bgg_scraper import BGGScraper


class GameImageUpdater:
    """Handles bulk updating of game images from BoardGameGeek"""

    def __init__(self, db_service: DatabaseService, bgg_scraper: BGGScraper):
        self.db_service = db_service
        self.bgg_scraper = bgg_scraper
        self.max_failures = 5

    def update_game_image_url(self, game_id: int, image_url: str):
        """
        Update the image_url for a specific game

        Args:
            game_id: The ID of the game to update
            image_url: The new image URL
        """
        # Use upsert to update the game record
        records = [
            (
                {"id": game_id},  # key_fields - identifies the record by id
                {"image_url": image_url},  # update_fields
            )
        ]

        successful_ids, errors = self.db_service.upsert_records("games", records)

        if errors:
            raise ValueError(f"Failed to update game image: {errors[0]['error']}")

    def update_missing_images(self) -> Dict[str, any]:
        """
        Update missing game image URLs from BoardGameGeek.

        Returns:
            Dict containing message, statistics, and results for each game processed
        """
        # Get all games missing image URLs
        games = self.db_service.read_table(
            table_name="games",
            columns=["id", "title", "bgg_link"],
            filter_criteria="bgg_link IS NOT NULL AND bgg_link != '' AND (image_url IS NULL OR image_url = '')",
            sort_by="id",
            sort_order="ASC",
        )

        if not games:
            return {
                "message": "No games with missing images found",
                "total": 0,
                "successful": 0,
                "failed": 0,
                "results": [],
            }

        results = []
        successful = 0
        failed = 0
        aborted = False

        # Process each game
        for game in games:
            # Abort if failure count reaches threshold
            if failed >= self.max_failures:
                aborted = True
                break

            result = {
                "id": game["id"],
                "title": game["title"],
                "bgg_link": game["bgg_link"],
                "status": "pending",
            }

            try:
                # Fetch image URL from BGG
                image_url = self.bgg_scraper.get_game_image_url(game["bgg_link"])

                if image_url:
                    # Update database
                    self.update_game_image_url(game["id"], image_url)
                    result["status"] = "success"
                    result["image_url"] = image_url
                    successful += 1
                else:
                    result["status"] = "failed"
                    result["error"] = "No image found on BGG page"
                    failed += 1

            except ValueError as e:
                result["status"] = "failed"
                result["error"] = str(e)
                failed += 1
            except Exception as e:
                result["status"] = "failed"
                result["error"] = f"Error: {str(e)}"
                failed += 1

            results.append(result)

        message = "Image update process completed"
        if aborted:
            message = f"Image update process aborted after {self.max_failures} failures"

        return {
            "message": message,
            "total": len(games),
            "processed": len(results),
            "successful": successful,
            "failed": failed,
            "aborted": aborted,
            "results": results,
        }
