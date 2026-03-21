#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.config import load_config
from flywire_wave.io_utils import read_root_ids, write_json
from flywire_wave.mesh_pipeline import process_mesh_into_wave_assets


def main() -> int:
    parser = argparse.ArgumentParser(description="Build simplified mesh + graph assets for wave simulation.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = cfg["paths"]
    meshing = cfg["meshing"]

    root_ids = read_root_ids(paths["selected_root_ids"])
    if not root_ids:
        raise RuntimeError("No root IDs found. Run scripts/01_select_subset.py first.")

    manifest: dict[str, dict[str, str]] = {}
    for root_id in tqdm(root_ids, desc="Building wave assets"):
        raw_mesh_path = Path(paths["meshes_raw_dir"]) / f"{int(root_id)}.ply"
        if not raw_mesh_path.exists():
            raise FileNotFoundError(f"Missing raw mesh for root_id={root_id}: {raw_mesh_path}")

        outputs = process_mesh_into_wave_assets(
            root_id=root_id,
            raw_mesh_path=raw_mesh_path,
            processed_mesh_dir=paths["processed_mesh_dir"],
            processed_graph_dir=paths["processed_graph_dir"],
            simplify_target_faces=int(meshing.get("simplify_target_faces", 15000)),
            patch_hops=int(meshing.get("patch_hops", 6)),
            patch_vertex_cap=int(meshing.get("patch_vertex_cap", 2500)),
        )
        manifest[str(root_id)] = outputs

    write_json(manifest, paths["manifest_json"])
    print(json.dumps({"n_assets": len(manifest), "manifest": paths["manifest_json"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
