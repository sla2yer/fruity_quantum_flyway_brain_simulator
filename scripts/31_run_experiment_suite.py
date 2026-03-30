#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flywire_wave.experiment_suite_execution import (
    execute_experiment_suite_workflow,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve one Milestone 15 suite plan, expand a deterministic local "
            "work schedule, and execute or preview the declared stages with "
            "resume-safe persisted state."
        )
    )
    parser.add_argument("--config", required=True, help="Path to the runtime config YAML.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--manifest",
        help="Path to an experiment manifest YAML that embeds a suite block.",
    )
    source_group.add_argument(
        "--suite-manifest",
        help="Path to a standalone experiment-suite manifest YAML.",
    )
    parser.add_argument("--schema", required=True, help="Path to the manifest schema JSON.")
    parser.add_argument(
        "--design-lock",
        required=True,
        help="Path to the authoritative design-lock YAML.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the stable work schedule and resume decisions without mutating state.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failed or partial work item instead of continuing.",
    )
    args = parser.parse_args(argv)

    summary = execute_experiment_suite_workflow(
        config_path=Path(args.config),
        manifest_path=None if args.manifest is None else Path(args.manifest),
        suite_manifest_path=(
            None if args.suite_manifest is None else Path(args.suite_manifest)
        ),
        schema_path=Path(args.schema),
        design_lock_path=Path(args.design_lock),
        dry_run=bool(args.dry_run),
        fail_fast=bool(args.fail_fast),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
