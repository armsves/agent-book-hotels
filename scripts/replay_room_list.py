#!/usr/bin/env python3
"""Replay the captured Trip.com getHotelRoomListOversea call."""

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.trip.com/restapi/soa2/33269/getHotelRoomListOversea"
BODY = (ROOT / "fixtures/getHotelRoomListOversea.request.json").read_bytes()
COOKIE = (ROOT / ".secrets/cookies.txt").read_text().strip()
PHANTOM = (ROOT / ".secrets/phantom-token.txt").read_text().strip()
OUT = ROOT / "fixtures/getHotelRoomListOversea.response.json"

headers = {
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.6",
    "content-type": "application/json",
    "cookie": COOKIE,
    "cookieorigin": "https://www.trip.com",
    "currency": "USD",
    "locale": "en-XX",
    "origin": "https://www.trip.com",
    "phantom-token": PHANTOM,
    "referer": "https://www.trip.com/hotels/detail/?hotelId=28866235&cityId=121851&checkIn=2026-10-18&checkOut=2026-10-22&adult=2&children=0&crn=1&curr=USD&locale=en-XX",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
    "x-ctx-currency": "USD",
    "x-ctx-locale": "en-XX",
    "x-ctx-ubt-pvid": "20",
    "x-ctx-ubt-sid": "293",
    "x-ctx-ubt-vid": "1736786220410.72cfkUFYn1Ew",
    "x-ctx-user-recognize": "NON_EU",
    "x-ctx-wclient-req": "52669398303ab934815d83c18c4a7b69",
}

req = urllib.request.Request(URL, data=BODY, headers=headers, method="POST")
try:
    with urllib.request.urlopen(req, timeout=40) as resp:
        raw = resp.read()
        status = resp.status
except urllib.error.HTTPError as err:
    raw = err.read()
    status = err.code

OUT.write_bytes(raw)
payload = json.loads(raw)
ack = (payload.get("ResponseStatus") or {}).get("Ack")
print(f"status={status} ack={ack} bytes={len(raw)} top={sorted(payload.keys())}")
