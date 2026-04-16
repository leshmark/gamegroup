from browser import ajax, window
import json
from config import BASE_URL


class VoteMixin:
    """Mixin that provides next-play vote toggle behaviour.

    Consumers must either inherit show_notification or accept the default
    window.alert fallback used here.
    """

    def show_notification(self, message, message_type="error"):
        """Fallback notification – subclasses should override for inline display."""
        window.alert(message)

    def toggle_vote(self, event):
        """Handle next play vote toggle"""
        event.stopPropagation()
        button = event.target
        game_id = button.getAttribute("data-game-id")
        if not game_id:
            return
        original_text = button.textContent
        button.disabled = True
        button.textContent = "..."
        self._fetch_vote_status(game_id, button, original_text)

    def _fetch_vote_status(self, game_id, button, original_text):
        """GET current vote status, then submit the toggled value"""

        def on_complete(req):
            if req.status == 200:
                response = json.loads(req.text)
                user_has_voted = response.get("user_has_voted", False)
                self._submit_vote(game_id, not user_has_voted, button, original_text)
            else:
                self._restore_vote_button(button, original_text)
                if req.status == 401:
                    self.show_notification("Please log in to vote.", "error")
                else:
                    self.show_notification(
                        f"Failed to get vote status. Status: {req.status}", "error"
                    )

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("GET", f"{BASE_URL}/api/v1/game/{game_id}/vote", True)
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
        req.send()

    def _submit_vote(self, game_id, vote_value, button, original_text):
        """POST the new vote value, then fetch the updated state"""

        def on_complete(req):
            if req.status == 200:
                self._fetch_updated_vote_state(game_id, button, original_text)
            else:
                self._restore_vote_button(button, original_text)
                self.show_notification(
                    f"Failed to update vote. Status: {req.status}", "error"
                )

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("POST", f"{BASE_URL}/api/v1/game/{game_id}/vote", True)
        req.set_header("Content-Type", "application/json")
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
        req.send(json.dumps({"vote": vote_value}))

    def _fetch_updated_vote_state(self, game_id, button, original_text):
        """GET the refreshed vote state and update the button"""

        def on_complete(req):
            if req.status == 200:
                response = json.loads(req.text)
                self._update_vote_button(
                    button,
                    response.get("total_votes", 0),
                    response.get("user_has_voted", False),
                )
            else:
                self._restore_vote_button(button, original_text)
                self.show_notification(
                    f"Failed to refresh vote count. Status: {req.status}", "error"
                )

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("GET", f"{BASE_URL}/api/v1/game/{game_id}/vote", True)
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
        req.send()

    def _update_vote_button(self, button, count, user_voted):
        """Update vote button text and styling after a successful toggle"""
        button.textContent = f"Play Next {count}"
        if user_voted:
            button.classList.add("voted")
        else:
            button.classList.remove("voted")
        button.disabled = False

    def _restore_vote_button(self, button, original_text):
        """Restore the vote button to its pre-request state"""
        button.textContent = original_text
        button.disabled = False
