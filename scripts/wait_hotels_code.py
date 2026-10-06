#!/usr/bin/env python3
"""Read a Hotels.com sign-in code from the AgentMail inbox.

The email is not the Hotels.com session. Hotels.com sends a one-time code to
the inbox. Submitting that code in IdentityVerifyOTPAuthenticationSubmit sets
EG_SESSIONTOKEN. This script only collects the code and writes it under
.secrets/. It does not print the code.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.mail import client, ensure_inbox  # noqa: E402

SENDERS = ("hotels.com", "expedia", "eg.expedia")
CODE = re.compile(r"\b(\d{6})\b")


def main() -> None:
    inbox = ensure_inbox()
    mail = client()
    deadline = time.time() + 180
    seen: set[str] = set()
    while time.time() < deadline:
        listed = mail.inboxes.messages.list(inbox.inbox_id, limit=10, from_=["hotels"])
        for message in listed.messages or []:
            message_id = message.message_id
            sender = (message.from_ or "").lower()
            if not message_id or message_id in seen:
                continue
            if not any(domain in sender for domain in SENDERS):
                continue
            seen.add(message_id)
            full = mail.inboxes.messages.get(inbox.inbox_id, message_id)
            body = full.extracted_text or full.text or full.preview or ""
            match = CODE.search(body)
            if not match:
                continue
            code = match.group(1)
            out = ROOT / ".secrets" / "hotels-login-code.txt"
            out.parent.mkdir(exist_ok=True)
            out.write_text(code + "\n")
            out.chmod(0o600)
            print(f"Saved a {len(code)}-digit Hotels.com code to .secrets/hotels-login-code.txt")
            print(f"From: {message.from_}")
            print(f"Subject: {message.subject}")
            return
        time.sleep(5)
    raise SystemExit("No Hotels.com sign-in code arrived within 3 minutes.")


if __name__ == "__main__":
    main()
