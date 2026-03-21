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
from flywire_wave.selection import extract_root_ids, load_classification_table, select_visual_subset


def main() -> int:
    parser = argparse.ArgumentParser(description="Select a small FlyWire subset from classification.csv")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = cfg["paths"]
    selection = cfg["selection"]

    df = load_classification_table(paths["classification_csv"])
    subset = select_visual_subset(
        df,
        super_class=selection.get("super_class", "visual"),
        limit=int(selection.get("limit", 12)),
        sort_by=selection.get("sort_by", "root_id"),
    )
    root_ids = extract_root_ids(subset)
    out_path = write_root_ids(root_ids, paths["selected_root_ids"])

    print(f"Selected {len(root_ids)} root IDs")
    print(f"Wrote: {out_path}")
    print(subset.head(min(len(subset), 10)).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
