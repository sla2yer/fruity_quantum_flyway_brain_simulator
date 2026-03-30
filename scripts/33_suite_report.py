#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from flywire_wave.experiment_suite_reporting import (
    generate_experiment_suite_review_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate deterministic Milestone 15 suite review artifacts from a "
            "packaged suite inventory, including summary-table discovery, "
            "auto-generated comparison plots, and a static offline HTML index."
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
            "Optional declared suite dimension id used as the plot/table slice key. "
            "Repeat to retain multiple dimensions. Defaults to the aggregation default."
        ),
    )
    parser.add_argument(
        "--aggregation-output-dir",
        help=(
            "Optional suite-aggregation output directory. Defaults to "
            "<suite_root>/package/aggregation."
        ),
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Optional review-report output directory. Defaults to "
            "<suite_root>/package/report/suite_review."
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
    result = generate_experiment_suite_review_report(
        record,
        table_dimension_ids=(args.table_dimension_id or None),
        aggregation_output_dir=(
            None
            if args.aggregation_output_dir is None
            else Path(args.aggregation_output_dir)
        ),
        output_dir=(None if args.output_dir is None else Path(args.output_dir)),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
