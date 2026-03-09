from browser import ajax, document, window, timer
import json
from config import BASE_URL
from game_card import GameCard


class GamesGrid:
    """Handles games grid display, pagination, and sorting"""

    def __init__(self, current_user=None):
        """Initialize the games grid"""
        self.current_page = 1
        self.games_per_page = 20
        self.current_sort = "title"
        self.current_sort_order = "ASC"
        self.current_user = current_user
    
    def show_notification(self, message, message_type="success", duration=4000):
        """Display an inline notification message
        
        Args:
            message: The message to display
            message_type: Type of message ('success', 'error')
            duration: How long to show the message in milliseconds
        """
        message_div = document["games-grid-message"]
        if not message_div:
            return
        
        # Set message and styling
        message_div.text = message
        message_div.className = f"message {message_type}"
        
        # Auto-hide after duration
        def hide_message():
            message_div.text = ""
            message_div.className = "message"
        
        timer.set_timeout(hide_message, duration)

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


                # Create game cards
                cards_html = ""
                for game in games:
                    game_card = GameCard(game, self.current_user)
                    cards_html += game_card.render()

                games_grid.innerHTML = cards_html

                # Bind card flip click events
                for card in document.select(".game-card"):
                    card.bind("click", self.handle_card_flip)

                # Bind delete button click events
                for delete_btn in document.select(".game-card-delete-btn"):
                    delete_btn.bind("click", self.delete_game)

                # Bind vote button click events
                for vote_btn in document.select(".game-card-next-play-vote-btn"):
                    vote_btn.bind("click", self.toggle_vote)

                # Bind favorite button click events
                for fav_btn in document.select(".game-card-favorite-btn"):
                    fav_btn.bind("click", self.toggle_favorite)

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
        
        # Get the selected option's default sort direction
        selected_option = event.target.options[event.target.selectedIndex]
        default_sort = selected_option.getAttribute("data-default-sort")
        
        # Set sort order based on default (asc or desc)
        if default_sort:
            self.current_sort_order = "ASC" if default_sort.lower() == "asc" else "DESC"
            
            # Update the direction button icon
            sort_btn = document["sort-direction-btn"]
            sort_btn.textContent = "▲" if self.current_sort_order == "ASC" else "▼"
        
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
        if not window.confirm("Are you sure you want to delete this game?"):
            return
        
        def on_complete(req):
            if req.status == 200:
                # Reload the current page
                self.load_games(self.current_page)
                self.show_notification("Game deleted successfully", "success")
            else:
                self.show_notification(f"Failed to delete game. Status: {req.status}", "error")
        
        # Send DELETE request
        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("DELETE", f"{BASE_URL}/api/game/{game_id}", True)
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
        req.send()

    def toggle_vote(self, event):
        """Handle next play vote toggle"""
        event.stopPropagation()  # Prevent card click events
        
        button = event.target
        game_id = button.getAttribute("data-game-id")
        
        if not game_id:
            return
        
        # Disable button while processing
        button.disabled = True
        original_text = button.textContent
        button.textContent = "..."
        
        def on_get_complete(req):
            if req.status == 200:
                response = json.loads(req.text)
                user_has_voted = response.get("user_has_voted", False)
                
                # Toggle the vote: if user has voted, remove it (false), otherwise add it (true)
                vote_value = not user_has_voted
                
                def on_post_complete(req2):
                    if req2.status == 200:
                        # response2 = json.loads(req2.text)
                        
                        # Get updated vote count from the response
                        # Since we toggled, we need to fetch the new count
                        def on_refresh_complete(req3):
                            if req3.status == 200:
                                response3 = json.loads(req3.text)
                                new_count = response3.get("total_votes", 0)
                                user_voted = response3.get("user_has_voted", False)
                                
                                # Update button text with new count - use checkmark when voted
                                emoji = "✅" if user_voted else "➕"
                                button.textContent = f"{emoji} {new_count}"
                                
                                # Update button styling based on vote status
                                if user_voted:
                                    button.classList.add("voted")
                                else:
                                    button.classList.remove("voted")
                                
                                button.disabled = False
                            else:
                                button.textContent = original_text
                                button.disabled = False
                                window.alert(f"Failed to refresh vote count. Status: {req3.status}")
                        
                        # Refresh to get the updated count
                        req3 = ajax.Ajax()
                        req3.bind("complete", on_refresh_complete)
                        req3.open("GET", f"{BASE_URL}/api/game/{game_id}/vote", True)
                        req3.set_header(
                            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
                        )
                        req3.send()
                    else:
                        button.textContent = original_text
                        button.disabled = False
                        window.alert(f"Failed to update vote. Status: {req2.status}")
                
                # Send POST request to toggle vote
                req2 = ajax.Ajax()
                req2.bind("complete", on_post_complete)
                req2.open("POST", f"{BASE_URL}/api/game/{game_id}/vote", True)
                req2.set_header("Content-Type", "application/json")
                req2.set_header(
                    "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
                )
                req2.send(json.dumps({"vote": vote_value}))
            else:
                button.textContent = original_text
                button.disabled = False
                if req.status == 401:
                    self.show_notification("Please log in to vote.", "error")
                else:
                    self.show_notification(f"Failed to get vote status. Status: {req.status}", "error")
        
        # First, get the current vote status
        req = ajax.Ajax()
        req.bind("complete", on_get_complete)
        req.open("GET", f"{BASE_URL}/api/game/{game_id}/vote", True)
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
        req.send()

    def toggle_favorite(self, event):
        """Handle favorite toggle using game upsert route"""
        event.stopPropagation()  # Prevent card click events
        
        button = event.target
        game_id = button.getAttribute("data-game-id")
        
        if not game_id:
            return
        
        # Disable button while processing
        button.disabled = True
        original_text = button.textContent
        button.textContent = "..."
        
        # Get current user email
        user_email = self.current_user.current_user_info.get("email") if self.current_user and self.current_user.current_user_info else None
        
        if not user_email:
            button.textContent = original_text
            button.disabled = False
            self.show_notification("Please log in to favorite games", "error")
            return
        
        # Get favorited_by list from data attribute (no need to fetch all games!)
        favorited_by_str = button.getAttribute("data-favorited-by")
        try:
            favorited_by = json.loads(favorited_by_str) if favorited_by_str else []
        except Exception:
            favorited_by = []
        
        # Toggle favorite
        if user_email in favorited_by:
            favorited_by.remove(user_email)
            new_is_favorited = False
        else:
            favorited_by.append(user_email)
            new_is_favorited = True
        
        # Update game via upsert
        def on_upsert_complete(req):
            if req.status == 200:
                # Update button data attribute and icon
                button.setAttribute("data-favorited-by", json.dumps(favorited_by))
                button.textContent = "❤️" if new_is_favorited else "🤍"
                button.disabled = False
            else:
                button.textContent = original_text
                button.disabled = False
                error_text = req.text
                self.show_notification(f"Failed to update favorite. Status: {req.status}. Error: {error_text}", "error")
        
        # Send upsert request
        req = ajax.Ajax()
        req.bind("complete", on_upsert_complete)
        req.open("POST", f"{BASE_URL}/api/game", True)
        req.set_header("Content-Type", "application/json")
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
        req.send(json.dumps({
            "game_id": int(game_id),
            "favorited_by": favorited_by
        }))
