#!/usr/bin/env python3
"""Replay the captured Trip.com fetchDynamicRefreshList call."""

import json
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.trip.com/restapi/soa2/34951/fetchDynamicRefreshList"
BODY = (ROOT / "fixtures/fetchDynamicRefreshList.request.json").read_bytes()
COOKIE = (ROOT / ".secrets/cookies.txt").read_text().strip()
PHANTOM = (ROOT / ".secrets/phantom-token.txt").read_text().strip()
OUT = ROOT / "fixtures/fetchDynamicRefreshList.response.json"

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
    "referer": "https://www.trip.com/hotels/list?city=364&cityName=City%20of%20Manila&provinceId=12620&countryId=32&checkIn=2026-10-18&checkOut=2026-10-22&lat=-1&lon=-1&districtId=0&barCurr=USD&searchType=CT&searchWord=City%20of%20Manila&searchValue=19|364*19*364*1&searchCoordinate=BAIDU_-1_-1|GAODE_-1_-1|GOOGLE_-1_-1|NORMAL_14.6010326_120.9761599&crn=1&adult=2&children=0&searchBoxArg=t&ctm_ref=ix_sb_dl&travelPurpose=0&domestic=false",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
    "w-payload-source": "1.0.9@102!mZy4TVA/NrkbK2tpKEjHK69V9lG/Olq5+XtZ+EGR9r9PKEbS9rOVK6KbOrK2+ET5+rApbbbpOSVpKlkL+EbL+EtLbE4bKtb5+rbSOEbLKrKp+rALKSKnOS4SKtbpOSK2OSk2Kl45OEA5QlTnG29eFq99wlCCh5b=",
    "x-ctx-currency": "USD",
    "x-ctx-locale": "en-XX",
    "x-ctx-ubt-pageid": "10320668148",
    "x-ctx-ubt-pvid": "4",
    "x-ctx-ubt-sid": "293",
    "x-ctx-ubt-vid": "1736786220410.72cfkUFYn1Ew",
    "x-ctx-user-recognize": "NON_EU",
    "x-ctx-wclient-req": "8996986bb0770517815493a05ab02532",
}

req = urllib.request.Request(URL, data=BODY, headers=headers, method="POST")
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        status = resp.status
        content_type = resp.headers.get("content-type", "")
except urllib.error.HTTPError as err:
    raw = err.read()
    status = err.code
    content_type = err.headers.get("content-type", "")

OUT.write_bytes(raw)
print(f"status={status} bytes={len(raw)} content_type={content_type}")
print(f"wrote {OUT}")

try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    print(raw[:500].decode("utf-8", "replace"))
    raise SystemExit(1)

print("top_keys", sorted(payload.keys()))
for key in ("ResponseStatus", "responseStatus", "code", "message", "msg"):
    if key in payload:
        print(key, json.dumps(payload[key])[:400])
