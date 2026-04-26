from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import HttpConfig
from .models import ElectricityReading, RawElectricityData
from .session import SessionStore


class ElectricityError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class DormElectricityClient:
    def __init__(self, http_config: HttpConfig, session_store: SessionStore) -> None:
        self.http_config = http_config
        self.session_store = session_store
        self.tokens = session_store.load()
        self.client = httpx.Client(
            base_url=http_config.base_url,
            timeout=http_config.timeout_seconds,
            follow_redirects=False,
            headers=self._base_headers(),
            cookies=self.tokens.cookies,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "DormElectricityClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _base_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Access_platform": "welink",
            "Referer": f"{self.http_config.base_url.rstrip('/')}/SSGL/StuMobile/StuView/VoucherCenter.html",
            "User-Agent": self.http_config.user_agent,
            "X-User-Agent": self.http_config.weaccess_user_agent,
            "X-Weaccess-Auth-Ver": "v3",
            "X-Weaccess-Org-Schema": "http",
        }
        if self.tokens.weaccess_token:
            headers["X-Weaccess-Token"] = self.tokens.weaccess_token
        if self.tokens.hw_code:
            headers["x-hw-code"] = self.tokens.hw_code
        return headers

    def _welink_headers(self) -> dict[str, str]:
        return {
            "Accept": "*/*",
            "Accept-Language": "zh-Hans-CN;q=1, en-CN;q=0.9",
            "AppName": "WeLink",
            "Content-Type": "application/x-www-form-urlencoded",
            "Lang": "zh",
            "User-Agent": "WorkPlace/7.52.16 (iPhone; iOS 26.4.2; Scale/3.00)",
            "X-Cloud-Type": "1",
            "X-Product-Type": "0",
        }

    def _persist_response_session(self, response: httpx.Response) -> None:
        cookies = dict(response.cookies)
        if not cookies:
            return
        self.tokens = self.session_store.update(cookies=cookies)
        for name, value in self.tokens.cookies.items():
            self.client.cookies.set(name, value)

    def _json_request(self, method: str, url: str, **kwargs: Any) -> Any:
        response = self.client.request(method, url, **kwargs)
        self._persist_response_session(response)
        if response.status_code >= 400:
            raise ElectricityError(
                f"{method} {url} failed: HTTP {response.status_code}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ElectricityError(f"{method} {url} did not return JSON") from exc

    def refresh_auth_code(self) -> str:
        if not self.tokens.welink_cookies:
            raise ElectricityError(
                "身份认证失败，请重新导入 WeLink ssoauth/v1/code 请求头以支持自动刷新 x-hw-code"
            )
        response = httpx.post(
            "https://api.welink.huaweicloud.com/mcloud/mag/ProxyForText/ssoauth/v1/code",
            headers=self._welink_headers(),
            cookies=self.tokens.welink_cookies,
            timeout=self.http_config.timeout_seconds,
        )
        if response.status_code >= 400:
            raise ElectricityError(
                f"WeLink auth code refresh failed: HTTP {response.status_code}",
                status_code=response.status_code,
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ElectricityError("WeLink auth code refresh did not return JSON") from exc
        code = data.get("code")
        if not code:
            raise ElectricityError("WeLink auth code refresh response did not contain code")
        self.tokens = self.session_store.update(hw_code=str(code))
        self.client.headers["x-hw-code"] = str(code)
        return str(code)

    def ensure_identity(self) -> None:
        if not self.tokens.hw_code:
            self.refresh_auth_code()
        data = self.refresh_identity()
        if data.get("Success") and data.get("Status") == 200:
            return
        self.refresh_auth_code()
        data = self.refresh_identity()
        if not data.get("Success") or data.get("Status") != 200:
            message = data.get("Message") or data.get("Error") or "身份认证失败，请重新登录"
            raise ElectricityError(str(message), status_code=data.get("Status"))

    def refresh_identity(self) -> Any:
        return self._json_request("GET", "/api/Authentication/GetCurrentUserIdentity", params={"ssid": ""})

    def get_dorm_electricity_fees(self, *, account_id: str, account_name: str) -> ElectricityReading:
        self.ensure_identity()
        data = self._json_request(
            "GET",
            "/api/Voucher/GetDormElectricityFees",
            params={"IsLoadData": "false"},
        )
        if should_refresh_identity(data):
            self.refresh_auth_code()
            self.refresh_identity()
            data = self._json_request(
                "GET",
                "/api/Voucher/GetDormElectricityFees",
                params={"IsLoadData": "false"},
            )
        if not data.get("Success") or data.get("Status") != 200:
            status = data.get("Status")
            message = data.get("Message") or data.get("Error") or "Dorm electricity request failed"
            if status == 300:
                message = f"{message}; login session may be expired"
            raise ElectricityError(str(message), status_code=status)
        raw = RawElectricityData.model_validate(data.get("Data") or {})
        return ElectricityReading(
            account_id=account_id,
            account_name=account_name,
            student_id=raw.StudentId,
            student_name=raw.StudentName,
            dorm_id=raw.SSId,
            dorm_address=raw.SSDZ,
            lighting_money=parse_number(raw.SurplusZMMoney),
            lighting_kwh=parse_number(raw.SurplusZM),
            aircon_money=parse_number(raw.SurplusKTMoney),
            aircon_kwh=parse_number(raw.SurplusKT),
            raw=raw,
            checked_at=datetime.now(timezone.utc),
        )


def parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if not match:
        return None
    return float(match.group(0))


def should_refresh_identity(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    message = str(data.get("Message") or data.get("Error") or "")
    return data.get("Status") == 300 or "身份认证失败" in message or "重新登录" in message
