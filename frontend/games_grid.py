from browser import ajax, document, window
import json
from config import BASE_URL
from game_card import GameCard

class GamesGrid:
    """Handles games grid display, pagination, and sorting"""
    
    def __init__(self):
        """Initialize the games grid"""
        self.current_page = 1
        self.games_per_page = 20
        self.current_sort = "title"
    
    def load_games(self, page: int = 1):
        """Fetch and display games from backend"""
        self.current_page = page
        offset = (page - 1) * self.games_per_page
        
        def on_complete(req):
            games_grid = document["games-grid"]
            games_count = document["games-count-text"]
            pagination_div = document["games-pagination"]
            
            if req.status == 200:
                response = json.loads(req.text)
                games = response.get("games", [])
                total = response.get("total", 0)
                
                # Update count
                games_count.text = f"Showing {len(games)} of {total} games"
                
                if not games:
                    games_grid.innerHTML = "<p>No games found in the library yet.</p>"
                    pagination_div.innerHTML = ""
                    return
                
                # Create game cards
                cards_html = ""
                for game in games:
                    game_card = GameCard(game)
                    cards_html += game_card.render()
                
                games_grid.innerHTML = cards_html
                
                # Create pagination
                total_pages = (total + self.games_per_page - 1) // self.games_per_page
                self.render_pagination(total_pages, page, pagination_div)
                
            else:
                games_grid.innerHTML = f"<p style='color: #e74c3c;'>Failed to load games. Status: {req.status}</p>"
                pagination_div.innerHTML = ""
        
        games_grid = document["games-grid"]
        games_grid.innerHTML = "<p>Loading games...</p>"
        
        # Build URL with parameters
        url = f'{BASE_URL}/games?limit={self.games_per_page}&offset={offset}'
        if self.current_sort:
            url += f'&sort_by={self.current_sort}'
        
        req = ajax.Ajax()
        req.bind('complete', on_complete)
        req.open('GET', url, True)
        req.set_header('Authorization', f'Bearer {window.localStorage.getItem("auth_token")}')
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
            html += f'<button class="pagination-btn" data-page="1">1</button>'
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
        # Scroll to top of games section
        games_section = document["games"]
        if games_section:
            games_section[0].scrollIntoView({"behavior": "smooth"})

    def handle_sort_change(self, event):
        """Handle sort selection change"""
        self.current_sort = event.target.value
        self.current_page = 1
        self.load_games(1)
