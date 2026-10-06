"""AgentMail inbox used for the Hotels.com sign-in code."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from agentmail import AgentMail
from agentmail.core.api_error import ApiError
from agentmail.errors.not_found_error import NotFoundError
from agentmail.inboxes.types.create_inbox_request import CreateInboxRequest
from agentmail.inboxes.types.inbox import Inbox

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

USERNAME = "armsves"
DOMAIN = "agentmail.to"


def client() -> AgentMail:
    key = os.environ.get("AGENTMAIL_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing AGENTMAIL_API_KEY")
    return AgentMail(api_key=key)


def inbox_address() -> str:
    return os.environ.get("AGENTMAIL_INBOX", f"{USERNAME}@{DOMAIN}").strip()


def ensure_inbox() -> Inbox:
    mail = client()
    address = inbox_address()
    try:
        return mail.inboxes.get(address)
    except NotFoundError:
        return mail.inboxes.create(
            request=CreateInboxRequest(username=USERNAME, domain=DOMAIN)
        )
    except ApiError as exc:
        if exc.status_code == 401:
            raise RuntimeError(
                "AgentMail rejected AGENTMAIL_API_KEY (HTTP 401). "
                "Replace the value in .env with a key from the AgentMail console."
            ) from exc
        raise


if __name__ == "__main__":
    inbox = ensure_inbox()
    print(f"inbox {inbox.email} status {inbox.status or 'active'}")
