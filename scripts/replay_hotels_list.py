#!/usr/bin/env python3
"""Replay the captured Hotels.com PropertyListingQuery with curl.

Python urllib is rejected (HTTP 429). The browser-shaped curl request is the
one that returns the signed-in list.
"""

import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.hotels.com/graphql"
BODY = ROOT / "fixtures/PropertyListingQuery.request.json"
COOKIE = ROOT / ".secrets/hotels-cookies.txt"
OUT = ROOT / "fixtures/PropertyListingQuery.response.json"
REFERER = (
    "https://www.hotels.com/Hotel-Search"
    "?destination=Manila%2C+National+Capital+Region%2C+Philippines"
    "&regionId=2375&latLong=14.594503%2C120.973702"
    "&d1=2026-10-18&startDate=2026-10-18"
    "&d2=2026-10-22&endDate=2026-10-22"
    "&adults=2&rooms=1&sort=PRICE_LOW_TO_HIGH&paymentType=PAY_LATER"
)

with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
    cmd = [
        "curl",
        "--http2",
        "--silent",
        "--show-error",
        "--compressed",
        "--output",
        tmp.name,
        "--write-out",
        "%{http_code}",
        URL,
        "-H",
        "accept: application/json, multipart/mixed",
        "-H",
        "accept-language: en;q=0.6",
        "-H",
        "client-info: shopping-pwa,00cd657c0a746cb3a71ac0b0370ed6edad9403f3,us-west-2",
        "-H",
        "content-type: application/json",
        "-H",
        f"cookie: {COOKIE.read_text().strip()}",
        "-H",
        "ctx-view-id: aaf4926d-d496-48e9-a96d-57108290968e",
        "-H",
        "origin: https://www.hotels.com",
        "-H",
        f"referer: {REFERER}",
        "-H",
        'sec-ch-ua: "Chromium";v="154", "Brave";v="154", "Not.A/Brand";v="99"',
        "-H",
        "sec-ch-ua-mobile: ?0",
        "-H",
        'sec-ch-ua-platform: "Linux"',
        "-H",
        "sec-fetch-dest: empty",
        "-H",
        "sec-fetch-mode: cors",
        "-H",
        "sec-fetch-site: same-origin",
        "-H",
        "sec-gpc: 1",
        "-H",
        "user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
        "-H",
        "x-enable-apq: true",
        "-H",
        "x-page-id: page.Hotel-Search,H,20",
        "-H",
        "x-shopping-product-line: lodging",
        "--data-binary",
        f"@{BODY}",
    ]
    status = subprocess.run(cmd, check=False, capture_output=True, text=True)
    code = status.stdout.strip()
    raw = Path(tmp.name).read_bytes()

print(f"status={code} bytes={len(raw)}")
if status.returncode != 0:
    print(status.stderr[:400])
    raise SystemExit(status.returncode)
if code != "200":
    print(raw[:200].decode("utf-8", "replace"))
    raise SystemExit(1)

OUT.write_bytes(raw)
payload = json.loads(raw)
search = payload["data"]["propertySearch"]
cards = [
    item
    for item in search["propertySearchListings"]
    if item.get("__typename") == "LodgingCard"
]
print(search["summary"]["resultsHeading"])
for card in cards:
    name = card["headingSection"]["heading"]
    price = card["priceSection"]["priceSummary"]["options"][0]["displayPrice"]["formatted"]
    print(f"{name} {price}")
