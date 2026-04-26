from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NotificationMessage(BaseModel):
    title: str
    body: str
    url: str | None = None


class SessionTokens(BaseModel):
    weaccess_token: str | None = None
    hw_code: str | None = None
    cookies: dict[str, str] = Field(default_factory=dict)
    welink_cookies: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime | None = None


class RawElectricityData(BaseModel):
    SSId: str | None = None
    StudentId: str | None = None
    StudentName: str | None = None
    SurplusZMMoney: str | None = None
    SurplusZM: str | None = None
    ZMFlg: bool | None = None
    SurplusKTMoney: str | None = None
    SurplusKT: str | None = None
    KTFlg: bool | None = None
    HasKT: bool | None = None
    HasZM: bool | None = None
    NotOnline: str | None = None
    SSDZ: str | None = None
    WHY: str | None = None
    KTReturn: int | None = None
    ZMReturn: int | None = None


class ElectricityReading(BaseModel):
    account_id: str
    account_name: str
    student_id: str | None = None
    student_name: str | None = None
    dorm_id: str | None = None
    dorm_address: str | None = None
    lighting_money: float | None = None
    lighting_kwh: float | None = None
    aircon_money: float | None = None
    aircon_kwh: float | None = None
    raw: RawElectricityData
    checked_at: datetime

    def value_for_kind(self, kind: str) -> float | None:
        if kind == "lighting":
            return self.lighting_money
        if kind == "aircon":
            return self.aircon_money
        raise ValueError(f"Unknown electricity kind: {kind}")
