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


def _load_run_review_prompt_tickets_module():
    script_path = ROOT / "scripts" / "run_review_prompt_tickets.py"
    spec = importlib.util.spec_from_file_location("run_review_prompt_tickets_script", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load script module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RunReviewPromptTicketsScriptTest(unittest.TestCase):
    def test_main_dry_run_prints_selected_prompt_sets(self) -> None:
        module = _load_run_review_prompt_tickets_module()
        self.addCleanup(sys.modules.pop, "run_review_prompt_tickets_script", None)

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = module.main(
                    [
                        "--prompt-set",
                        "efficiency_and_modularity",
                        "--output-dir",
                        str(Path(tmp_dir_str) / "review_runs"),
                        "--dry-run",
                    ]
                )

        self.assertEqual(exit_code, 0)
        plan = json.loads(stdout.getvalue())
        self.assertEqual(plan["prompt_sets"][0]["slug"], "efficiency_and_modularity")
        self.assertEqual(len(plan["prompt_sets"]), 1)


if __name__ == "__main__":
    unittest.main()
