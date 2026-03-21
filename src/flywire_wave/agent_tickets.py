from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


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


def _compact_text(text: str, *, max_len: int = 240) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 3].rstrip() + "..."


def _progress_label(event: dict[str, Any]) -> str | None:
    event_type = event.get("type")
    if event_type == "turn.started":
        return "thinking"
    if event_type != "item.completed" and event_type != "item.started":
        return None

    item = event.get("item", {})
    item_type = item.get("type")

    if item_type == "agent_message" and event_type == "item.completed":
        text = str(item.get("text", "")).strip()
        if not text:
            return None
        return f"thought: {_compact_text(text)}"

    if item_type == "command_execution":
        command = _compact_text(str(item.get("command", "")).strip(), max_len=160)
        if event_type == "item.started":
            return f"working: running command {command}"
        exit_code = item.get("exit_code")
        status = "ok" if exit_code == 0 else f"exit {exit_code}"
        return f"working: command finished ({status})"

    return None


def _stream_ticket_process(
    process: subprocess.Popen[str],
    *,
    raw_output_path: Path,
    progress_callback: Callable[[str], None] | None,
    heartbeat_seconds: float,
    heartbeat_label: str,
) -> int:
    assert process.stdout is not None

    last_progress_at = time.monotonic()
    with raw_output_path.open("w", encoding="utf-8") as raw_output:
        while True:
            line = process.stdout.readline()
            if line:
                raw_output.write(line)
                raw_output.flush()

                stripped = line.strip()
                progress_line: str | None = None
                if stripped.startswith("{") and stripped.endswith("}"):
                    try:
                        event = json.loads(stripped)
                    except json.JSONDecodeError:
                        event = None
                    if isinstance(event, dict):
                        progress_line = _progress_label(event)
                elif " WARN " in stripped:
                    progress_line = None
                elif stripped:
                    progress_line = f"runner: {_compact_text(stripped)}"

                if progress_line and progress_callback is not None:
                    progress_callback(progress_line)
                    last_progress_at = time.monotonic()
                continue

            return_code = process.poll()
            if return_code is not None:
                break

            if progress_callback is not None and (time.monotonic() - last_progress_at) >= heartbeat_seconds:
                progress_callback(f"still working: {heartbeat_label}")
                last_progress_at = time.monotonic()
            time.sleep(0.5)

        # Drain any remaining buffered lines after process exit.
        for line in process.stdout:
            raw_output.write(line)
            raw_output.flush()
            stripped = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    event = json.loads(stripped)
                except json.JSONDecodeError:
                    event = None
                progress_line = _progress_label(event) if isinstance(event, dict) else None
                if progress_line and progress_callback is not None:
                    progress_callback(progress_line)

    return int(process.wait())


def run_ticket(
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
    repo_root = Path(repo_root)
    output_dir = Path(output_dir)
    ticket_dir = output_dir / _safe_ticket_name(ticket)
    ticket_dir.mkdir(parents=True, exist_ok=True)

    prompt = build_ticket_prompt(ticket, repo_root=repo_root)
    prompt_path = ticket_dir / "prompt.md"
    stdout_path = ticket_dir / "stdout.jsonl"
    stderr_path = ticket_dir / "stderr.log"
    last_message_path = ticket_dir / "last_message.md"

    prompt_path.write_text(prompt, encoding="utf-8")

    cmd = [
        runner,
        "exec",
        "--json",
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

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert process.stdin is not None
    process.stdin.write(prompt)
    process.stdin.close()

    return_code = _stream_ticket_process(
        process,
        raw_output_path=stdout_path,
        progress_callback=progress_callback,
        heartbeat_seconds=heartbeat_seconds,
        heartbeat_label=f"{ticket.ticket_id} ({ticket.title})",
    )

    # stderr is merged into stdout for streaming simplicity; keep a placeholder file
    # so callers still have a stable artifact path.
    if not stderr_path.exists():
        stderr_path.write_text("", encoding="utf-8")

    return {
        "ticket_id": ticket.ticket_id,
        "title": ticket.title,
        "status": ticket.status,
        "command": cmd,
        "returncode": int(return_code),
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
