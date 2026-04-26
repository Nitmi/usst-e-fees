from __future__ import annotations

import time

from .config import AccountConfig, ThresholdConfig
from .models import ElectricityReading, NotificationMessage
from .notify import Notifier
from .state import StateStore


KINDS = {
    "lighting": ("插电照明", "lighting_money"),
    "aircon": ("空调", "aircon_money"),
}


def build_status_body(reading: ElectricityReading) -> str:
    lines = [
        f"账号：{reading.account_name} ({reading.account_id})",
        f"学生：{reading.student_name or '<unknown>'} ({reading.student_id or '<unknown>'})",
        f"宿舍：{reading.dorm_address or '<unknown>'}",
        f"照明：{format_money(reading.lighting_money)} / {format_kwh(reading.lighting_kwh)}",
        f"空调：{format_money(reading.aircon_money)} / {format_kwh(reading.aircon_kwh)}",
    ]
    return "\n".join(lines)


def build_low_balance_message(
    reading: ElectricityReading,
    *,
    kind: str,
    value: float,
    threshold: float,
) -> NotificationMessage:
    label = KINDS[kind][0]
    return NotificationMessage(
        title=f"USST 宿舍{label}电费不足",
        body=(
            f"{label}剩余电费 {value:.2f} 元，低于阈值 {threshold:.2f} 元。\n"
            f"{build_status_body(reading)}"
        ),
    )


def build_recovered_message(reading: ElectricityReading, *, kind: str, value: float | None) -> NotificationMessage:
    label = KINDS[kind][0]
    return NotificationMessage(
        title=f"USST 宿舍{label}电费已恢复",
        body=f"{label}当前剩余电费：{format_money(value)}。\n{build_status_body(reading)}",
    )


def low_balance_messages(
    reading: ElectricityReading,
    thresholds: ThresholdConfig,
    state_store: StateStore,
    *,
    cooldown_seconds: float,
    notify_recovered: bool,
) -> list[NotificationMessage]:
    messages: list[NotificationMessage] = []
    for kind, (_label, threshold_attr) in KINDS.items():
        value = reading.value_for_kind(kind)
        threshold = getattr(thresholds, threshold_attr)
        if value is None:
            continue
        if value < threshold:
            if state_store.should_alert(reading.account_id, kind, cooldown_seconds=cooldown_seconds):
                messages.append(build_low_balance_message(reading, kind=kind, value=value, threshold=threshold))
                state_store.mark_alerted(reading.account_id, kind, value, threshold)
            continue
        recovered = state_store.mark_ok(reading.account_id, kind, value)
        if recovered and notify_recovered:
            messages.append(build_recovered_message(reading, kind=kind, value=value))
    return messages


def watch(
    poll: callable,
    accounts: list[AccountConfig],
    notifier_for_account: callable,
    thresholds_for_account: callable,
    state_store: StateStore,
    *,
    interval_seconds: float,
    alert_cooldown_seconds: float,
    notify_recovered: bool,
    ticks: int | None = None,
    on_tick: callable | None = None,
) -> None:
    tick = 0
    while ticks is None or tick < ticks:
        tick += 1
        sent_count = 0
        for account in accounts:
            reading = poll(account)
            messages = low_balance_messages(
                reading,
                thresholds_for_account(account),
                state_store,
                cooldown_seconds=alert_cooldown_seconds,
                notify_recovered=notify_recovered,
            )
            notifier: Notifier = notifier_for_account(account)
            for message in messages:
                notifier.send(message)
                sent_count += 1
        state_store.save()
        if on_tick:
            on_tick(tick, sent_count)
        if ticks is not None and tick >= ticks:
            break
        time.sleep(interval_seconds)


def format_money(value: float | None) -> str:
    if value is None:
        return "<unknown>"
    return f"{value:.2f} 元"


def format_kwh(value: float | None) -> str:
    if value is None:
        return "<unknown>"
    return f"{value:g} 度"
