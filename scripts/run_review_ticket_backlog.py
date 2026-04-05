#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.agent_tickets import select_cli_runner
from flywire_wave.review_ticket_backlog import (
    execute_review_ticket_backlog,
)


def _now_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _resolve_repo_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run tickets from a review run and revalidate each later ticket "
            "before execution."
        )
    )
    parser.add_argument(
        "--review-run-dir",
        required=True,
        help="Path to an existing review run directory created by run_review_prompt_tickets.py.",
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
        default=f"agent_tickets/review_ticket_runs/{_now_utc_stamp()}",
        help="Directory for ticket-run artifacts, ticket-review artifacts, and the backlog summary.",
    )
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Sandbox mode passed to the CLI runner.",
    )
    parser.add_argument("--ticket-model", help="Optional model override for the ticket-implementation phase.")
    parser.add_argument("--review-model", help="Optional model override for the pre-ticket review phase.")
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
        help="Run only the specified ticket ID(s). Repeatable.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        dest="extra_args",
        default=[],
        help="Additional raw argument passed through to the ticket-execution runner. Repeatable.",
    )
    parser.add_argument(
        "--review-extra-arg",
        action="append",
        dest="review_extra_args",
        default=[],
        help="Additional raw argument passed through to the pre-ticket review runner. Repeatable.",
    )
    parser.add_argument(
        "--no-ticket-review",
        action="store_true",
        help="Disable the review/update pass that runs before each ticket after the first one.",
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
        help="Print the execution plan without launching the CLI runner.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    review_run_dir = _resolve_repo_path(args.review_run_dir)
    repo_root = _resolve_repo_path(args.repo_root)
    output_dir = _resolve_repo_path(args.output_dir)
    initial_tickets_file = review_run_dir / "combined_tickets.md"
    if not initial_tickets_file.exists():
        raise FileNotFoundError(f"Combined tickets file does not exist: {initial_tickets_file}")

    if args.dry_run:
        plan = {
            "review_run_dir": str(review_run_dir),
            "initial_tickets_file": str(initial_tickets_file),
            "repo_root": str(repo_root),
            "output_dir": str(output_dir),
            "runner": args.runner or "auto",
            "sandbox": args.sandbox,
            "ticket_model": args.ticket_model,
            "review_model": args.review_model,
            "statuses": args.statuses or ["open"],
            "ticket_ids": args.ticket_ids or [],
            "extra_args": args.extra_args,
            "review_extra_args": args.review_extra_args,
            "review_before_tickets": not args.no_ticket_review,
        }
        print(json.dumps(plan, indent=2))
        return 0

    runner = select_cli_runner(args.runner)
    output_dir.mkdir(parents=True, exist_ok=True)

    progress_lock = Lock()

    def progress_callback(message: str) -> None:
        with progress_lock:
            print(message, flush=True)

    summary = execute_review_ticket_backlog(
        review_run_dir=review_run_dir,
        repo_root=repo_root,
        runner=runner,
        output_dir=output_dir,
        sandbox=args.sandbox,
        ticket_model=args.ticket_model,
        review_model=args.review_model,
        statuses=set(args.statuses or ["open"]),
        ticket_ids=set(args.ticket_ids) if args.ticket_ids else None,
        extra_args=args.extra_args,
        review_extra_args=args.review_extra_args,
        heartbeat_seconds=args.heartbeat_seconds,
        review_before_tickets=not args.no_ticket_review,
        progress_callback=progress_callback,
    )

    print(f"Summary written to {summary['summary_path']}", flush=True)
    print(f"Latest backlog file: {summary['final_tickets_file']}", flush=True)
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
