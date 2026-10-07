"""MIP-003 server for the Hotels.com travel agent.

With PAYMENT_API_KEY and AGENT_IDENTIFIER set, this delegates to the Masumi
SDK so jobs wait for escrow. Otherwise it runs the job immediately so the
agency session can be tested before the agent NFT is minted.
"""

from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
import uvicorn

from agent.hotels import HotelsError
from agent.jobs import INPUT_SCHEMA, book_hotel, process_job, search_hotels
from agent.pay import PaymentError, create_payment_request

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

JOBS: dict[str, dict] = {}


class Load(BaseModel):
    active_jobs: int
    queued_jobs: int
    max_capacity: int


class Availability(BaseModel):
    status: str
    message: str
    current_load: Load


class JobField(BaseModel):
    key: str | None = None
    id: str | None = None
    value: str | None = None
    data: str | None = None


class StartJob(BaseModel):
    identifier_from_purchaser: str | None = "local"
    input_data: list[JobField] = Field(
        examples=[
            [
                {"key": "destination", "value": "Manila"},
                {"key": "check_in", "value": "2026-10-23"},
                {"key": "check_out", "value": "2026-10-25"},
                {"key": "adults", "value": "2"},
                {"key": "payment_type", "value": "PAY_LATER"},
                {"key": "action", "value": "search"},
            ]
        ]
    )


class PaymentInfo(BaseModel):
    blockchain_identifier: str
    payment_source_type: str
    network: str
    supported_payment_source_index: int
    amount: str
    unit: str
    pay_by_time: str | int | None = None
    submit_result_time: str | int | None = None
    on_chain_state: str | None = None


class JobResult(BaseModel):
    job_id: str
    identifier_from_seller: str | None = None
    status: str
    output: str | None = None
    message: str | None = None
    payment: PaymentInfo | None = None


class StayQuery(BaseModel):
    destination: str = Field(examples=["Manila"])
    check_in: str = Field(examples=["2026-10-23"], description="YYYY-MM-DD")
    check_out: str = Field(examples=["2026-10-25"], description="YYYY-MM-DD")
    adults: int = 2
    payment_type: str = "PAY_LATER"
    lodging: str = Field(default="", description="Optional, for example APART_HOTEL")


class BookQuery(BaseModel):
    destination: str = "Manila"
    check_in: str = Field(default="2026-10-23", description="YYYY-MM-DD")
    check_out: str = Field(default="2026-10-25", description="YYYY-MM-DD")
    adults: int = 2
    payment_type: str = "PAY_LATER"
    lodging: str = "APART_HOTEL"
    property_id: str = "113900859"


class Stay(BaseModel):
    property_id: str
    name: str | None = None
    price: str | None = None
    free_cancellation: bool
    url: str | None = None


class SearchResult(BaseModel):
    status: str
    destination: str
    check_in: str
    check_out: str
    payment_type: str
    lodging: str | None = None
    heading: str | None = None
    stays: list[Stay]


class CheckoutTotal(BaseModel):
    amount: float | int | str | None = None
    currency: str | None = None


class Checkout(BaseModel):
    property_id: str
    name: str | None = None
    price: str | None = None
    free_cancellation: bool
    payment_model: str
    total: CheckoutTotal | None = None
    trip_id: str | None = None
    checkout_url: str | None = None
    failure_reason: str | None = None


class BookResult(SearchResult):
    checkout: Checkout


