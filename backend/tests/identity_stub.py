"""Test-only identity boundary. Never loaded by app.main or deployment startup."""

from fastapi import HTTPException
from app.core import utcnow


class FakeIdentity:
    def __init__(self):
        self.users, self.accesses, self.used = {}, {}, set()
        self.links = {}

    def exchange(self, code, verifier):
        from supabase_auth.helpers import generate_pkce_challenge

        value = self.links.get(code)
        if not value or generate_pkce_challenge(verifier) != value[1]:
            raise HTTPException(401, "Invalid or already used email link")
        user, _ = self.links.pop(code)
        user["verified"] = True
        key = f"opaque-link-{len(self.accesses)}"
        self.accesses[key] = user
        return {"access_token": key, "refresh_token": key, "expires_at": utcnow().timestamp() + 300}

    def call(self, method, path, body=None, access=None):
        if path.startswith("signup"):
            self.users[body["email"]] = {
                "id": body["email"].split("@")[0],
                "email": body["email"],
                "password": body["password"],
                "verified": False,
            }
            self.links["link-" + self.users[body["email"]]["id"] + "-signup"] = (
                self.users[body["email"]],
                body.get("code_challenge"),
            )
            return {"user": {"id": self.users[body["email"]]["id"]}}
        if path.startswith("recover"):
            if body["email"] in self.users:
                self.links["link-" + self.users[body["email"]]["id"] + "-recovery"] = (
                    self.users[body["email"]],
                    body.get("code_challenge"),
                )
            return {}
        if path == "resend":
            return {}
        if path == "verify":
            key = (body["email"], body["type"], body["token"])
            if body["token"] != "123456" or key in self.used or body["email"] not in self.users:
                raise HTTPException(401, "Invalid or already used verification code")
            self.used.add(key)
            user = self.users[body["email"]]
            user["verified"] = True
        elif path == "token?grant_type=password":
            user = self.users.get(body["email"])
            if not user or user["password"] != body["password"]:
                raise HTTPException(401, "Invalid identity credentials")
        elif path.split("?", 1)[0] == "user":
            user = self.accesses.get(access)
            if not user:
                raise HTTPException(401, "Invalid identity access")
            if method == "PUT":
                user.update(body)
            return {
                "id": user["id"],
                "email": user["email"],
                "email_confirmed_at": str(utcnow()) if user["verified"] else None,
            }
        elif path.startswith("logout"):
            return {}
        elif path == "token?grant_type=refresh_token":
            user = self.accesses.get(body["refresh_token"])
            if not user:
                raise HTTPException(401, "Invalid refresh")
        else:
            raise AssertionError(path)
        key = f"opaque-{len(self.accesses)}"
        self.accesses[key] = user
        return {"access_token": key, "refresh_token": key, "expires_at": utcnow().timestamp() + 300}
