class GameCard:
    """Handles the creation of individual game card HTML"""

    def __init__(self, game_data, authorizations):
        """
        Initialize the GameCard with game data

        Args:
            game_data: Dictionary containing game information
            is_admin: Boolean indicating if the current user is an admin
        """
        self.game = game_data
        self.authorizations = authorizations

    def render(self):
        """Generate and return the HTML for this game card"""
        # Handle image
        image_style = ""
        image_content = ""
        if self.game.get("image_url"):
            image_style = f"style=\"background-image: url('{self.game['image_url']}'); background-size: 100%; background-repeat: no-repeat; background-position: top;\""
            image_content = ""
        else:
            image_style = ""
            image_content = '<div style="font-size: 3rem;">🎲</div>'

        # Handle description
        description = self.game.get("description", "")
        desc_html = ""
        if description:
            desc_html = f'<p class="game-card-description">{description}</p>'

        # Handle short description 
        short_description = self.game.get("short_description", "")
        short_desc_html = ""
        if short_description:
            short_desc_html = f'<p class="game-card-short-description">{short_description}</p>'
            short_desc_html = short_desc_html 


        # Handle tags
        tags_html = ""
        if self.game.get("tags"):
            tags_html = '<div class="game-card-tags">'
            for tag in self.game["tags"]:
                tags_html += f'<span class="game-tag">{tag}</span>'
            tags_html += "</div>"

        # Handle BGG rating
        rating_html = ""
        if self.game.get("bgg_rating"):
            rating_html = (
                f'<div class="game-card-rating">⭐ {self.game["bgg_rating"]:.1f}</div>'
            )

        # Handle BGG link
        bgg_link_html = ""
        if self.game.get("bgg_link"):
            bgg_link_html = (
                '<div class="game-card-link">'
                f'<a href="{self.game["bgg_link"]}" target="_blank" rel="noopener noreferrer">'
                "View on BoardGameGeek</a>"
                "</div>"
            )

        # Player count
        players = f"{self.game['min_players']}"
        if self.game["min_players"] != self.game["max_players"]:
            players += f"-{self.game['max_players']}"

        # Delete button for admins
        delete_button_html = ""
        if self.authorizations.get("is_admin", False):
            delete_button_html = f'''
            <button class="game-card-delete-btn" data-game-id="{self.game['id']}" title="Delete game">
                🗑
            </button>
            '''
        # Next play vote button for contributors as Plus Emoji
        if self.authorizations.get("is_contributor", False):
            next_play_vote_count = self.game.get("next_play_vote_count", 0)
            next_play_vote_html = f'''
            <button class="game-card-next-play-vote-btn" data-game-id="{self.game['id']}" title="Vote for next play">
                ➕ {next_play_vote_count}
            </button>
            '''
        
        #Favoriting button for logged in contributors as Heart Emoji
        if self.authorizations.get("is_contributor", False):
            favorited_by = self.game.get("favorited_by", [])
            # is_favorited = self.current_user_email in favorited_by
            is_favorited = True
            favorite_icon = "❤️" if is_favorited else "🤍"
            favorite_html = f'''
            <button class="game-card-favorite-btn" data-game-id="{self.game['id']}" title="Favorite game">
                {favorite_icon} 
            </button>
            '''

        # Build the complete card HTML with flip structure
        card_html = f"""
        <div class="game-card-container">
            <div class="game-card">
                <div class="game-card-front">
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
                        {short_desc_html}
                        {rating_html}
                        {bgg_link_html}
                        {tags_html}
                        <div class="game-card-front-footer">
                            <span class="flip-hint">Click to flip to details</span>
                        </div>
                    </div>
                        <div class="game-card-actions">
                            {delete_button_html if self.authorizations.get("is_admin", False) else ""}
                            {next_play_vote_html if self.authorizations.get("is_contributor", False) else ""}
                            {favorite_html if self.authorizations.get("is_contributor", False) else ""}
                        </div>
                </div>
                <div class="game-card-back">
                    <div class="game-card-back-content">
                        <h3 class="game-card-title">{self.game["title"]}</h3>
                        <div class="game-card-back-description">
                            {desc_html if description else '<p class="game-card-description">No detailed description available.</p>'}
                        </div>
                        <div class="game-card-back-footer">
                            <span class="flip-hint">Click to flip back</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

        return card_html
