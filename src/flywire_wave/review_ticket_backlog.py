from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from flywire_wave.agent_tickets import (
    AgentTicket,
    filter_tickets,
    parse_ticket_markdown,
    run_ticket,
)
from flywire_wave.review_prompt_tickets import SUMMARY_FILENAME, run_prompt_job


WORKING_BACKLOG_FILENAME = "working_backlog.md"

TicketRunner = Callable[..., dict[str, Any]]
TicketReviewRunner = Callable[..., dict[str, Any]]


def _section_heading(section_name: str) -> str:
    return " ".join(part.capitalize() for part in section_name.split())


def render_ticket_markdown(ticket: AgentTicket) -> str:
    parts = [f"## {ticket.ticket_id} - {ticket.title}"]
    for key, value in ticket.metadata.items():
        parts.append(f"- {key.title()}: {value}")
    for section_name, body in ticket.sections.items():
        parts.extend(
            [
                "",
                f"### {_section_heading(section_name)}",
                body,
            ]
        )
    return "\n".join(parts).rstrip() + "\n"


def render_ticket_backlog_markdown(tickets: list[AgentTicket]) -> str:
    parts = [
        "# Review Ticket Backlog",
        "",
        "This file is maintained by `scripts/run_review_ticket_backlog.py`.",
        "",
    ]
    for index, ticket in enumerate(tickets):
        parts.append(render_ticket_markdown(ticket).rstrip())
        if index != len(tickets) - 1:
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def write_ticket_backlog(tickets: list[AgentTicket], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_ticket_backlog_markdown(tickets), encoding="utf-8")
    return output_path


def _replace_ticket(tickets: list[AgentTicket], updated_ticket: AgentTicket) -> list[AgentTicket]:
    replaced = False
    updated: list[AgentTicket] = []
    for ticket in tickets:
        if ticket.ticket_id == updated_ticket.ticket_id:
            updated.append(updated_ticket)
            replaced = True
            continue
        updated.append(ticket)
    if not replaced:
        raise RuntimeError(f"Ticket {updated_ticket.ticket_id} was not found in the working backlog.")
    return updated


def _select_next_ticket(
    tickets_file: str | Path,
    *,
    statuses: set[str] | None,
    handled_ticket_ids: set[str],
    ticket_ids: set[str] | None = None,
) -> tuple[AgentTicket | None, list[AgentTicket]]:
    tickets = parse_ticket_markdown(tickets_file)
    selected = filter_tickets(
        tickets,
        include_statuses=statuses,
        ticket_ids=ticket_ids,
    )
    remaining = [ticket for ticket in selected if ticket.ticket_id not in handled_ticket_ids]
    if not remaining:
        return None, selected
    return remaining[0], selected


def build_ticket_review_prompt(ticket: AgentTicket, *, repo_root: str | Path) -> str:
    parts = [
        f"Review work ticket {ticket.ticket_id}: {ticket.title}.",
        f"Repository root: {Path(repo_root).resolve()}",
        "",
        "This is a ticket review pass only. Do not implement code.",
        "Earlier backlog tickets may already have changed the surrounding code.",
        "Check whether this ticket is still accurate for the repository's current state and update it if needed.",
        "",
        "Rules:",
        "- Keep the same ticket ID.",
        "- Return exactly one ticket in the same markdown ticket format.",
        "- Update the title, priority, area, and sections if the ticket needs refinement.",
        "- If the ticket no longer needs implementation, set `- Status: closed` and explain why.",
        "- Do not create new tickets or broaden this ticket into a larger backlog item.",
        "- Return only the updated single-ticket markdown and do not use code fences.",
        "",
        "Existing Ticket:",
        render_ticket_markdown(ticket).rstrip(),
    ]
    return "\n".join(parts).strip() + "\n"


