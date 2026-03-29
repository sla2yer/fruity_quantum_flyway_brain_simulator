#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.validation_circuit import execute_circuit_validation_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Milestone 13 circuit-sanity validation workflow on local "
            "simulator bundles and shared-readout analysis surfaces."
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
        "--pathway-readout-id",
        action="append",
        default=[],
        help=(
            "Pathway readout_id to test for preferred-vs-null motion asymmetry. "
            "Repeat to validate multiple pathway readouts. When omitted, the "
            "workflow derives the active shared readout ids from the manifest's "
            "readout-analysis plan."
        ),
    )
    parser.add_argument(
        "--analysis-bundle-metadata",
        help=(
            "Optional path to an existing experiment_analysis_bundle.json. When omitted, "
            "the workflow regenerates the packaged analysis bundle from local simulator bundles."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = execute_circuit_validation_workflow(
        manifest_path=Path(args.manifest),
        config_path=Path(args.config),
        schema_path=Path(args.schema),
        design_lock_path=Path(args.design_lock),
        pathway_readout_ids=args.pathway_readout_id or None,
        analysis_bundle_metadata_path=(
            None
            if args.analysis_bundle_metadata is None
            else Path(args.analysis_bundle_metadata)
        ),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
