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

from flywire_wave.experiment_comparison_analysis import (
    execute_experiment_comparison_workflow,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Discover one experiment's local simulator bundle set and compute "
            "experiment-level Milestone 12 comparison summaries."
        )
    )
    parser.add_argument("--config", required=True, help="Path to the runtime config YAML.")
    parser.add_argument("--manifest", required=True, help="Path to the experiment manifest YAML.")
    parser.add_argument("--schema", required=True, help="Path to the manifest schema JSON.")
    parser.add_argument(
        "--design-lock",
        required=True,
        help="Path to the authoritative design-lock YAML.",
    )
    parser.add_argument(
        "--output",
        help="Optional JSON output path for the computed experiment summary.",
    )
    args = parser.parse_args(argv)

    summary = execute_experiment_comparison_workflow(
        manifest_path=args.manifest,
        config_path=args.config,
        schema_path=args.schema,
        design_lock_path=args.design_lock,
        output_path=args.output,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
