from browser import ajax, document, window
import json
from config import BASE_URL

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
                    # Handle image
                    image_style = ""
                    image_content = ""
                    if game.get("image_url"):
                        image_style = f'style="background-image: url(\'{game["image_url"]}\'); background-size: 100%; background-repeat: no-repeat; background-position: top;"'
                        image_content = ""
                    else:
                        image_style = ""
                        image_content = '<div style="font-size: 3rem;">🎲</div>'
                    
                    # Handle description
                    description = game.get("description", "")
                    desc_html = ""
                    if description:
                        desc_html = f'<p class="game-card-description">{description}</p>'
                    
                    # Handle tags
                    tags_html = ""
                    if game.get("tags"):
                        tags_html = '<div class="game-card-tags">'
                        for tag in game["tags"]:
                            tags_html += f'<span class="game-tag">{tag}</span>'
                        tags_html += '</div>'
                    
                    # Handle BGG rating
                    rating_html = ""
                    if game.get("bgg_rating"):
                        rating_html = f'<div class="game-card-rating">⭐ {game["bgg_rating"]:.1f}</div>'

                    # Handle BGG link
                    bgg_link_html = ""
                    if game.get("bgg_link"):
                        bgg_link_html = (
                            '<div class="game-card-link">'
                            f'<a href="{game["bgg_link"]}" target="_blank" rel="noopener noreferrer">'
                            'View on BoardGameGeek</a>'
                            '</div>'
                        )
                    
                    # Player count
                    players = f'{game["min_players"]}'
                    if game["min_players"] != game["max_players"]:
                        players += f'-{game["max_players"]}'
                    
                    cards_html += f"""
                    <div class="game-card">
                        <div class="game-card-image" {image_style}>
                            {image_content}
                        </div>
                        <div class="game-card-content">
                            <h3 class="game-card-title">{game["title"]}</h3>
                            <p class="game-card-owner">Owner: {game["owner"]}</p>
                            <div class="game-card-details">
                                <div class="game-card-detail">
                                    <span class="game-card-detail-icon">👥</span>
                                    <span>{players} players</span>
                                </div>
                            </div>
                            {desc_html}
                            {rating_html}
                            {bgg_link_html}
                            {tags_html}
                        </div>
                    </div>
                    """
                
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
