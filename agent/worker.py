"""Run one Sokosumi task through the Hotels.com reservation steps."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from agent.brief import brief_from_text, render_result
from agent.hotels import HotelsError
from agent.jobs import process_job

ROOT = Path(__file__).resolve().parents[1]
COWORKER_ID = "01a111bb-5cb1-771f-81f7-5de4ae635bba"


def answer_task(text: str) -> str:
    try:
        requested = brief_from_text(text)
        raw = process_job("sokosumi", requested)
        payload = json.loads(raw)
    except HotelsError as exc:
        return f"Could not complete the stay request. {exc}"
    except json.JSONDecodeError:
        return "Could not complete the stay request. The Hotels.com result was not readable."
    return render_result(payload)


def run_sokosumi_task(task_id: str) -> str:
    started = _sokosumi(
        [
            "runtime",
            "start",
            task_id,
            "--coworker-id",
            COWORKER_ID,
            "--personal",
            "--json",
        ]
    )
    task = json.loads(started)
    description = task.get("description") or task.get("name") or ""
    if isinstance(task.get("data"), dict):
        description = task["data"].get("description") or description
    answer = answer_task(str(description))
    result_path = ROOT / ".secrets" / f"task-{task_id}.txt"
    result_path.parent.mkdir(exist_ok=True)
    result_path.write_text(answer)
    completed = _sokosumi(
        [
            "runtime",
            "complete",
            task_id,
            "--coworker-id",
            COWORKER_ID,
            "--personal",
            "--result-file",
            str(result_path),
            "--json",
        ]
    )
    status = json.loads(completed)
    state = status.get("status") or (status.get("data") or {}).get("status")
    return f"{state or 'submitted'}\n\n{answer}"


def _sokosumi(args: list[str]) -> str:
    cleaned = ["sokosumi", "--preprod", *[arg for arg in args if arg]]
    result = subprocess.run(cleaned, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Sokosumi command failed").strip()
        raise SystemExit(detail[:500])
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Hotels.com reservation task")
    parser.add_argument("text", nargs="?", help="Task description")
    parser.add_argument("--task-id", help="Sokosumi personal task to start and complete")
    args = parser.parse_args()
    if args.task_id:
        print(run_sokosumi_task(args.task_id))
        return
    text = args.text if args.text is not None else sys.stdin.read()
    print(answer_task(text))


if __name__ == "__main__":
    main()
