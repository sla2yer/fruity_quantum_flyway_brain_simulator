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

from flywire_wave.config import load_config
from flywire_wave.io_utils import ensure_dir, read_root_ids
from flywire_wave.milestone6_readiness import (
    DEFAULT_FIXTURE_TEST_TARGETS,
    build_milestone6_readiness_paths,
    generate_milestone6_readiness_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Milestone 6 fixture and local-bundle verification pass, then publish a readiness report."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML config file that defines the local verification bundle.",
    )
    parser.add_argument(
        "--fixture-test-target",
        action="append",
        dest="fixture_test_targets",
        default=[],
        help="Optional unittest target to add to the fixture verification suite. Repeatable.",
    )
    parser.add_argument(
        "--skip-fixture-tests",
        action="store_true",
        help="Skip the focused fixture verification suite.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip scripts/03_build_wave_assets.py and reuse existing processed bundles.",
    )
    parser.add_argument(
        "--skip-operator-qa",
        action="store_true",
        help="Skip scripts/06_operator_qa.py and reuse an existing operator QA bundle.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = cfg["paths"]
    root_ids = read_root_ids(paths["selected_root_ids"])
    if not root_ids:
        raise RuntimeError("No root IDs resolved for the Milestone 6 readiness pass.")

    readiness_paths = build_milestone6_readiness_paths(paths["operator_qa_dir"], root_ids)
    command_log_dir = ensure_dir(readiness_paths["report_dir"] / "commands")

    fixture_targets = list(DEFAULT_FIXTURE_TEST_TARGETS)
    fixture_targets.extend(args.fixture_test_targets)
    fixture_verification = (
        _skipped_command_result("fixture_verification", "skipped by --skip-fixture-tests")
        if args.skip_fixture_tests
        else _run_command(
            name="fixture_verification",
            command=[sys.executable, "-m", "unittest", *fixture_targets],
            log_dir=command_log_dir,
        )
    )

    build_command = (
        _skipped_command_result("build_wave_assets", "skipped by --skip-build")
        if args.skip_build
        else _run_command(
            name="build_wave_assets",
            command=[sys.executable, str(ROOT / "scripts" / "03_build_wave_assets.py"), "--config", str(args.config)],
            log_dir=command_log_dir,
        )
    )

    if args.skip_operator_qa:
        operator_qa_command = _skipped_command_result("operator_qa", "skipped by --skip-operator-qa")
    elif build_command["status"] == "fail":
        operator_qa_command = _skipped_command_result("operator_qa", "skipped because build_wave_assets failed")
    else:
        operator_qa_command = _run_command(
            name="operator_qa",
            command=[sys.executable, str(ROOT / "scripts" / "06_operator_qa.py"), "--config", str(args.config)],
            log_dir=command_log_dir,
        )

    summary = generate_milestone6_readiness_report(
        config_path=args.config,
        manifest_path=paths["manifest_json"],
        operator_qa_dir=paths["operator_qa_dir"],
        root_ids=root_ids,
        fixture_verification=fixture_verification,
        build_command=build_command,
        operator_qa_command=operator_qa_command,
    )
    print(
        json.dumps(
            {
                "report_version": summary["report_version"],
                "readiness_status": summary["milestone10_readiness"]["status"],
                "ready_for_engine_work": summary["milestone10_readiness"]["ready_for_engine_work"],
                "markdown_path": summary["markdown_path"],
                "json_path": summary["json_path"],
                "operator_qa_summary_path": summary["operator_qa_summary_path"],
            },
            indent=2,
        )
    )
    return 1 if summary["milestone10_readiness"]["status"] == "hold" else 0


def _run_command(*, name: str, command: list[str], log_dir: Path) -> dict[str, object]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout_path = log_dir / f"{name}.stdout.log"
    stderr_path = log_dir / f"{name}.stderr.log"
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")

    payload: dict[str, object] = {
        "name": name,
        "status": "pass" if result.returncode == 0 else "fail",
        "command": " ".join(command),
        "returncode": int(result.returncode),
        "stdout_log_path": str(stdout_path.resolve()),
        "stderr_log_path": str(stderr_path.resolve()),
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
        "stdout_log_path": "",
        "stderr_log_path": "",
    }


if __name__ == "__main__":
    raise SystemExit(main())
