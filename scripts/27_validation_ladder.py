#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.validation_reporting import (
    package_validation_ladder_outputs,
    write_validation_ladder_regression_baseline,
)


DEFAULT_BASELINE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "validation_ladder_smoke_baseline.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Package Milestone 13 validation outputs into deterministic review, "
            "regression, and notebook-friendly artifacts."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    smoke = subparsers.add_parser(
        "smoke",
        help="Run the deterministic local Milestone 13 smoke fixture and package all four layers.",
    )
    smoke.add_argument(
        "--processed-simulator-results-dir",
        default="data/processed/simulator_results",
        help="Output root for generated smoke-layer bundles and packaged validation outputs.",
    )
    smoke.add_argument(
        "--baseline",
        default=str(DEFAULT_BASELINE_PATH),
        help=(
            "Optional regression baseline snapshot. Defaults to the committed "
            "fixture baseline when that file exists."
        ),
    )
    smoke.add_argument(
        "--no-baseline",
        action="store_true",
        help="Skip regression baseline comparison for the smoke workflow.",
    )
    smoke.add_argument(
        "--enforce-baseline",
        action="store_true",
        help="Fail the command when the packaged smoke summary diverges from the baseline snapshot.",
    )
    smoke.add_argument(
        "--write-baseline",
        help="Optional path to overwrite with the packaged smoke summary baseline snapshot.",
    )

    package = subparsers.add_parser(
        "package",
        help="Package one or more existing validation layer bundles into one deterministic review/regression bundle.",
    )
    package.add_argument(
        "--layer-bundle-metadata",
        action="append",
        default=[],
        help=(
            "Path to a layer-level validation_bundle.json. Repeat once per layer "
            "bundle to package."
        ),
    )
    package.add_argument(
        "--processed-simulator-results-dir",
        help=(
            "Optional output root override for the packaged validation ladder "
            "bundle. Defaults to the first layer bundle's processed-results root."
        ),
    )
    package.add_argument(
        "--baseline",
        help="Optional regression baseline snapshot to compare against the packaged summary.",
    )
    package.add_argument(
        "--write-baseline",
        help="Optional path to overwrite with the packaged summary baseline snapshot.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "smoke":
        from flywire_wave.validation_ladder_smoke import (
            run_validation_ladder_smoke_workflow,
        )

        baseline_path = None if args.no_baseline else _resolve_optional_path(args.baseline)
        result = run_validation_ladder_smoke_workflow(
            processed_simulator_results_dir=Path(args.processed_simulator_results_dir),
            baseline_path=baseline_path,
            enforce_baseline=bool(args.enforce_baseline),
        )
    else:
        if not args.layer_bundle_metadata:
            raise SystemExit(
                "--layer-bundle-metadata must be provided at least once for the package subcommand."
            )
        result = package_validation_ladder_outputs(
            layer_bundle_metadata_paths=[
                Path(path) for path in args.layer_bundle_metadata
            ],
            processed_simulator_results_dir=(
                None
                if args.processed_simulator_results_dir is None
                else Path(args.processed_simulator_results_dir)
            ),
            baseline_path=_resolve_optional_path(args.baseline),
        )
    if args.write_baseline:
        summary_path = Path(result["summary_path"]).resolve()
        summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
        write_validation_ladder_regression_baseline(
            summary_payload,
            Path(args.write_baseline).resolve(),
        )
    print(json.dumps(result, indent=2, sort_keys=True))


def _resolve_optional_path(value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).resolve()
    return path if path.exists() else path


if __name__ == "__main__":
    main()
