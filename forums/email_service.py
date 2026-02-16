import base64
import json
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from .models import Forum, ForumEmailSettings
from .crypto import decrypt_json


class EmailServiceError(Exception):
    pass


class EmailService:
    """Centralized email service for Meet-In.

    Flow A: send_system_notification() - uses central Meet-In email settings
    Flow B: send_forum_email() - uses forum-specific configured transport (OAuth2 or SMTP)
    """

    SYSTEM_FROM = getattr(settings, 'MEETIN_SYSTEM_FROM', 'Meet-In <notifications@meetin.app>')

    @staticmethod
    def send_system_notification(subject: str, html_body: str, text_body: Optional[str] = None, to: Optional[list] = None, forum: Optional[Forum] = None):
        """Send a system-generated notification from the central Meet-In address.

        - Uses Django's email backend configured in settings (EMAIL_HOST, etc.)
        - `to` should be list of recipient emails.
        - Never uses forum-specific credentials; forum arg used only to render content.
        """
        if not to:
            raise EmailServiceError("No recipients provided for system notification")

        from_email = EmailService.SYSTEM_FROM
        subject = subject
        text_body = text_body or ''

        msg = EmailMultiAlternatives(subject=subject, body=text_body, from_email=from_email, to=to)
        msg.attach_alternative(html_body, "text/html")
        # Rely on Django email backend for sending
        try:
            print(f"[EmailService] Sending system email '{subject}' to: {to}")
            msg.send(fail_silently=False)
            print(f"[EmailService] System email sent to: {to}")
        except Exception as e:
            print(f"[EmailService] Error sending system email to {to}: {e}")
            raise

    @staticmethod
    def _smtp_send(host: str, port: int, username: str, password: str, use_tls: bool, from_addr: str, to_addrs: list, subject: str, html_body: str, text_body: Optional[str] = None):
        text_body = text_body or ''
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = from_addr
        message['To'] = ', '.join(to_addrs)
        part1 = MIMEText(text_body, 'plain')
        part2 = MIMEText(html_body, 'html')
        message.attach(part1)
        message.attach(part2)

        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=60) as server:
            if use_tls:
                server.starttls(context=context)
            # Use login with username/password
            server.login(username, password)
            server.sendmail(from_addr, to_addrs, message.as_string())

    @staticmethod
    def _smtp_send_xoauth2(host: str, port: int, username: str, access_token: str, use_tls: bool, from_addr: str, to_addrs: list, subject: str, html_body: str, text_body: Optional[str] = None):
        """Send via SMTP using XOAUTH2 (Google/Microsoft). Generates XOAUTH2 auth string and issues AUTH command."""
        text_body = text_body or ''
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = from_addr
        message['To'] = ', '.join(to_addrs)
        message.attach(MIMEText(text_body, 'plain'))
        message.attach(MIMEText(html_body, 'html'))

        auth_string = f'user={username}\1auth=Bearer {access_token}\1\1'
        auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=60) as server:
            if use_tls:
                server.starttls(context=context)
            # Issue AUTH XOAUTH2 <base64>
            code, resp = server.docmd('AUTH', 'XOAUTH2 ' + auth_b64)
            if code != 235 and code != 334:
                raise EmailServiceError(f"XOAUTH2 authentication failed: {code} {resp}")
            server.sendmail(from_addr, to_addrs, message.as_string())

    @staticmethod
    def send_forum_email(forum: Forum, subject: str, html_body: str, text_body: Optional[str] = None, recipients: Optional[list] = None):
        """Send email on behalf of a forum using its configured email connection.

        Steps:
        - Load forum.email_settings
        - Decrypt stored oauth_tokens or smtp_config
        - Use appropriate transport
        - Throw clear errors if not configured
        """
        if recipients is None or len(recipients) == 0:
            raise EmailServiceError("No recipients provided for forum email")

        try:
            settings_obj: ForumEmailSettings = forum.email_settings
        except ForumEmailSettings.DoesNotExist:
            raise EmailServiceError("Forum email is not connected")

        provider = settings_obj.email_provider
        from_addr = settings_obj.email_address
        if not provider or not from_addr:
            raise EmailServiceError("Forum email provider or address not configured")

        # Ensure recipients is list of emails
        to = recipients

        # Provider flows
        if provider in (ForumEmailSettings.EMAIL_PROVIDER_GOOGLE, ForumEmailSettings.EMAIL_PROVIDER_MICROSOFT):
            # Use OAuth2 tokens stored encrypted in oauth_tokens
            if not settings_obj.oauth_tokens:
                raise EmailServiceError("OAuth tokens not found for forum email")

            # Decrypt token blob
            token_blob = settings_obj.oauth_tokens
            if isinstance(token_blob, str):
                token_data = decrypt_json(token_blob)
            else:
                # assume already JSON
                token_data = token_blob

            access_token = token_data.get('access_token')
            smtp_host = token_data.get('smtp_host') or 'smtp.gmail.com'
            smtp_port = int(token_data.get('smtp_port', 587))
            use_tls = True

            if not access_token:
                raise EmailServiceError("OAuth access token missing for forum email")

            # Send via SMTP XOAUTH2
            try:
                print(f"[EmailService] Sending forum-owned XOAUTH2 email for forum {forum.id} ('{forum.name}') to: {to}")
                EmailService._smtp_send_xoauth2(smtp_host, smtp_port, from_addr, access_token, use_tls, from_addr, to, subject, html_body, text_body)
                print(f"[EmailService] Forum-owned XOAUTH2 email sent to: {to}")
            except Exception as e:
                print(f"[EmailService] Error sending forum-owned XOAUTH2 email to {to}: {e}")
                raise

        elif provider == ForumEmailSettings.EMAIL_PROVIDER_SMTP:
            # Decrypt smtp_config
            smtp_blob = settings_obj.smtp_config
            if not smtp_blob:
                raise EmailServiceError("SMTP config not found for forum email")

            if isinstance(smtp_blob, str):
                smtp_data = decrypt_json(smtp_blob)
            else:
                smtp_data = smtp_blob

            host = smtp_data.get('host')
            port = int(smtp_data.get('port', 587))
            username = smtp_data.get('username')
            password = smtp_data.get('password')
            use_tls = smtp_data.get('use_tls', True)

            if not all([host, port, username, password]):
                raise EmailServiceError("Incomplete SMTP configuration for forum email")

            try:
                print(f"[EmailService] Sending forum-owned SMTP email for forum {forum.id} ('{forum.name}') to: {to} via {host}:{port}")
                EmailService._smtp_send(host, port, username, password, use_tls, from_addr, to, subject, html_body, text_body)
                print(f"[EmailService] Forum-owned SMTP email sent to: {to}")
            except Exception as e:
                print(f"[EmailService] Error sending forum-owned SMTP email to {to}: {e}")
                raise
        else:
            raise EmailServiceError("Unsupported forum email provider")


__all__ = ['EmailService', 'EmailServiceError']
