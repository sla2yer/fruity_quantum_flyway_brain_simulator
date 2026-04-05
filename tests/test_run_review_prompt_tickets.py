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


def _write_stub_runner(path: Path, *, fail_specialization: bool) -> Path:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "",
                "import argparse",
                "import sys",
                "from pathlib import Path",
                "",
                "",
                "def main() -> int:",
                "    parser = argparse.ArgumentParser()",
                "    subparsers = parser.add_subparsers(dest='command', required=True)",
                "    exec_parser = subparsers.add_parser('exec')",
                "    exec_parser.add_argument('--json', action='store_true')",
                "    exec_parser.add_argument('--cd')",
                "    exec_parser.add_argument('--sandbox')",
                "    exec_parser.add_argument('--output-last-message', dest='output_last_message')",
                "    exec_parser.add_argument('--model')",
                "    args, _ = parser.parse_known_args()",
                "    prompt = sys.stdin.read()",
                "    last_message_path = Path(args.output_last_message)",
                "    is_specialization = '## Generic Prompt To Rewrite' in prompt",
                f"    fail_specialization = {str(fail_specialization)}",
                "    if is_specialization and fail_specialization:",
                "        sys.stderr.write('specialization failed for efficiency_and_modularity\\n')",
                "        sys.stderr.flush()",
                "        return 17",
                "    sys.stdout.write('{\"type\":\"turn.started\"}\\n')",
                "    sys.stdout.flush()",
                "    if is_specialization:",
                "        last_message_path.write_text('# Specialized prompt\\n\\nRepo-specific specialization.\\n', encoding='utf-8')",
                "    else:",
                "        last_message_path.write_text(",
                "            '# Review tickets\\n\\n## EFFMOD-001 - Stub finding\\n- Status: open\\n- Priority: medium\\n- Source: stub review\\n\\n### Problem\\nStub problem.\\n\\n### Evidence\\nREADME.md:1\\n\\n### Requested Change\\nStub change.\\n\\n### Acceptance Criteria\\nStub acceptance.\\n\\n### Verification\\nmake test\\n',",
                "            encoding='utf-8',",
                "        )",
                "    return 0",
                "",
                "",
                "if __name__ == '__main__':",
                "    raise SystemExit(main())",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


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

    def test_main_prints_failed_prompt_jobs_with_diagnostic_artifacts(self) -> None:
        module = _load_run_review_prompt_tickets_module()
        self.addCleanup(sys.modules.pop, "run_review_prompt_tickets_script", None)

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            runner_path = _write_stub_runner(
                tmp_dir / "stub-review-runner.py",
                fail_specialization=True,
            )
            output_dir = tmp_dir / "review_runs"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = module.main(
                    [
                        "--prompt-set",
                        "efficiency_and_modularity",
                        "--runner",
                        str(runner_path),
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            self.assertEqual(exit_code, 1)
            stderr_path = output_dir / "specialization" / "efficiency_and_modularity" / "stderr.log"
            stdout_text = stdout.getvalue()
            self.assertIn("Failed prompt jobs:", stdout_text)
            self.assertIn("prompt_set=efficiency_and_modularity", stdout_text)
            self.assertIn("stage=specialization", stdout_text)
            self.assertIn("returncode=17", stdout_text)
            self.assertIn(str(stderr_path.resolve()), stdout_text)
            self.assertEqual(
                stderr_path.read_text(encoding="utf-8"),
                "specialization failed for efficiency_and_modularity\n",
            )

            summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertFalse(summary["success"])
            self.assertEqual(summary["failed_result_count"], 1)
            self.assertEqual(summary["failed_results"][0]["prompt_set"], "efficiency_and_modularity")
            self.assertEqual(summary["failed_results"][0]["stage"], "specialization")
            self.assertEqual(summary["failed_results"][0]["returncode"], 17)
            self.assertEqual(
                summary["failed_results"][0]["diagnostic_paths"],
                [str(stderr_path.resolve())],
            )


if __name__ == "__main__":
    unittest.main()
