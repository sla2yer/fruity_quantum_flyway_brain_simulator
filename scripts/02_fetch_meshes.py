#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.auth import ensure_flywire_secret
from flywire_wave.config import load_config
from flywire_wave.io_utils import read_root_ids
from flywire_wave.mesh_pipeline import fetch_mesh_and_optional_skeleton
from flywire_wave.registry import load_neuron_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch per-neuron FlyWire meshes/skeletons.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    token = os.getenv("FLYWIRE_TOKEN", "").strip()

    cfg = load_config(args.config)
    paths = cfg["paths"]
    meshing = cfg["meshing"]
    dataset = cfg["dataset"].get("flywire_dataset", "public")
    registry_path = paths.get("neuron_registry_csv", "data/interim/registry/neuron_registry.csv")

    if token:
        try:
            token_sync = ensure_flywire_secret(token)
            if token_sync == "updated":
                print("Synced FLYWIRE_TOKEN into local FlyWire secret storage for fafbseg.")
        except Exception as exc:
            raise RuntimeError("Could not set FlyWire token for fafbseg.") from exc

    root_ids = read_root_ids(paths["selected_root_ids"])
    if not root_ids:
        raise RuntimeError("No root IDs found. Run scripts/01_select_subset.py first.")

    registry = load_neuron_registry(registry_path)
    known_root_ids = {int(root_id) for root_id in registry["root_id"].tolist()}
    missing_root_ids = sorted(set(root_ids) - known_root_ids)
    if missing_root_ids:
        raise RuntimeError(
            f"{len(missing_root_ids)} selected root IDs were not found in the registry {registry_path}: "
            f"{missing_root_ids[:10]}"
        )

    print(f"Fetching {len(root_ids)} neurons validated against {registry_path}.")

    for root_id in tqdm(root_ids, desc="Fetching meshes"):
        fetch_mesh_and_optional_skeleton(
            root_id=root_id,
            raw_mesh_dir=paths["meshes_raw_dir"],
            raw_skeleton_dir=paths["skeletons_raw_dir"],
            flywire_dataset=dataset,
            fetch_skeletons=bool(meshing.get("fetch_skeletons", True)),
        )

    print("Finished downloading raw assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
