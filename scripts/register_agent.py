#!/usr/bin/env python3
"""Mint the Expert Travel Advisor NFT on Masumi Preprod.

Reads keys from .env. Refuses Mainnet. Does not print secrets.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

REQUIRED = [
    "PAYMENT_SERVICE_URL",
    "PAYMENT_API_KEY",
    "AGENT_API_BASE_URL",
    "AGENT_AUTHOR_EMAIL",
    "AGENT_EXAMPLE_OUTPUT_URL",
    "AGENT_TERMS_URL",
    "AGENT_PRIVACY_URL",
]


def require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(
            f"Missing {name}. Add it to .env (see .env.example). "
            "Payment keys come from the Masumi node admin dashboard."
        )
    return value


def main() -> None:
    network = os.environ.get("NETWORK", "Preprod")
    if network != "Preprod":
        raise SystemExit(
            "Refusing to register. NETWORK must be Preprod. "
            "Mainnet spends real ADA."
        )
    for name in REQUIRED:
        require(name)
    base = os.environ["PAYMENT_SERVICE_URL"].rstrip("/")
    wallets = _request("GET", f"{base}/wallet?network=Preprod")
    selling = _selling_wallet(wallets)
    vkey = (
        selling.get("vkey")
        or selling.get("walletVkey")
        or selling.get("verificationKey")
        or os.environ.get("SELLER_VKEY", "")
    )
    if not vkey:
        names = sorted(selling.keys())
        raise SystemExit(
            "Selling wallet has no vkey field. Set SELLER_VKEY in .env. "
            f"Wallet fields: {', '.join(names)}"
        )
    body = {
        "network": "Preprod",
        "sellingWalletVkey": vkey,
        "name": "Expert Travel Advisor",
        "description": (
            "Searches Hotels.com for pay-later stays with free cancellation "
            "and opens checkout on the agency account."
        ),
        "apiBaseUrl": os.environ["AGENT_API_BASE_URL"].rstrip("/"),
        "Tags": ["travel", "hotels", "lodging", "free-cancellation"],
        "ExampleOutputs": [
            {
                "name": "manila-pay-later-search",
                "url": os.environ["AGENT_EXAMPLE_OUTPUT_URL"],
                "mimeType": "application/json",
            }
        ],
        "Capability": {"name": "hotels.com", "version": "2026-10"},
        "AgentPricing": {"pricingType": "Free", "Pricing": []},
        "Author": {
            "name": os.environ.get("AGENT_AUTHOR_NAME", "Expert Travel Advisor"),
            "contactEmail": os.environ["AGENT_AUTHOR_EMAIL"],
            "organization": os.environ.get(
                "AGENT_AUTHOR_ORGANIZATION", "Expert Travel Advisor"
            ),
            "contactOther": "",
        },
        "Legal": {
            "privacyPolicy": os.environ["AGENT_PRIVACY_URL"],
            "terms": os.environ["AGENT_TERMS_URL"],
            "other": "",
        },
    }
    created = _request("POST", f"{base}/registry", body)
    data = created.get("data", created)
    identifier = data.get("agentIdentifier") or data.get("blockchainIdentifier")
    print("Registered on Preprod")
    if identifier:
        print(f"agentIdentifier: {identifier}")
    else:
        print("Registration response did not include agentIdentifier")


def _selling_wallet(payload: dict) -> dict:
    rows = payload.get("data", payload)
    if isinstance(rows, dict):
        rows = rows.get("wallets") or rows.get("data") or [rows]
    for row in rows:
        wallet_type = str(row.get("type") or row.get("walletType") or "").lower()
        if "sell" in wallet_type:
            return row
    raise SystemExit("No selling wallet on the payment node. Create one in the admin dashboard.")


def _request(method: str, url: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "token": os.environ["PAYMENT_API_KEY"],
            "content-type": "application/json",
            "accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"Registry call failed with HTTP {exc.code}: {detail}") from exc
    return json.loads(raw) if raw else {}


if __name__ == "__main__":
    main()
