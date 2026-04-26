from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {"alerts": {}}

    def load(self) -> None:
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def __enter__(self) -> "StateStore":
        self.load()
        return self

    def __exit__(self, *_args: object) -> None:
        self.save()

    def alert_state(self, account_id: str, kind: str) -> dict[str, Any]:
        key = f"{account_id}:{kind}"
        alerts = self.data.setdefault("alerts", {})
        return alerts.setdefault(key, {})

    def should_alert(self, account_id: str, kind: str, *, cooldown_seconds: float) -> bool:
        state = self.alert_state(account_id, kind)
        last_alert_at = parse_datetime(state.get("last_alert_at"))
        if last_alert_at is None:
            return True
        elapsed = (datetime.now(timezone.utc) - last_alert_at).total_seconds()
        return elapsed >= cooldown_seconds

    def mark_alerted(self, account_id: str, kind: str, value: float, threshold: float) -> None:
        state = self.alert_state(account_id, kind)
        state["last_alert_at"] = datetime.now(timezone.utc).isoformat()
        state["last_value"] = value
        state["last_threshold"] = threshold
        state["below_threshold"] = True

    def mark_ok(self, account_id: str, kind: str, value: float | None) -> bool:
        state = self.alert_state(account_id, kind)
        was_below = bool(state.get("below_threshold"))
        state["below_threshold"] = False
        state["last_ok_at"] = datetime.now(timezone.utc).isoformat()
        state["last_value"] = value
        return was_below


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
