from browser import ajax, document, window
import json
from config import BASE_URL


class UserAdmin:
    """Handles admin user management functionality"""

    def __init__(self):
        """Initialize UserAdmin"""
        self.add_user_form_visible = False
        self.update_auth_form_visible = False

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
            window.alert("Please select at least one user to update.")
            return
        
        form_container = document["add-user-form-container"]
        if not form_container:
            return
        
        # Create list of selected usernames
        usernames = ", ".join([u["username"] for u in selected_users])
        
        form_html = f"""
        <div class="add-user-form">
            <h3>Update Authorizations</h3>
            <p>Update authorizations for: {usernames}</p>
            <form id="update-auth-form">
                <div class="form-group">
                    <label>Authorizations:</label>
                    <div class="checkbox-group">
                        <label>
                            <input type="checkbox" id="update-is-viewer" name="is_viewer"/>
                            Viewer
                        </label>
                        <label>
                            <input type="checkbox" id="update-is-contributor" name="is_contributor" />
                            Contributor
                        </label>
                        <label>
                            <input type="checkbox" id="update-is-admin" name="is_admin" />
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
                "is_admin": is_admin
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
                        window.alert(f"Updated {updated_count} user(s).\\nFailed: {len(failed_updates)}")
                    elif updated_count == 0 and len(failed_updates) > 0:
                        window.alert(f"Failed to update all users.\\n{failed_updates[0] if failed_updates else ''}")
                    
                    # Hide form and reload the user list
                    self.hide_update_auth_form()
                    self.load_users()
            
            req = ajax.Ajax()
            req.bind("complete", on_complete)
            req.open("POST", f"{BASE_URL}/api/admin/user", True)
            req.set_header("Content-Type", "application/json")
            req.set_header(
                "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
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
            window.alert("Email and username are required.")
            return
        
        # Prepare data
        user_data = {
            "email": email,
            "username": username,
            "is_viewer": is_viewer,
            "is_contributor": is_contributor,
            "is_admin": is_admin
        }
        
        # Send request
        def on_complete(req):
            if req.status == 200:
                window.alert(f"User '{username}' added successfully!")
                self.hide_add_user_form()
                self.load_users()
            else:
                try:
                    error = json.loads(req.text)
                    window.alert(f"Failed to add user: {error.get('detail', 'Unknown error')}")
                except Exception:
                    window.alert(f"Failed to add user. Status: {req.status}")
        
        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("POST", f"{BASE_URL}/api/admin/user", True)
        req.set_header("Content-Type", "application/json")
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
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

                    table_html += f"""
                        <tr>
                            <td><input type="checkbox" class="user-select-checkbox" data-email="{user.get("email", "")}" data-username="{user.get("username", "")}" /></td>
                            <td>{user.get("username", "")}</td>
                            <td>{user.get("email", "")}</td>
                            <td>{auth_html}</td>
                            <td>{created_at}</td>
                        </tr>
                    """

                table_html += """
                    </tbody>
                </table>
                <div class="user-actions" style="margin-top: 1rem;">
                    <button id="add-user-btn" class="submit-btn">Add User</button>
                    <button id="delete-selected-users-btn" class="submit-btn" style="margin-left: 1rem;">Delete Selected</button>
                    <button id="update-auth-btn" class="submit-btn" style="margin-left: 1rem;">Update Authorizations</button>
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
                    update_auth_btn.bind("click", lambda e: self.show_update_auth_form())
            elif req.status == 403:
                users_container.innerHTML = "<p style='color: #e74c3c;'>Access denied. Admin privileges required.</p>"
            else:
                users_container.innerHTML = f"<p style='color: #e74c3c;'>Failed to load users. Status: {req.status}</p>"

        users_container = document["users-list-container"]
        users_container.innerHTML = "<p>Loading users...</p>"

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("GET", f"{BASE_URL}/api/admin/user", True)
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
        req.send()

    def get_selected_users(self):
        """Get list of selected users from checkboxes"""
        selected_users = []
        checkboxes = document.select(".user-select-checkbox")
        for checkbox in checkboxes:
            if checkbox.checked:
                selected_users.append({
                    "email": checkbox.attrs.get("data-email", ""),
                    "username": checkbox.attrs.get("data-username", "")
                })
        return selected_users

    def delete_selected_users(self):
        """Delete selected users after confirmation"""
        selected_users = self.get_selected_users()
        
        if not selected_users:
            window.alert("Please select at least one user to delete.")
            return
        
        # Confirm deletion
        usernames = ", ".join([u["username"] for u in selected_users])
        count = len(selected_users)
        confirm_msg = f"Are you sure you want to delete {count} user(s)?\n\nUsers: {usernames}"
        
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
                        window.alert(f"Successfully deleted {deleted_count} user(s).")
                    elif deleted_count > 0:
                        window.alert(f"Deleted {deleted_count} user(s).\nFailed: {len(failed_deletions)}")
                    else:
                        window.alert(f"Failed to delete all users.\n{failed_deletions[0] if failed_deletions else ''}")
                    
                    # Reload the user list
                    self.load_users()
            
            req = ajax.Ajax()
            req.bind("complete", on_complete)
            req.open("DELETE", f"{BASE_URL}/api/admin/user/{username}", True)
            req.set_header(
                "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
            )
            req.send()
        
        # Delete each selected user
        for idx, user in enumerate(selected_users):
            delete_user(user["username"], idx)
