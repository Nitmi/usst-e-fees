from __future__ import annotations

from pathlib import Path

from .session import parse_cookie_header


def parse_raw_headers(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.upper().startswith(("GET ", "POST ", "PUT ", "DELETE ")):
            continue
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        name = name.strip()
        value = value.strip()
        if name.lower() == "cookie":
            cookies.update(parse_cookie_header(value))
            continue
        headers[name] = value
    return headers, cookies


def get_case_insensitive(headers: dict[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None
