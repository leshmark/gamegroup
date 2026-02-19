class GameCard:
    """Handles the creation of individual game card HTML"""
    
    def __init__(self, game_data):
        """
        Initialize the GameCard with game data
        
        Args:
            game_data: Dictionary containing game information
        """
        self.game = game_data
    
    def render(self):
        """Generate and return the HTML for this game card"""
        # Handle image
        image_style = ""
        image_content = ""
        if self.game.get("image_url"):
            image_style = f'style="background-image: url(\'{self.game["image_url"]}\'); background-size: 100%; background-repeat: no-repeat; background-position: top;"'
            image_content = ""
        else:
            image_style = ""
            image_content = '<div style="font-size: 3rem;">🎲</div>'
        
        # Handle description
        description = self.game.get("description", "")
        desc_html = ""
        if description:
            desc_html = f'<p class="game-card-description">{description}</p>'
        
        # Handle tags
        tags_html = ""
        if self.game.get("tags"):
            tags_html = '<div class="game-card-tags">'
            for tag in self.game["tags"]:
                tags_html += f'<span class="game-tag">{tag}</span>'
            tags_html += '</div>'
        
        # Handle BGG rating
        rating_html = ""
        if self.game.get("bgg_rating"):
            rating_html = f'<div class="game-card-rating">⭐ {self.game["bgg_rating"]:.1f}</div>'

        # Handle BGG link
        bgg_link_html = ""
        if self.game.get("bgg_link"):
            bgg_link_html = (
                '<div class="game-card-link">'
                f'<a href="{self.game["bgg_link"]}" target="_blank" rel="noopener noreferrer">'
                'View on BoardGameGeek</a>'
                '</div>'
            )
        
        # Player count
        players = f'{self.game["min_players"]}'
        if self.game["min_players"] != self.game["max_players"]:
            players += f'-{self.game["max_players"]}'
        
        # Build the complete card HTML
        card_html = f"""
        <div class="game-card">
            <div class="game-card-image" {image_style}>
                {image_content}
            </div>
            <div class="game-card-content">
                <h3 class="game-card-title">{self.game["title"]}</h3>
                <p class="game-card-owner">Owner: {self.game["owner"]}</p>
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
        
        return card_html
