#!/usr/bin/env python3
"""Replay the captured Trip.com fetchHotelList call and print a short summary."""

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.trip.com/restapi/soa2/34951/fetchHotelList"
BODY = (ROOT / "fixtures/fetchHotelList.request.json").read_bytes()
COOKIE = (ROOT / ".secrets/cookies.txt").read_text().strip()
PHANTOM = (ROOT / ".secrets/phantom-token.txt").read_text().strip()
OUT = ROOT / "fixtures/fetchHotelList.response.json"

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
    "referer": "https://www.trip.com/hotels/list?flexType=1&fixedDate=0&cityId=364&provinceId=12620&countryId=32&cityName=City%20of%20Manila&destName=City%20of%20Manila,%20Metro%20Manila,%20Philippines&searchWord=City%20of%20Manila&searchType=CT&searchValue=19|364*19*364&checkin=2026-10-13&checkout=2026-10-15&crn=1&adult=1&listFilters=29~1*29*1~1*2,17~1*17*1,23~10*23*10,80~0~1*80*0&curr=USD&locale=en-XX&old=1",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
    "w-payload-source": "1.0.9@102!qBjCqA9ehZKb9ltZ9Xt/Grt5OETpOEb2O69VKEjdKlhHO6FdKXK/OE4bOrK2+ET5+rApbbbpOSVpKlk/OrV5KSTIbE4bKtb5+rbSOEbLKrKp+rALKSKnOS4SKtbpOSK2OSk2Kl45OEA5QlTnG29eFq99wlCCh5b=",
    "x-ctx-currency": "USD",
    "x-ctx-locale": "en-XX",
    "x-ctx-ubt-pageid": "10320668148",
    "x-ctx-ubt-pvid": "10",
    "x-ctx-ubt-sid": "293",
    "x-ctx-ubt-vid": "1736786220410.72cfkUFYn1Ew",
    "x-ctx-user-recognize": "NON_EU",
    "x-ctx-wclient-req": "b05e26548c21be7be0d10da6d76bf972",
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
ack = payload.get("ResponseStatus", {}).get("Ack")
data = payload.get("data") or {}
hotels = data.get("hotelList") or []
addition = data.get("hotelListAddtionInfo") or {}
print(f"status={status} ack={ack} hotels={len(hotels)} bytes={len(raw)}")
print("loginType", addition.get("loginType"))
print("hotelTotal", addition.get("hotelTotalNum") or addition.get("hotelCount") or addition.get("totalCount"))
print("addition_keys", sorted(addition.keys()))
if hotels:
    print("hotel_keys", sorted(hotels[0].keys()))
