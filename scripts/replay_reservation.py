#!/usr/bin/env python3
"""Replay the captured Trip.com reservation form call. This loads the booking page; it does not submit an order."""

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.trip.com/restapi/soa2/35033/reservation"
BODY = (ROOT / ".secrets/reservation.request.json").read_bytes()
COOKIE = (ROOT / ".secrets/cookies.txt").read_text().strip()
PHANTOM = (ROOT / ".secrets/phantom-token.txt").read_text().strip()
OUT = ROOT / "fixtures/reservation.response.json"

headers = {
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.8",
    "content-type": "application/json",
    "cookie": COOKIE,
    "cookieorigin": "https://www.trip.com",
    "currency": "USD",
    "locale": "en-XX",
    "origin": "https://www.trip.com",
    "phantom-token": PHANTOM,
    "referer": "https://www.trip.com/hotels/detail/?hotelId=28866235&cityId=121851&checkIn=2026-10-18&checkOut=2026-10-22&adult=2&crn=1&curr=USD&locale=en-XX",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
    "w-payload-source": "1.0.9@102!+AOQhEdnmPWb+EqpGPCaOX4L+rOHGP9d+XqnG6GIKPCVKSCPOE9PKEbbOrK2+ET5+rApbbbpOSVpKlkZKlkpOrGpbE4bKtb5+rbSOEbLKrKp+rALKSKnOS4SKtbpOSK2OSk2Kl45OEA5QlTnG29eFq99wlCCh5b=",
    "x-ctx-currency": "USD",
    "x-ctx-locale": "en-XX",
    "x-ctx-ubt-pageid": "10320668147",
    "x-ctx-ubt-pvid": "20",
    "x-ctx-ubt-sid": "293",
    "x-ctx-ubt-vid": "1736786220410.72cfkUFYn1Ew",
    "x-ctx-user-recognize": "NON_EU",
    "x-ctx-wclient-req": "4d5361c761ed8ae0af26c4637625095e",
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
