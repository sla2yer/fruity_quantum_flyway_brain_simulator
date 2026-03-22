#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flywire_wave.simulator_visualization import generate_simulator_visualization_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a deterministic offline HTML viewer from one or more "
            "simulator_result_bundle.json files."
        )
    )
    parser.add_argument(
        "--bundle-metadata",
        action="append",
        dest="bundle_metadata",
        required=True,
        help="Path to a simulator_result_bundle.json file. Repeatable.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional output directory override for the generated viewer.",
    )
    args = parser.parse_args(argv)

    summary = generate_simulator_visualization_report(
        bundle_metadata_paths=args.bundle_metadata,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
