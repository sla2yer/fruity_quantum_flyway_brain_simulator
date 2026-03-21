from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TICKET_HEADING_RE = re.compile(r"^##\s+([A-Za-z0-9._-]+)\s+-\s+(.+?)\s*$")
SECTION_HEADING_RE = re.compile(r"^###\s+(.+?)\s*$")
STATUS_DEFAULT = "open"


@dataclass(frozen=True)
class AgentTicket:
    ticket_id: str
    title: str
    metadata: dict[str, str]
    sections: dict[str, str]

    @property
    def status(self) -> str:
        return self.metadata.get("status", STATUS_DEFAULT).strip().lower()


def parse_ticket_markdown(path: str | Path) -> list[AgentTicket]:
    file_path = Path(path)
    lines = file_path.read_text(encoding="utf-8").splitlines()

    tickets: list[AgentTicket] = []
    ticket_id: str | None = None
    title: str | None = None
    metadata: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    in_metadata = False

    def flush_ticket() -> None:
        nonlocal ticket_id, title, metadata, sections, current_section, in_metadata
        if ticket_id is None or title is None:
            return
        normalized_sections = {
            name: "\n".join(content).strip()
            for name, content in sections.items()
            if "\n".join(content).strip()
        }
        tickets.append(
            AgentTicket(
                ticket_id=ticket_id,
                title=title,
                metadata={key.lower(): value.strip() for key, value in metadata.items()},
                sections=normalized_sections,
            )
        )
        ticket_id = None
        title = None
        metadata = {}
        sections = {}
        current_section = None
        in_metadata = False

    for raw_line in lines:
        heading_match = TICKET_HEADING_RE.match(raw_line)
        if heading_match:
            flush_ticket()
            ticket_id = heading_match.group(1).strip()
            title = heading_match.group(2).strip()
            metadata = {}
            sections = {}
            current_section = None
            in_metadata = True
            continue

        if ticket_id is None:
            continue

        section_match = SECTION_HEADING_RE.match(raw_line)
        if section_match:
            current_section = section_match.group(1).strip().lower()
            sections.setdefault(current_section, [])
            in_metadata = False
            continue

        if in_metadata and raw_line.startswith("- ") and ":" in raw_line:
            key, value = raw_line[2:].split(":", 1)
            metadata[key.strip()] = value.strip()
            continue

        if current_section is None:
            continue
        sections.setdefault(current_section, []).append(raw_line)

    flush_ticket()
    return tickets


def filter_tickets(
    tickets: list[AgentTicket],
    *,
    include_statuses: set[str] | None = None,
    ticket_ids: set[str] | None = None,
) -> list[AgentTicket]:
    selected = tickets
    if include_statuses is not None:
        normalized_statuses = {status.strip().lower() for status in include_statuses}
        selected = [ticket for ticket in selected if ticket.status in normalized_statuses]
    if ticket_ids is not None:
        normalized_ids = {ticket_id.strip() for ticket_id in ticket_ids}
        selected = [ticket for ticket in selected if ticket.ticket_id in normalized_ids]
    return selected


def select_cli_runner(preferred_runner: str | None = None) -> str:
    candidates = []
    if preferred_runner:
        candidates.append(preferred_runner)
    env_runner = os.getenv("CODEL_CLI_BIN", "").strip()
    if env_runner:
        candidates.append(env_runner)
    candidates.extend(["codel-cli", "codex"])

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    raise FileNotFoundError(
        "Could not find a ticket runner. Install `codel-cli` or `codex`, "
        "or set CODEL_CLI_BIN to the executable path."
    )


def build_ticket_prompt(ticket: AgentTicket, *, repo_root: str | Path) -> str:
    sections = ticket.sections
    priority = ticket.metadata.get("priority", "unspecified")
    source = ticket.metadata.get("source", "unspecified")

    prompt_parts = [
        f"Work ticket {ticket.ticket_id}: {ticket.title}.",
        f"Repository root: {Path(repo_root)}",
        f"Priority: {priority}",
        f"Source: {source}",
        "",
        "Please implement the ticket end-to-end in this repository.",
        "Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.",
    ]

    for section_name in ["problem", "requested change", "acceptance criteria", "verification", "notes"]:
        body = sections.get(section_name)
        if not body:
            continue
        prompt_parts.extend(
            [
                "",
                f"{section_name.title()}:",
                body,
            ]
        )

    return "\n".join(prompt_parts).strip() + "\n"


def _safe_ticket_name(ticket: AgentTicket) -> str:
    raw = f"{ticket.ticket_id}_{ticket.title}"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_") or ticket.ticket_id


def run_ticket(
    ticket: AgentTicket,
    *,
    repo_root: str | Path,
    runner: str,
    output_dir: str | Path,
    sandbox: str,
    model: str | None = None,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    output_dir = Path(output_dir)
    ticket_dir = output_dir / _safe_ticket_name(ticket)
    ticket_dir.mkdir(parents=True, exist_ok=True)

    prompt = build_ticket_prompt(ticket, repo_root=repo_root)
    prompt_path = ticket_dir / "prompt.md"
    stdout_path = ticket_dir / "stdout.log"
    stderr_path = ticket_dir / "stderr.log"
    last_message_path = ticket_dir / "last_message.md"

    prompt_path.write_text(prompt, encoding="utf-8")

    cmd = [
        runner,
        "exec",
        "--cd",
        str(repo_root),
        "--sandbox",
        sandbox,
        "--output-last-message",
        str(last_message_path),
    ]
    if model:
        cmd.extend(["--model", model])
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )

    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")

    return {
        "ticket_id": ticket.ticket_id,
        "title": ticket.title,
        "status": ticket.status,
        "command": cmd,
        "returncode": int(result.returncode),
        "output_dir": str(ticket_dir),
        "prompt_path": str(prompt_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "last_message_path": str(last_message_path),
    }


def write_run_summary(results: list[dict[str, Any]], output_dir: str | Path) -> Path:
    output_path = Path(output_dir) / "summary.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return output_path
