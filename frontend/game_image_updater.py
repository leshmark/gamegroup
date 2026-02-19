from browser import ajax, document, window
import json
from config import BASE_URL

class GameImageUpdater:
    """Handles updating game images from BoardGameGeek"""
    
    def update_game_images(self, event):
        """Handle update game images button click"""
        event.preventDefault()
        
        update_btn = document["update-images-btn"]
        status_div = document["update-images-status"]
        results_div = document["update-images-results"]
        
        # Disable button and show loading message
        update_btn.disabled = True
        update_btn.text = "Updating..."
        status_div.innerHTML = "<p>Fetching game images from BoardGameGeek. This may take a while...</p>"
        status_div.className = "message info"
        results_div.innerHTML = ""
        
        def on_complete(req):
            update_btn.disabled = False
            update_btn.text = "Update Missing Game Images"
            
            if req.status == 200:
                response = json.loads(req.text)
                
                # Show summary
                status_html = f"""
                <h4>Update Complete</h4>
                <p><strong>Total games processed:</strong> {response['total']}</p>
                <p><strong>Successfully updated:</strong> <span style="color: #27ae60;">{response['successful']}</span></p>
                <p><strong>Failed:</strong> <span style="color: #e74c3c;">{response['failed']}</span></p>
                """
                status_div.innerHTML = status_html
                status_div.className = "message success"
                
                # Show detailed results if there are any
                if response.get('results'):
                    results_html = '<h4>Detailed Results</h4><div class="results-list">'
                    
                    for result in response['results']:
                        status_icon = "✓" if result['status'] == 'success' else "✗"
                        status_color = "#27ae60" if result['status'] == 'success' else "#e74c3c"
                        
                        results_html += f"""
                        <div class="result-item" style="margin-bottom: 10px; padding: 10px; border-left: 3px solid {status_color};">
                            <p style="margin: 0;"><strong style="color: {status_color};">{status_icon}</strong> <strong>{result['title']}</strong> (ID: {result['id']})</p>
                        """
                        
                        if result['status'] == 'success':
                            results_html += f'<p style="margin: 5px 0 0 0; font-size: 0.9em; color: #7f8c8d;">Image URL updated successfully</p>'
                        else:
                            error_msg = result.get('error', 'Unknown error')
                            results_html += f'<p style="margin: 5px 0 0 0; font-size: 0.9em; color: #e74c3c;">Error: {error_msg}</p>'
                        
                        results_html += '</div>'
                    
                    results_html += '</div>'
                    results_div.innerHTML = results_html
                    
            elif req.status == 403:
                status_div.innerHTML = "<p>Access denied. Admin privileges required.</p>"
                status_div.className = "message error"
            else:
                error_msg = "Unknown error"
                try:
                    error_data = json.loads(req.text)
                    error_msg = error_data.get('detail', error_msg)
                except:
                    pass
                status_div.innerHTML = f"<p>Failed to update images: {error_msg}</p>"
                status_div.className = "message error"
        
        def on_error(req):
            update_btn.disabled = False
            update_btn.text = "Update Missing Game Images"
            status_div.innerHTML = "<p>Network error occurred. Please try again.</p>"
            status_div.className = "message error"
        
        # Make API request
        auth_token = window.localStorage.getItem("auth_token")
        req = ajax.Ajax()
        req.bind('complete', on_complete)
        req.bind('error', on_error)
        req.open('POST', f'{BASE_URL}/api/admin/action/update-game-images', True)
        req.set_header('Authorization', f'Bearer {auth_token}')
        req.set_header('Content-Type', 'application/json')
        req.send()
