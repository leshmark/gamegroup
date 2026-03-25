from browser import ajax, document, window, timer
import json
from datetime import datetime, timedelta
from config import BASE_URL


def _next_tuesday_6pm():
    """Return the next Tuesday at 18:00 as a datetime string for an input[type=datetime-local]"""
    today = datetime.now()
    # weekday(): Monday=0 … Sunday=6; Tuesday=1
    days_ahead = (1 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_tuesday = today + timedelta(days=days_ahead)
    dt = next_tuesday.replace(hour=18, minute=0, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M")


class PlayLog:
    """Handles the Play Log section: requested games, log-entry form, and past sessions"""

    SESSIONS_PER_PAGE = 5

    def __init__(self, current_user=None):
        self.current_user = current_user
        self._current_page = 1
        self._all_games = []  # populated when section is shown
        self._pending_game_id = None    # game highlighted in the <select>
        self._pending_game_title = None

    # ------------------------------------------------------------------ #
    # Public entry point                                                   #
    # ------------------------------------------------------------------ #

    def load(self):
        """Load all three sub-sections of the play log page"""
        self._load_requested_games()
        self._render_log_form()
        self._load_sessions(page=1)
        self._load_all_games_for_dropdown()

    # ------------------------------------------------------------------ #
    # Section 1 – Requested Games                                         #
    # ------------------------------------------------------------------ #

    def _load_requested_games(self):
        container = document.get(selector="#requested-games-body")
        if not container:
            return
        container[0].innerHTML = "<tr><td colspan='6'>Loading…</td></tr>"

        def on_complete(req):
            if req.status == 200:
                data = json.loads(req.text)
                games = data.get("games", [])
                if not games:
                    container[0].innerHTML = "<tr><td colspan='6'>No votes yet.</td></tr>"
                    return
                rows = ""
                for g in games:
                    img = (
                        f'<img src="{g["image_url"]}" alt="" style="height:32px;width:auto;">'
                        if g.get("image_url")
                        else ""
                    )
                    rating = g.get("bgg_rating") or "—"
                    short_desc = g.get("short_description") or ""
                    rows += (
                        f'<tr>'
                        f'<td><input type="checkbox" class="requested-game-check" data-game-id="{g["id"]}" data-game-title="{g["title"]}"></td>'
                        f'<td>{img}</td>'
                        f'<td>{g["title"]}</td>'
                        f'<td>{rating}</td>'
                        f'<td class="short-desc-cell">{short_desc}</td>'
                        f'<td><strong>{g["next_play_vote_count"]}</strong></td>'
                        f'</tr>'
                    )
                container[0].innerHTML = rows
            else:
                container[0].innerHTML = "<tr><td colspan='6'>Failed to load requested games.</td></tr>"

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("GET", f"{BASE_URL}/api/v1/play-log/requested-games?limit=5", True)
        req.set_header("Authorization", f"Bearer {window.localStorage.getItem('auth_token')}")
        req.send()

    # ------------------------------------------------------------------ #
    # Section 2 – Log-entry form                                          #
    # ------------------------------------------------------------------ #

    def _render_log_form(self):
        container = document.get(selector="#play-log-form-container")
        if not container:
            return

        default_dt = _next_tuesday_6pm()

        form_html = f"""
        <form id="play-log-form">
            <div class="form-group">
                <label for="session-date">Date &amp; Time:</label>
                <input type="datetime-local" id="session-date" name="session_date"
                       value="{default_dt}" required>
            </div>
            <div class="form-group">
                <label for="session-location">Location:</label>
                <input type="text" id="session-location" name="location"
                       placeholder="e.g. Mark's place" maxlength="500">
            </div>
            <div class="form-group">
                <label>Games Played:</label>
                <div class="play-log-picker-row">
                    <input type="text" id="games-played-search" placeholder="Search games\u2026"
                           autocomplete="off">
                    <button type="button" id="add-game-btn" class="submit-btn secondary-btn">Add</button>
                </div>
                <select id="games-played-select" size="5" class="play-log-select">
                    <option value="" disabled>Loading games\u2026</option>
                </select>
                <input type="hidden" id="pending-game-id" value="">
                <div id="games-played-selected" class="play-log-selected-games"></div>
                <input type="hidden" id="games-played-data" name="games_played" value="[]">
            </div>
            <div class="form-group">
                <button type="button" id="populate-from-votes-btn" class="submit-btn secondary-btn">
                    Populate from Votes
                </button>
            </div>
            <div class="form-group">
                <label for="session-notes">Notes:</label>
                <textarea id="session-notes" name="notes" rows="10"
                          placeholder="How did it go? Who won? Any highlights or misses?"></textarea>
            </div>
            <div class="form-actions">
                <button type="submit" class="submit-btn">Submit Play Log</button>
            </div>
        </form>
        <div id="play-log-message" class="message"></div>
        """
        container[0].innerHTML = form_html

        form = document.get(selector="#play-log-form")
        if form:
            form[0].bind("submit", self._handle_submit)

        # Use event delegation on the form container for reliable click handling
        form_container = document.get(selector="#play-log-form-container")
        if form_container:
            form_container[0].bind("click", self._handle_form_container_click)

        search_input = document.get(selector="#games-played-search")
        if search_input:
            search_input[0].bind("input", self._handle_game_search)

        select_el = document.get(selector="#games-played-select")
        if select_el:
            select_el[0].bind("change", self._handle_select_change)

        populate_btn = document.get(selector="#populate-from-votes-btn")
        if populate_btn:
            populate_btn[0].bind("click", self._populate_from_votes)

    def _load_all_games_for_dropdown(self):
        """Fetch a full game list (id + title) for the game picker"""
        def on_complete(req):
            if req.status == 200:
                data = json.loads(req.text)
                self._all_games = data.get("games", [])
                # Populate the select with all games initially
                self._update_game_select("")

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("GET", f"{BASE_URL}/api/v1/game?limit=1000&offset=0", True)
        req.set_header("Authorization", f"Bearer {window.localStorage.getItem('auth_token')}")
        req.send()

    def _update_game_select(self, query: str):
        """Rebuild the <select> options filtered by query, excluding already-selected games"""
        select_el = document.get(selector="#games-played-select")
        if not select_el:
            return
        selected_ids = [g["id"] for g in self._get_selected_games()]
        q = query.strip().lower()
        matches = sorted(
            [
                g for g in self._all_games
                if (not q or q in g["title"].lower()) and g["id"] not in selected_ids
            ],
            key=lambda g: g["title"].lower(),
        )
        options_html = "".join(
            f'<option value="{g["id"]}">{g["title"]}</option>'
            for g in matches
        )
        if not options_html:
            options_html = '<option value="" disabled>No matches</option>'
        select_el[0].innerHTML = options_html

    def _handle_game_search(self, event):
        search_input = document.get(selector="#games-played-search")
        query = search_input[0].value if search_input else ""
        self._update_game_select(query)

    def _handle_select_change(self, event):
        """Cache the highlighted game id in a hidden input and fill the search box"""
        from browser import console
        select_el = document.get(selector="#games-played-select")
        search_input = document.get(selector="#games-played-search")
        pending_input = document.get(selector="#pending-game-id")
        if not select_el:
            console.log("[PlayLog] _handle_select_change: select_el not found")
            return
        game_id_str = select_el[0].value
        console.log(f"[PlayLog] select change: value='{game_id_str}'")
        if not game_id_str:
            return
        try:
            game_id = int(game_id_str)
        except (ValueError, TypeError):
            return
        id_to_title = {g["id"]: g["title"] for g in self._all_games}
        game_title = id_to_title.get(game_id, "")
        if pending_input:
            pending_input[0].value = game_id_str
            console.log(f"[PlayLog] wrote pending-game-id={game_id_str}")
        else:
            console.log("[PlayLog] pending-game-id input NOT FOUND in DOM")
        self._pending_game_id = game_id
        self._pending_game_title = game_title
        if search_input and game_title:
            search_input[0].value = game_title

    def _handle_form_container_click(self, event):
        """Event delegation handler for clicks inside the form container"""
        from browser import console
        target = event.target
        el_id = target.id if hasattr(target, "id") else ""
        console.log(f"[PlayLog] form container click: id='{el_id}'")
        if el_id == "add-game-btn":
            event.preventDefault()
            event.stopPropagation()
            self._handle_add_game_btn(event)

    def _handle_add_game_btn(self, event):
        """Add the pending game (from hidden input) to the selected games list"""
        from browser import console
        console.log("[PlayLog] Add button clicked")
        pending_input = document.get(selector="#pending-game-id")
        console.log(f"[PlayLog] pending_input found: {bool(pending_input)}")
        if not pending_input or not pending_input[0].value:
            console.log(f"[PlayLog] No pending game id - pending_input: {pending_input}, value: {pending_input[0].value if pending_input else 'N/A'}")
            return
        pending_val = pending_input[0].value
        console.log(f"[PlayLog] pending game id value: {pending_val}")
        try:
            game_id = int(pending_val)
        except (ValueError, TypeError) as e:
            console.log(f"[PlayLog] Failed to parse game id: {e}")
            return
        id_to_title = {g["id"]: g["title"] for g in self._all_games}
        game_title = id_to_title.get(game_id, "")
        console.log(f"[PlayLog] Resolved game_id={game_id} title='{game_title}', all_games count={len(self._all_games)}")
        if not game_title:
            console.log("[PlayLog] game_title empty, aborting")
            return
        self._add_selected_game(game_id, game_title)
        pending_input[0].value = ""
        self._pending_game_id = None
        self._pending_game_title = None
        search_input = document.get(selector="#games-played-search")
        if search_input:
            search_input[0].value = ""
        self._update_game_select("")

    def _add_selected_game(self, game_id: int, game_title: str):
        selected = self._get_selected_games()
        if any(g["id"] == game_id for g in selected):
            return
        selected.append({"id": game_id, "title": game_title})
        self._set_selected_games(selected)
        self._render_selected_games()

    def _remove_selected_game(self, event):
        game_id = int(event.target.attrs["data-game-id"])
        selected = [g for g in self._get_selected_games() if g["id"] != game_id]
        self._set_selected_games(selected)
        self._render_selected_games()
        search_el = document.get(selector="#games-played-search")
        self._update_game_select(search_el[0].value if search_el else "")

    def _get_selected_games(self):
        """Return list of {id, title} dicts from the hidden input"""
        hidden = document.get(selector="#games-played-data")
        if hidden:
            return json.loads(hidden[0].value or "[]")
        return []

    def _set_selected_games(self, games: list):
        hidden = document.get(selector="#games-played-data")
        if hidden:
            hidden[0].value = json.dumps(games)

    def _render_selected_games(self):
        container = document.get(selector="#games-played-selected")
        if not container:
            return
        selected = self._get_selected_games()
        tags_html = "".join(
            f'<span class="play-log-game-tag">'
            f'{g["title"]}'
            f'<button type="button" class="play-log-remove-game" data-game-id="{g["id"]}">×</button>'
            f'</span>'
            for g in selected
        )
        container[0].innerHTML = tags_html
        for btn in document.select(".play-log-remove-game"):
            btn.bind("click", self._remove_selected_game)

    def _populate_from_votes(self, event):
        """Pre-select all games that have votes from the requested-games table"""
        checkboxes = document.select(".requested-game-check:checked")
        if checkboxes:
            for cb in checkboxes:
                game_id = int(cb.attrs["data-game-id"])
                game_title = cb.attrs["data-game-title"]
                self._add_selected_game(game_id, game_title)
        else:
            for cb in document.select(".requested-game-check"):
                game_id = int(cb.attrs["data-game-id"])
                game_title = cb.attrs["data-game-title"]
                self._add_selected_game(game_id, game_title)
        self._update_game_select("")

    def _handle_submit(self, event):
        event.preventDefault()
        message_div = document.get(selector="#play-log-message")

        session_date_el = document.get(selector="#session-date")
        location_el = document.get(selector="#session-location")
        notes_el = document.get(selector="#session-notes")

        if not session_date_el or not session_date_el[0].value:
            if message_div:
                message_div[0].text = "Please select a session date."
                message_div[0].className = "message error"
            return

        payload = {
            "session_date": session_date_el[0].value,
            "location": location_el[0].value if location_el else "",
            "games_played": [g["id"] for g in self._get_selected_games()],
            "notes": notes_el[0].value if notes_el else "",
        }

        def on_complete(req):
            if message_div:
                if req.status == 200:
                    message_div[0].text = "Play log session saved!"
                    message_div[0].className = "message success"
                    # Reset form
                    form = document.get(selector="#play-log-form")
                    if form:
                        form[0].reset()
                    self._set_selected_games([])
                    self._render_selected_games()
                    self._update_game_select("")
                    self._load_sessions(page=1)
                    timer.set_timeout(lambda: self._clear_message(message_div[0]), 4000)
                else:
                    message_div[0].text = f"Failed to save session. Status: {req.status}"
                    message_div[0].className = "message error"

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("POST", f"{BASE_URL}/api/v1/play-log", True)
        req.set_header("Authorization", f"Bearer {window.localStorage.getItem('auth_token')}")
        req.set_header("Content-Type", "application/json")
        req.send(json.dumps(payload))

    def _clear_message(self, el):
        el.text = ""
        el.className = "message"

    # ------------------------------------------------------------------ #
    # Section 3 – Past sessions                                           #
    # ------------------------------------------------------------------ #

    def _load_sessions(self, page: int = 1):
        self._current_page = page
        offset = (page - 1) * self.SESSIONS_PER_PAGE
        container = document.get(selector="#play-log-sessions-list")
        pagination = document.get(selector="#play-log-sessions-pagination")

        if not container:
            return
        container[0].innerHTML = "<p>Loading sessions…</p>"

        def on_complete(req):
            if req.status == 200:
                data = json.loads(req.text)
                sessions = data.get("sessions", [])
                total = data.get("total", 0)

                if not sessions:
                    container[0].innerHTML = "<p>No play sessions recorded yet.</p>"
                    if pagination:
                        pagination[0].innerHTML = ""
                    return

                html = ""
                for s in sessions:
                    session_date = s.get("session_date", "")
                    if session_date:
                        try:
                            dt = datetime.fromisoformat(str(session_date).replace("Z", "+00:00"))
                            _months = ["January","February","March","April","May","June",
                                       "July","August","September","October","November","December"]
                            _hour = dt.hour
                            _hour12 = _hour % 12 or 12
                            _ampm = "AM" if _hour < 12 else "PM"
                            _minute = f"{dt.minute:02d}"
                            session_date = f"{_months[dt.month - 1]} {dt.day}, {dt.year} at {_hour12}:{_minute} {_ampm}"
                        except Exception:
                            pass
                    location = s.get("location") or "No location specified"
                    notes = s.get("notes") or ""
                    game_details = s.get("games_played_details", [])
                    games_html = ", ".join(g["title"] for g in game_details) if game_details else "No games recorded"
                    session_id = s.get("id", "")

                    is_admin = (
                        self.current_user
                        and self.current_user.current_user_info
                        and self.current_user.current_user_info.get("authorizations", {}).get("is_admin", False)
                    )
                    delete_btn = (
                        f'<button type="button" class="play-log-delete-session-btn" '
                        f'data-session-id="{session_id}">Delete</button>'
                        if is_admin else ""
                    )

                    html += f"""
                    <div class="play-log-session-card" data-session-id="{session_id}">
                        <div class="play-log-session-header">
                            <span class="play-log-session-date">{session_date}</span>
                            <span class="play-log-session-location">{location}</span>
                            {delete_btn}
                        </div>
                        <div class="play-log-session-games"><strong>Games:</strong> {games_html}</div>
                        {f'<div class="play-log-session-notes"><strong>Notes:</strong> {notes}</div>' if notes else ''}
                    </div>
                    """
                container[0].innerHTML = html

                for btn in document.select(".play-log-delete-session-btn"):
                    btn.bind("click", self._handle_delete_session)

                # Pagination
                if pagination:
                    total_pages = (total + self.SESSIONS_PER_PAGE - 1) // self.SESSIONS_PER_PAGE
                    self._render_sessions_pagination(total_pages, page, pagination[0])
            else:
                container[0].innerHTML = f"<p>Failed to load sessions. Status: {req.status}</p>"

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open(
            "GET",
            f"{BASE_URL}/api/v1/play-log?limit={self.SESSIONS_PER_PAGE}&offset={offset}",
            True,
        )
        req.set_header("Authorization", f"Bearer {window.localStorage.getItem('auth_token')}")
        req.send()

    def _handle_delete_session(self, event):
        session_id = int(event.target.attrs["data-session-id"])

        def on_complete(req):
            if req.status == 200:
                self._load_sessions(self._current_page)
            else:
                container = document.get(selector="#play-log-sessions-list")
                if container:
                    container[0].insertAdjacentHTML(
                        "afterbegin",
                        f'<p style="color:#e74c3c;">Failed to delete session. Status: {req.status}</p>',
                    )

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("DELETE", f"{BASE_URL}/api/v1/play-log/{session_id}", True)
        req.set_header("Authorization", f"Bearer {window.localStorage.getItem('auth_token')}")
        req.send()

    def _render_sessions_pagination(self, total_pages: int, current_page: int, container):
        if total_pages <= 1:
            container.innerHTML = ""
            return

        html = '<div class="pagination-controls">'
        if current_page > 1:
            html += f'<button class="page-btn" data-page="{current_page - 1}">‹ Prev</button>'
        for p in range(1, total_pages + 1):
            active = ' active' if p == current_page else ''
            html += f'<button class="page-btn{active}" data-page="{p}">{p}</button>'
        if current_page < total_pages:
            html += f'<button class="page-btn" data-page="{current_page + 1}">Next ›</button>'
        html += "</div>"
        container.innerHTML = html

        for btn in container.select(".page-btn"):
            btn.bind("click", self._handle_pagination_click)

    def _handle_pagination_click(self, event):
        event.stopPropagation()
        page = int(event.target.attrs["data-page"])
        self._load_sessions(page)
