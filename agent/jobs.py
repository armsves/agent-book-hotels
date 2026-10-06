"""Job runner for the Hotels.com travel desk."""

from __future__ import annotations

import json
from datetime import date, datetime

from agent.hotels import (
    HotelsError,
    bind_session,
    lookup_city,
    open_checkout,
    reset_session,
    search_stays,
    stored_session,
)

INPUT_SCHEMA = {
    "input_data": [
        {
            "id": "destination",
            "type": "string",
            "name": "City",
            "data": {"description": "City name, for example Manila"},
        },
        {
            "id": "check_in",
            "type": "string",
            "name": "Check-in",
            "data": {"description": "YYYY-MM-DD"},
        },
        {
            "id": "check_out",
            "type": "string",
            "name": "Check-out",
            "data": {"description": "YYYY-MM-DD"},
        },
        {
            "id": "adults",
            "type": "string",
            "name": "Adults",
            "data": {"description": "Defaults to 2"},
        },
        {
            "id": "payment_type",
            "type": "string",
            "name": "Payment type",
            "data": {"description": "PAY_LATER"},
        },
        {
            "id": "lodging",
            "type": "string",
            "name": "Lodging filter",
            "data": {"description": "Optional, for example APART_HOTEL"},
        },
        {
            "id": "action",
            "type": "string",
            "name": "Action",
            "data": {"description": "search or checkout"},
        },
        {
            "id": "property_id",
            "type": "string",
            "name": "Property id",
            "data": {"description": "Required for checkout when not taking the first match"},
        },
    ]
}


def process_job(identifier_from_purchaser: str, input_data: dict) -> str:
    del identifier_from_purchaser
    try:
        return json.dumps(_with_session(lambda: _run(input_data)))
    except HotelsError as exc:
        status = "needs_login" if "sign-in" in str(exc).lower() else "failed"
        return json.dumps({"status": status, "message": str(exc)})


def search_hotels(input_data: dict) -> dict:
    payload = dict(input_data)
    payload["action"] = "search"
    return _with_session(lambda: _run(payload))


def book_hotel(input_data: dict) -> dict:
    payload = dict(input_data)
    payload["action"] = "checkout"
    return _with_session(lambda: _run(payload))


def _with_session(run):
    token = bind_session(_account_session())
    try:
        return run()
    finally:
        reset_session(token)


def _account_session() -> str:
    saved = stored_session()
    if saved:
        return saved
    raise HotelsError(
        "Hotels.com sign-in is missing. Sign in on this computer, then set HOTELS_COOKIE."
    )


def _run(input_data: dict) -> dict:
    destination_name = (input_data.get("destination") or "").strip()
    check_in = _parse_date(input_data.get("check_in"), "check_in")
    check_out = _parse_date(input_data.get("check_out"), "check_out")
    if check_out <= check_in:
        raise HotelsError("check_out must be after check_in")
    adults = int(input_data.get("adults") or 2)
    payment_type = (input_data.get("payment_type") or "PAY_LATER").strip()
    lodging = (input_data.get("lodging") or "").strip()
    action = (input_data.get("action") or "search").strip().lower()
    if action not in {"search", "checkout"}:
        raise HotelsError("action must be search or checkout")
    destination = lookup_city(destination_name)
    found = search_stays(
        destination, check_in, check_out, adults, payment_type, lodging
    )
    stays = [
        stay for stay in found["stays"] if stay["free_cancellation"]
    ] or found["stays"]
    result = {
        "status": "completed",
        "action": action,
        "destination": destination["regionName"],
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "payment_type": payment_type,
        "lodging": lodging or None,
        "heading": found["heading"],
        "stays": [
            {
                "property_id": stay["property_id"],
                "name": stay["name"],
                "price": stay["price"],
                "free_cancellation": stay["free_cancellation"],
                "url": stay["url"],
            }
            for stay in stays
        ],
    }
    if action == "search":
        return result
    wanted = (input_data.get("property_id") or "").strip()
    candidates = stays
    if wanted:
        candidates = [stay for stay in stays if stay["property_id"] == wanted]
        if not candidates:
            raise HotelsError("No stay matched that property id")
    last_error = HotelsError("No stay matched that property id")
    for chosen in candidates:
        try:
            result["checkout"] = open_checkout(
                destination, chosen, check_in, check_out, adults, payment_type, lodging
            )
        except HotelsError as exc:
            last_error = exc
            continue
        return result
    raise last_error


def _parse_date(value: str | None, name: str) -> date:
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise HotelsError(f"{name} must be YYYY-MM-DD") from exc
