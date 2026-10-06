"""Open Hotels.com and let the traveler sign in with their own account.

The window stays open until EG_SESSIONTOKEN is set. The traveler completes
the email code and any check Hotels.com shows. Cookies are saved only after
that session exists.
"""

from __future__ import annotations

import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from agent.hotels import cookie_path

LOGIN_URL = (
    "https://www.hotels.com/login?lineOfBusiness=LODGING"
    "&loginIngressPoint=HEADER_SIGN_IN&pageLocation=SEARCH_RESULTS"
)
WAIT_SECONDS = 180
PROMPT = """
() => {
  const id = "expert-travel-advisor-signin";
  if (document.getElementById(id)) return;
  const bar = document.createElement("div");
  bar.id = id;
  bar.textContent = "Sign in with your Hotels.com account. This window closes when you're signed in.";
  bar.style.cssText = [
    "position:fixed",
    "top:0",
    "left:0",
    "right:0",
    "z-index:2147483647",
    "background:#111",
    "color:#fff",
    "padding:12px 16px",
    "font:16px/1.4 sans-serif",
    "text-align:center"
  ].join(";");
  document.documentElement.appendChild(bar);
}
"""


def login() -> str:
    """Open the login window and return the signed-in cookie header."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel="chrome",
            headless=False,
            ignore_default_args=["--enable-automation"],
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context()
        seeded = _browser_cookies()
        if seeded:
            context.add_cookies(seeded)
        page = context.new_page()
        page.on("domcontentloaded", lambda _page: _show_prompt(_page))
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        _show_prompt(page)
        if "Bot or Not" in page.title():
            browser.close()
            raise RuntimeError("Hotels.com showed a bot check instead of the login form")
        print("Sign in with your Hotels.com account in the window that opened.", flush=True)
        if not _wait_for_session(context):
            browser.close()
            raise RuntimeError(
                "Sign in to Hotels.com in the browser window, then try the stay again."
            )
        cookies = context.cookies()
        browser.close()
    _save(cookies)
    return _header(cookies)


def _show_prompt(page) -> None:
    try:
        page.evaluate(PROMPT)
    except Exception:
        return


def _browser_cookies() -> list[dict]:
    path = cookie_path()
    if not path.is_file():
        return []
    cookies = []
    for part in path.read_text().strip().split("; "):
        name, _, value = part.partition("=")
        if not name or name in {"EG_SESSIONTOKEN", "EG_ANONTOKEN"}:
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": ".hotels.com",
                "path": "/",
            }
        )
    return cookies


def _wait_for_session(context) -> bool:
    deadline = time.time() + WAIT_SECONDS
    while time.time() < deadline:
        names = {cookie["name"] for cookie in context.cookies()}
        if "EG_SESSIONTOKEN" in names and "EG_ANONTOKEN" not in names:
            return True
        time.sleep(1)
    return False


def _header(cookies: list[dict]) -> str:
    return "; ".join(
        f"{cookie['name']}={cookie['value']}"
        for cookie in cookies
        if cookie.get("domain", "").endswith("hotels.com")
    )


def _save(cookies: list[dict]) -> None:
    path = cookie_path()
    path.parent.mkdir(exist_ok=True)
    path.write_text(_header(cookies) + "\n")
    path.chmod(0o600)


if __name__ == "__main__":
    try:
        login()
    except PlaywrightTimeout as exc:
        raise SystemExit(f"Login page did not become ready: {exc}") from exc
    print("logged_in")
