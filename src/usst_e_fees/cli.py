from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as metadata_version
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .client import DormElectricityClient, ElectricityError
from .config import (
    AccountConfig,
    AppConfig,
    default_config_path,
    load_config,
    resolve_data_path,
    write_default_config,
)
from .headers import get_case_insensitive, parse_raw_headers
from .models import NotificationMessage
from .notify import Notifier
from .session import SessionStore, parse_cookie_header, redact
from .state import StateStore
from .watcher import build_status_body, low_balance_messages, watch


app = typer.Typer(help="USST dorm electricity fees watcher.")
console = Console()


def package_version() -> str:
    try:
        return metadata_version("usst-e-fees")
    except PackageNotFoundError:
        return __version__


def version_callback(value: bool) -> None:
    if value:
        console.print(f"usst-e-fees {package_version()}")
        raise typer.Exit()


def _load_runtime(config_path: Path | None) -> tuple[AppConfig, Path, StateStore]:
    config, resolved_config_path = load_config(config_path)
    state_store = StateStore(resolve_data_path(resolved_config_path, config.state_file))
    return config, resolved_config_path, state_store


def _session_store(config_path: Path, account: AccountConfig) -> SessionStore:
    return SessionStore(resolve_data_path(config_path, account.session_file))


def _select_account(config: AppConfig, account_id: str) -> AccountConfig:
    try:
        return config.get_account(account_id)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


def _read_once(config: AppConfig, config_path: Path, account: AccountConfig) -> object:
    session_store = _session_store(config_path, account)
    with DormElectricityClient(config.http, session_store) as client:
        return client.get_dorm_electricity_fees(account_id=account.id, account_name=account.name)


def is_welink_sso_request(host: str, path: str, cookies: dict[str, str]) -> bool:
    host = host.lower()
    path = path.lower()
    if "api.welink.huaweicloud.com" in host and "/ssoauth/v1/code" in path:
        return True
    return any(name in cookies for name in ("token", "cdn_token", "HWWAFSESID", "HWWAFSESTIME"))


@app.command("init-config")
def init_config(
    path: Annotated[Path | None, typer.Option(help="Config file path.")] = None,
    force: Annotated[bool, typer.Option(help="Overwrite existing config.")] = False,
) -> None:
    config_path = write_default_config(path, force=force)
    console.print(f"Config written: {config_path}")


@app.command("where")
def where() -> None:
    console.print(default_config_path())


@app.command("version")
def version_command() -> None:
    console.print(f"usst-e-fees {package_version()}")


@app.command("accounts")
def accounts(config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None) -> None:
    config, resolved_config_path = load_config(config_path)
    table = Table("ID", "Name", "Enabled", "Session File", "Lighting Threshold", "Aircon Threshold")
    for account in config.accounts:
        thresholds = config.thresholds_for_account(account)
        table.add_row(
            account.id,
            account.name,
            str(account.enabled),
            str(resolve_data_path(resolved_config_path, account.session_file)),
            f"{thresholds.lighting_money:g}",
            f"{thresholds.aircon_money:g}",
        )
    console.print(table)


@app.command("auth-import")
def auth_import(
    headers_path: Annotated[Path, typer.Argument(help="Path to request_header_raw.txt from Loon capture.")],
    account_id: Annotated[str, typer.Option("--account", "-a", help="Account ID.")] = "main",
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
) -> None:
    config, resolved_config_path = load_config(config_path)
    account = _select_account(config, account_id)
    headers, cookies = parse_raw_headers(headers_path)
    weaccess_token = get_case_insensitive(headers, "X-Weaccess-Token")
    hw_code = get_case_insensitive(headers, "x-hw-code")
    host = get_case_insensitive(headers, "Host") or get_case_insensitive(headers, ":authority") or ""
    path = get_case_insensitive(headers, ":path") or ""
    welink_cookies = cookies if is_welink_sso_request(host, path, cookies) else None
    dorm_cookies = None if welink_cookies else cookies
    if not weaccess_token and not hw_code and not cookies:
        console.print("[red]No X-Weaccess-Token, x-hw-code, or Cookie found in header file.[/red]")
        raise typer.Exit(1)
    store = _session_store(resolved_config_path, account)
    store.update(
        weaccess_token=weaccess_token,
        hw_code=hw_code,
        cookies=dorm_cookies,
        welink_cookies=welink_cookies,
    )
    console.print(f"Auth imported for account: {account.id}")
    console.print(f"X-Weaccess-Token: {redact(weaccess_token)}")
    console.print(f"x-hw-code: {redact(hw_code)}")
    console.print(f"Dorm cookies: {', '.join((dorm_cookies or {}).keys()) or '<empty>'}")
    console.print(f"WeLink cookies: {', '.join((welink_cookies or {}).keys()) or '<empty>'}")


@app.command("auth-set")
def auth_set(
    weaccess_token: Annotated[str | None, typer.Option("--weaccess-token", help="Value of X-Weaccess-Token.")] = None,
    hw_code: Annotated[str | None, typer.Option("--hw-code", help="Value of x-hw-code.")] = None,
    cookie: Annotated[str | None, typer.Option("--cookie", help="Raw Cookie header.")] = None,
    welink_cookie: Annotated[str | None, typer.Option("--welink-cookie", help="Raw WeLink Cookie header for ssoauth/v1/code.")] = None,
    account_id: Annotated[str, typer.Option("--account", "-a", help="Account ID.")] = "main",
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
) -> None:
    config, resolved_config_path = load_config(config_path)
    account = _select_account(config, account_id)
    store = _session_store(resolved_config_path, account)
    store.update(
        weaccess_token=weaccess_token,
        hw_code=hw_code,
        cookies=parse_cookie_header(cookie),
        welink_cookies=parse_cookie_header(welink_cookie),
    )
    console.print(f"Auth saved for account: {account.id}")


