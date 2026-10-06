"""Hotels.com sign-in through a cloud browser the traveler can open.

Vercel starts the browser and returns a link. Sokosumi shows that link.
The traveler signs in there. A later job reads the session from the same browser.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from agent.hotels import ROOT, cookie_path, normalize_session

LOGIN_URL = (
    "https://www.hotels.com/login?lineOfBusiness=LODGING"
    "&loginIngressPoint=HEADER_SIGN_IN&pageLocation=SEARCH_RESULTS"
)
API = "https://api.browserbase.com/v1/sessions"


class LoginLink(Exception):
    def __init__(self, login_url: str, browser_session_id: str):
        self.login_url = login_url
        self.browser_session_id = browser_session_id
        super().__init__(login_url)


def start_login() -> LoginLink:
    created = _api("POST", API, _session_body())
    session_id = created["id"]
    connect_url = created["connectUrl"]
    _open_login_page(connect_url)
    live = _api("GET", f"{API}/{session_id}/debug?expiresIn=3600")
    login_url = live["debuggerFullscreenUrl"]
    _remember(session_id)
    return LoginLink(login_url, session_id)


def collect_session(browser_session_id: str) -> str:
    live = _api("GET", f"{API}/{browser_session_id}/debug?expiresIn=300")
    header = _read_cookie_header(live["wsUrl"])
    return normalize_session(header)


def remembered_session_id() -> str:
    path = _session_file()
    if not path.is_file():
        return ""
    return path.read_text().strip()


def _session_body() -> dict:
    body = {
        "keepAlive": True,
        "timeout": 600,
        "browserSettings": {"solveCaptchas": True, "viewport": {"width": 1280, "height": 800}},
    }
    project_id = os.environ.get("BROWSERBASE_PROJECT_ID", "").strip()
    if project_id:
        body["projectId"] = project_id
    return body


def _open_login_page(connect_url: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(connect_url)
        context = browser.contexts[0]
        seeded = _seed_cookies()
        if seeded:
            context.add_cookies(seeded)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        browser.close()


def _read_cookie_header(connect_url: str) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(connect_url)
        context = browser.contexts[0]
        cookies = context.cookies()
        browser.close()
    return "; ".join(
        f"{cookie['name']}={cookie['value']}"
        for cookie in cookies
        if str(cookie.get("domain", "")).endswith("hotels.com")
    )


def _seed_cookies() -> list[dict]:
    path = cookie_path()
    if not path.is_file():
        return []
    cookies = []
    for part in path.read_text().strip().split("; "):
        name, _, value = part.partition("=")
        if not name or name in {"EG_SESSIONTOKEN", "EG_ANONTOKEN"}:
            continue
        cookies.append(
            {"name": name, "value": value, "domain": ".hotels.com", "path": "/"}
        )
    return cookies


def _api(method: str, url: str, body: dict | None = None) -> dict:
    key = os.environ.get("BROWSERBASE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Set BROWSERBASE_API_KEY. The sign-in link comes from that browser session."
        )
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"X-BB-API-Key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Sign-in browser failed with HTTP {exc.code}") from exc


def _remember(session_id: str) -> None:
    path = _session_file()
    path.parent.mkdir(exist_ok=True)
    path.write_text(session_id + "\n")
    path.chmod(0o600)


def _session_file() -> Path:
    return ROOT / ".secrets" / "hotels-browser-session.txt"