def review_ticket_before_execution(
    ticket: AgentTicket,
    *,
    repo_root: str | Path,
    runner: str,
    output_dir: str | Path,
    sandbox: str,
    model: str | None = None,
    extra_args: list[str] | None = None,
    progress_callback: Callable[[str], None] | None = None,
    heartbeat_seconds: float = 20.0,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    review_output_dir = output_dir / "ticket_reviews" / ticket.ticket_id
    result = run_prompt_job(
        f"ticket_review_{ticket.ticket_id}",
        prompt_text=build_ticket_review_prompt(ticket, repo_root=repo_root),
        repo_root=repo_root,
        runner=runner,
        output_dir=review_output_dir,
        sandbox=sandbox,
        model=model,
        extra_args=extra_args,
        progress_callback=progress_callback,
        heartbeat_seconds=heartbeat_seconds,
    )
    result.update(
        {
            "stage": "ticket_review",
            "ticket_id": ticket.ticket_id,
            "original_title": ticket.title,
        }
    )
    if result["returncode"] != 0:
        return result

    reviewed_ticket_path = review_output_dir / "reviewed_ticket.md"
    reviewed_ticket_path.write_text(
        Path(result["last_message_path"]).read_text(encoding="utf-8").rstrip() + "\n",
        encoding="utf-8",
    )
    reviewed_tickets = parse_ticket_markdown(reviewed_ticket_path)
    if len(reviewed_tickets) != 1:
        raise RuntimeError(
            f"Ticket review for {ticket.ticket_id} must return exactly one ticket, got {len(reviewed_tickets)}."
        )

    reviewed_ticket = reviewed_tickets[0]
    if reviewed_ticket.ticket_id != ticket.ticket_id:
        raise RuntimeError(
            f"Ticket review changed ID from {ticket.ticket_id} to {reviewed_ticket.ticket_id}."
        )

    result["reviewed_ticket"] = reviewed_ticket
    result["reviewed_ticket_path"] = str(reviewed_ticket_path)
    result["reviewed_title"] = reviewed_ticket.title
    result["reviewed_status"] = reviewed_ticket.status
    return result


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
    heartbeat_seconds: float = 20.0,
    review_before_tickets: bool = True,
    progress_callback: Callable[[str], None] | None = None,
    ticket_runner: TicketRunner | None = None,
    ticket_review_runner: TicketReviewRunner | None = None,
) -> dict[str, Any]:
    review_run_dir = Path(review_run_dir).resolve()
    repo_root = Path(repo_root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    initial_tickets_file = review_run_dir / "combined_tickets.md"
    if not initial_tickets_file.exists():
        raise FileNotFoundError(f"Combined tickets file does not exist: {initial_tickets_file}")

    working_backlog_path = output_dir / WORKING_BACKLOG_FILENAME
    working_tickets = parse_ticket_markdown(initial_tickets_file)
    write_ticket_backlog(working_tickets, working_backlog_path)

    ticket_runner = ticket_runner or run_ticket
    ticket_review_runner = ticket_review_runner or review_ticket_before_execution

    handled_ticket_ids: set[str] = set()
    executed_ticket_ids: list[str] = []
    skipped_ticket_ids: list[str] = []
    ticket_results: list[dict[str, Any]] = []
    ticket_review_results: list[dict[str, Any]] = []

    while True:
        ticket, selected_tickets = _select_next_ticket(
            working_backlog_path,
            statuses=statuses,
            handled_ticket_ids=handled_ticket_ids,
            ticket_ids=ticket_ids,
        )
        if ticket is None:
            break

        next_index = len(executed_ticket_ids) + len(skipped_ticket_ids) + 1
        total_visible = len(selected_tickets)
        active_ticket = ticket

        if review_before_tickets and (len(executed_ticket_ids) + len(skipped_ticket_ids)) > 0:
            if progress_callback is not None:
                progress_callback(f"[review:{next_index}] checking {ticket.ticket_id} before execution")

            def review_progress(message: str, *, prefix: str = f"[review:{next_index}] {ticket.ticket_id}") -> None:
                if progress_callback is not None:
                    progress_callback(f"{prefix} {message}")

            review_result = ticket_review_runner(
                ticket,
                repo_root=repo_root,
                runner=runner,
                output_dir=output_dir,
                sandbox=sandbox,
                model=review_model,
                extra_args=review_extra_args,
                progress_callback=review_progress,
                heartbeat_seconds=heartbeat_seconds,
            )
            reviewed_ticket = review_result.pop("reviewed_ticket", None)
            review_result["source_tickets_file"] = str(working_backlog_path)
            ticket_review_results.append(review_result)

            if review_result["returncode"] != 0:
                break
            if not isinstance(reviewed_ticket, AgentTicket):
                raise RuntimeError(f"Ticket review for {ticket.ticket_id} did not return a parsed ticket.")

            working_tickets = _replace_ticket(working_tickets, reviewed_ticket)
            write_ticket_backlog(working_tickets, working_backlog_path)
            active_ticket = reviewed_ticket

            if progress_callback is not None:
                progress_callback(
                    f"[review:{next_index}] finished {ticket.ticket_id}: status {active_ticket.status}"
                )

            if active_ticket.status != "open" or (statuses is not None and active_ticket.status not in statuses):
                skipped_ticket_ids.append(active_ticket.ticket_id)
                handled_ticket_ids.add(active_ticket.ticket_id)
                if progress_callback is not None:
                    progress_callback(
                        f"[review:{next_index}] skipping {active_ticket.ticket_id} because it is now `{active_ticket.status}`"
                    )
                continue

        if progress_callback is not None:
            progress_callback(
                f"[ticket:{next_index}] starting {active_ticket.ticket_id} from {working_backlog_path}"
            )

        def ticket_progress(message: str, *, prefix: str = f"[ticket:{next_index}] {active_ticket.ticket_id}") -> None:
            if progress_callback is not None:
                progress_callback(f"{prefix} {message}")

        result = ticket_runner(
            active_ticket,
            repo_root=repo_root,
            runner=runner,
            output_dir=output_dir / "ticket_runs",
            sandbox=sandbox,
            model=ticket_model,
            extra_args=extra_args,
            progress_callback=ticket_progress,
            heartbeat_seconds=heartbeat_seconds,
        )
        result["source_tickets_file"] = str(working_backlog_path)
        result["selection_size"] = total_visible
        ticket_results.append(result)
        handled_ticket_ids.add(active_ticket.ticket_id)
        executed_ticket_ids.append(active_ticket.ticket_id)

        if progress_callback is not None:
            status_text = "ok" if result["returncode"] == 0 else f"failed ({result['returncode']})"
            progress_callback(f"[ticket:{next_index}] finished {active_ticket.ticket_id}: {status_text}")

        if result["returncode"] != 0:
            break

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
        "review_before_tickets": review_before_tickets,
        "executed_ticket_ids": executed_ticket_ids,
        "skipped_ticket_ids": skipped_ticket_ids,
        "final_tickets_file": str(working_backlog_path),
        "ticket_results": ticket_results,
        "ticket_review_results": ticket_review_results,
    }
    summary["successful_ticket_count"] = sum(
        1 for result in ticket_results if result.get("returncode") == 0
    )
    summary["successful_review_count"] = sum(
        1 for result in ticket_review_results if result.get("returncode") == 0
    )
    summary["success"] = (
        all(result.get("returncode") == 0 for result in ticket_results)
        and all(result.get("returncode") == 0 for result in ticket_review_results)
    )

    summary_path = output_dir / SUMMARY_FILENAME
    summary["summary_path"] = str(summary_path)
    write_backlog_run_summary(summary, output_dir)
    return summary
