#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from types import FrameType
from typing import Any

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


def _resolve_repo_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


class _GracefulShutdownState:
    def __init__(self) -> None:
        self.stop_requested = False
        self.signal_name: str | None = None
        self.active_ticket_id: str | None = None


def _signal_name(signum: int) -> str:
    try:
        return signal.Signals(signum).name
    except ValueError:
        return f"signal {signum}"


def _install_signal_handlers(shutdown_state: _GracefulShutdownState) -> dict[int, Any]:
    handled_signals = [signal.SIGINT]
    sigterm = getattr(signal, "SIGTERM", None)
    if sigterm is not None:
        handled_signals.append(sigterm)

    def _handle_signal(signum: int, _frame: FrameType | None) -> None:
        signal_name = _signal_name(signum)
        if shutdown_state.stop_requested:
            if shutdown_state.active_ticket_id:
                print(
                    f"\nReceived {signal_name} again; still waiting for {shutdown_state.active_ticket_id} to finish before stopping.",
                    flush=True,
                )
            else:
                print(f"\nReceived {signal_name} again; shutdown is already pending.", flush=True)
            return

        shutdown_state.stop_requested = True
        shutdown_state.signal_name = signal_name
        if shutdown_state.active_ticket_id:
            print(
                f"\nReceived {signal_name}; will stop after the current ticket ({shutdown_state.active_ticket_id}) finishes.",
                flush=True,
            )
            return
        print(f"\nReceived {signal_name}; stopping before the next ticket starts.", flush=True)

    previous_handlers = {signum: signal.getsignal(signum) for signum in handled_signals}
    for signum in handled_signals:
        signal.signal(signum, _handle_signal)
    return previous_handlers


def _restore_signal_handlers(previous_handlers: dict[int, Any]) -> None:
    for signum, handler in previous_handlers.items():
        signal.signal(signum, handler)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
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
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    tickets = parse_ticket_markdown(_resolve_repo_path(args.tickets_file))
    selected = filter_tickets(
        tickets,
        include_statuses=set(args.statuses or ["open"]),
        ticket_ids=set(args.ticket_ids) if args.ticket_ids else None,
    )
    if not selected:
        raise RuntimeError("No tickets matched the requested filters.")

    runner = select_cli_runner(args.runner)
    repo_root = _resolve_repo_path(args.repo_root)
    output_dir = _resolve_repo_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        plan = {
            "runner": runner,
            "repo_root": str(repo_root),
            "tickets_file": str(_resolve_repo_path(args.tickets_file)),
            "output_dir": str(output_dir),
            "ticket_ids": [ticket.ticket_id for ticket in selected],
            "sandbox": args.sandbox,
            "model": args.model,
            "extra_args": args.extra_args,
        }
        print(json.dumps(plan, indent=2))
        return 0

    shutdown_state = _GracefulShutdownState()
    previous_handlers = _install_signal_handlers(shutdown_state)
    results = []
    total = len(selected)

    try:
        print("Press Ctrl+C once to stop after the current ticket finishes.", flush=True)
        for index, ticket in enumerate(selected, start=1):
            if shutdown_state.stop_requested:
                print(
                    f"Graceful shutdown requested; skipping remaining tickets before {ticket.ticket_id}.",
                    flush=True,
                )
                break

            print(f"[{index}/{total}] Starting {ticket.ticket_id} - {ticket.title}")
            started_at = time.monotonic()
            shutdown_state.active_ticket_id = ticket.ticket_id

            def progress_callback(message: str, *, prefix: str = f"[{index}/{total}] {ticket.ticket_id}") -> None:
                print(f"{prefix} {message}", flush=True)

            try:
                result = run_ticket(
                    ticket,
                    repo_root=repo_root,
                    runner=runner,
                    output_dir=output_dir,
                    sandbox=args.sandbox,
                    model=args.model,
                    extra_args=args.extra_args,
                    progress_callback=progress_callback,
                    heartbeat_seconds=args.heartbeat_seconds,
                )
            finally:
                shutdown_state.active_ticket_id = None

            results.append(result)
            elapsed_seconds = time.monotonic() - started_at
            status_text = "ok" if result["returncode"] == 0 else f"failed ({result['returncode']})"
            print(
                f"[{index}/{total}] Finished {ticket.ticket_id} in {elapsed_seconds:.1f}s: {status_text}",
                flush=True,
            )
            if shutdown_state.stop_requested:
                print(
                    f"Graceful shutdown requested; stopping after {ticket.ticket_id}.",
                    flush=True,
                )
                break
            if result["returncode"] != 0 and not args.continue_on_error:
                break
    finally:
        _restore_signal_handlers(previous_handlers)

    summary_path = write_run_summary(results, output_dir)
    completed_all_selected = len(results) == total
    failed_ticket_ids = [item["ticket_id"] for item in results if item["returncode"] != 0]
    remaining_ticket_ids = [ticket.ticket_id for ticket in selected[len(results) :]]
    print(
        json.dumps(
            {
                "runner": runner,
                "output_dir": str(output_dir),
                "summary_path": str(summary_path),
                "ran_ticket_ids": [item["ticket_id"] for item in results],
                "failed_ticket_ids": failed_ticket_ids,
                "remaining_ticket_ids": remaining_ticket_ids,
                "graceful_stop_requested": shutdown_state.stop_requested,
                "completed_all_selected": completed_all_selected,
            },
            indent=2,
        )
    )

    if shutdown_state.stop_requested and not completed_all_selected:
        return 130
    return 1 if failed_ticket_ids else 0


if __name__ == "__main__":
    raise SystemExit(main())
