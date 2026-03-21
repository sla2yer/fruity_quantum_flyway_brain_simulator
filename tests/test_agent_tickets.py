from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.agent_tickets import build_ticket_prompt, filter_tickets, parse_ticket_markdown, select_cli_runner


class AgentTicketParsingTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
