"""Sign-in page served from Chrome on this computer.

Hotels.com blocks datacenter browsers. This Chrome is the one that already
gets through. A tunnel publishes the page so Sokosumi can hand the traveler a link.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty, Queue
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

from agent.login import LOGIN_URL, _browser_cookies, _save

PORT = 8765
VIEWPORT = {"width": 1100, "height": 800}


class _State:
    def __init__(self) -> None:
        self.commands: Queue = Queue()
        self.jpeg = b""
        self.title = ""
        self.signed_in = False
        self.stop = False
        self.lock = threading.Lock()


def serve() -> str:
    state = _State()
    threading.Thread(target=_chrome, args=(state,), daemon=True).start()
    deadline = time.time() + 30
    while time.time() < deadline and not state.jpeg:
        time.sleep(0.2)
    if not state.jpeg:
        raise RuntimeError("Hotels.com login page did not appear")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), _handler(state))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    public = _tunnel()
    print(f"local http://127.0.0.1:{PORT}", flush=True)
    print(f"public {public}", flush=True)
    print(f"title {state.title}", flush=True)
    try:
        while not state.signed_in and not state.stop:
            time.sleep(1)
    except KeyboardInterrupt:
        state.stop = True
    return "signed_in" if state.signed_in else "stopped"


def _chrome(state: _State) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel="chrome",
            headless=False,
            ignore_default_args=["--enable-automation"],
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
        seeded = _browser_cookies()
        if seeded:
            context.add_cookies(seeded)
        page = context.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        while not state.stop:
            try:
                command = state.commands.get(timeout=0.4)
            except Empty:
                command = None
            if command:
                _apply(page, command)
            names = {cookie["name"] for cookie in context.cookies()}
            signed_in = "EG_SESSIONTOKEN" in names and "EG_ANONTOKEN" not in names
            if signed_in and not state.signed_in:
                _save(context.cookies())
            frame = page.screenshot(type="jpeg", quality=60)
            with state.lock:
                state.jpeg = frame
                state.title = page.title()
                state.signed_in = signed_in
        browser.close()


def _apply(page, command: dict) -> None:
    kind = command.get("type")
    if kind == "click":
        page.mouse.click(float(command["x"]), float(command["y"]))
    elif kind == "type":
        page.keyboard.type(str(command.get("text") or ""))
    elif kind == "press":
        page.keyboard.press(str(command.get("key") or "Enter"))
    elif kind == "scroll":
        page.mouse.wheel(0, float(command.get("dy") or 0))


def _handler(state: _State):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.startswith("/frame.jpg"):
                with state.lock:
                    body = state.jpeg
                self._send(body, "image/jpeg")
                return
            if self.path.startswith("/status"):
                with state.lock:
                    payload = {"signed_in": state.signed_in, "title": state.title}
                self._send(json.dumps(payload).encode(), "application/json")
                return
            self._send(PAGE.encode(), "text/html; charset=utf-8")

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                command = json.loads(raw.decode() or "{}")
            except json.JSONDecodeError:
                command = {}
            state.commands.put(command)
            self._send(b"{}", "application/json")

        def _send(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def _tunnel() -> str:
    subprocess.Popen(
        ["ngrok", "http", str(PORT), "--log", "stdout"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urlopen("http://127.0.0.1:4040/api/tunnels", timeout=2) as response:
                payload = json.loads(response.read().decode())
        except Exception:
            time.sleep(0.5)
            continue
        for tunnel in payload.get("tunnels") or []:
            public = tunnel.get("public_url") or ""
            if public.startswith("https://"):
                return public
        time.sleep(0.5)
    raise RuntimeError("ngrok did not publish the sign-in page")


PAGE = """<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in to Hotels.com</title>
<style>
  body { font: 16px/1.4 sans-serif; margin: 0; background: #111; color: #fff; }
  header { padding: 12px 16px; }
  img { width: min(1100px, 100%); background: #fff; cursor: pointer; }
  form { display: flex; gap: 8px; padding: 0 16px 16px; }
  input { flex: 1; font: 16px sans-serif; padding: 8px; }
  button { font: 16px sans-serif; padding: 8px 12px; }
</style>
<header>Sign in to Hotels.com below. Click the page, type in the box, then press Enter.</header>
<img id="screen" alt="Hotels.com sign-in">
<form id="typing">
  <input id="text" autocomplete="off" placeholder="Type here">
  <button type="submit">Type</button>
  <button type="button" id="enter">Enter</button>
  <button type="button" id="back">Backspace</button>
</form>
<script>
const screen = document.getElementById("screen");
function refresh() {
  screen.src = "/frame.jpg?" + Date.now();
}
setInterval(refresh, 500);
refresh();
function send(body) {
  return fetch("/input", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
}
screen.addEventListener("click", (event) => {
  const rect = screen.getBoundingClientRect();
  const x = (event.clientX - rect.left) * (screen.naturalWidth / rect.width);
  const y = (event.clientY - rect.top) * (screen.naturalHeight / rect.height);
  send({type: "click", x, y});
});
document.getElementById("typing").addEventListener("submit", (event) => {
  event.preventDefault();
  const text = document.getElementById("text");
  send({type: "type", text: text.value});
  text.value = "";
});
document.getElementById("enter").addEventListener("click", () => send({type: "press", key: "Enter"}));
document.getElementById("back").addEventListener("click", () => send({type: "press", key: "Backspace"}));
setInterval(async () => {
  const status = await fetch("/status").then((response) => response.json());
  if (status.signed_in) {
    document.querySelector("header").textContent = "Signed in. You can close this page.";
  }
}, 2000);
</script>
"""


if __name__ == "__main__":
    print(serve())
