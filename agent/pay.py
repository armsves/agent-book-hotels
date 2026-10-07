"""Create a Masumi v2 payment request for 1 USDM."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

# Preprod tUSDM, 6 decimals. 1 USDM = 1000000.
USDM_UNIT = "16a55b2a349361ff88c03788f93e1e966e5d689605d044fef722ddde0014df10745553444d"
USDM_AMOUNT = "1000000"
PAYMENT_SOURCE_TYPE = "Web3CardanoV2"


class PaymentError(Exception):
    pass


def purchaser_id(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{14,26}", value):
        return value
    return secrets.token_hex(10)


def input_hash(input_data: dict, identifier_from_purchaser: str) -> str:
    canonical = json.dumps(input_data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{identifier_from_purchaser};{canonical}".encode()).hexdigest()


def create_payment_request(identifier_from_purchaser: str | None, input_data: dict) -> dict:
    base = os.environ.get("PAYMENT_SERVICE_URL", "").rstrip("/")
    token = os.environ.get("PAYMENT_API_KEY", "")
    agent_identifier = os.environ.get("AGENT_IDENTIFIER", "")
    if not base or not token or not agent_identifier:
        raise PaymentError("PAYMENT_SERVICE_URL, PAYMENT_API_KEY, and AGENT_IDENTIFIER are required")
    buyer = purchaser_id(identifier_from_purchaser)
    now = datetime.now(timezone.utc)
    # The agent NFT advertises a fixed 1 USDM price. V2 fixed pricing rejects RequestedFunds.
    payload = {
        "network": os.environ.get("NETWORK", "Preprod"),
        "agentIdentifier": agent_identifier,
        "paymentSourceType": PAYMENT_SOURCE_TYPE,
        "supportedPaymentSourceIndex": int(os.environ.get("PAYMENT_SOURCE_INDEX", "0")),
        "inputHash": input_hash(input_data, buyer),
        "identifierFromPurchaser": buyer,
        "payByTime": _iso(now + timedelta(hours=1)),
        "submitResultTime": _iso(now + timedelta(hours=2)),
        "unlockTime": _iso(now + timedelta(hours=8)),
        "externalDisputeUnlockTime": _iso(now + timedelta(hours=14)),
        "metadata": "1 USDM",
    }
    request = urllib.request.Request(
        f"{base}/payment/",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "token": token,
            "ngrok-skip-browser-warning": "1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise PaymentError(f"Payment request failed ({exc.code}): {detail}") from exc
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict) or not data.get("blockchainIdentifier"):
        raise PaymentError("Payment service did not return a blockchain identifier")
    source = data.get("PaymentSource") or {}
    return {
        "blockchain_identifier": data["blockchainIdentifier"],
        "payment_source_type": source.get("paymentSourceType") or PAYMENT_SOURCE_TYPE,
        "network": source.get("network") or payload["network"],
        "supported_payment_source_index": payload["supportedPaymentSourceIndex"],
        "amount": USDM_AMOUNT,
        "unit": USDM_UNIT,
        "pay_by_time": data.get("payByTime"),
        "submit_result_time": data.get("submitResultTime"),
        "on_chain_state": data.get("onChainState"),
    }


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
