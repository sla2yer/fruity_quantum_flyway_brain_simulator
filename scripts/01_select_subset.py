#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.config import load_config
from flywire_wave.io_utils import write_root_ids
from flywire_wave.registry import load_neuron_registry
from flywire_wave.selection import extract_root_ids, select_visual_subset


def main() -> int:
    parser = argparse.ArgumentParser(description="Select a FlyWire subset from the canonical neuron registry.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = cfg["paths"]
    selection = cfg["selection"]

    registry_path = paths.get("neuron_registry_csv", "data/interim/registry/neuron_registry.csv")
    df = load_neuron_registry(registry_path)
    subset = select_visual_subset(
        df,
        super_class=selection.get("super_class"),
        super_classes=selection.get("super_classes"),
        project_roles=selection.get("project_roles"),
        limit=int(selection.get("limit", 12)),
        sort_by=selection.get("sort_by", "root_id"),
    )
    root_ids = extract_root_ids(subset)
    out_path = write_root_ids(root_ids, paths["selected_root_ids"])

    print(f"Selected {len(root_ids)} root IDs")
    print(f"Registry: {registry_path}")
    print(f"Wrote: {out_path}")
    print(subset.head(min(len(subset), 10)).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
