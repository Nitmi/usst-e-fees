from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


APP_NAME = "usst-e-fees"


def default_config_dir() -> Path:
    env_path = os.environ.get("USST_E_FEES_CONFIG_DIR") or os.environ.get("USST_ELECTRICITY_CONFIG_DIR")
    if env_path:
        return Path(env_path).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_NAME
    return Path.home() / ".config" / APP_NAME


def default_config_path() -> Path:
    return default_config_dir() / "config.yaml"


class HttpConfig(BaseModel):
    base_url: str = "http://ssgl.usst.edu.cn"
    timeout_seconds: float = 15.0
    user_agent: str = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Mobile/15E148/HuaWei-AnyOffice/2.6.1802.0010/"
        "com.huawei.cloudlink.workplace"
    )
    weaccess_user_agent: str = "WeAccess-IOS"


class WatchConfig(BaseModel):
    interval_seconds: float = 600.0
    alert_cooldown_seconds: float = 21600.0
    notify_recovered: bool = True


class ThresholdConfig(BaseModel):
    lighting_money: float = 20.0
    aircon_money: float = 20.0


class BarkConfig(BaseModel):
    enabled: bool = False
    server: str = "https://api.day.app"
    key: str = ""
    sound: str | None = None
    group: str = "USST Electricity"


class GotifyConfig(BaseModel):
    enabled: bool = False
    server: str = ""
    token: str = ""
    priority: int = 5


class EmailConfig(BaseModel):
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    from_addr: str = ""
    to_addrs: list[str] = Field(default_factory=list)
    use_tls: bool = True


class ConsoleConfig(BaseModel):
    enabled: bool = True


class NotifyConfig(BaseModel):
    console: ConsoleConfig = Field(default_factory=ConsoleConfig)
    bark: BarkConfig = Field(default_factory=BarkConfig)
    gotify: GotifyConfig = Field(default_factory=GotifyConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)


class AccountConfig(BaseModel):
    id: str = "main"
    name: str = "Main"
    enabled: bool = True
    session_file: str = "sessions/main.json"
    thresholds: dict[str, Any] | None = None
    notify: dict[str, Any] | None = None


class AppConfig(BaseModel):
    http: HttpConfig = Field(default_factory=HttpConfig)
    watch: WatchConfig = Field(default_factory=WatchConfig)
    thresholds: ThresholdConfig = Field(default_factory=ThresholdConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)
    accounts: list[AccountConfig] = Field(default_factory=lambda: [AccountConfig()])
    state_file: str = "state.json"

    def get_account(self, account_id: str) -> AccountConfig:
        for account in self.accounts:
            if account.id == account_id:
                return account
        raise KeyError(f"Unknown account: {account_id}")

    def enabled_accounts(self) -> list[AccountConfig]:
        return [account for account in self.accounts if account.enabled]

    def thresholds_for_account(self, account: AccountConfig) -> ThresholdConfig:
        data = self.thresholds.model_dump(mode="json")
        if account.thresholds:
            data = deep_merge(data, deepcopy(account.thresholds))
        return ThresholdConfig.model_validate(data)

    def notify_for_account(self, account: AccountConfig) -> NotifyConfig:
        data = self.notify.model_dump(mode="json")
        if account.notify:
            data = deep_merge(data, deepcopy(account.notify))
        return NotifyConfig.model_validate(data)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(path: Path | None = None) -> tuple[AppConfig, Path]:
    config_path = path or default_config_path()
    if not config_path.exists():
        return AppConfig(), config_path
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(data), config_path


def write_default_config(path: Path | None = None, *, force: bool = False) -> Path:
    config_path = path or default_config_path()
    if config_path.exists() and not force:
        raise FileExistsError(f"Config already exists: {config_path}")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = AppConfig()
    config_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return config_path


def resolve_data_path(config_path: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return config_path.parent / path
