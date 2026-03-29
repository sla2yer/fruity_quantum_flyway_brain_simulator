#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.validation_morphology import execute_morphology_validation_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Milestone 13 morphology-sanity validation suite on local "
            "surface-wave assets and write deterministic validation artifacts."
        )
    )
    parser.add_argument("--config", required=True, help="Path to the repo config YAML.")
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to the experiment manifest YAML.",
    )
    parser.add_argument(
        "--schema",
        required=True,
        help="Path to the manifest schema JSON.",
    )
    parser.add_argument(
        "--design-lock",
        required=True,
        help="Path to the Milestone 1 design lock YAML.",
    )
    parser.add_argument(
        "--arm-id",
        action="append",
        default=[],
        help="Optional surface-wave arm_id to validate. Repeat to target multiple arms.",
    )
    parser.add_argument(
        "--reference-root",
        action="append",
        default=[],
        help=(
            "Optional mixed-fidelity reference root spec in "
            "'<root_id>:<reference_morphology_class>' form. Repeat to target "
            "multiple surrogate roots."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = execute_morphology_validation_workflow(
        manifest_path=Path(args.manifest),
        config_path=Path(args.config),
        schema_path=Path(args.schema),
        design_lock_path=Path(args.design_lock),
        arm_ids=args.arm_id or None,
        reference_root_specs=args.reference_root or None,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
