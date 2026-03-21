#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.manifests import validate_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Milestone 1 experiment manifest.")
    parser.add_argument(
        "--manifest",
        default="manifests/examples/milestone_1_demo.yaml",
        help="Path to the YAML manifest to validate.",
    )
    parser.add_argument(
        "--schema",
        default="schemas/milestone_1_experiment_manifest.schema.json",
        help="Path to the JSON Schema file.",
    )
    parser.add_argument(
        "--design-lock",
        default="config/milestone_1_design_lock.yaml",
        help="Path to the Milestone 1 design-lock metadata file.",
    )
    args = parser.parse_args()

    summary = validate_manifest(
        manifest_path=ROOT / args.manifest,
        schema_path=ROOT / args.schema,
        design_lock_path=ROOT / args.design_lock,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
