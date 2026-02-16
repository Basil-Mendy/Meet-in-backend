import os
import uuid
import requests
from django.conf import settings


class BaseWalletProvider:
    """Abstract provider interface for issuing wallet/virtual account numbers."""
    def create_virtual_account(self, forum, wallet):
        """Create or request a wallet number for the forum.

        Should return a dict with at least {"wallet_number": "..."} on success.
        """
        raise NotImplementedError()


class MockProvider(BaseWalletProvider):
    """Simple mock provider used for development/testing."""
    def create_virtual_account(self, forum, wallet):
        # Deterministic-ish but human-friendly string based on UUID
        number = f"FWX{uuid.uuid4().hex[:10].upper()}"
        return {"wallet_number": number}


class FlutterwaveProvider(BaseWalletProvider):
    """Provider implementation for Flutterwave Virtual Accounts.

    Note: This is a minimal implementation and may need adjustments to match
    the exact provider API and required fields for production use.
    """
    BASE_URL = "https://api.flutterwave.com/v3"

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("FLUTTERWAVE_SECRET_KEY") or getattr(settings, "FLUTTERWAVE_SECRET_KEY", None)

    def create_virtual_account(self, forum, wallet):
        if not self.api_key:
            raise RuntimeError("Flutterwave API key not configured")

        url = f"{self.BASE_URL}/virtual-account-numbers"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        payload = {
            "account_bank": "",  # optional depending on integration
            "currency": "NGN",
            "customer": {
                "name": forum.name,
                # optional: include email/phone if available
            },
            "merchant_id": "",  # provider-specific
            "is_permanent": False,
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        # Attempt several common response shapes
        wallet_number = None
        if isinstance(data, dict):
            # Flutterwave often returns data.data.account_number
            d = data.get("data") or data
            wallet_number = d.get("account_number") or (d.get("data") or {}).get("account_number")

        if not wallet_number:
            raise RuntimeError("Failed to extract wallet number from provider response")

        return {"wallet_number": str(wallet_number)}


def get_provider(name: str = None):
    name = (name or os.environ.get("WALLET_PROVIDER") or getattr(settings, "WALLET_PROVIDER", "MOCK")).upper()
    if name == "FLUTTERWAVE":
        return FlutterwaveProvider()
    # Default to mock for safety
    return MockProvider()
