#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.milestone8b_readiness import (
    DEFAULT_FIXTURE_TEST_TARGETS,
    execute_milestone8b_readiness_pass,
)
from flywire_wave.readiness_contract import FOLLOW_ON_READINESS_KEY, READY_FOR_FOLLOW_ON_WORK_KEY


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Milestone 8B integration verification pass and publish a readiness report."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML config file that defines the local Milestone 8B verification outputs.",
    )
    parser.add_argument(
        "--fixture-test-target",
        action="append",
        dest="fixture_test_targets",
        default=[],
        help="Optional unittest target to add to the focused Milestone 8B verification suite. Repeatable.",
    )
    parser.add_argument(
        "--skip-fixture-tests",
        action="store_true",
        help="Skip the focused Milestone 8B fixture verification suite.",
    )
    args = parser.parse_args()

    fixture_targets = list(DEFAULT_FIXTURE_TEST_TARGETS)
    fixture_targets.extend(args.fixture_test_targets)
    fixture_verification = (
        _skipped_command_result("fixture_verification", "skipped by --skip-fixture-tests")
        if args.skip_fixture_tests
        else _run_command(
            name="fixture_verification",
            command=[sys.executable, "-m", "unittest", *fixture_targets],
        )
    )

    summary = execute_milestone8b_readiness_pass(
        config_path=args.config,
        fixture_verification=fixture_verification,
        python_executable=sys.executable,
        root_dir=ROOT,
    )
    print(
        json.dumps(
            {
                "report_version": summary["report_version"],
                "readiness_status": summary[FOLLOW_ON_READINESS_KEY]["status"],
                READY_FOR_FOLLOW_ON_WORK_KEY: summary[FOLLOW_ON_READINESS_KEY][READY_FOR_FOLLOW_ON_WORK_KEY],
                "markdown_path": summary["markdown_path"],
                "json_path": summary["json_path"],
            },
            indent=2,
        )
    )
    return 1 if summary[FOLLOW_ON_READINESS_KEY]["status"] == "hold" else 0


def _run_command(*, name: str, command: list[str]) -> dict[str, object]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload: dict[str, object] = {
        "name": name,
        "status": "pass" if result.returncode == 0 else "fail",
        "command": " ".join(command),
        "returncode": int(result.returncode),
    }
    parsed_summary = _parse_json_from_command_output(result.stdout)
    if parsed_summary is not None:
        payload["parsed_summary"] = parsed_summary
    return payload


def _parse_json_from_command_output(stdout: str) -> dict[str, object] | None:
    stripped = stdout.strip()
    if not stripped:
        return None
    start = stripped.find("{")
    if start < 0:
        return None
    candidate = stripped[start:]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _skipped_command_result(name: str, reason: str) -> dict[str, object]:
    return {
        "name": name,
        "status": "skipped",
        "command": "",
        "returncode": None,
        "reason": reason,
    }


if __name__ == "__main__":
    raise SystemExit(main())
