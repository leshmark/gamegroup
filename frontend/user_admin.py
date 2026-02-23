from browser import ajax, document, window
import json
from config import BASE_URL


class UserAdmin:
    """Handles admin user management functionality"""

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
                        except Exception:
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
        req.bind("complete", on_complete)
        req.open("GET", f"{BASE_URL}/api/admin/user", True)
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
        req.send()
