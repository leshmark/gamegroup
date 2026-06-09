from browser import document, ajax, window, html
from browser.local_storage import storage
import json
import urllib.parse
from config import BASE_URL


class VerifyLinkHandler:
    """Handles authentication link verification"""

    def __init__(self):
        token = self.get_query_param('token')
        if token:
            self.verify_link(token)
        else:
            self._set_step('error', '\u2717', 'No token found in the link. Please use the original link from your email.')

    def get_query_param(self, param_name):
        query_string = window.location.search
        params = urllib.parse.parse_qs(query_string[1:])
        return params.get(param_name, [None])[-1]

    def _set_step(self, state, icon, text):
        """Replace the main status step with a new state/icon/message."""
        step = document['step-main']
        step.className = f'status-step {state}'
        step.html = f'<span class="status-icon">{icon}</span><span>{text}</span>'

    def _add_step(self, state, icon, text):
        """Append an additional status row below the main step."""
        document['status-steps'] <= html.DIV(
            html.SPAN(icon, Class='status-icon') + html.SPAN(text),
            Class=f'status-step {state}',
        )

    def _close_or_redirect(self):
        """Close the window if script-opened, otherwise redirect to home."""
        if storage.get('link_verification_semaphore', 'true') == 'true':
            storage.pop('link_verification_semaphore', None)
            window.location.href = BASE_URL
        else:
            storage.pop('link_verification_semaphore', None)
            window.close()

    def _show_pin_setup(self, jwt_token):
        """Display the PIN set/reset section after successful authentication."""
        section = document['pin-setup-section']
        section.style.display = ''
        window.setTimeout(self._close_or_redirect, 5000)

        def on_submit(event):
            event.preventDefault()
            pin = document['pin-new'].value.strip()
            confirm = document['pin-confirm'].value.strip()
            msg = document['pin-setup-message']

            if not pin:
                msg.text = 'Please enter a PIN.'
                msg.className = 'message error'
                return
            if pin != confirm:
                msg.text = 'PINs do not match.'
                msg.className = 'message error'
                return
            import re
            if not re.match(r'^\d{4,8}$', pin):
                msg.text = 'PIN must be 4\u20138 digits.'
                msg.className = 'message error'
                return

            submit_btn = document.querySelector('#pin-setup-form .pin-submit-btn')
            submit_btn.disabled = True
            submit_btn.text = 'Saving\u2026'
            msg.text = ''
            msg.className = 'message'

            def on_complete(req):
                submit_btn.disabled = False
                submit_btn.text = 'Set PIN'
                if req.status == 200:
                    section.style.display = 'none'
                    self._add_step('success', '\u2713', 'PIN set successfully.')
                    window.setTimeout(self._close_or_redirect, 3000)
                else:
                    try:
                        detail = json.loads(req.text).get('detail', 'Failed to set PIN.')
                    except Exception:
                        detail = 'Failed to set PIN.'
                    msg.text = detail
                    msg.className = 'message error'

            req = ajax.Ajax()
            req.bind('complete', on_complete)
            req.open('POST', f'{BASE_URL}/api/v1/auth/action/set-pin', True)
            req.set_header('Content-Type', 'application/json')
            req.set_header('Authorization', f'Bearer {jwt_token}')
            req.send(json.dumps({'pin': pin}))

        document['pin-setup-form'].bind('submit', on_submit)
        document['pin-skip-btn'].bind('click', lambda e: window.setTimeout(self._close_or_redirect, 100))

    def verify_link(self, token):
        """Verify the authentication token with the backend"""
        def on_complete(req):
            if req.status == 200:
                response = json.loads(req.text)
                jwt_token = response['jwt']
                storage['auth_token'] = jwt_token
                storage['user_email'] = response['user_email']
                # Set a semaphore to detect if the originating window is still open for receiving the auth verification response.
                storage['link_verification_semaphore'] = 'true'
                self._set_step('success', '\u2713', f"Authenticated as {response['user_email']}")
                self._show_pin_setup(jwt_token)
            else:
                self._set_step('error', '\u2717', 'Verification failed \u2014 the link may be invalid or expired.')
                self._add_step('info', '\u23f1', 'This window will close or you will be redirected in 5\xa0seconds\u2026')
                window.setTimeout(self._close_or_redirect, 5000)

        req = ajax.Ajax()
        req.bind('complete', on_complete)
        req.open('POST', f'{BASE_URL}/api/v1/auth/action/verify-link', True)
        req.set_header('Content-Type', 'application/json')
        req.send(json.dumps({'token': token}))
