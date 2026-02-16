import base64
import json
import hashlib
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken


def _derive_key() -> bytes:
    """Derive a 32-byte url-safe base64 key from either env EMAIL_ENCRYPTION_KEY or SECRET_KEY.

    WARNING: In production, set a dedicated EMAIL_ENCRYPTION_KEY.
    """
    key = getattr(settings, 'EMAIL_ENCRYPTION_KEY', '')
    if key:
        # If user provided raw key, ensure it's bytes and valid length
        try:
            return key.encode()
        except Exception:
            pass

    # Fallback: derive from SECRET_KEY
    secret = settings.SECRET_KEY.encode()
    digest = hashlib.sha256(secret).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    key = _derive_key()
    return Fernet(key)


def encrypt_json(obj: dict) -> str:
    """Encrypt a JSON-serializable object and return base64 string."""
    f = _get_fernet()
    raw = json.dumps(obj, separators=(",", ":")).encode('utf-8')
    token = f.encrypt(raw)
    return token.decode('utf-8')


def decrypt_json(token_str: str) -> dict:
    """Decrypt a token string and return the JSON object. Raises InvalidToken on failure."""
    f = _get_fernet()
    try:
        raw = f.decrypt(token_str.encode('utf-8'))
        return json.loads(raw.decode('utf-8'))
    except InvalidToken:
        raise
    except Exception:
        raise
