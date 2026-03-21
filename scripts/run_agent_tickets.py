#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.agent_tickets import (
    filter_tickets,
    parse_ticket_markdown,
    run_ticket,
    select_cli_runner,
    write_run_summary,
)


def _now_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run agent tickets from a markdown file through Codex/Codel CLI.")
    parser.add_argument(
        "--tickets-file",
        default="agent_tickets/repo_review_tickets.md",
        help="Path to the markdown ticket file.",
    )
    parser.add_argument(
        "--runner",
        help="Override the CLI executable. Defaults to CODEL_CLI_BIN, then codel-cli, then codex.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(ROOT),
        help="Repository root to pass to the CLI.",
    )
    parser.add_argument(
        "--output-dir",
        default=f"agent_tickets/runs/{_now_utc_stamp()}",
        help="Directory for prompts, logs, and summary output.",
    )
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Sandbox mode passed to the CLI runner.",
    )
    parser.add_argument("--model", help="Optional model override passed to the CLI runner.")
    parser.add_argument(
        "--status",
        action="append",
        dest="statuses",
        help="Status filter. Repeatable. Defaults to `open`.",
    )
    parser.add_argument(
        "--ticket-id",
        action="append",
        dest="ticket_ids",
        help="Run only the specified ticket ID. Repeatable.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        dest="extra_args",
        default=[],
        help="Additional raw argument passed through to the CLI runner. Repeatable.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Keep running later tickets even if one ticket fails.",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=20.0,
        help="How often to print a keep-alive message if the child runner stays quiet.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print the execution plan without launching the CLI runner.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    tickets = parse_ticket_markdown(ROOT / args.tickets_file)
    selected = filter_tickets(
        tickets,
        include_statuses=set(args.statuses or ["open"]),
        ticket_ids=set(args.ticket_ids) if args.ticket_ids else None,
    )
    if not selected:
        raise RuntimeError("No tickets matched the requested filters.")

    runner = select_cli_runner(args.runner)
    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        plan = {
            "runner": runner,
            "repo_root": str(ROOT / args.repo_root if not Path(args.repo_root).is_absolute() else Path(args.repo_root)),
            "tickets_file": str(ROOT / args.tickets_file),
            "output_dir": str(output_dir),
            "ticket_ids": [ticket.ticket_id for ticket in selected],
            "sandbox": args.sandbox,
            "model": args.model,
            "extra_args": args.extra_args,
        }
        print(json.dumps(plan, indent=2))
        return 0

    results = []
    total = len(selected)
    for index, ticket in enumerate(selected, start=1):
        print(f"[{index}/{total}] Starting {ticket.ticket_id} - {ticket.title}")
        started_at = time.monotonic()

        def progress_callback(message: str, *, prefix: str = f"[{index}/{total}] {ticket.ticket_id}") -> None:
            print(f"{prefix} {message}", flush=True)

        result = run_ticket(
            ticket,
            repo_root=ROOT / args.repo_root if not Path(args.repo_root).is_absolute() else Path(args.repo_root),
            runner=runner,
            output_dir=output_dir,
            sandbox=args.sandbox,
            model=args.model,
            extra_args=args.extra_args,
            progress_callback=progress_callback,
            heartbeat_seconds=args.heartbeat_seconds,
        )
        results.append(result)
        elapsed_seconds = time.monotonic() - started_at
        status_text = "ok" if result["returncode"] == 0 else f"failed ({result['returncode']})"
        print(
            f"[{index}/{total}] Finished {ticket.ticket_id} in {elapsed_seconds:.1f}s: {status_text}",
            flush=True,
        )
        if result["returncode"] != 0 and not args.continue_on_error:
            break

    summary_path = write_run_summary(results, output_dir)
    print(
        json.dumps(
            {
                "runner": runner,
                "output_dir": str(output_dir),
                "summary_path": str(summary_path),
                "ran_ticket_ids": [item["ticket_id"] for item in results],
                "failed_ticket_ids": [item["ticket_id"] for item in results if item["returncode"] != 0],
            },
            indent=2,
        )
    )

    return 1 if any(item["returncode"] != 0 for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
