"""Exercise the actual maintained SDK with a fake HTTP transport."""

import json

import httpx

from app.account_auth import SupabaseIdentity
from app.core import settings, utcnow


def test_supported_sdk_pkce_exchange_contract(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://fixture.supabase.co")
    monkeypatch.setattr(settings, "supabase_publishable_key", "test-only-publishable")
    original_client = httpx.Client
    now = utcnow()

    def handle(request):
        assert str(request.url) == "https://fixture.supabase.co/auth/v1/token?grant_type=pkce"
        assert json.loads(request.content) == {
            "auth_code": "fictional-single-use-code",
            "code_verifier": "fictional-verifier",
        }
        assert request.headers["apikey"] == "test-only-publishable"
        return httpx.Response(
            200,
            json={
                "access_token": "fictional-access",
                "refresh_token": "fictional-refresh",
                "token_type": "bearer",
                "expires_in": 300,
                "expires_at": int(now.timestamp()) + 300,
                "user": {
                    "id": "00000000-0000-4000-8000-000000000001",
                    "aud": "authenticated",
                    "role": "authenticated",
                    "email": "fixture@example.test",
                    "email_confirmed_at": now.isoformat(),
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "app_metadata": {},
                    "user_metadata": {},
                },
            },
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    result = SupabaseIdentity().exchange("fictional-single-use-code", "fictional-verifier")
    assert (
        result["access_token"] == "fictional-access"
        and result["user"]["email"] == "fixture@example.test"
    )
