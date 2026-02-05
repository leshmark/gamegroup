import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import HTTPException


class EmailService:
    """Service for sending authentication emails"""
    
    def __init__(self):
        """Initialize email service with configuration from environment variables"""
        self.logger = logging.getLogger(__name__)
        self.sender_email = os.getenv("FORWARD_EMAIL_USER")
        self.password = os.getenv("FORWARD_EMAIL_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@gamegroup.com")
        
        if not self.sender_email or not self.password:
            raise ValueError("Email configuration missing: FORWARD_EMAIL_USER and FORWARD_EMAIL_PASSWORD required")
    
    def send_auth_email(self, email: str, magic_link: str):
        """
        Send authentication magic link via email using SMTP
        
        Args:
            email: Recipient email address
            magic_link: Authentication URL to include in email
        """
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = "Your Game Group Login Link"
        message["From"] = self.from_email
        message["To"] = email
        
        # Create the plain-text and HTML version of the message
        text = f"""Hello!

Click the following link to log in to Game Group:

{magic_link}

This link will expire in 15 minutes.

If you did not request this login link, please ignore this email.
"""
        
        html = f"""
        <html>
            <body>
                <h2>Game Group Login</h2>
                <p>Click the button below to log in to Game Group:</p>
                <p><a href="{magic_link}" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-align: center; text-decoration: none; display: inline-block; border-radius: 4px;">Login to Game Group</a></p>
                <p>Or copy and paste this link into your browser:</p>
                <p>{magic_link}</p>
                <p><em>This link will expire in 15 minutes.</em></p>
                <p>If you did not request this login link, please ignore this email.</p>
            </body>
        </html>
        """
        
        # Turn these into plain/html MIMEText objects
        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        
        # Add HTML/plain-text parts to MIMEMultipart message
        message.attach(part1)
        message.attach(part2)
        
        # Send email
        try:
            server = smtplib.SMTP_SSL("smtp.forwardemail.net", 465)
            server.login(self.sender_email, self.password)
            server.sendmail(self.from_email, email, message.as_string())
            server.quit()
            self.logger.info(f"Email sent successfully to {email}")
        except Exception as e:
            self.logger.error(f"Error sending email: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Email sending failed: {str(e)}")
