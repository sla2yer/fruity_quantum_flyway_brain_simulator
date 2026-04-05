from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
import os
import subprocess
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.agent_tickets import (
    AgentTicket,
    _progress_label,
    _safe_ticket_name,
    build_ticket_prompt,
    filter_tickets,
    parse_ticket_markdown,
    run_ticket,
    select_cli_runner,
    write_run_summary,
)


class AgentTicketParsingTest(unittest.TestCase):
    class _FakeStdin:
        def __init__(self) -> None:
            self.buffer = ""
            self.closed = False

        def write(self, text: str) -> int:
            self.buffer += text
            return len(text)

        def close(self) -> None:
            self.closed = True

    class _FakeProcess:
        def __init__(self, cmd: list[str]) -> None:
            self.cmd = cmd
            self.stdin = AgentTicketParsingTest._FakeStdin()
            self.stdout = iter(())
            last_message_index = cmd.index("--output-last-message") + 1
            self.last_message_path = Path(cmd[last_message_index])

        def wait(self) -> int:
            return 0

    def test_parse_ticket_markdown_extracts_metadata_and_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            ticket_file = tmp_dir / "tickets.md"
            ticket_file.write_text(
                "\n".join(
                    [
                        "# Tickets",
                        "",
                        "## FW-001 - Fix path handling",
                        "- Status: open",
                        "- Priority: high",
                        "",
                        "### Problem",
                        "Paths break outside the repo root.",
                        "",
                        "### Acceptance Criteria",
                        "- Works from `/tmp`.",
                        "",
                        "## FW-002 - Fail fast on bad overrides",
                        "- Status: in_progress",
                        "",
                        "### Problem",
                        "Bad override paths are ignored.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            tickets = parse_ticket_markdown(ticket_file)

            self.assertEqual([ticket.ticket_id for ticket in tickets], ["FW-001", "FW-002"])
            self.assertEqual(tickets[0].status, "open")
            self.assertEqual(tickets[0].metadata["priority"], "high")
            self.assertIn("Paths break outside the repo root.", tickets[0].sections["problem"])
            self.assertIn("Works from `/tmp`.", tickets[0].sections["acceptance criteria"])

    def test_filter_tickets_can_select_by_status_and_id(self) -> None:
        ticket_file = ROOT / "agent_tickets" / "repo_review_tickets.md"
        tickets = parse_ticket_markdown(ticket_file)

        selected = filter_tickets(
            tickets,
            include_statuses={"open"},
            ticket_ids={"FW-002"},
        )

        self.assertEqual([ticket.ticket_id for ticket in selected], ["FW-002"])

    def test_build_ticket_prompt_includes_core_sections(self) -> None:
        ticket = parse_ticket_markdown(ROOT / "agent_tickets" / "repo_review_tickets.md")[0]

        prompt = build_ticket_prompt(ticket, repo_root=ROOT)

        self.assertIn("Work ticket FW-001", prompt)
        self.assertIn("Problem:", prompt)
        self.assertIn("Acceptance Criteria:", prompt)
        self.assertIn(str(ROOT), prompt)

    def test_select_cli_runner_prefers_codel_env_override_then_codex(self) -> None:
        with mock.patch("shutil.which") as which_mock:
            which_mock.side_effect = lambda name: {
                "/custom/codel-cli": "/custom/codel-cli",
                "codel-cli": None,
                "codex": "/usr/local/bin/codex",
            }.get(name)

            with mock.patch.dict("os.environ", {"CODEL_CLI_BIN": "/custom/codel-cli"}, clear=False):
                self.assertEqual(select_cli_runner(), "/custom/codel-cli")

    def test_progress_label_formats_agent_messages(self) -> None:
        label = _progress_label(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": "Listing the repository root with a shell command so I can report the top-level files precisely.",
                },
            }
        )

        self.assertEqual(
            label,
            "thought: Listing the repository root with a shell command so I can report the top-level files precisely.",
        )

    def test_progress_label_formats_command_state(self) -> None:
        started = _progress_label(
            {
                "type": "item.started",
                "item": {
                    "type": "command_execution",
                    "command": "/bin/bash -lc 'pwd'",
                },
            }
        )
        completed = _progress_label(
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "/bin/bash -lc 'pwd'",
                    "exit_code": 0,
                },
            }
        )

        self.assertIn("working: running command", started)
        self.assertEqual(completed, "working: command finished (ok)")

    def test_safe_ticket_name_truncates_long_titles_with_digest(self) -> None:
        ticket = AgentTicket(
            ticket_id="FW-LONG-001",
            title=" ".join(["extremely_long_title"] * 20),
            metadata={},
            sections={},
        )

        safe_name = _safe_ticket_name(ticket)

        self.assertLessEqual(len(safe_name), 120)
        self.assertTrue(safe_name.startswith("FW-LONG-001_"))
        self.assertRegex(safe_name, r"_[0-9a-f]{12}$")

    def test_run_ticket_restores_artifacts_when_output_dir_is_removed(self) -> None:
        ticket = AgentTicket(
            ticket_id="FW-TEST-001",
            title="Keep runner artifacts stable",
            metadata={"status": "open"},
            sections={"problem": "The child process may delete untracked output directories."},
        )

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            repo_root = tmp_dir / "repo"
            repo_root.mkdir()
            output_dir = repo_root / "agent_tickets" / "runs" / "fixture"
            output_dir.mkdir(parents=True)

            def fake_popen(cmd: list[str], **_: object) -> AgentTicketParsingTest._FakeProcess:
                return AgentTicketParsingTest._FakeProcess(cmd)

            def fake_stream(
                process: AgentTicketParsingTest._FakeProcess,
                *,
                raw_output_path: Path,
                progress_callback: object,
                heartbeat_seconds: float,
                heartbeat_label: str,
            ) -> int:
                del progress_callback, heartbeat_seconds, heartbeat_label
                raw_output_path.write_text('{"type":"turn.started"}\n', encoding="utf-8")
                process.last_message_path.write_text("All set.\n", encoding="utf-8")
                shutil.rmtree(output_dir)
                return 0

            with mock.patch("flywire_wave.agent_tickets.subprocess.Popen", side_effect=fake_popen):
                with mock.patch("flywire_wave.agent_tickets._stream_ticket_process", side_effect=fake_stream):
                    result = run_ticket(
                        ticket,
                        repo_root=repo_root,
                        runner="/tmp/fake-runner",
                        output_dir=output_dir,
                        sandbox="workspace-write",
                    )

            ticket_dir = Path(result["output_dir"])
            self.assertTrue(ticket_dir.exists())
            self.assertEqual((ticket_dir / "prompt.md").read_text(encoding="utf-8").splitlines()[0], "Work ticket FW-TEST-001: Keep runner artifacts stable.")
            self.assertEqual((ticket_dir / "stdout.jsonl").read_text(encoding="utf-8"), '{"type":"turn.started"}\n')
            self.assertEqual((ticket_dir / "stderr.log").read_text(encoding="utf-8"), "")
            self.assertEqual((ticket_dir / "last_message.md").read_text(encoding="utf-8"), "All set.\n")

    def test_run_ticket_launches_runner_in_separate_process_group(self) -> None:
        ticket = AgentTicket(
            ticket_id="FW-TEST-002",
            title="Isolate runner signals",
            metadata={"status": "open"},
            sections={"problem": "Ctrl+C should not interrupt the active child runner immediately."},
        )

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            repo_root = tmp_dir / "repo"
            repo_root.mkdir()
            output_dir = repo_root / "agent_tickets" / "runs" / "fixture"
            output_dir.mkdir(parents=True)
            popen_kwargs: dict[str, object] = {}

            def fake_popen(cmd: list[str], **kwargs: object) -> AgentTicketParsingTest._FakeProcess:
                popen_kwargs.update(kwargs)
                return AgentTicketParsingTest._FakeProcess(cmd)

            with mock.patch("flywire_wave.agent_tickets.subprocess.Popen", side_effect=fake_popen):
                with mock.patch("flywire_wave.agent_tickets._stream_ticket_process", return_value=0):
                    run_ticket(
                        ticket,
                        repo_root=repo_root,
                        runner="/tmp/fake-runner",
                        output_dir=output_dir,
                        sandbox="workspace-write",
                    )

            if os.name == "nt":
                self.assertEqual(
                    popen_kwargs.get("creationflags"),
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                )
            else:
                self.assertTrue(popen_kwargs.get("start_new_session"))

    def test_write_run_summary_recreates_missing_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            output_dir = tmp_dir / "missing" / "summary"

            summary_path = write_run_summary([{"ticket_id": "FW-001", "returncode": 0}], output_dir)

            self.assertTrue(summary_path.exists())
            self.assertIn("FW-001", summary_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
