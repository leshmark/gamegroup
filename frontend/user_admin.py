from browser import ajax, document, window, timer
from browser.local_storage import storage
import json
from config import BASE_URL


class UserAdmin:
    """Handles admin user management functionality"""

    def __init__(self):
        """Initialize UserAdmin"""
        self.add_user_form_visible = False
        self.update_auth_form_visible = False

    def show_notification(self, message, message_type="success", duration=4000):
        """Display an inline notification message

        Args:
            message: The message to display
            message_type: Type of message ('success', 'error')
            duration: How long to show the message in milliseconds
        """
        message_div = document["admin-message"]
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

    def show_add_user_form(self):
        """Display the add user form"""
        form_container = document["add-user-form-container"]
        if not form_container:
            return

        form_html = """
        <div class="add-user-form">
            <h3>Add New User</h3>
            <form id="add-user-form">
                <div class="form-group">
                    <label for="user-email">Email:</label>
                    <input type="email" id="user-email" name="email" required />
                </div>
                <div class="form-group">
                    <label for="user-username">Username:</label>
                    <input type="text" id="user-username" name="username" required />
                </div>
                <div class="form-group">
                    <label>Authorizations:</label>
                    <div class="checkbox-group">
                        <label>
                            <input type="checkbox" id="user-is-viewer" name="is_viewer"/>
                            Viewer
                        </label>
                        <label>
                            <input type="checkbox" id="user-is-contributor" name="is_contributor" />
                            Contributor
                        </label>
                        <label>
                            <input type="checkbox" id="user-is-admin" name="is_admin" />
                            Admin
                        </label>
                    </div>
                </div>
                <div class="form-actions">
                    <button type="submit" class="submit-btn">Add User</button>
                    <button type="button" id="cancel-add-user" class="submit-btn" style="margin-left: 1rem;">Cancel</button>
                </div>
            </form>
        </div>
        """

        form_container.innerHTML = form_html
        self.add_user_form_visible = True

        # Hide the Add User button
        add_user_btn = document["add-user-btn"]
        if add_user_btn:
            add_user_btn.style.display = "none"

        # Bind form events
        add_form = document["add-user-form"]
        if add_form:
            add_form.bind("submit", lambda e: self.handle_add_user_submit(e))

        cancel_btn = document["cancel-add-user"]
        if cancel_btn:
            cancel_btn.bind("click", lambda e: self.hide_add_user_form())

    def hide_add_user_form(self):
        """Hide the add user form"""
        form_container = document["add-user-form-container"]
        if form_container:
            form_container.innerHTML = ""
            self.add_user_form_visible = False

        # Show the Add User button
        add_user_btn = document["add-user-btn"]
        if add_user_btn:
            add_user_btn.style.display = ""

    def show_update_auth_form(self):
        """Display the update authorizations form"""
        # Get selected users
        selected_users = self.get_selected_users()

        if not selected_users:
            self.show_notification(
                "Please select at least one user to update.", "error"
            )
            return

        form_container = document["add-user-form-container"]
        if not form_container:
            return

        # Create list of selected usernames
        usernames = ", ".join([u["username"] for u in selected_users])

        # Determine which checkboxes should be checked
        # If all selected users share an authorization, check that box
        is_viewer_checked = ""
        is_contributor_checked = ""
        is_admin_checked = ""

        if selected_users:
            # Count how many users have each authorization
            viewer_count = sum(
                1 for u in selected_users if "is_viewer" in u.get("authorizations", "")
            )
            contributor_count = sum(
                1
                for u in selected_users
                if "is_contributor" in u.get("authorizations", "")
            )
            admin_count = sum(
                1 for u in selected_users if "is_admin" in u.get("authorizations", "")
            )
            total = len(selected_users)

            # Check the box if all selected users have that authorization
            if viewer_count == total:
                is_viewer_checked = "checked"
            if contributor_count == total:
                is_contributor_checked = "checked"
            if admin_count == total:
                is_admin_checked = "checked"

        form_html = f"""
        <div class="add-user-form">
            <h3>Update Authorizations</h3>
            <p>Update authorizations for: {usernames}</p>
            <form id="update-auth-form">
                <div class="form-group">
                    <label>Authorizations:</label>
                    <div class="checkbox-group">
                        <label>
                            <input type="checkbox" id="update-is-viewer" name="is_viewer" {is_viewer_checked}/>
                            Viewer
                        </label>
                        <label>
                            <input type="checkbox" id="update-is-contributor" name="is_contributor" {is_contributor_checked}/>
                            Contributor
                        </label>
                        <label>
                            <input type="checkbox" id="update-is-admin" name="is_admin" {is_admin_checked}/>
                            Admin
                        </label>
                    </div>
                </div>
                <div class="form-actions">
                    <button type="submit" class="submit-btn">Update Authorizations</button>
                    <button type="button" id="cancel-update-auth" class="submit-btn" style="margin-left: 1rem;">Cancel</button>
                </div>
            </form>
        </div>
        """

        form_container.innerHTML = form_html
        self.update_auth_form_visible = True

        # Hide the Update Authorizations button
        update_auth_btn = document["update-auth-btn"]
        if update_auth_btn:
            update_auth_btn.style.display = "none"

        # Bind form events
        update_form = document["update-auth-form"]
        if update_form:
            update_form.bind("submit", lambda e: self.handle_update_auth_submit(e))

        cancel_btn = document["cancel-update-auth"]
        if cancel_btn:
            cancel_btn.bind("click", lambda e: self.hide_update_auth_form())

    def hide_update_auth_form(self):
        """Hide the update authorizations form"""
        form_container = document["add-user-form-container"]
        if form_container:
            form_container.innerHTML = ""
            self.update_auth_form_visible = False

        # Show the Update Authorizations button
        update_auth_btn = document["update-auth-btn"]
        if update_auth_btn:
            update_auth_btn.style.display = ""

    def handle_update_auth_submit(self, event):
        """Handle update authorizations form submission"""
        event.preventDefault()

        # Get selected users
        selected_users = self.get_selected_users()

        if not selected_users:
            window.alert("No users selected.")
            return

        # Get form values
        is_viewer = document["update-is-viewer"].checked
        is_contributor = document["update-is-contributor"].checked
        is_admin = document["update-is-admin"].checked

        # Track update results
        updated_count = 0
        failed_updates = []
        total = len(selected_users)

        def update_user(user, idx):
            """Update a single user's authorizations"""
            nonlocal updated_count, failed_updates

            # Prepare data using existing POST endpoint (upsert)
            user_data = {
                "email": user["email"],
                "username": user["username"],
                "is_viewer": is_viewer,
                "is_contributor": is_contributor,
                "is_admin": is_admin,
            }

            def on_complete(req):
                nonlocal updated_count, failed_updates

                if req.status == 200:
                    updated_count += 1
                else:
                    try:
                        error = json.loads(req.text)
                        error_msg = f"{user['username']}: {error.get('detail', 'Unknown error')}"
                    except Exception:
                        error_msg = f"{user['username']}: Status {req.status}"
                    failed_updates.append(error_msg)

                # Check if all requests are complete
                if updated_count + len(failed_updates) == total:
                    # Show results if failed updates exist
                    if updated_count > 0 and len(failed_updates) > 0:
                        self.show_notification(
                            f"Updated {updated_count} user(s). Failed: {len(failed_updates)}",
                            "error",
                            5000,
                        )
                    elif updated_count == 0 and len(failed_updates) > 0:
                        self.show_notification(
                            f"Failed to update all users. {failed_updates[0] if failed_updates else ''}",
                            "error",
                            5000,
                        )
                    else:
                        self.show_notification(
                            f"Successfully updated {updated_count} user(s)", "success"
                        )

                    # Hide form and reload the user list
                    self.hide_update_auth_form()
                    self.load_users()

            req = ajax.Ajax()
            req.bind("complete", on_complete)
            req.open("POST", f"{BASE_URL}/api/v1/admin/user", True)
            req.set_header("Content-Type", "application/json")
            req.set_header(
                "Authorization", f"Bearer {storage.get('auth_token','')}"
            )
            req.send(json.dumps(user_data))

        # Update each selected user
        for idx, user in enumerate(selected_users):
            update_user(user, idx)

    def handle_add_user_submit(self, event):
        """Handle add user form submission"""
        event.preventDefault()

        # Get form values
        email = document["user-email"].value.strip()
        username = document["user-username"].value.strip()
        is_viewer = document["user-is-viewer"].checked
        is_contributor = document["user-is-contributor"].checked
        is_admin = document["user-is-admin"].checked

        # Validate
        if not email or not username:
            self.show_notification("Email and username are required.", "error")
            return

        # Prepare data
        user_data = {
            "email": email,
            "username": username,
            "is_viewer": is_viewer,
            "is_contributor": is_contributor,
            "is_admin": is_admin,
        }

        # Send request
        def on_complete(req):
            if req.status == 200:
                self.show_notification(
                    f"User '{username}' added successfully!", "success"
                )
                self.hide_add_user_form()
                self.load_users()
            else:
                try:
                    error = json.loads(req.text)
                    self.show_notification(
                        f"Failed to add user: {error.get('detail', 'Unknown error')}",
                        "error",
                    )
                except Exception:
                    self.show_notification(
                        f"Failed to add user. Status: {req.status}", "error"
                    )

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("POST", f"{BASE_URL}/api/v1/admin/user", True)
        req.set_header("Content-Type", "application/json")
        req.set_header(
            "Authorization", f"Bearer {storage.get('auth_token','')}"
        )
        req.send(json.dumps(user_data))

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
                            <th><input type="checkbox" id="select-all-users" /></th>
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
                        except Exception:
                            pass

                    # Store authorizations in data attributes
                    authorizations = user.get("authorizations", "")

                    table_html += f"""
                        <tr>
                            <td><input type="checkbox" class="user-select-checkbox" data-email="{user.get("email", "")}" data-username="{user.get("username", "")}" data-authorizations="{authorizations}" /></td>
                            <td>{user.get("username", "")}</td>
                            <td>{user.get("email", "")}</td>
                            <td>{auth_html}</td>
                            <td>{created_at}</td>
                        </tr>
                    """

                table_html += """
                    </tbody>
                </table>
                <div class="user-actions">
                    <button id="add-user-btn" class="submit-btn">Add User</button>
                    <button id="delete-selected-users-btn" class="submit-btn">Delete Selected</button>
                    <button id="update-auth-btn" class="submit-btn">Update Authorizations</button>
                    <button id="get-magic-link-btn" class="submit-btn">Get Login Link</button>
                </div>
                """

                users_container.innerHTML = table_html

                # Add event listeners for checkboxes
                def toggle_all(event):
                    """Toggle all user checkboxes"""
                    checkboxes = document.select(".user-select-checkbox")
                    for checkbox in checkboxes:
                        checkbox.checked = event.target.checked

                def update_select_all():
                    """Update select-all checkbox state based on individual selections"""
                    checkboxes = document.select(".user-select-checkbox")
                    select_all = document["select-all-users"]
                    if checkboxes:
                        total = len(checkboxes)
                        checked = sum(1 for cb in checkboxes if cb.checked)
                        select_all.checked = checked == total
                        select_all.indeterminate = 0 < checked < total

                # Bind select-all checkbox
                select_all_checkbox = document["select-all-users"]
                if select_all_checkbox:
                    select_all_checkbox.bind("change", toggle_all)

                # Bind individual checkboxes
                user_checkboxes = document.select(".user-select-checkbox")
                for checkbox in user_checkboxes:
                    checkbox.bind("change", lambda e: update_select_all())

                # Bind action buttons
                add_btn = document["add-user-btn"]
                if add_btn:
                    add_btn.bind("click", lambda e: self.show_add_user_form())

                delete_btn = document["delete-selected-users-btn"]
                if delete_btn:
                    delete_btn.bind("click", lambda e: self.delete_selected_users())

                update_auth_btn = document["update-auth-btn"]
                if update_auth_btn:
                    update_auth_btn.bind(
                        "click", lambda e: self.show_update_auth_form()
                    )

                get_magic_link_btn = document["get-magic-link-btn"]
                if get_magic_link_btn:
                    get_magic_link_btn.bind(
                        "click", lambda e: self.request_magic_link()
                    )
            elif req.status == 403:
                users_container.innerHTML = "<p style='color: #e74c3c;'>Access denied. Admin privileges required.</p>"
            else:
                users_container.innerHTML = f"<p style='color: #e74c3c;'>Failed to load users. Status: {req.status}</p>"

        users_container = document["users-list-container"]
        users_container.innerHTML = "<p>Loading users...</p>"

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("GET", f"{BASE_URL}/api/v1/admin/user", True)
        req.set_header(
            "Authorization", f"Bearer {storage.get('auth_token','')}"
        )
        req.send()
        self.load_vote_history()

    def load_vote_history(self):
        """Fetch and display 12 weeks of next-play vote counts for every game."""
        vote_history_container = document["vote-history-container"]
        vote_history_container.innerHTML = "<p>Loading vote history...</p>"

        def on_complete(req):
            if req.status == 200:
                response = json.loads(req.text)
                games = response.get("games", [])
                weeks = response.get("weeks", [])

                games = [
                    game
                    for game in games
                    if sum(
                        week_vote.get("vote_count", 0)
                        for week_vote in game.get("weekly_votes", [])
                    )
                    > 0
                ]

                if not games:
                    vote_history_container.innerHTML = "<p>No votes recorded in the last 12 weeks.</p>"
                    return

                vote_totals = [
                    sum(week_vote.get("vote_count", 0) for week_vote in game.get("weekly_votes", []))
                    for game in games
                ]
                maximum_vote_total = max(vote_totals) if vote_totals else 0

                table_html = """
                <table class="vote-history-table">
                    <thead>
                        <tr>
                            <th>Game</th>
                            <th class="vote-history-total-header">12-Week Total</th>
                """
                for week in weeks:
                    table_html += f"<th>{week}</th>"

                table_html += """
                        </tr>
                    </thead>
                    <tbody>
                """
                for index, game in enumerate(games):
                    vote_total = vote_totals[index]
                    bar_width = (
                        (vote_total / maximum_vote_total) * 100
                        if maximum_vote_total
                        else 0
                    )
                    table_html += f"<tr><td>{game.get('title', '')}</td>"
                    table_html += f"""
                        <td class="vote-history-total-column">
                            <div class="vote-total-bar" title="{vote_total} votes in the last 12 weeks">
                                <div class="vote-total-bar-fill" style="width: {bar_width}%;"></div>
                            </div>
                            <span class="vote-total-value">{vote_total}</span>
                        </td>
                    """
                    for week_vote in game.get("weekly_votes", []):
                        table_html += f"<td>{week_vote.get('vote_count', 0)}</td>"
                    table_html += "</tr>"

                table_html += """
                    </tbody>
                </table>
                """
                vote_history_container.innerHTML = table_html
            elif req.status == 403:
                vote_history_container.innerHTML = "<p style='color: #e74c3c;'>Access denied. Admin privileges required.</p>"
            else:
                vote_history_container.innerHTML = f"<p style='color: #e74c3c;'>Failed to load vote history. Status: {req.status}</p>"

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("GET", f"{BASE_URL}/api/v1/admin/vote-history", True)
        req.set_header(
            "Authorization", f"Bearer {storage.get('auth_token','')}"
        )
        req.send()

    def get_selected_users(self):
        """Get list of selected users from checkboxes"""
        selected_users = []
        checkboxes = document.select(".user-select-checkbox")
        for checkbox in checkboxes:
            if checkbox.checked:
                selected_users.append(
                    {
                        "email": checkbox.attrs.get("data-email", ""),
                        "username": checkbox.attrs.get("data-username", ""),
                        "authorizations": checkbox.attrs.get("data-authorizations", ""),
                    }
                )
        return selected_users

    def delete_selected_users(self):
        """Delete selected users after confirmation"""
        selected_users = self.get_selected_users()

        if not selected_users:
            self.show_notification(
                "Please select at least one user to delete.", "error"
            )
            return

        # Confirm deletion
        usernames = ", ".join([u["username"] for u in selected_users])
        count = len(selected_users)
        confirm_msg = (
            f"Are you sure you want to delete {count} user(s)?\n\nUsers: {usernames}"
        )

        if not window.confirm(confirm_msg):
            return

        # Track deletion results
        deleted_count = 0
        failed_deletions = []
        total = len(selected_users)

        def delete_user(username, idx):
            """Delete a single user"""
            nonlocal deleted_count, failed_deletions

            def on_complete(req):
                nonlocal deleted_count, failed_deletions

                if req.status == 200:
                    deleted_count += 1
                else:
                    error_msg = f"{username}: {req.text}"
                    failed_deletions.append(error_msg)

                # Check if all requests are complete
                if deleted_count + len(failed_deletions) == total:
                    # Show results
                    if deleted_count > 0 and len(failed_deletions) == 0:
                        self.show_notification(
                            f"Successfully deleted {deleted_count} user(s).", "success"
                        )
                    elif deleted_count > 0:
                        self.show_notification(
                            f"Deleted {deleted_count} user(s). Failed: {len(failed_deletions)}",
                            "error",
                            5000,
                        )
                    else:
                        self.show_notification(
                            f"Failed to delete all users. {failed_deletions[0] if failed_deletions else ''}",
                            "error",
                            5000,
                        )

                    # Reload the user list
                    self.load_users()

            req = ajax.Ajax()
            req.bind("complete", on_complete)
            req.open("DELETE", f"{BASE_URL}/api/v1/admin/user/{username}", True)
            req.set_header(
                "Authorization", f"Bearer {storage.get('auth_token','')}"
            )
            req.send()

        # Delete each selected user
        for idx, user in enumerate(selected_users):
            delete_user(user["username"], idx)

    def request_magic_link(self):
        """Request a reusable (non-one-time) magic link for the selected user"""
        selected_users = self.get_selected_users()

        if len(selected_users) != 1:
            self.show_notification(
                "Please select exactly one user to generate a login link.", "error"
            )
            return

        email = selected_users[0]["email"]

        def on_complete(req):
            if req.status == 200:
                response = json.loads(req.text)
                magic_link = response.get("magic_link")
                if magic_link:
                    self.show_magic_link(magic_link, email)
                else:
                    self.show_notification(
                        "No magic link returned from server.", "error"
                    )
            else:
                try:
                    error = json.loads(req.text)
                    self.show_notification(
                        f"Failed to generate link: {error.get('detail', 'Unknown error')}",
                        "error",
                    )
                except Exception:
                    self.show_notification(
                        f"Failed to generate link. Status: {req.status}", "error"
                    )

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("POST", f"{BASE_URL}/api/v1/auth/action/request-link", True)
        req.set_header("Content-Type", "application/json")
        req.set_header(
            "Authorization", f"Bearer {storage.get('auth_token','')}"
        )
        req.send(json.dumps({"email": email, "one_time_link": False}))

    def show_magic_link(self, magic_link, email):
        """Display the generated magic link to the admin"""
        form_container = document["add-user-form-container"]
        if not form_container:
            return

        form_html = f"""
        <div class="add-user-form">
            <h3>Login Link</h3>
            <p>Reusable login link for <strong>{email}</strong>. This link remains valid until 24&nbsp;hours after creation. Share it securely.</p>
            <div class="form-group">
                <label for="magic-link-display">Magic Link:</label>
                <div style="display: flex; gap: 0.5rem; align-items: stretch;">
                    <input type="text" id="magic-link-display" value="{magic_link}" readonly
                           style="flex: 1; background: #f8f9fa; cursor: text; font-size: 0.9rem; font-family: monospace;" />
                    <button id="copy-magic-link-btn" class="submit-btn" style="white-space: nowrap;">Copy</button>
                </div>
            </div>
            <div class="form-actions">
                <button type="button" id="close-magic-link" class="submit-btn">Close</button>
            </div>
        </div>
        """

        form_container.innerHTML = form_html

        # Hide the Get Login Link button while the panel is open
        link_btn = document["get-magic-link-btn"]
        if link_btn:
            link_btn.style.display = "none"

        copy_btn = document["copy-magic-link-btn"]
        if copy_btn:

            def do_copy(e):
                window.navigator.clipboard.writeText(magic_link)
                copy_btn.textContent = "Copied!"
                timer.set_timeout(
                    lambda: setattr(copy_btn, "textContent", "Copy"), 2000
                )

            copy_btn.bind("click", do_copy)

        close_btn = document["close-magic-link"]
        if close_btn:

            def do_close(e):
                form_container.innerHTML = ""
                btn = document["get-magic-link-btn"]
                if btn:
                    btn.style.display = ""

            close_btn.bind("click", do_close)