def create_app() -> FastAPI:
    app = FastAPI(
        title="Expert Travel Advisor",
        description=(
            "Search Hotels.com for a free-cancellation, pay-at-property stay, "
            "then open checkout for the chosen hotel."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    @app.get("/", include_in_schema=False)
    def home():
        return RedirectResponse("/docs")

    @app.get("/availability", response_model=Availability)
    def availability():
        return {
            "status": "available",
            "message": "Hotels.com travel desk is accepting jobs",
            "current_load": {"active_jobs": _active(), "queued_jobs": 0, "max_capacity": 4},
        }

    @app.get("/input_schema")
    def input_schema():
        return INPUT_SCHEMA

    @app.get("/demo")
    def demo():
        sample = ROOT / "fixtures" / "example-search-output.json"
        return {
            "input": {
                "destination": "Manila",
                "check_in": "2026-10-18",
                "check_out": "2026-10-22",
                "adults": "2",
                "payment_type": "PAY_LATER",
                "action": "search",
            },
            "output": sample.read_text() if sample.is_file() else "",
        }

    @app.post("/hotels/search", response_model=SearchResult, tags=["Hotels"])
    def hotels_search(body: StayQuery):
        """Search pay-at-property stays and keep free-cancellation matches."""
        return _hotels_call(search_hotels, body)

    @app.post("/hotels/book", response_model=BookResult, tags=["Hotels"])
    def hotels_book(
        body: Annotated[
            BookQuery,
            Body(
                openapi_examples={
                    "manila": {
                        "summary": "Open checkout for a Manila stay",
                        "value": {
                            "destination": "Manila",
                            "check_in": "2026-10-23",
                            "check_out": "2026-10-25",
                            "adults": 2,
                            "payment_type": "PAY_LATER",
                            "lodging": "APART_HOTEL",
                            "property_id": "113900859",
                        },
                    }
                }
            ),
        ],
    ):
        """Open checkout for a pay-at-property stay. Does not confirm the reservation."""
        return _hotels_call(book_hotel, body)

    @app.post("/start_job", response_model=JobResult)
    def start_job(body: StartJob):
        raw_input = [item.model_dump(exclude_none=True) for item in body.input_data]
        buyer = body.identifier_from_purchaser or "local"
        values = {}
        for item in raw_input:
            if "key" in item:
                values[item["key"]] = item.get("value")
            elif "id" in item:
                values[item["id"]] = item.get("value", item.get("data"))
        if not values.get("destination") or not values.get("check_in") or not values.get("check_out"):
            raise HTTPException(status_code=400, detail="INVALID_INPUT")
        payment = _payment_request(buyer, values)
        job_id = f"job-{uuid.uuid4()}"
        JOBS[job_id] = {"status": "running", "buyer": buyer, "input": values, "payment": payment}
        if os.environ.get("VERCEL"):
            _execute(job_id)
            job = JOBS[job_id]
            return {
                "job_id": job_id,
                "identifier_from_seller": job_id,
                "status": job["status"],
                "output": job.get("output"),
                "payment": payment,
            }
        threading.Thread(target=_execute, args=(job_id,), daemon=True).start()
        return {
            "job_id": job_id,
            "identifier_from_seller": job_id,
            "status": "running",
            "payment": payment,
        }

    @app.get("/status", response_model=JobResult)
    def status(job_id: str | None = None, jobId: str | None = None):
        key = job_id or jobId
        job = JOBS.get(key or "")
        if not job:
            raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
        return {
            "job_id": key,
            "status": job["status"],
            "output": job.get("output"),
            "message": job.get("message"),
            "payment": job.get("payment"),
        }

    return app


def _payment_request(buyer: str, values: dict) -> dict | None:
    if not (os.environ.get("PAYMENT_API_KEY") and os.environ.get("AGENT_IDENTIFIER")):
        return None
    try:
        return create_payment_request(buyer, values)
    except PaymentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _hotels_call(run, body: StayQuery | BookQuery):
    try:
        return run(body.model_dump())
    except HotelsError as exc:
        status = 401 if "sign-in" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


def _execute(job_id: str) -> None:
    job = JOBS[job_id]
    output = process_job(job["buyer"], job["input"])
    parsed_status = "completed"
    try:
        import json

        payload = json.loads(output)
        if payload.get("status") == "failed":
            parsed_status = "failed"
            job["message"] = payload.get("message")
    except json.JSONDecodeError:
        parsed_status = "failed"
    job["status"] = parsed_status
    job["output"] = output


def _active() -> int:
    return sum(1 for job in JOBS.values() if job["status"] == "running")


def main() -> None:
    if os.environ.get("PAYMENT_API_KEY") and os.environ.get("AGENT_IDENTIFIER"):
        from masumi import run

        run(start_job_handler=process_job, input_schema_handler=INPUT_SCHEMA)
        return
    port = int(os.environ.get("AGENT_PORT", "8080"))
    uvicorn.run(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
