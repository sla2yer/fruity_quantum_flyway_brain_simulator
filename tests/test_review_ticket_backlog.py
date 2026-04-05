from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.agent_tickets import AgentTicket
from flywire_wave.review_ticket_backlog import execute_review_ticket_backlog


class ReviewTicketBacklogTest(unittest.TestCase):
    def test_execute_review_ticket_backlog_reviews_each_later_ticket_before_running_it(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            review_run_dir = tmp_dir / "review_run"
            review_run_dir.mkdir(parents=True)
            (review_run_dir / "combined_tickets.md").write_text(
                "\n".join(
                    [
                        "# Combined Review Tickets",
                        "",
                        "## ALPHA-001 - First issue",
                        "- Status: open",
                        "- Priority: medium",
                        "",
                        "### Problem",
                        "One",
                        "",
                        "## ALPHA-002 - Second issue",
                        "- Status: open",
                        "- Priority: medium",
                        "",
                        "### Problem",
                        "Two",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            ticket_runs: list[tuple[str, str]] = []
            review_runs: list[str] = []

            def fake_ticket_runner(ticket, **_: object) -> dict[str, object]:
                ticket_runs.append((ticket.ticket_id, ticket.title))
                ticket_output_dir = tmp_dir / "ticket_runs" / ticket.ticket_id
                ticket_output_dir.mkdir(parents=True, exist_ok=True)
                return {
                    "ticket_id": ticket.ticket_id,
                    "title": ticket.title,
                    "status": ticket.status,
                    "command": ["fake-runner", "exec"],
                    "returncode": 0,
                    "output_dir": str(ticket_output_dir),
                    "prompt_path": str(ticket_output_dir / "prompt.md"),
                    "stdout_path": str(ticket_output_dir / "stdout.jsonl"),
                    "stderr_path": str(ticket_output_dir / "stderr.log"),
                    "last_message_path": str(ticket_output_dir / "last_message.md"),
                }

            def fake_ticket_review_runner(ticket, **_: object) -> dict[str, object]:
                review_runs.append(ticket.ticket_id)
                review_output_dir = tmp_dir / "ticket_reviews" / ticket.ticket_id
                review_output_dir.mkdir(parents=True, exist_ok=True)
                reviewed_ticket = AgentTicket(
                    ticket_id=ticket.ticket_id,
                    title="Second issue updated",
                    metadata={"status": "open", "priority": "high"},
                    sections={"problem": "Two updated"},
                )
                return {
                    "stage": "ticket_review",
                    "ticket_id": ticket.ticket_id,
                    "command": ["fake-runner", "exec"],
                    "returncode": 0,
                    "output_dir": str(review_output_dir),
                    "prompt_path": str(review_output_dir / "prompt.md"),
                    "stdout_path": str(review_output_dir / "stdout.jsonl"),
                    "stderr_path": str(review_output_dir / "stderr.log"),
                    "last_message_path": str(review_output_dir / "last_message.md"),
                    "reviewed_ticket_path": str(review_output_dir / "reviewed_ticket.md"),
                    "reviewed_title": reviewed_ticket.title,
                    "reviewed_status": reviewed_ticket.status,
                    "reviewed_ticket": reviewed_ticket,
                }

            summary = execute_review_ticket_backlog(
                review_run_dir=review_run_dir,
                repo_root=ROOT,
                runner="/tmp/fake-runner",
                output_dir=tmp_dir / "backlog_run",
                sandbox="workspace-write",
                ticket_runner=fake_ticket_runner,
                ticket_review_runner=fake_ticket_review_runner,
            )

            self.assertTrue(summary["success"])
            self.assertEqual(ticket_runs, [("ALPHA-001", "First issue"), ("ALPHA-002", "Second issue updated")])
            self.assertEqual(review_runs, ["ALPHA-002"])
            self.assertEqual(summary["successful_ticket_count"], 2)
            self.assertEqual(summary["successful_review_count"], 1)
            working_backlog_text = Path(summary["final_tickets_file"]).read_text(encoding="utf-8")
            self.assertIn("## ALPHA-002 - Second issue updated", working_backlog_text)

    def test_execute_review_ticket_backlog_skips_ticket_when_review_closes_it(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            review_run_dir = tmp_dir / "review_run"
            review_run_dir.mkdir(parents=True)
            (review_run_dir / "combined_tickets.md").write_text(
                "\n".join(
                    [
                        "# Combined Review Tickets",
                        "",
                        "## ALPHA-001 - First issue",
                        "- Status: open",
                        "",
                        "### Problem",
                        "One",
                        "",
                        "## ALPHA-002 - Second issue",
                        "- Status: open",
                        "",
                        "### Problem",
                        "Two",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            ticket_runs: list[str] = []

            def fake_ticket_runner(ticket, **_: object) -> dict[str, object]:
                ticket_runs.append(ticket.ticket_id)
                ticket_output_dir = tmp_dir / "ticket_runs" / ticket.ticket_id
                ticket_output_dir.mkdir(parents=True, exist_ok=True)
                return {
                    "ticket_id": ticket.ticket_id,
                    "title": ticket.title,
                    "status": ticket.status,
                    "command": ["fake-runner", "exec"],
                    "returncode": 0,
                    "output_dir": str(ticket_output_dir),
                    "prompt_path": str(ticket_output_dir / "prompt.md"),
                    "stdout_path": str(ticket_output_dir / "stdout.jsonl"),
                    "stderr_path": str(ticket_output_dir / "stderr.log"),
                    "last_message_path": str(ticket_output_dir / "last_message.md"),
                }

            def fake_ticket_review_runner(ticket, **_: object) -> dict[str, object]:
                review_output_dir = tmp_dir / "ticket_reviews" / ticket.ticket_id
                review_output_dir.mkdir(parents=True, exist_ok=True)
                reviewed_ticket = AgentTicket(
                    ticket_id=ticket.ticket_id,
                    title=ticket.title,
                    metadata={"status": "closed"},
                    sections={"problem": "Already handled by previous work."},
                )
                return {
                    "stage": "ticket_review",
                    "ticket_id": ticket.ticket_id,
                    "command": ["fake-runner", "exec"],
                    "returncode": 0,
                    "output_dir": str(review_output_dir),
                    "prompt_path": str(review_output_dir / "prompt.md"),
                    "stdout_path": str(review_output_dir / "stdout.jsonl"),
                    "stderr_path": str(review_output_dir / "stderr.log"),
                    "last_message_path": str(review_output_dir / "last_message.md"),
                    "reviewed_ticket_path": str(review_output_dir / "reviewed_ticket.md"),
                    "reviewed_title": reviewed_ticket.title,
                    "reviewed_status": reviewed_ticket.status,
                    "reviewed_ticket": reviewed_ticket,
                }

            summary = execute_review_ticket_backlog(
                review_run_dir=review_run_dir,
                repo_root=ROOT,
                runner="/tmp/fake-runner",
                output_dir=tmp_dir / "backlog_run",
                sandbox="workspace-write",
                ticket_runner=fake_ticket_runner,
                ticket_review_runner=fake_ticket_review_runner,
            )

            self.assertTrue(summary["success"])
            self.assertEqual(ticket_runs, ["ALPHA-001"])
            self.assertEqual(summary["skipped_ticket_ids"], ["ALPHA-002"])
            self.assertEqual(summary["successful_review_count"], 1)


if __name__ == "__main__":
    unittest.main()
