#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.config import load_config
from flywire_wave.io_utils import read_root_ids
from flywire_wave.operator_qa import generate_operator_qa_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an offline operator QA report from local Milestone 6 bundles."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML config file. Relative paths inside config.paths resolve from the repository root.",
    )
    parser.add_argument(
        "--root-id",
        action="append",
        type=int,
        default=[],
        help="Root ID to include. Repeat to inspect multiple neurons.",
    )
    parser.add_argument(
        "--root-ids-file",
        help="Optional path to a newline-delimited root-id file. Defaults to config.paths.selected_root_ids.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit applied after reading the chosen root-id source.",
    )
    parser.add_argument(
        "--pulse-steps",
        type=int,
        default=8,
        help="Number of explicit smoke-evolution steps to apply to the localized pulse.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = cfg["paths"]

    if args.root_id:
        root_ids = list(args.root_id)
    else:
        root_id_source = args.root_ids_file or paths["selected_root_ids"]
        root_ids = read_root_ids(root_id_source)
    if args.limit is not None:
        root_ids = root_ids[: max(int(args.limit), 0)]
    if not root_ids:
        raise RuntimeError("No root IDs were resolved for operator QA generation.")

    meshing = cfg.get("meshing", {})
    summary = generate_operator_qa_report(
        root_ids=root_ids,
        meshes_raw_dir=paths["meshes_raw_dir"],
        skeletons_raw_dir=paths["skeletons_raw_dir"],
        processed_mesh_dir=paths["processed_mesh_dir"],
        processed_graph_dir=paths["processed_graph_dir"],
        operator_qa_dir=paths["operator_qa_dir"],
        thresholds=meshing.get("operator_qa_thresholds"),
        pulse_step_count=int(args.pulse_steps),
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