@app.command("auth-show")
def auth_show(
    account_id: Annotated[str, typer.Option("--account", "-a", help="Account ID.")] = "main",
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
) -> None:
    config, resolved_config_path = load_config(config_path)
    account = _select_account(config, account_id)
    tokens = _session_store(resolved_config_path, account).load()
    table = Table("Field", "Value")
    table.add_row("config", str(resolved_config_path))
    table.add_row("account_id", account.id)
    table.add_row("session_file", str(resolve_data_path(resolved_config_path, account.session_file)))
    table.add_row("X-Weaccess-Token", redact(tokens.weaccess_token))
    table.add_row("x-hw-code", redact(tokens.hw_code))
    table.add_row("cookies", ", ".join(tokens.cookies.keys()) or "<empty>")
    table.add_row("welink_cookies", ", ".join(tokens.welink_cookies.keys()) or "<empty>")
    table.add_row("updated_at", str(tokens.updated_at or "<never>"))
    console.print(table)


@app.command("auth-refresh")
def auth_refresh(
    account_id: Annotated[str, typer.Option("--account", "-a", help="Account ID.")] = "main",
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
) -> None:
    config, resolved_config_path = load_config(config_path)
    account = _select_account(config, account_id)
    session_store = _session_store(resolved_config_path, account)
    with DormElectricityClient(config.http, session_store) as client:
        code = client.refresh_auth_code()
        client.refresh_identity()
    console.print(f"Auth refreshed for account: {account.id}")
    console.print(f"x-hw-code: {redact(code)}")


@app.command("poll-once")
def poll_once_command(
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    account_id: Annotated[str, typer.Option("--account", "-a", help="Account ID.")] = "main",
    all_accounts: Annotated[bool, typer.Option("--all", help="Poll all enabled accounts.")] = False,
    notify: Annotated[bool, typer.Option(help="Send notification when below threshold.")] = False,
) -> None:
    config, resolved_config_path, state_store = _load_runtime(config_path)
    accounts_to_poll = config.enabled_accounts() if all_accounts else [_select_account(config, account_id)]
    try:
        with state_store:
            for account in accounts_to_poll:
                reading = _read_once(config, resolved_config_path, account)
                console.print(f"[bold]{account.id}[/bold]")
                console.print(build_status_body(reading))
                if notify:
                    messages = low_balance_messages(
                        reading,
                        config.thresholds_for_account(account),
                        state_store,
                        cooldown_seconds=config.watch.alert_cooldown_seconds,
                        notify_recovered=config.watch.notify_recovered,
                    )
                    notifier = Notifier(config.notify_for_account(account))
                    for message in messages:
                        notifier.send(message)
    except ElectricityError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


@app.command("notify-test")
def notify_test(
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    account_id: Annotated[str, typer.Option("--account", "-a", help="Account ID.")] = "main",
) -> None:
    config, _resolved_config_path = load_config(config_path)
    account = _select_account(config, account_id)
    notifier = Notifier(config.notify_for_account(account))
    sent = notifier.send(
        NotificationMessage(
            title="USST electricity notification test",
            body=f"Account: {account.name} ({account.id})",
        )
    )
    console.print(f"Sent via: {', '.join(sent) or '<none>'}")


@app.command("watch")
def watch_command(
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    account_id: Annotated[str, typer.Option("--account", "-a", help="Account ID.")] = "main",
    all_accounts: Annotated[bool, typer.Option("--all", help="Watch all enabled accounts.")] = False,
    interval: Annotated[float | None, typer.Option(help="Override interval seconds.")] = None,
    ticks: Annotated[int | None, typer.Option(help="Stop after N ticks, useful for testing.")] = None,
) -> None:
    config, resolved_config_path, state_store = _load_runtime(config_path)
    accounts_to_watch = config.enabled_accounts() if all_accounts else [_select_account(config, account_id)]
    interval_seconds = interval if interval is not None else config.watch.interval_seconds
    console.print("[bold]USST electricity watch started[/bold]")
    console.print(f"Version: {package_version()}")
    console.print(f"Interval: {interval_seconds:g}s")
    console.print(f"Accounts: {', '.join(account.id for account in accounts_to_watch)}")

    def poll(account: AccountConfig) -> object:
        return _read_once(config, resolved_config_path, account)

    def notifier_for_account(account: AccountConfig) -> Notifier:
        return Notifier(config.notify_for_account(account))

    try:
        with state_store:
            watch(
                poll,
                accounts_to_watch,
                notifier_for_account,
                config.thresholds_for_account,
                state_store,
                interval_seconds=interval_seconds,
                alert_cooldown_seconds=config.watch.alert_cooldown_seconds,
                notify_recovered=config.watch.notify_recovered,
                ticks=ticks,
                on_tick=lambda tick, sent_count: console.print(f"tick={tick} sent={sent_count}"),
            )
    except ElectricityError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


def main() -> None:
    app(
        obj={},
        prog_name="usst-e-fees",
        standalone_mode=True,
    )
