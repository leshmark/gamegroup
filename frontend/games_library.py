from browser import ajax, document, window
import json
from config import BASE_URL

class GamesLibrary:
    """Handles games library management and display"""
    
    def __init__(self, games_grid):
        """
        Initialize the games library
        
        Args:
            games_grid: GamesGrid instance for reloading games after operations
        """
        self.games_grid = games_grid
    
    def handle_add_game(self, event):
        """Handle manual game addition form submission"""
        event.preventDefault()
        
        # Get form inputs
        title_input = document["game-title"]
        owner_input = document["game-owner"]
        min_players_input = document["game-min-players"]
        max_players_input = document["game-max-players"]
        bgg_link_input = document["game-bgg-link"]
        bgg_rating_input = document["game-bgg-rating"]
        message_div = document["add-game-message"]
        submit_btn = event.target.querySelector(".submit-btn")
        
        # Get values
        title = title_input.value.strip()
        owner = owner_input.value.strip()
        min_players = int(min_players_input.value) if min_players_input.value else 0
        max_players = int(max_players_input.value) if max_players_input.value else 0
        bgg_link = bgg_link_input.value.strip() if bgg_link_input.value else None
        bgg_rating = float(bgg_rating_input.value) if bgg_rating_input.value else None
        
        # Validate
        if not title or not owner:
            message_div.text = "Title and owner are required"
            message_div.className = "message error"
            return
        
        if min_players < 1 or max_players < 1:
            message_div.text = "Player counts must be at least 1"
            message_div.className = "message error"
            return
        
        if min_players > max_players:
            message_div.text = "Minimum players cannot exceed maximum players"
            message_div.className = "message error"
            return
        
        # Disable submit button
        submit_btn.disabled = True
        submit_btn.textContent = "Adding..."
        message_div.text = ""
        message_div.className = ""
        
        def on_complete(req):
            submit_btn.disabled = False
            submit_btn.textContent = "Add Game"
            
            if req.status == 200:
                response = json.loads(req.text)
                message_div.text = "Game added successfully!"
                message_div.className = "message success"
                
                # Clear form
                title_input.value = ""
                owner_input.value = ""
                min_players_input.value = ""
                max_players_input.value = ""
                bgg_link_input.value = ""
                bgg_rating_input.value = ""
                
                # Reload games
                self.games_grid.load_games(self.games_grid.current_page)
            elif req.status == 403:
                message_div.text = "Access denied. Contributor privileges required."
                message_div.className = "message error"
            else:
                try:
                    error_data = json.loads(req.text)
                    message_div.text = f"Failed to add game: {error_data.get('detail', 'Unknown error')}"
                except:
                    message_div.text = f"Failed to add game. Status: {req.status}"
                message_div.className = "message error"
        
        # Prepare game data
        game_data = {
            "title": title,
            "owner": owner,
            "min_players": min_players,
            "max_players": max_players
        }
        
        if bgg_link is not None:
            game_data["bgg_link"] = bgg_link
        
        if bgg_rating is not None:
            game_data["bgg_rating"] = bgg_rating
        
        # Send request
        req = ajax.Ajax()
        req.bind('complete', on_complete)
        req.open('POST', f'{BASE_URL}/api/game', True)
        req.set_header('Content-Type', 'application/json')
        req.set_header('Authorization', f'Bearer {window.localStorage.getItem("auth_token")}')
        req.send(json.dumps(game_data))

    def handle_csv_upload(self, event):
        """Handle CSV file upload"""
        event.preventDefault()
        
        file_input = document["csv-file"]
        message_div = document["csv-upload-message"]
        submit_btn = event.target.querySelector(".submit-btn")
        
        if not file_input.files or len(file_input.files) == 0:
            message_div.text = "Please select a CSV file"
            message_div.className = "message error"
            return
        
        file = file_input.files[0]
        
        # Validate file type
        if not file.name.endswith('.csv'):
            message_div.text = "Please select a valid CSV file"
            message_div.className = "message error"
            return
        
        # Disable submit button
        submit_btn.disabled = True
        submit_btn.text = "Uploading..."
        message_div.text = ""
        message_div.className = ""
        
        def on_complete(req):
            submit_btn.disabled = False
            submit_btn.text = "Upload CSV"
            
            if req.status == 200:
                response = json.loads(req.text)
                games_added = response.get("games_added", 0)
                errors = response.get("errors", [])
                
                message_text = f"Successfully added {games_added} game(s)"
                if errors:
                    message_text += f"\n\nErrors encountered:\n" + "\n".join(errors[:5])
                    if len(errors) > 5:
                        message_text += f"\n... and {len(errors) - 5} more errors"
                
                message_div.text = message_text
                message_div.className = "message success"
                
                # Clear file input
                file_input.value = ""
                
            elif req.status == 403:
                message_div.text = "Access denied. Contributor privileges required."
                message_div.className = "message error"
            else:
                try:
                    error_data = json.loads(req.text)
                    message_div.text = f"Upload failed: {error_data.get('detail', 'Unknown error')}"
                except:
                    message_div.text = f"Upload failed with status {req.status}"
                message_div.className = "message error"
        
        # Create FormData and append file
        from browser import window as win
        FormData = win.FormData.new()
        FormData.append('file', file)
        
        req = ajax.Ajax()
        req.bind('complete', on_complete)
        req.open('POST', f'{BASE_URL}/api/game/upload-csv', True)
        req.set_header('Authorization', f'Bearer {window.localStorage.getItem("auth_token")}')
        req.send(FormData)
