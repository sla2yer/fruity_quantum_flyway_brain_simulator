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
from flywire_wave.coupling_inspection import (
    generate_coupling_inspection_report,
    parse_edge_spec,
    read_edge_specs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an offline coupling inspection report from local Milestone 7 artifacts."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML config file. Relative paths inside config.paths resolve from the repository root.",
    )
    parser.add_argument(
        "--edge",
        action="append",
        default=[],
        help="Edge to inspect in 'pre:post', 'pre,post', or 'pre->post' form. Repeat to inspect multiple edges.",
    )
    parser.add_argument(
        "--edges-file",
        help="Optional path to a newline-delimited edge list. Lines may use 'pre:post', 'pre,post', or 'pre->post'.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit applied after deduplicating and sorting the chosen edge set.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = cfg["paths"]
    meshing = cfg.get("meshing", {})

    edge_specs = [parse_edge_spec(value) for value in args.edge]
    if args.edges_file:
        edge_specs.extend(read_edge_specs(args.edges_file))
    edge_specs = sorted({(int(pre_root_id), int(post_root_id)) for pre_root_id, post_root_id in edge_specs})
    if args.limit is not None:
        edge_specs = edge_specs[: max(int(args.limit), 0)]
    if not edge_specs:
        raise RuntimeError("No edge specs were provided. Pass --edge and/or --edges-file.")

    summary = generate_coupling_inspection_report(
        edge_specs=edge_specs,
        processed_coupling_dir=paths["processed_coupling_dir"],
        meshes_raw_dir=paths["meshes_raw_dir"],
        skeletons_raw_dir=paths["skeletons_raw_dir"],
        processed_mesh_dir=paths["processed_mesh_dir"],
        processed_graph_dir=paths["processed_graph_dir"],
        coupling_inspection_dir=paths["coupling_inspection_dir"],
        thresholds=meshing.get("coupling_inspection_thresholds"),
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
