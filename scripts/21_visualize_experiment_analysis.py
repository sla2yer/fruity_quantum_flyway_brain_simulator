#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flywire_wave.experiment_analysis_visualization import (
    generate_experiment_analysis_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a deterministic offline HTML report from one packaged "
            "Milestone 12 experiment analysis bundle."
        )
    )
    parser.add_argument(
        "--analysis-bundle",
        required=True,
        help="Path to an experiment_analysis_bundle.json file.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional output directory override for the generated report.",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the generated static report directly from disk after writing it.",
    )
    args = parser.parse_args(argv)

    summary = generate_experiment_analysis_report(
        analysis_bundle_metadata_path=args.analysis_bundle,
        output_dir=args.output_dir,
    )
    if args.open_browser:
        webbrowser.open(summary["report_file_url"], new=2)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
