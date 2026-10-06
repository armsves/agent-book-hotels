"""Turn a Sokosumi task into a Hotels.com search or reservation."""

from __future__ import annotations

import json
import re

from agent.hotels import HotelsError

_DATE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_ADULTS = re.compile(r"\b(\d+)\s+adults?\b", re.I)
_PROPERTY = re.compile(r"\bproperty(?:\s+id)?\s*[:=]?\s*(\d{5,})\b", re.I)
_IN = re.compile(r"\bin\s+([A-Za-z][A-Za-z .'-]{1,60}?)(?:\s+from|\s+for|\s+on|,|\.|$)", re.I)


def brief_from_text(text: str) -> dict:
    stripped = (text or "").strip()
    if not stripped:
        raise HotelsError("The task needs a city and check-in and check-out dates")
    if stripped.startswith("{"):
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload
    dates = _DATE.findall(stripped)
    if len(dates) < 2:
        raise HotelsError("The task needs check-in and check-out as YYYY-MM-DD")
    destination = _destination(stripped)
    if not destination:
        raise HotelsError("The task needs a city, for example: in Manila")
    lowered = stripped.lower()
    reserve = any(word in lowered for word in ("reserv", "book", "checkout"))
    lodging = "APART_HOTEL" if "apart" in lowered else ""
    adults = _ADULTS.search(stripped)
    property_id = _PROPERTY.search(stripped)
    return {
        "destination": destination,
        "check_in": dates[0],
        "check_out": dates[1],
        "adults": adults.group(1) if adults else "2",
        "payment_type": "PAY_LATER",
        "lodging": lodging,
        "action": "checkout" if reserve else "search",
        "property_id": property_id.group(1) if property_id else "",
        "browser_session_id": _browser_session(stripped),
    }


def render_result(payload: dict) -> str:
    if payload.get("status") == "needs_login":
        url = payload.get("login_url")
        if url:
            return (
                "Open this link and sign in to Hotels.com:\n"
                f"{url}\n\n"
                "Reply when you are signed in.\n"
                f"browser_session_id: {payload.get('browser_session_id')}"
            )
        return str(payload.get("message") or "").strip()
    if payload.get("status") == "failed":
        return f"Could not complete the stay request. {payload.get('message', '')}".strip()
    lines = [
        f"Destination: {payload.get('destination')}",
        f"Stay: {payload.get('check_in')} to {payload.get('check_out')}",
        f"Payment: {payload.get('payment_type')}",
    ]
    if payload.get("heading"):
        lines.append(str(payload["heading"]))
    lines.append("Free-cancellation matches:")
    for stay in payload.get("stays") or []:
        lines.append(
            f"- {stay.get('name')} ({stay.get('property_id')}), {stay.get('price')}, "
            f"free cancellation {stay.get('free_cancellation')}"
        )
    checkout = payload.get("checkout") or {}
    if checkout:
        lines.extend(
            [
                "Reservation checkout:",
                f"- Property: {checkout.get('name')}",
                f"- Total: {checkout.get('total')}",
                f"- Checkout URL: {checkout.get('checkout_url')}",
            ]
        )
        if checkout.get("failure_reason"):
            lines.append(f"- Checkout was not opened: {checkout.get('failure_reason')}")
    elif payload.get("action") == "search":
        lines.append("Search only. Ask to reserve a property to open checkout.")
    return "\n".join(lines)


def _browser_session(text: str) -> str:
    match = re.search(r"\bbrowser_session_id\s*[:=]\s*(\S+)", text, re.I)
    if match:
        return match.group(1)
    if re.search(r"\bsigned in\b", text, re.I):
        from agent.remote_login import remembered_session_id

        return remembered_session_id()
    return ""


def _destination(text: str) -> str:
    match = _IN.search(text)
    if not match:
        return ""
    name = match.group(1).strip(" .")
    for stopper in (" from ", " for ", " on "):
        if stopper in name.lower():
            name = re.split(stopper, name, flags=re.I)[0].strip()
    return name
