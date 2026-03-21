from browser import ajax, document, window, timer
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
        self.add_game_form_visible = False
        self.csv_upload_form_visible = False
        self.add_game_by_bgg_form_visible = False
        document["add-game-btn"].bind("click", lambda e: self.show_add_game_form())
        document["add-game-by-bgg-btn"].bind("click", lambda e: self.show_add_game_by_bgg_form())
        document["upload-csv-btn"].bind("click", lambda e: self.show_csv_upload_form())

    def show_notification(self, message, message_type="success", duration=4000):
        """Display an inline notification message (unused - forms have their own message divs)
        
        Args:
            message: The message to display
            message_type: Type of message ('success', 'error')
            duration: How long to show the message in milliseconds
        """
        # This method is not used in games_library as each form has its own message div
        pass

    def show_add_game_form(self):
        """Display the add game form"""
        form_container = document["add-game-form-container"]
        if not form_container:
            return
        
        form_html = """
        <div class="add-game-form">
            <h3>Add Game Manually</h3>
            <p>Add a single game to the library by filling out the form below.</p>
            <form id="add-game-form">
                <div class="form-group">
                    <label for="game-title">Title: *</label>
                    <input type="text" id="game-title" name="title" required placeholder="Game title">
                </div>
                <div class="form-group">
                    <label for="game-owner">Owner: *</label>
                    <input type="text" id="game-owner" name="owner" required placeholder="Owner username">
                </div>
                <div class="form-group">
                    <label for="game-min-players">Minimum Players: *</label>
                    <input type="number" id="game-min-players" name="min_players" required min="1" placeholder="1">
                </div>
                <div class="form-group">
                    <label for="game-max-players">Maximum Players: *</label>
                    <input type="number" id="game-max-players" name="max_players" required min="1" placeholder="4">
                </div>
                <div class="form-group">
                    <label for="game-bgg-link">BGG Link:</label>
                    <input type="url" id="game-bgg-link" name="bgg_link" placeholder="https://boardgamegeek.com/boardgame/...">
                </div>
                <div class="form-group">
                    <label for="game-bgg-rating">BGG Rating:</label>
                    <input type="number" id="game-bgg-rating" name="bgg_rating" step="0.01" min="0" max="10" placeholder="7.5">
                </div>
                <div class="form-actions">
                    <button type="submit" class="submit-btn">Add Game</button>
                    <button type="button" id="cancel-add-game" class="submit-btn" style="margin-left: 1rem;">Cancel</button>
                </div>
            </form>
            <div id="add-game-message" class="message"></div>
        </div>
        """
        
        form_container.innerHTML = form_html
        self.add_game_form_visible = True
        
        # Hide the Add Game button
        add_game_btn = document["add-game-btn"]
        if add_game_btn:
            add_game_btn.style.display = "none"
        
        # Bind form events
        add_form = document["add-game-form"]
        if add_form:
            add_form.bind("submit", lambda e: self.handle_add_game(e))
        
        cancel_btn = document["cancel-add-game"]
        if cancel_btn:
            cancel_btn.bind("click", lambda e: self.hide_add_game_form())
    
    def hide_add_game_form(self):
        """Hide the add game form"""
        form_container = document["add-game-form-container"]
        if form_container:
            form_container.innerHTML = ""
            self.add_game_form_visible = False
        
        # Show the Add Game button
        add_game_btn = document["add-game-btn"]
        if add_game_btn:
            add_game_btn.style.display = ""

    def show_csv_upload_form(self):
        """Display the CSV upload form"""
        form_container = document["csv-upload-form-container"]
        if not form_container:
            return
        
        form_html = """
        <div class="csv-upload-form">
            <h3>Import Games from CSV</h3>
            <p>Upload a CSV file to bulk import games. Required columns: title, owner, min_players, max_players</p>
            <form id="csv-upload-form">
                <div class="form-group">
                    <label for="csv-file">Select CSV File:</label>
                    <input type="file" id="csv-file" name="csv-file" accept=".csv" required>
                </div>
                <div class="form-actions">
                    <button type="submit" class="submit-btn">Upload CSV</button>
                    <button type="button" id="cancel-csv-upload" class="submit-btn" style="margin-left: 1rem;">Cancel</button>
                </div>
            </form>
            <div id="csv-upload-message" class="message"></div>
        </div>
        """
        
        form_container.innerHTML = form_html
        self.csv_upload_form_visible = True
        
        # Hide the Upload CSV button
        upload_csv_btn = document["upload-csv-btn"]
        if upload_csv_btn:
            upload_csv_btn.style.display = "none"
        
        # Bind form events
        upload_form = document["csv-upload-form"]
        if upload_form:
            upload_form.bind("submit", lambda e: self.handle_csv_upload(e))
        
        cancel_btn = document["cancel-csv-upload"]
        if cancel_btn:
            cancel_btn.bind("click", lambda e: self.hide_csv_upload_form())
    
    def hide_csv_upload_form(self):
        """Hide the CSV upload form"""
        form_container = document["csv-upload-form-container"]
        if form_container:
            form_container.innerHTML = ""
            self.csv_upload_form_visible = False
        
        # Show the Upload CSV button
        upload_csv_btn = document["upload-csv-btn"]
        if upload_csv_btn:
            upload_csv_btn.style.display = ""

    def show_add_game_by_bgg_form(self):
        """Display the add game by BGG link form"""
        form_container = document["add-game-by-bgg-form-container"]
        if not form_container:
            return
        
        form_html = """
        <div class="add-game-by-bgg-form">
            <h3>Add Game from BoardGameGeek</h3>
            <p>Add a game by providing its BoardGameGeek URL. Game details will be automatically fetched.</p>
            <form id="add-game-by-bgg-form">
                <div class="form-group">
                    <label for="game-bgg-url">BGG URL: *</label>
                    <input type="url" id="game-bgg-url" name="bgg_url" required placeholder="https://boardgamegeek.com/boardgame/...">
                </div>
                <div class="form-group">
                    <label for="game-bgg-owner">Owner: *</label>
                    <input type="text" id="game-bgg-owner" name="owner" required placeholder="Owner username">
                </div>
                <div class="form-actions">
                    <button type="submit" class="submit-btn">Add Game from BGG</button>
                    <button type="button" id="cancel-add-game-by-bgg" class="submit-btn" style="margin-left: 1rem;">Cancel</button>
                </div>
            </form>
            <div id="add-game-by-bgg-message" class="message"></div>
        </div>
        """
        
        form_container.innerHTML = form_html
        self.add_game_by_bgg_form_visible = True
        
        # Hide the Add by BGG Link button
        add_bgg_btn = document["add-game-by-bgg-btn"]
        if add_bgg_btn:
            add_bgg_btn.style.display = "none"
        
        # Bind form events
        add_form = document["add-game-by-bgg-form"]
        if add_form:
            add_form.bind("submit", lambda e: self.handle_add_game_by_bgg(e))
        
        cancel_btn = document["cancel-add-game-by-bgg"]
        if cancel_btn:
            cancel_btn.bind("click", lambda e: self.hide_add_game_by_bgg_form())
    
    def hide_add_game_by_bgg_form(self):
        """Hide the add game by BGG link form"""
        form_container = document["add-game-by-bgg-form-container"]
        if form_container:
            form_container.innerHTML = ""
            self.add_game_by_bgg_form_visible = False
        
        # Show the Add by BGG Link button
        add_bgg_btn = document["add-game-by-bgg-btn"]
        if add_bgg_btn:
            add_bgg_btn.style.display = ""

    def handle_add_game_by_bgg(self, event):
        """Handle add game by BGG link form submission"""
        event.preventDefault()

        # Get form inputs
        bgg_url_input = document["game-bgg-url"]
        owner_input = document["game-bgg-owner"]
        message_div = document["add-game-by-bgg-message"]
        submit_btn = event.target.querySelector(".submit-btn")

        # Get values
        bgg_url = bgg_url_input.value.strip()
        owner = owner_input.value.strip()

        # Validate
        if not bgg_url or not owner:
            message_div.text = "BGG URL and owner are required"
            message_div.className = "message error"
            return

        # Disable submit button
        submit_btn.disabled = True
        submit_btn.textContent = "Fetching game data..."
        message_div.text = ""
        message_div.className = ""

        def on_complete(req):
            submit_btn.disabled = False
            submit_btn.textContent = "Add Game from BGG"

            if req.status == 200:
                response = json.loads(req.text)
                game_title = response.get("title", "Game")
                message_div.text = f"'{game_title}' added successfully from BGG!"
                message_div.className = "message success"
                # Hide form after delay
                def hide_form():
                    self.hide_add_game_by_bgg_form()
                    self.games_grid.load_games(self.games_grid.current_page)
                timer.set_timeout(hide_form, 2000)
            elif req.status == 403:
                message_div.text = "Access denied. Contributor privileges required."
                message_div.className = "message error"
            elif req.status == 404:
                message_div.text = "Could not extract game data from the provided BGG URL. Please check the URL and try again."
                message_div.className = "message error"
            else:
                try:
                    error_data = json.loads(req.text)
                    message_div.text = f"Failed to add game: {error_data.get('detail', 'Unknown error')}"
                except Exception:
                    message_div.text = f"Failed to add game. Status: {req.status}"
                message_div.className = "message error"

        # Prepare request data
        game_data = {
            "bgg_url": bgg_url,
            "owner": owner,
        }

        # Send request
        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("POST", f"{BASE_URL}/api/v1/game/action/add-game-by-bgg-link", True)
        req.set_header("Content-Type", "application/json")
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
        req.send(json.dumps(game_data))

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
                message_div.text = "Game added successfully!"
                message_div.className = "message success"
                # Hide form after delay
                def hide_form():
                    self.hide_add_game_form()
                    self.games_grid.load_games(self.games_grid.current_page)
                timer.set_timeout(hide_form, 2000)
            elif req.status == 403:
                message_div.text = "Access denied. Contributor privileges required."
                message_div.className = "message error"
            else:
                try:
                    error_data = json.loads(req.text)
                    message_div.text = f"Failed to add game: {error_data.get('detail', 'Unknown error')}"
                except Exception:
                    message_div.text = f"Failed to add game. Status: {req.status}"
                message_div.className = "message error"

        # Prepare game data
        game_data = {
            "title": title,
            "owner": owner,
            "min_players": min_players,
            "max_players": max_players,
        }

        if bgg_link is not None:
            game_data["bgg_link"] = bgg_link

        if bgg_rating is not None:
            game_data["bgg_rating"] = bgg_rating

        # Send request
        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("POST", f"{BASE_URL}/api/v1/game", True)
        req.set_header("Content-Type", "application/json")
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
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
        if not file.name.endswith(".csv"):
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
                    message_text += "\n\nErrors encountered:\n" + "\n".join(errors[:5])
                    if len(errors) > 5:
                        message_text += f"\n... and {len(errors) - 5} more errors"

                message_div.text = message_text
                message_div.className = "message success" if not errors else "message error"
                # Hide form after delay
                def hide_form():
                    self.hide_csv_upload_form()
                    self.games_grid.load_games(self.games_grid.current_page)
                timer.set_timeout(hide_form, 3000)

            elif req.status == 403:
                message_div.text = "Access denied. Contributor privileges required."
                message_div.className = "message error"
            else:
                try:
                    error_data = json.loads(req.text)
                    message_div.text = (
                        f"Upload failed: {error_data.get('detail', 'Unknown error')}"
                    )
                except Exception:
                    message_div.text = f"Upload failed with status {req.status}"
                message_div.className = "message error"

        # Create FormData and append file
        from browser import window as win

        FormData = win.FormData.new()
        FormData.append("file", file)

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("POST", f"{BASE_URL}/api/v1/game/upload-csv", True)
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
        req.send(FormData)
