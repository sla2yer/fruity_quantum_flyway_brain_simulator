from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.review_ticket_backlog import execute_review_ticket_backlog


class ReviewTicketBacklogTest(unittest.TestCase):
    def test_execute_review_ticket_backlog_runs_ticket_then_uses_refreshed_backlog(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            review_run_dir = tmp_dir / "review_run"
            (review_run_dir / "specialization" / "alpha").mkdir(parents=True)
            (review_run_dir / "reviews" / "alpha").mkdir(parents=True)
            (review_run_dir / "specialization" / "alpha" / "specialized_prompt.md").write_text(
                "# Alpha specialized prompt\n",
                encoding="utf-8",
            )
            (review_run_dir / "reviews" / "alpha" / "tickets.md").write_text(
                "# Alpha tickets\n\n## ALPHA-001 - First issue\n- Status: open\n\n### Problem\nOne\n",
                encoding="utf-8",
            )
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
            (review_run_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "specialization_results": [
                            {
                                "prompt_set": "alpha",
                                "title": "Alpha Prompt",
                            }
                        ]
                    }
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

            def fake_refresh_runner(
                prompts,
                *,
                repo_root: str | Path,
                runner: str,
                output_dir: str | Path,
                sandbox: str,
                model: str | None = None,
                extra_args: list[str] | None = None,
                max_workers: int | None = None,
                heartbeat_seconds: float = 20.0,
                progress_callback=None,
            ) -> dict[str, object]:
                del prompts, repo_root, runner, sandbox, model, extra_args, max_workers, heartbeat_seconds, progress_callback
                output_path = Path(output_dir)
                review_dir = output_path / "reviews" / "alpha"
                review_dir.mkdir(parents=True, exist_ok=True)
                tickets_path = review_dir / "tickets.md"
                tickets_path.write_text(
                    "\n".join(
                        [
                            "# Alpha tickets",
                            "",
                            "## ALPHA-002 - Second issue updated",
                            "- Status: open",
                            "",
                            "### Problem",
                            "Two updated",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )
                combined_tickets_path = output_path / "combined_tickets.md"
                combined_tickets_path.write_text(
                    "\n".join(
                        [
                            "# Combined Review Tickets",
                            "",
                            "## ALPHA-002 - Second issue updated",
                            "- Status: open",
                            "",
                            "### Problem",
                            "Two updated",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )
                summary_path = output_path / "summary.json"
                summary_path.write_text("{}", encoding="utf-8")
                return {
                    "success": True,
                    "summary_path": str(summary_path),
                    "combined_tickets_path": str(combined_tickets_path),
                    "review_results": [
                        {
                            "prompt_set": "alpha",
                            "tickets_path": str(tickets_path),
                        }
                    ],
                }

            summary = execute_review_ticket_backlog(
                review_run_dir=review_run_dir,
                repo_root=ROOT,
                runner="/tmp/fake-runner",
                output_dir=tmp_dir / "backlog_run",
                sandbox="workspace-write",
                ticket_runner=fake_ticket_runner,
                refresh_runner=fake_refresh_runner,
            )

            self.assertTrue(summary["success"])
            self.assertEqual(ticket_runs, ["ALPHA-001", "ALPHA-002"])
            self.assertEqual(summary["successful_ticket_count"], 2)
            self.assertEqual(summary["successful_refresh_count"], 2)
            self.assertTrue(Path(summary["summary_path"]).exists())
            self.assertTrue(summary["final_tickets_file"].endswith("combined_tickets.md"))


if __name__ == "__main__":
    unittest.main()
