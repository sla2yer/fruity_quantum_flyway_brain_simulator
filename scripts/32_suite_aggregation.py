#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from flywire_wave.experiment_suite_aggregation import (
    execute_experiment_suite_aggregation_workflow,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compute Milestone 15 suite-level aggregation rows and ablation-aware "
            "summary tables from a packaged suite inventory."
        )
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--suite-package-metadata",
        help="Path to package/experiment_suite_package.json.",
    )
    source_group.add_argument(
        "--suite-result-index",
        help="Path to package/indexes/result_index.json.",
    )
    parser.add_argument(
        "--table-dimension-id",
        action="append",
        default=[],
        help=(
            "Optional declared suite dimension id used to collapse paired rows into "
            "summary tables. Repeat to keep multiple dimensions in the table key. "
            "Defaults to all declared suite dimensions."
        ),
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Optional output directory. Defaults to "
            "<suite_root>/package/aggregation."
        ),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    record = (
        Path(args.suite_package_metadata)
        if args.suite_package_metadata is not None
        else Path(args.suite_result_index)
    )
    result = execute_experiment_suite_aggregation_workflow(
        record,
        table_dimension_ids=(args.table_dimension_id or None),
        output_dir=(None if args.output_dir is None else Path(args.output_dir)),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
