Meet-In Email System — Setup & Notes

Overview
--------
This document describes env settings and steps to enable the two email flows:

Flow A — System Notifications (central)
- Uses Django's configured email backend (EMAIL_HOST, EMAIL_HOST_USER, etc.).
- Sender: configured via `MEETIN_SYSTEM_FROM` (default: "Meet-In <notifications@meetin.app>").

Flow B — Forum-Initiated Emails
- Forum admins can connect their own email via OAuth2 (Google/Microsoft) or provide SMTP.
- Tokens and SMTP config are stored encrypted using `EMAIL_ENCRYPTION_KEY`.

Required env variables
----------------------
- EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD — for central system emails.
- MEETIN_SYSTEM_FROM — central FROM address (optional).
- EMAIL_ENCRYPTION_KEY — base64 url-safe 32-byte key (recommended). If not provided the system derives a key from SECRET_KEY (not recommended for production).

Install dependencies
--------------------
Ensure `cryptography` is available in your Python environment:

```bash
pip install cryptography
```

Migrations
----------
After pulling changes, create and run migrations to add `ForumEmailSettings` model:

```bash
cd backend
python manage.py makemigrations
python manage.py migrate
```

Testing
-------
1. Create test notification:

```bash
python manage.py test_notifications
```

2. For forum email tests, the forum must have an associated `ForumEmailSettings` record with encrypted `oauth_tokens` or `smtp_config`.

Security notes
--------------
- Do not commit `EMAIL_ENCRYPTION_KEY` into source control.
- Use a dedicated encryption key (32 url-safe base64 bytes) in production.
- Never log credentials or tokens. The code is designed to avoid printing tokens/passwords.
