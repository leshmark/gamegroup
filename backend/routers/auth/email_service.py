"""Email service for sending authentication emails.

This module provides the :class:`EmailService` class, which handles delivery of
passwordless "magic link" login emails for the Game Group site. Emails are sent
over SMTP using the Forward Email (smtp.forwardemail.net) provider over an
SSL-encrypted connection on port 465.

Each authentication email is sent as a multipart/alternative message containing
both a plain-text and an HTML version, so that recipients with basic or
feature-rich mail clients both receive a usable login link.

Environment variables:
    FORWARD_EMAIL_USER (required):
        The Forward Email account username used to authenticate with the SMTP
        server. Typically the full email address of the sending account.
    FORWARD_EMAIL_PASSWORD (required):
        The password/API key for the Forward Email account.
    FROM_EMAIL (optional, default "noreply@gamegroup.com"):
        The display sender address placed in the ``From`` header of outgoing
        messages.

Usage:
    from routers.auth.email_service import EmailService

    service = EmailService()
    service.send_auth_email("user@example.com", "https://gamegroup.example/login?token=abc123")
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import HTTPException

# SMTP provider constants for Forward Email. Kept as module-level constants so
# they can be overridden in tests or reused elsewhere without re-reading env vars.
SMTP_HOST = "smtp.forwardemail.net"
SMTP_PORT = 465

# How long (in minutes) a magic link remains valid. This value is embedded in
# the email body and must stay in sync with the token expiration configured in
# AuthService.get_token_expiration / build_magic_link (default: 15 minutes).
LINK_EXPIRY_MINUTES = 15


class EmailService:
    """Service for sending authentication emails via SMTP.

    This class encapsulates all email-sending logic for the authentication
    flow. It is instantiated once by :class:`AuthRouter` and reused for every
    login-link request, so it holds no per-request state beyond configuration
    loaded from environment variables at construction time.

    Attributes:
        logger: Logger instance scoped to this module.
        sender_email: SMTP username used to authenticate with the mail server.
        password: SMTP password/API key for the sending account.
        from_email: Sender address shown in the ``From`` header of emails.
    """

    def __init__(self):
        """Initialize email service with configuration from environment variables.

        Reads the Forward Email credentials and sender address from the
        environment. The service is considered misconfigured (and will refuse
        to start) if either SMTP credential is missing, since no fallback or
        dry-run mode exists — authentication emails are a core feature.

        Raises:
            ValueError: If ``FORWARD_EMAIL_USER`` or ``FORWARD_EMAIL_PASSWORD``
                is not set in the environment.
        """
        self.logger = logging.getLogger(__name__)
        self.sender_email = os.getenv("FORWARD_EMAIL_USER")
        self.password = os.getenv("FORWARD_EMAIL_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@gamegroup.com")

        if not self.sender_email or not self.password:
            raise ValueError(
                "Email configuration missing: FORWARD_EMAIL_USER and FORWARD_EMAIL_PASSWORD required"
            )

    def send_auth_email(self, email: str, magic_link: str):
        """Send an authentication magic link to the given recipient via SMTP.

        Builds a multipart/alternative MIME message containing both plain-text
        and HTML renderings of the login link, then delivers it over an
        SSL-encrypted SMTP connection (port 465) using the configured Forward
        Email credentials.

        The email body informs the recipient that the link expires after
        :data:`LINK_EXPIRY_MINUTES` minutes and that they should ignore the
        message if they did not request it.

        Args:
            email: Recipient email address (the user's account email).
            magic_link: Full authentication URL to include in the email. This
                is produced by ``AuthService.build_magic_link`` and contains a
                one-time token query parameter.

        Raises:
            HTTPException: 500 if the SMTP connection, login, or send fails.
                The underlying exception message is included in the detail so
                callers (and logs) can diagnose connectivity or credential
                problems.
        """
        # Create a multipart/alternative message: mail clients that support
        # HTML will render the "html" part, while basic clients fall back to
        # the "plain" part. Both parts must contain equivalent content.
        message = MIMEMultipart("alternative")
        message["Subject"] = "Your Game Group Login Link"
        message["From"] = self.from_email
        message["To"] = email

        # Create the plain-text and HTML version of the message. The expiry
        # notice references LINK_EXPIRY_MINUTES so the copy stays in sync with
        # the actual token lifetime configured in AuthService.
        text = f"""Hello!

Click the following link to log in to Game Group:

{magic_link}

This link will expire in {LINK_EXPIRY_MINUTES} minutes.

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
                <p><em>This link will expire in {LINK_EXPIRY_MINUTES} minutes.</em></p>
                <p>If you did not request this login link, please ignore this email.</p>
            </body>
        </html>
        """

        # Turn these into plain/html MIMEText objects. The subtype argument
        # ("plain"/"html") sets the Content-Type of each part so clients can
        # pick the best rendering.
        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")

        # Add both parts to the multipart message. Order matters for some
        # clients: plain text first, HTML second.
        message.attach(part1)
        message.attach(part2)

        # Send email over an SSL-encrypted SMTP connection (SMTP_SSL wraps the
        # entire session in TLS from the start, unlike STARTTLS which upgrades
        # a plaintext connection). A new connection is opened per send; this is
        # fine at the low volume of auth emails and keeps the service stateless.
        try:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
            server.login(self.sender_email, self.password)
            server.sendmail(self.from_email, email, message.as_string())
            server.quit()
            # Log the recipient (not the magic link) for auditability without
            # leaking a still-valid credential into logs.
            self.logger.info(f"Email sent successfully to {email}")
        except Exception as e:
            # Log with full traceback for server-side diagnosis, then surface a
            # generic 500 to the client so internal SMTP details (host,
            # credentials context) are not leaked in the API response.
            self.logger.error(f"Error sending email: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Email sending failed: {str(e)}"
            )
