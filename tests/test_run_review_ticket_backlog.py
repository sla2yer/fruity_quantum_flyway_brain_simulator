from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def _load_run_review_ticket_backlog_module():
    script_path = ROOT / "scripts" / "run_review_ticket_backlog.py"
    spec = importlib.util.spec_from_file_location("run_review_ticket_backlog_script", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load script module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RunReviewTicketBacklogScriptTest(unittest.TestCase):
    def test_main_dry_run_prints_backlog_plan(self) -> None:
        module = _load_run_review_ticket_backlog_module()
        self.addCleanup(sys.modules.pop, "run_review_ticket_backlog_script", None)

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            review_run_dir = Path(tmp_dir_str) / "review_run"
            review_run_dir.mkdir()
            (review_run_dir / "combined_tickets.md").write_text("# Combined Review Tickets\n", encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = module.main(
                    [
                        "--review-run-dir",
                        str(review_run_dir),
                        "--output-dir",
                        str(Path(tmp_dir_str) / "backlog_run"),
                        "--dry-run",
                    ]
                )

        self.assertEqual(exit_code, 0)
        plan = json.loads(stdout.getvalue())
        self.assertEqual(plan["review_run_dir"], str(review_run_dir.resolve()))
        self.assertTrue(plan["initial_tickets_file"].endswith("combined_tickets.md"))
        self.assertTrue(plan["review_before_tickets"])


if __name__ == "__main__":
    unittest.main()
