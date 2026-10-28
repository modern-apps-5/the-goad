"""Avi controller session. Password stays in memory.

The controller rejects HTTP Basic. Login is POST /login, then the
CSRF cookie goes on later calls. The password is read from the
environment or from SDDC Manager's credential store. It is never
returned and never written to a file by this module.
"""

from __future__ import annotations

import json
import os
import ssl
import threading
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

CTX = ssl._create_unverified_context()


def _env_file(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    file = Path(path)
    if not file.is_file():
        return out
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip("'").strip('"')
    return out


def _sddc_password() -> str:
    direct = os.environ.get("SDDC_PASSWORD") or os.environ.get("NSX_ADMIN_PASSWORD") or ""
    if direct:
        return direct
    path = os.environ.get("SDDC_ENV_FILE") or ""
    key = os.environ.get("SDDC_PASSWORD_KEY") or "NSX_ADMIN_PASSWORD"
    if not path:
        return ""
    return _env_file(path).get(key, "")


def _http(
    opener,
    url: str,
    method: str = "GET",
    body: dict | None = None,
    headers: dict | None = None,
    timeout: int = 40,
):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, raw
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


class AviSession:
    def __init__(self) -> None:
        self.controller = (os.environ.get("AVI_CONTROLLER") or "").strip().rstrip("/")
        if self.controller.startswith("https://"):
            self.controller = self.controller[len("https://") :]
        if not self.controller:
            raise RuntimeError("AVI_CONTROLLER is unset")
        self.base = f"https://{self.controller}"
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=CTX),
            urllib.request.HTTPCookieProcessor(self.jar),
        )
        self.csrf = ""
        self.version = ""
        # One controller session serves every request thread. A sign-in on
        # one thread clears the cookies another thread is using, and calls
        # that overlap ran past the AI Gateway's 30 second backend wait.
        self.lock = threading.RLock()
        self._login()

    def _login(self) -> None:
        username = os.environ.get("AVI_USERNAME") or "admin"
        password = os.environ.get("AVI_PASSWORD") or ""
        if not password:
            username, password = self._password_from_sddc()
        status, raw = _http(
            self.opener,
            self.base + "/login",
            "POST",
            {"username": username, "password": password},
            {"Content-Type": "application/json", "Accept": "application/json"},
        )
        if status not in (200, 201):
            raise RuntimeError(f"Avi login HTTP {status}")
        for cookie in self.jar:
            if cookie.name == "csrftoken":
                self.csrf = cookie.value
        if not self.csrf:
            raise RuntimeError("Avi login returned no csrftoken")
        status, raw = self._get_once("/api/cluster/version")
        info = json.loads(raw.decode()) if status == 200 and raw else {}
        if isinstance(info, dict):
            self.version = str(info.get("Version") or info.get("version") or "")

    def _password_from_sddc(self) -> tuple[str, str]:
        sddc = (os.environ.get("SDDC_URL") or "").rstrip("/")
        user = os.environ.get("SDDC_USER") or "administrator@${VSPHERE_SSO_DOMAIN}"
        password = _sddc_password()
        if not sddc or not password:
            raise RuntimeError("Avi password is unset and SDDC_URL or SDDC password is missing")
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX))
        status, raw = _http(
            opener,
            sddc + "/v1/tokens",
            "POST",
            {"username": user, "password": password},
            {"Content-Type": "application/json", "Accept": "application/json"},
        )
        if status not in (200, 201):
            raise RuntimeError(f"SDDC login HTTP {status}")
        token = json.loads(raw.decode()).get("accessToken")
        if not token:
            raise RuntimeError("SDDC login returned no token")
        auth = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        status, raw = _http(opener, sddc + "/v1/credentials?resourceType=NSX_ALB", headers=auth)
        if status != 200:
            raise RuntimeError(f"SDDC credential list HTTP {status}")
        elements = json.loads(raw.decode()).get("elements") or []
        if not elements:
            raise RuntimeError("SDDC has no NSX_ALB credential")
        cid = elements[0].get("id")
        status, raw = _http(opener, f"{sddc}/v1/credentials/{cid}", headers=auth)
        if status != 200:
            raise RuntimeError(f"SDDC credential read HTTP {status}")
        detail = json.loads(raw.decode())
        if not detail.get("password"):
            raise RuntimeError("SDDC credential had no password")
        return detail.get("username") or "admin", detail["password"]

    def _get_once(self, path: str, timeout: int = 40) -> tuple[int, bytes]:
        return _http(
            self.opener,
            self.base + path,
            headers={
                "Accept": "application/json",
                "X-CSRFToken": self.csrf,
                "Referer": self.base + "/",
                "X-Avi-Tenant": os.environ.get("AVI_TENANT") or "admin",
            },
            timeout=timeout,
        )

    def get(self, path: str, *, timeout: int = 40) -> dict | list:
        with self.lock:
            status, raw = self._get_once(path, timeout)
            if status == 401:
                # The controller ends idle sessions. Sign in again once.
                self.jar.clear()
                self._login()
                status, raw = self._get_once(path, timeout)
        if status != 200:
            raise RuntimeError(f"Avi GET {path} HTTP {status}")
        if not raw:
            return {}
        parsed = json.loads(raw.decode())
        return parsed


_SESSION: AviSession | None = None
_SESSION_LOCK = threading.Lock()


def session() -> AviSession:
    global _SESSION
    with _SESSION_LOCK:
        if _SESSION is None:
            _SESSION = AviSession()
    return _SESSION


def results(doc: dict | list) -> list[dict]:
    if isinstance(doc, list):
        return [item for item in doc if isinstance(item, dict)]
    if isinstance(doc, dict):
        rows = doc.get("results")
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
    return []


def oper_state(doc: dict) -> str:
    oper = doc.get("oper_status") or {}
    if isinstance(oper, dict):
        return str(oper.get("state") or "UNKNOWN")
    return "UNKNOWN"


def reason_text(doc: dict) -> str:
    oper = doc.get("oper_status") or {}
    if not isinstance(oper, dict):
        return ""
    reason = oper.get("reason")
    if isinstance(reason, list) and reason:
        return str(reason[0])[:240]
    if isinstance(reason, str):
        return reason[:240]
    return ""


def vip_of(item: dict, avi: AviSession) -> list[str]:
    found: list[str] = []
    vip = item.get("vip")
    if isinstance(vip, list):
        for row in vip:
            addr = ((row or {}).get("ip_address") or {}).get("addr")
            if addr:
                found.append(str(addr))
    if found:
        return found
    ref = str(item.get("vsvip_ref") or "")
    if "/api/vsvip/" not in ref:
        return found
    uuid = ref.rstrip("/").split("/")[-1]
    try:
        doc = avi.get(f"/api/vsvip/{uuid}", timeout=5)
    except (RuntimeError, TimeoutError, OSError):
        return found
    if isinstance(doc, dict):
        for row in doc.get("vip") or []:
            addr = ((row or {}).get("ip_address") or {}).get("addr")
            if addr:
                found.append(str(addr))
    return found


def last_metric(series: dict) -> dict:
    header = series.get("header") or {}
    data = series.get("data") or []
    value = None
    stamp = None
    if isinstance(data, list) and data:
        last = data[-1] or {}
        value = last.get("value")
        stamp = last.get("timestamp")
    return {
        "metric": header.get("name") or header.get("metric_id"),
        "units": header.get("units"),
        "value": value,
        "timestamp": stamp,
    }
