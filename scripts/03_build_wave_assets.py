#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.config import load_config
from flywire_wave.io_utils import read_root_ids, write_json
from flywire_wave.mesh_pipeline import process_mesh_into_wave_assets
from flywire_wave.registry import load_neuron_registry, validate_selected_root_ids


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build simplified mesh + graph assets for wave simulation.")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML config file. Relative paths inside config.paths resolve from the repository root.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = cfg["paths"]
    meshing = cfg["meshing"]
    registry_path = paths.get("neuron_registry_csv", "data/interim/registry/neuron_registry.csv")

    root_ids = read_root_ids(paths["selected_root_ids"])
    if not root_ids:
        raise RuntimeError("No root IDs found. Run scripts/01_select_subset.py first.")

    registry_df = load_neuron_registry(registry_path)
    validate_selected_root_ids(root_ids, registry_df, registry_path)

    registry = registry_df.set_index("root_id", drop=False)
    manifest: dict[str, dict[str, str]] = {}
    for root_id in tqdm(root_ids, desc="Building wave assets"):
        raw_mesh_path = Path(paths["meshes_raw_dir"]) / f"{int(root_id)}.ply"
        if not raw_mesh_path.exists():
            raise FileNotFoundError(f"Missing raw mesh for root_id={root_id}: {raw_mesh_path}")

        registry_metadata: dict[str, object] = {}
        if int(root_id) in registry.index:
            row = registry.loc[int(root_id)]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            registry_metadata = {
                key: _json_safe(value)
                for key, value in row.to_dict().items()
                if not pd.isna(value)
            }

        outputs = process_mesh_into_wave_assets(
            root_id=root_id,
            raw_mesh_path=raw_mesh_path,
            processed_mesh_dir=paths["processed_mesh_dir"],
            processed_graph_dir=paths["processed_graph_dir"],
            simplify_target_faces=int(meshing.get("simplify_target_faces", 15000)),
            patch_hops=int(meshing.get("patch_hops", 6)),
            patch_vertex_cap=int(meshing.get("patch_vertex_cap", 2500)),
            registry_metadata=registry_metadata,
        )
        manifest[str(root_id)] = {
            **outputs,
            "cell_type": str(registry_metadata.get("cell_type", "")),
            "project_role": str(registry_metadata.get("project_role", "")),
            "snapshot_version": str(registry_metadata.get("snapshot_version", "")),
            "materialization_version": str(registry_metadata.get("materialization_version", "")),
        }

    write_json(manifest, paths["manifest_json"])
    print(
        json.dumps(
            {
                "n_assets": len(manifest),
                "manifest": paths["manifest_json"],
                "registry": registry_path,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
