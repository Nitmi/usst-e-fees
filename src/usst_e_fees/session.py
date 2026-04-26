from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import SessionTokens


class SessionStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> SessionTokens:
        if not self.path.exists():
            return SessionTokens()
        return SessionTokens.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, tokens: SessionTokens) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tokens.updated_at = datetime.now(timezone.utc)
        self.path.write_text(tokens.model_dump_json(indent=2), encoding="utf-8")

    def update(
        self,
        *,
        weaccess_token: str | None = None,
        hw_code: str | None = None,
        cookies: dict[str, str] | None = None,
        welink_cookies: dict[str, str] | None = None,
    ) -> SessionTokens:
        tokens = self.load()
        if weaccess_token:
            tokens.weaccess_token = weaccess_token
        if hw_code:
            tokens.hw_code = hw_code
        if cookies:
            tokens.cookies.update(cookies)
        if welink_cookies:
            tokens.welink_cookies.update(welink_cookies)
        self.save(tokens)
        return tokens


def parse_cookie_header(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    cookies: dict[str, str] = {}
    for part in value.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, cookie_value = part.split("=", 1)
        cookies[name.strip()] = cookie_value.strip()
    return cookies


def redact(value: str | None, keep: int = 8) -> str:
    if not value:
        return "<empty>"
    if len(value) <= keep * 2:
        return "<redacted>"
    return f"{value[:keep]}...{value[-keep:]}"
