from browser import ajax, document, window
from auth import Auth
import json
from config import BASE_URL

class App:
    """Main application class for managing navigation and authentication"""
    
    def __init__(self):
        """Initialize the application and bind event handlers"""
        self.current_user_info = {}
        self.current_page = 1
        self.games_per_page = 20
        self.current_sort = "title"
        self.get_current_user_info()
        self.auth = Auth()
        self.bind_events()
        self.handle_navigation()
    
    def show_section(self, section_id):
        """Show the specified section and hide all others"""
        sections = document.select(".content-section")
        for section in sections:
            section.style.display = "none"
        
        if section_id:
            target = document.get(selector=f"#{section_id}")
            if target:
                target[0].style.display = "block"
                # Load users when admin section is shown
                if section_id == "admin" and self.current_user_info and self.current_user_info["authorizations"].get("is_admin"):
                    self.load_users()
                # Show CSV upload form when games section is shown and user is contributor
                if section_id == "games" and self.current_user_info and self.current_user_info["authorizations"].get("is_contributor"):
                    self.show_add_game_form()
                    self.show_csv_upload_form()
                # Load games when games section is shown
                if section_id == "games":
                    self.load_games()
    
    def handle_navigation(self):
        """Update navigation links based on authentication status and user info"""
        logout_container = document.select(".logout-container")
        login_container = document.select(".login-container")
        user_email = window.localStorage.getItem("user_email")
        login_link = document.get(selector="a[href='#login']")
        admin_nav = document.get(selector="#admin_nav")
        admin_nav[0].style.display = "none"
        
        if self.logged_in():
            login_link[0].text = self.current_user_info.get("username", "unknown user")
            logout_container[0].style.display = "block"
            login_container[0].style.display = "none"
            if self.current_user_info and self.current_user_info["authorizations"].get("is_admin"):
                admin_nav[0].style.display = "block"
        else:
            login_link[0].text = "Login"
            logout_container[0].style.display = "none"
            login_container[0].style.display = "block"
            admin_nav[0].style.display = "none"

        """Handle URL hash changes for navigation"""
        hash_value = window.location.hash[1:]  # Remove the # symbol
        self.show_section(hash_value)
    
    def logged_in(self):
        """Check if the user is logged in by verifying the presence of a JWT token"""
        token = window.localStorage.getItem("auth_token") or None
        return token is not None
    
    def handle_login(self, event):
        """Handle login form submission"""
        event.preventDefault()
        
        email_input = document["email"]
        message_div = document["login-message"]
        submit_btn = document.querySelector(".submit-btn")
        
        email = email_input.value.strip()
        
        if not email:
            message_div.text = "Please enter a valid email address"
            message_div.className = "message error"
            return
        
        # Submit the login request
        self.auth.submit_login_request(email, email_input, message_div, submit_btn)
    
    def handle_logout(self, event):
        """Handle logout action"""
        event.preventDefault()
        
        # Clear local storage
        window.localStorage.removeItem("auth_token")
        window.localStorage.removeItem("user_email")
        
        # Redirect to home
        window.location.href = "/#home"
        
        # Update navigation
        self.handle_navigation()
    
    def bind_events(self):
        """Bind all event handlers"""
        document["login-form"].bind("submit", self.handle_login)
        document["logout-btn"].bind("click", self.handle_logout)
        document["add-game-form"].bind("submit", self.handle_add_game)
        document["csv-upload-form"].bind("submit", self.handle_csv_upload)
        document["sort-select"].bind("change", self.handle_sort_change)
        window.bind("hashchange", lambda e: self.handle_navigation())

    def get_current_user_info(self):
        """Fetch current user info from backend"""
        def on_complete(req):
            if req.status == 200:
                response = json.loads(req.text)
                self.current_user_info = response
                self.handle_navigation()
                #under document["user-info"] add user info as bulleted list with indentation for sub-items recursively
                user_info_div = document["user-info"]
                user_info_div.innerHTML = ""
                def create_list(data, parent):
                    ul = document.createElement("ul")
                    for key, value in data.items():
                        li = document.createElement("li")
                        if isinstance(value, dict):
                            li.textContent = f"{key}:"
                            create_list(value, li)
                        else:
                            li.textContent = f"{key}: {value}"
                        ul.appendChild(li)
                    parent.appendChild(ul)
                create_list(response, user_info_div)
                return response
            else:
                print("Failed to fetch user info")
                self.current_user_info = {}
                return None
        
        req = ajax.Ajax()
        req.bind('complete', on_complete)
        req.open('GET', f'{BASE_URL}/auth/me', True)
        req.set_header('Authorization', f'Bearer {window.localStorage.getItem("auth_token")}')
        req.send()

    def load_users(self):
        """Fetch and display all users from backend"""
        def on_complete(req):
            users_container = document["users-list-container"]
            if req.status == 200:
                response = json.loads(req.text)
                users = response.get("users", [])
                
                if not users:
                    users_container.innerHTML = "<p>No users found.</p>"
                    return
                
                # Create table
                table_html = """
                <table class="users-table">
                    <thead>
                        <tr>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Authorizations</th>
                            <th>Created</th>
                        </tr>
                    </thead>
                    <tbody>
                """
                
                for user in users:
                    # Parse authorizations
                    auth_html = ""
                    if user.get("authorizations"):
                        auths = user["authorizations"].split(",")
                        for auth in auths:
                            auth_class = ""
                            if "admin" in auth.lower():
                                auth_class = "admin"
                            elif "contributor" in auth.lower():
                                auth_class = "contributor"
                            elif "viewer" in auth.lower():
                                auth_class = "viewer"
                            auth_html += f'<span class="user-auth-badge {auth_class}">{auth.strip()}</span>'
                    else:
                        auth_html = '<span style="color: #95a5a6;">None</span>'
                    
                    # Format date
                    created_at = user.get("created_at", "Unknown")
                    if created_at and created_at != "Unknown":
                        # Parse ISO date and format it
                        try:
                            date_parts = created_at.split("T")[0]
                            created_at = date_parts
                        except:
                            pass
                    
                    table_html += f"""
                        <tr>
                            <td>{user.get("username", "")}</td>
                            <td>{user.get("email", "")}</td>
                            <td>{auth_html}</td>
                            <td>{created_at}</td>
                        </tr>
                    """
                
                table_html += """
                    </tbody>
                </table>
                """
                
                users_container.innerHTML = table_html
            elif req.status == 403:
                users_container.innerHTML = "<p style='color: #e74c3c;'>Access denied. Admin privileges required.</p>"
            else:
                users_container.innerHTML = f"<p style='color: #e74c3c;'>Failed to load users. Status: {req.status}</p>"
        
        users_container = document["users-list-container"]
        users_container.innerHTML = "<p>Loading users...</p>"
        
        req = ajax.Ajax()
        req.bind('complete', on_complete)
        req.open('GET', f'{BASE_URL}/admin/users', True)
        req.set_header('Authorization', f'Bearer {window.localStorage.getItem("auth_token")}')
        req.send()

    def show_add_game_form(self):
        """Show manual add game form for contributors"""
        add_game_container = document["add-game-container"]
        add_game_container.style.display = "block"

    def show_csv_upload_form(self):
        """Show CSV upload form for contributors"""
        upload_container = document["csv-upload-container"]
        upload_container.style.display = "block"

    def handle_add_game(self, event):
        """Handle manual game addition form submission"""
        event.preventDefault()
        
        # Get form inputs
        title_input = document["game-title"]
        owner_input = document["game-owner"]
        min_players_input = document["game-min-players"]
        max_players_input = document["game-max-players"]
        bgg_rating_input = document["game-bgg-rating"]
        message_div = document["add-game-message"]
        submit_btn = event.target.querySelector(".submit-btn")
        
        # Get values
        title = title_input.value.strip()
        owner = owner_input.value.strip()
        min_players = int(min_players_input.value) if min_players_input.value else 0
        max_players = int(max_players_input.value) if max_players_input.value else 0
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
                bgg_rating_input.value = ""
                
                # Reload games
                self.load_games(self.current_page)
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
        
        if bgg_rating is not None:
            game_data["bgg_rating"] = bgg_rating
        
        # Send request
        req = ajax.Ajax()
        req.bind('complete', on_complete)
        req.open('POST', f'{BASE_URL}/games', True)
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
        req.open('POST', f'{BASE_URL}/games/upload-csv', True)
        req.set_header('Authorization', f'Bearer {window.localStorage.getItem("auth_token")}')
        req.send(FormData)

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
                    image_html = ""
                    if game.get("image_url"):
                        image_html = f'<img src="{game["image_url"]}" alt="{game["title"]}">'
                    else:
                        image_html = '<div style="font-size: 3rem;">🎲</div>'
                    
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
                        <div class="game-card-image">
                            {image_html}
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

# Initialize the application
app = App()
