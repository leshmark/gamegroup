from browser import ajax, document, window, timer
import json
from config import BASE_URL


class GameLibraryUpdater:
    """Handles updating game data from BoardGameGeek"""

    def __init__(self):
        document["refresh-game-data-btn"].bind("click", self.refresh_game_data)

    def refresh_game_data(self, event):
        """Handle refresh game data button click.

        Fetches all games with a BGG link and calls the add-game-by-bgg-link route
        for each one with a 10-second delay between calls.
        """
        event.preventDefault()

        update_btn = document["refresh-game-data-btn"]
        status_div = document["refresh-game-data-status"]
        results_div = document["refresh-game-data-results"]

        update_btn.disabled = True
        update_btn.text = "Updating..."
        status_div.innerHTML = "<p>Fetching all games from database...</p>"
        status_div.className = "message info"
        results_div.innerHTML = ""

        auth_token = window.localStorage.getItem("auth_token")

        filter_str = window.encodeURIComponent(
            "bgg_link IS NOT NULL AND bgg_link != ''"
        )

        def on_games_fetched(req):
            if req.status != 200:
                error_msg = "Unknown error"
                try:
                    error_msg = json.loads(req.text).get("detail", error_msg)
                except Exception:
                    pass
                status_div.innerHTML = f"<p>Failed to fetch games: {error_msg}</p>"
                status_div.className = "message error"
                update_btn.disabled = False
                update_btn.text = "Refresh Game Data"
                return

            data = json.loads(req.text)
            games = data.get("games", [])

            if not games:
                status_div.innerHTML = "<p>No games with a BGG link found in the database.</p>"
                status_div.className = "message info"
                update_btn.disabled = False
                update_btn.text = "Refresh Game Data"
                return

            total = len(games)
            results = []

            def render_results():
                successful = sum(1 for r in results if r["status"] == "success")
                failed = sum(1 for r in results if r["status"] == "failed")
                status_html = f"""
                <h4>Refresh Complete</h4>
                <p><strong>Total games processed:</strong> {total}</p>
                <p><strong>Successfully updated:</strong> <span style="color: #27ae60;">{successful}</span></p>
                <p><strong>Failed:</strong> <span style="color: #e74c3c;">{failed}</span></p>
                """
                status_div.innerHTML = status_html
                status_div.className = "message success"

                results_html = '<h4>Detailed Results</h4><div class="results-list">'
                for result in results:
                    status_icon = "\u2713" if result["status"] == "success" else "\u2717"
                    status_color = "#27ae60" if result["status"] == "success" else "#e74c3c"
                    results_html += f"""
                    <div class="result-item" style="margin-bottom: 10px; padding: 10px; border-left: 3px solid {status_color};">
                        <p style="margin: 0;"><strong style="color: {status_color};">{status_icon}</strong> <strong>{result["title"]}</strong> (ID: {result["id"]})</p>
                    """
                    if result["status"] == "success":
                        results_html += '<p style="margin: 5px 0 0 0; font-size: 0.9em; color: #7f8c8d;">Game data refreshed successfully</p>'
                    else:
                        results_html += f'<p style="margin: 5px 0 0 0; font-size: 0.9em; color: #e74c3c;">Error: {result.get("error", "Unknown error")}</p>'
                    results_html += "</div>"
                results_html += "</div>"
                results_div.innerHTML = results_html

            def process_game(index):
                if index >= total:
                    update_btn.disabled = False
                    update_btn.text = "Refresh Game Data"
                    render_results()
                    return

                game = games[index]
                status_div.innerHTML = f"<p>Processing game {index + 1}/{total}: {game['title']}...</p>"
                status_div.className = "message info"

                def on_game_updated(req):
                    if req.status == 200:
                        results.append({"id": game["id"], "title": game["title"], "status": "success"})
                    else:
                        error_msg = "Unknown error"
                        try:
                            error_msg = json.loads(req.text).get("detail", error_msg)
                        except Exception:
                            pass
                        results.append({"id": game["id"], "title": game["title"], "status": "failed", "error": error_msg})

                    if index < total - 1:
                        timer.set_timeout(lambda: process_game(index + 1), 10000)
                    else:
                        process_game(index + 1)

                token = window.localStorage.getItem("auth_token")
                game_req = ajax.Ajax()
                game_req.bind("complete", on_game_updated)
                game_req.open("POST", f"{BASE_URL}/api/v1/game/action/add-game-by-bgg-link", True)
                game_req.set_header("Authorization", f"Bearer {token}")
                game_req.set_header("Content-Type", "application/json")
                game_req.send(json.dumps({"bgg_url": game["bgg_link"], "owner": game["owner"]}))

            process_game(0)

        fetch_req = ajax.Ajax()
        fetch_req.bind("complete", on_games_fetched)
        fetch_req.open(
            "GET",
            f"{BASE_URL}/api/v1/game?limit=1000&filter_criteria={filter_str}",
            True,
        )
        fetch_req.set_header("Authorization", f"Bearer {auth_token}")
        fetch_req.send()
