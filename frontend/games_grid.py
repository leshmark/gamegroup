from browser import ajax, document, window
import json
from config import BASE_URL
from game_card import GameCard


class GamesGrid:
    """Handles games grid display, pagination, and sorting"""

    def __init__(self, user_login=None):
        """Initialize the games grid"""
        self.current_page = 1
        self.games_per_page = 20
        self.current_sort = "title"
        self.current_sort_order = "ASC"
        self.user_login = user_login

    def load_games(self, page: int = 1):
        """Fetch and display games from backend"""
        self.current_page = page
        offset = (page - 1) * self.games_per_page

        def on_complete(req):
            games_grid = document["games-grid"]
            games_count = document["games-count-text"]
            pagination_div_top = document["games-pagination-top"]
            pagination_div_bottom = document["games-pagination-bottom"]

            if req.status == 200:
                response = json.loads(req.text)
                games = response.get("games", [])
                total = response.get("total", 0)

                # Update count
                start = offset + 1 if games else 0
                end = offset + len(games)
                games_count.text = f"Showing {start}-{end} of {total} games"

                if not games:
                    games_grid.innerHTML = "<p>No games found in the library yet.</p>"
                    pagination_div_top.innerHTML = ""
                    pagination_div_bottom.innerHTML = ""
                    return

                # Check if user is admin
                is_admin = False
                if self.user_login and self.user_login.current_user_info:
                    is_admin = self.user_login.current_user_info.get("authorizations", {}).get("is_admin", False)

                # Create game cards
                cards_html = ""
                for game in games:
                    game_card = GameCard(game, is_admin)
                    cards_html += game_card.render()

                games_grid.innerHTML = cards_html

                # Bind card flip click events
                for card in document.select(".game-card"):
                    card.bind("click", self.handle_card_flip)

                # Bind delete button click events
                for delete_btn in document.select(".game-card-delete-btn"):
                    delete_btn.bind("click", self.delete_game)

                # Create pagination
                total_pages = (total + self.games_per_page - 1) // self.games_per_page
                self.render_pagination(total_pages, page, pagination_div_top)
                self.render_pagination(total_pages, page, pagination_div_bottom)

            else:
                games_grid.innerHTML = f"<p style='color: #e74c3c;'>Failed to load games. Status: {req.status}</p>"
                pagination_div_top.innerHTML = ""
                pagination_div_bottom.innerHTML = ""

            # Scroll to top of page after loading games
            window.scrollTo({"top": 0, "behavior": "smooth"})

        games_grid = document["games-grid"]
        games_grid.innerHTML = "<p>Loading games...</p>"

        # Build URL with parameters
        url = f"{BASE_URL}/api/game?limit={self.games_per_page}&offset={offset}"
        if self.current_sort:
            url += f"&sort_by={self.current_sort}"
        if self.current_sort_order:
            url += f"&sort_order={self.current_sort_order}"

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("GET", url, True)
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
        req.send()

    def render_pagination(self, total_pages, current_page, container):
        """Render pagination controls"""
        if total_pages <= 1:
            container.innerHTML = ""
            return

        html = ""

        # Previous button
        prev_disabled = "disabled" if current_page == 1 else ""
        html += f'<button class="pagination-btn" data-page="{current_page - 1}" {prev_disabled}>← Previous</button>'

        # Page numbers
        start_page = max(1, current_page - 2)
        end_page = min(total_pages, current_page + 2)

        if start_page > 1:
            html += '<button class="pagination-btn" data-page="1">1</button>'
            if start_page > 2:
                html += '<span class="pagination-info">...</span>'

        for i in range(start_page, end_page + 1):
            active_class = "active" if i == current_page else ""
            html += f'<button class="pagination-btn {active_class}" data-page="{i}">{i}</button>'

        if end_page < total_pages:
            if end_page < total_pages - 1:
                html += '<span class="pagination-info">...</span>'
            html += f'<button class="pagination-btn" data-page="{total_pages}">{total_pages}</button>'

        # Next button
        next_disabled = "disabled" if current_page == total_pages else ""
        html += f'<button class="pagination-btn" data-page="{current_page + 1}" {next_disabled}>Next →</button>'

        container.innerHTML = html

        # Bind click events to pagination buttons
        for btn in document.select(".pagination-btn"):
            btn.bind("click", self.handle_pagination_click)

    def handle_pagination_click(self, event):
        """Handle pagination button clicks"""
        if event.target.disabled:
            return
        page = int(event.target.getAttribute("data-page"))
        self.load_games(page)

    def handle_sort_change(self, event):
        """Handle sort selection change"""
        self.current_sort = event.target.value
        self.current_page = 1
        self.load_games(1)

    def handle_sort_direction_change(self, event):
        """Handle sort direction toggle"""
        self.current_sort_order = "DESC" if self.current_sort_order == "ASC" else "ASC"
        # Update button icon
        event.target.textContent = "▼" if self.current_sort_order == "DESC" else "▲"
        self.current_page = 1
        self.load_games(1)

    def handle_card_flip(self, event):
        """Handle card flip animation"""
        # Don't flip if clicking on links, buttons, or interactive elements
        target = event.target
        
        # Check if click is on a link or button
        if target.tagName in ["A", "BUTTON"]:
            return
        
        # Check if click is inside a link or button
        parent = target
        while parent and parent != event.currentTarget:
            if parent.tagName in ["A", "BUTTON"]:
                return
            parent = parent.parent
        
        # Toggle the flipped class on the card
        event.currentTarget.classList.toggle("flipped")

    def delete_game(self, event):
        """Handle game deletion"""
        event.stopPropagation()  # Prevent card click events
        
        game_id = event.target.getAttribute("data-game-id")
        
        if not game_id:
            return
        
        # Confirm deletion
        if not window.confirm(f"Are you sure you want to delete this game?"):
            return
        
        def on_complete(req):
            if req.status == 200:
                # Reload the current page
                self.load_games(self.current_page)
            else:
                window.alert(f"Failed to delete game. Status: {req.status}")
        
        # Send DELETE request
        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("DELETE", f"{BASE_URL}/api/game/{game_id}", True)
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
        req.send()
