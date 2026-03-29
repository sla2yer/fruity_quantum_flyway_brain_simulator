#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.validation_task import execute_task_validation_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Milestone 13 task-sanity validation workflow on packaged "
            "Milestone 12 experiment-analysis bundles."
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
        "--analysis-bundle-metadata",
        help=(
            "Optional path to an existing experiment_analysis_bundle.json. When omitted, "
            "the workflow regenerates the packaged analysis bundle from local simulator bundles."
        ),
    )
    parser.add_argument(
        "--perturbation-analysis-bundle",
        action="append",
        default=[],
        help=(
            "Perturbation analysis bundle spec in '<suite_id>:<variant_id>:<metadata_path>' "
            "form. Repeat to attach multiple perturbation/noise-sweep analysis bundles."
        ),
    )
    return parser.parse_args()


def _parse_perturbation_spec(value: str) -> dict[str, object]:
    parts = value.split(":", 2)
    if len(parts) != 3 or not all(part.strip() for part in parts):
        raise ValueError(
            "--perturbation-analysis-bundle entries must use "
            "'<suite_id>:<variant_id>:<metadata_path>' form."
        )
    suite_id, variant_id, metadata_path = parts
    return {
        "suite_id": suite_id,
        "variant_id": variant_id,
        "analysis_bundle_metadata_path": Path(metadata_path),
    }


def main() -> None:
    args = parse_args()
    perturbation_specs = [
        _parse_perturbation_spec(value)
        for value in args.perturbation_analysis_bundle
    ]
    summary = execute_task_validation_workflow(
        manifest_path=Path(args.manifest),
        config_path=Path(args.config),
        schema_path=Path(args.schema),
        design_lock_path=Path(args.design_lock),
        analysis_bundle_metadata_path=(
            None
            if args.analysis_bundle_metadata is None
            else Path(args.analysis_bundle_metadata)
        ),
        perturbation_analysis_bundle_specs=perturbation_specs,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
