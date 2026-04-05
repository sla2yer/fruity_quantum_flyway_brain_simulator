from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from flywire_wave.agent_tickets import (
    filter_tickets,
    parse_ticket_markdown,
    run_ticket,
)
from flywire_wave.review_prompt_tickets import (
    SUMMARY_FILENAME,
    SpecializedReviewPrompt,
    execute_specialized_review_refresh,
    load_specialized_review_prompts,
)


TicketRunner = Callable[..., dict[str, Any]]
RefreshRunner = Callable[..., dict[str, Any]]


def _select_next_ticket(
    tickets_file: str | Path,
    *,
    statuses: set[str] | None,
    executed_ticket_ids: set[str],
    ticket_ids: set[str] | None = None,
) -> tuple[Any | None, list[Any]]:
    tickets = parse_ticket_markdown(tickets_file)
    selected = filter_tickets(
        tickets,
        include_statuses=statuses,
        ticket_ids=ticket_ids,
    )
    remaining = [ticket for ticket in selected if ticket.ticket_id not in executed_ticket_ids]
    if not remaining:
        return None, selected
    return remaining[0], selected


def _advance_specialized_prompts(
    prompts: Sequence[SpecializedReviewPrompt],
    refresh_summary: dict[str, Any],
) -> list[SpecializedReviewPrompt]:
    tickets_by_slug: dict[str, Path] = {}
    for result in refresh_summary.get("review_results", []):
        slug = str(result.get("prompt_set", "")).strip()
        tickets_path_text = str(result.get("tickets_path", "")).strip()
        if slug and tickets_path_text:
            tickets_by_slug[slug] = Path(tickets_path_text)

    advanced: list[SpecializedReviewPrompt] = []
    for prompt in prompts:
        advanced.append(
            SpecializedReviewPrompt(
                slug=prompt.slug,
                title=prompt.title,
                specialized_prompt_path=prompt.specialized_prompt_path,
                previous_tickets_path=tickets_by_slug.get(prompt.slug, prompt.previous_tickets_path),
            )
        )
    return advanced


def write_backlog_run_summary(summary: dict[str, Any], output_dir: str | Path) -> Path:
    output_path = Path(output_dir) / SUMMARY_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return output_path


def execute_review_ticket_backlog(
    *,
    review_run_dir: str | Path,
    repo_root: str | Path,
    runner: str,
    output_dir: str | Path,
    sandbox: str,
    ticket_model: str | None = None,
    review_model: str | None = None,
    statuses: set[str] | None = None,
    ticket_ids: set[str] | None = None,
    extra_args: list[str] | None = None,
    review_extra_args: list[str] | None = None,
    max_review_workers: int | None = None,
    heartbeat_seconds: float = 20.0,
    refresh_between_tickets: bool = True,
    progress_callback: Callable[[str], None] | None = None,
    ticket_runner: TicketRunner | None = None,
    refresh_runner: RefreshRunner | None = None,
) -> dict[str, Any]:
    review_run_dir = Path(review_run_dir).resolve()
    repo_root = Path(repo_root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    current_tickets_file = review_run_dir / "combined_tickets.md"
    if not current_tickets_file.exists():
        raise FileNotFoundError(f"Combined tickets file does not exist: {current_tickets_file}")

    specialized_prompts = load_specialized_review_prompts(review_run_dir)
    if not specialized_prompts:
        raise RuntimeError(f"No specialized prompts were found under {review_run_dir}.")

    ticket_runner = ticket_runner or run_ticket
    refresh_runner = refresh_runner or execute_specialized_review_refresh

    executed_ticket_ids: set[str] = set()
    ticket_results: list[dict[str, Any]] = []
    refresh_results: list[dict[str, Any]] = []
    latest_tickets_file = current_tickets_file

    while True:
        ticket, selected_tickets = _select_next_ticket(
            latest_tickets_file,
            statuses=statuses,
            executed_ticket_ids=executed_ticket_ids,
            ticket_ids=ticket_ids,
        )
        if ticket is None:
            break

        next_index = len(ticket_results) + 1
        total_visible = len(selected_tickets)
        if progress_callback is not None:
            progress_callback(
                f"[ticket:{next_index}] starting {ticket.ticket_id} from {latest_tickets_file}"
            )

        def ticket_progress(message: str, *, prefix: str = f"[ticket:{next_index}] {ticket.ticket_id}") -> None:
            if progress_callback is not None:
                progress_callback(f"{prefix} {message}")

        result = ticket_runner(
            ticket,
            repo_root=repo_root,
            runner=runner,
            output_dir=output_dir / "ticket_runs",
            sandbox=sandbox,
            model=ticket_model,
            extra_args=extra_args,
            progress_callback=ticket_progress,
            heartbeat_seconds=heartbeat_seconds,
        )
        result["source_tickets_file"] = str(latest_tickets_file)
        result["selection_size"] = total_visible
        ticket_results.append(result)
        executed_ticket_ids.add(ticket.ticket_id)

        if progress_callback is not None:
            status_text = "ok" if result["returncode"] == 0 else f"failed ({result['returncode']})"
            progress_callback(f"[ticket:{next_index}] finished {ticket.ticket_id}: {status_text}")

        if result["returncode"] != 0:
            break
        if not refresh_between_tickets:
            continue

        refresh_index = len(refresh_results) + 1
        refresh_output_dir = output_dir / "refreshes" / f"{refresh_index:03d}_{ticket.ticket_id}"
        if progress_callback is not None:
            progress_callback(f"[refresh:{refresh_index}] rebuilding backlog after {ticket.ticket_id}")

        refresh_summary = refresh_runner(
            specialized_prompts,
            repo_root=repo_root,
            runner=runner,
            output_dir=refresh_output_dir,
            sandbox=sandbox,
            model=review_model,
            extra_args=review_extra_args,
            max_workers=max_review_workers,
            heartbeat_seconds=heartbeat_seconds,
            progress_callback=progress_callback,
        )
        refresh_summary["trigger_ticket_id"] = ticket.ticket_id
        refresh_results.append(refresh_summary)

        if not refresh_summary.get("success", False):
            break
        combined_tickets_path = refresh_summary.get("combined_tickets_path")
        if not combined_tickets_path:
            break

        latest_tickets_file = Path(combined_tickets_path)
        specialized_prompts = _advance_specialized_prompts(specialized_prompts, refresh_summary)

    summary: dict[str, Any] = {
        "review_run_dir": str(review_run_dir),
        "repo_root": str(repo_root),
        "output_dir": str(output_dir),
        "runner": runner,
        "sandbox": sandbox,
        "ticket_model": ticket_model,
        "review_model": review_model,
        "extra_args": list(extra_args or []),
        "review_extra_args": list(review_extra_args or []),
        "max_review_workers": max_review_workers,
        "refresh_between_tickets": refresh_between_tickets,
        "executed_ticket_ids": [result["ticket_id"] for result in ticket_results],
        "final_tickets_file": str(latest_tickets_file),
        "ticket_results": ticket_results,
        "refresh_results": refresh_results,
    }
    summary["successful_ticket_count"] = sum(
        1 for result in ticket_results if result.get("returncode") == 0
    )
    summary["successful_refresh_count"] = sum(
        1 for result in refresh_results if result.get("success")
    )
    summary["success"] = (
        all(result.get("returncode") == 0 for result in ticket_results)
        and all(result.get("success") for result in refresh_results)
    )

    summary_path = output_dir / SUMMARY_FILENAME
    summary["summary_path"] = str(summary_path)
    write_backlog_run_summary(summary, output_dir)
    return summary
