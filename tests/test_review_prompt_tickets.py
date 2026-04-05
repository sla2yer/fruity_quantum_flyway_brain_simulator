from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.review_prompt_tickets import (
    COMBINED_TICKETS_FILENAME,
    SpecializedReviewPrompt,
    ReviewPromptSet,
    SUMMARY_FILENAME,
    build_specialization_prompt,
    build_review_refresh_prompt,
    execute_review_prompt_workflow,
    execute_specialized_review_refresh,
    filter_review_prompt_sets,
    load_review_prompt_sets,
    load_specialized_review_prompts,
)


class ReviewPromptTicketsTest(unittest.TestCase):
    def test_load_review_prompt_sets_discovers_prompt_pairs_and_titles(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            prompt_root = Path(tmp_dir_str)
            prompt_dir = prompt_root / "focused_review"
            prompt_dir.mkdir()
            (prompt_dir / "generic_prompt.md").write_text(
                "# Focused Review Prompt\n\nReview text.\n",
                encoding="utf-8",
            )
            (prompt_dir / "specializer_prompt.md").write_text(
                "# Focused Review Specializer\n\nSpecializer text.\n",
                encoding="utf-8",
            )

            prompt_sets = load_review_prompt_sets(prompt_root)

            self.assertEqual(len(prompt_sets), 1)
            self.assertEqual(prompt_sets[0].slug, "focused_review")
            self.assertEqual(prompt_sets[0].title, "Focused Review Prompt")

    def test_filter_review_prompt_sets_rejects_unknown_slug(self) -> None:
        prompt_sets = [
            ReviewPromptSet(
                slug="alpha",
                title="Alpha",
                directory=ROOT,
                generic_prompt_path=ROOT / "generic_prompt.md",
                specializer_prompt_path=ROOT / "specializer_prompt.md",
            )
        ]

        with self.assertRaisesRegex(RuntimeError, "Unknown prompt set"):
            filter_review_prompt_sets(prompt_sets, include_slugs={"missing"})

    def test_build_specialization_prompt_embeds_repo_context_and_generic_prompt(self) -> None:
        prompt_set = ReviewPromptSet(
            slug="alpha",
            title="Alpha Prompt",
            directory=ROOT,
            generic_prompt_path=ROOT / "agent_tickets" / "review_prompt_sets" / "efficiency_and_modularity" / "generic_prompt.md",
            specializer_prompt_path=ROOT / "agent_tickets" / "review_prompt_sets" / "efficiency_and_modularity" / "specializer_prompt.md",
        )

        prompt = build_specialization_prompt(prompt_set, repo_root=ROOT)

        self.assertIn("Prompt set slug: alpha", prompt)
        self.assertIn("Repository root:", prompt)
        self.assertIn("Efficiency And Modularity Review Prompt", prompt)

    def test_load_specialized_review_prompts_discovers_saved_specializations(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            review_run_dir = Path(tmp_dir_str)
            specialization_dir = review_run_dir / "specialization" / "alpha"
            review_dir = review_run_dir / "reviews" / "alpha"
            specialization_dir.mkdir(parents=True)
            review_dir.mkdir(parents=True)
            (specialization_dir / "specialized_prompt.md").write_text(
                "# Alpha specialized prompt\n",
                encoding="utf-8",
            )
            (review_dir / "tickets.md").write_text(
                "# Alpha tickets\n",
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

            prompts = load_specialized_review_prompts(review_run_dir)

            self.assertEqual(len(prompts), 1)
            self.assertEqual(prompts[0].slug, "alpha")
            self.assertEqual(prompts[0].title, "Alpha Prompt")
            self.assertEqual(prompts[0].previous_tickets_path, review_dir / "tickets.md")

    def test_build_review_refresh_prompt_includes_previous_ticket_pack(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            specialized_prompt_path = tmp_dir / "specialized_prompt.md"
            previous_tickets_path = tmp_dir / "tickets.md"
            specialized_prompt_path.write_text("# Specialized prompt\n\nReview it.\n", encoding="utf-8")
            previous_tickets_path.write_text("## APICPL-001 - Existing issue\n", encoding="utf-8")
            prompt = SpecializedReviewPrompt(
                slug="alpha",
                title="Alpha Prompt",
                specialized_prompt_path=specialized_prompt_path,
                previous_tickets_path=previous_tickets_path,
            )

            refresh_prompt = build_review_refresh_prompt(prompt, repo_root=ROOT)

            self.assertIn("If a previously reported issue is still valid, keep its existing ticket ID", refresh_prompt)
            self.assertIn("## Previous Ticket Pack", refresh_prompt)
            self.assertIn("APICPL-001", refresh_prompt)

    def test_execute_review_prompt_workflow_writes_specialized_prompts_tickets_and_summary(self) -> None:
        prompt_sets = [
            ReviewPromptSet(
                slug="alpha",
                title="Alpha Prompt",
                directory=ROOT,
                generic_prompt_path=ROOT / "agent_tickets" / "review_prompt_sets" / "efficiency_and_modularity" / "generic_prompt.md",
                specializer_prompt_path=ROOT / "agent_tickets" / "review_prompt_sets" / "efficiency_and_modularity" / "specializer_prompt.md",
            ),
            ReviewPromptSet(
                slug="beta",
                title="Beta Prompt",
                directory=ROOT,
                generic_prompt_path=ROOT / "agent_tickets" / "review_prompt_sets" / "file_length_and_cohesion" / "generic_prompt.md",
                specializer_prompt_path=ROOT / "agent_tickets" / "review_prompt_sets" / "file_length_and_cohesion" / "specializer_prompt.md",
            ),
        ]
        job_calls: list[tuple[str, str | None, Path]] = []

        def fake_job_runner(
            job_name: str,
            *,
            prompt_text: str,
            repo_root: str | Path,
            runner: str,
            output_dir: str | Path,
            sandbox: str,
            model: str | None = None,
            extra_args: list[str] | None = None,
            progress_callback=None,
            heartbeat_seconds: float = 20.0,
        ) -> dict[str, object]:
            del repo_root, runner, sandbox, extra_args, progress_callback, heartbeat_seconds
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            (output_path / "prompt.md").write_text(prompt_text, encoding="utf-8")
            (output_path / "stdout.jsonl").write_text("", encoding="utf-8")
            (output_path / "stderr.log").write_text("", encoding="utf-8")

            stage, slug = job_name.split("_", 1)
            if stage == "specialization":
                last_message = f"# {slug} specialized prompt\n\nUse repo-specific review instructions.\n"
            else:
                last_message = (
                    f"# {slug} tickets\n\n"
                    f"## {slug.upper()}-001 - Review finding\n"
                    "- Status: open\n"
                    "- Priority: medium\n"
                    f"- Source: {slug} review\n"
                    "- Area: tests\n\n"
                    "### Problem\n"
                    "A meaningful issue exists.\n\n"
                    "### Evidence\n"
                    "tests/example.py:10\n\n"
                    "### Requested Change\n"
                    "Make the improvement.\n\n"
                    "### Acceptance Criteria\n"
                    "The issue is resolved.\n\n"
                    "### Verification\n"
                    "make test\n"
                )
            last_message_path = output_path / "last_message.md"
            last_message_path.write_text(last_message, encoding="utf-8")
            job_calls.append((job_name, model, output_path))
            return {
                "job_name": job_name,
                "command": ["fake-runner", "exec"],
                "returncode": 0,
                "output_dir": str(output_path),
                "prompt_path": str(output_path / "prompt.md"),
                "stdout_path": str(output_path / "stdout.jsonl"),
                "stderr_path": str(output_path / "stderr.log"),
                "last_message_path": str(last_message_path),
            }

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            output_dir = Path(tmp_dir_str) / "review_run"

            summary = execute_review_prompt_workflow(
                prompt_sets,
                repo_root=ROOT,
                runner="/tmp/fake-runner",
                output_dir=output_dir,
                sandbox="workspace-write",
                specializer_model="model-specializer",
                review_model="model-review",
                max_workers=2,
                job_runner=fake_job_runner,
            )

            self.assertTrue(summary["success"])
            self.assertEqual(summary["successful_specialization_count"], 2)
            self.assertEqual(summary["successful_review_count"], 2)
            self.assertEqual(summary["failed_result_count"], 0)
            self.assertEqual(summary["failed_results"], [])
            self.assertEqual(len(job_calls), 4)
            self.assertEqual(
                sorted(model for _, model, _ in job_calls),
                ["model-review", "model-review", "model-specializer", "model-specializer"],
            )

            summary_path = Path(summary["summary_path"])
            combined_tickets_path = Path(summary["combined_tickets_path"])
            self.assertTrue(summary_path.exists())
            self.assertTrue(combined_tickets_path.exists())
            self.assertTrue(
                (output_dir / "specialization" / "alpha" / "specialized_prompt.md").exists()
            )
            self.assertTrue((output_dir / "reviews" / "beta" / "tickets.md").exists())

            persisted_summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted_summary["prompt_set_slugs"], ["alpha", "beta"])
            self.assertEqual(Path(persisted_summary["summary_path"]).name, SUMMARY_FILENAME)
            self.assertEqual(
                Path(persisted_summary["combined_tickets_path"]).name,
                COMBINED_TICKETS_FILENAME,
            )
            combined_text = combined_tickets_path.read_text(encoding="utf-8")
            self.assertIn("## alpha", combined_text)
            self.assertIn("## beta", combined_text)

    def test_execute_specialized_review_refresh_writes_refreshed_ticket_pack(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            specialized_prompt_path = tmp_dir / "specialized_prompt.md"
            previous_tickets_path = tmp_dir / "previous_tickets.md"
            specialized_prompt_path.write_text("# Specialized prompt\n\nReview it.\n", encoding="utf-8")
            previous_tickets_path.write_text(
                "# Previous tickets\n\n## ALPHA-001 - Existing issue\n",
                encoding="utf-8",
            )
            prompts = [
                SpecializedReviewPrompt(
                    slug="alpha",
                    title="Alpha Prompt",
                    specialized_prompt_path=specialized_prompt_path,
                    previous_tickets_path=previous_tickets_path,
                )
            ]

            def fake_job_runner(
                job_name: str,
                *,
                prompt_text: str,
                repo_root: str | Path,
                runner: str,
                output_dir: str | Path,
                sandbox: str,
                model: str | None = None,
                extra_args: list[str] | None = None,
                progress_callback=None,
                heartbeat_seconds: float = 20.0,
            ) -> dict[str, object]:
                del job_name, repo_root, runner, sandbox, model, extra_args, progress_callback, heartbeat_seconds
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
                (output_path / "prompt.md").write_text(prompt_text, encoding="utf-8")
                (output_path / "stdout.jsonl").write_text("", encoding="utf-8")
                (output_path / "stderr.log").write_text("", encoding="utf-8")
                last_message_path = output_path / "last_message.md"
                last_message_path.write_text(
                    "# Refreshed tickets\n\n## ALPHA-001 - Existing issue\n",
                    encoding="utf-8",
                )
                return {
                    "job_name": "refresh_alpha",
                    "command": ["fake-runner", "exec"],
                    "returncode": 0,
                    "output_dir": str(output_path),
                    "prompt_path": str(output_path / "prompt.md"),
                    "stdout_path": str(output_path / "stdout.jsonl"),
                    "stderr_path": str(output_path / "stderr.log"),
                    "last_message_path": str(last_message_path),
                }

            summary = execute_specialized_review_refresh(
                prompts,
                repo_root=ROOT,
                runner="/tmp/fake-runner",
                output_dir=tmp_dir / "refresh_run",
                sandbox="workspace-write",
                job_runner=fake_job_runner,
            )

            self.assertTrue(summary["success"])
            self.assertEqual(summary["successful_review_count"], 1)
            refresh_tickets = Path(summary["review_results"][0]["tickets_path"]).read_text(encoding="utf-8")
            self.assertIn("ALPHA-001", refresh_tickets)
            refresh_prompt_text = Path(summary["review_results"][0]["prompt_path"]).read_text(encoding="utf-8")
            self.assertIn("## Previous Ticket Pack", refresh_prompt_text)


if __name__ == "__main__":
    unittest.main()
