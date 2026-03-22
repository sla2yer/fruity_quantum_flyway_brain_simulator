from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .retinal_geometry import has_retinal_geometry_reference, resolve_retinal_geometry_spec
from .stimulus_registry import has_stimulus_reference, resolve_stimulus_spec


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_METADATA_KEY = "__config_metadata__"
DEFAULT_PATHS = {
    "codex_raw_dir": Path("data/raw/codex"),
    "neuron_registry_csv": Path("data/interim/registry/neuron_registry.csv"),
    "connectivity_registry_csv": Path("data/interim/registry/connectivity_registry.csv"),
    "registry_provenance_json": Path("data/interim/registry/registry_provenance.json"),
    "selected_root_ids": Path("data/interim/root_ids_visual_sample.txt"),
    "subset_output_dir": Path("data/interim/subsets"),
    "meshes_raw_dir": Path("data/interim/meshes_raw"),
    "skeletons_raw_dir": Path("data/interim/skeletons_raw"),
    "processed_mesh_dir": Path("data/processed/meshes"),
    "processed_graph_dir": Path("data/processed/graphs"),
    "processed_coupling_dir": Path("data/processed/coupling"),
    "coupling_inspection_dir": Path("data/processed/coupling_inspection"),
    "geometry_preview_dir": Path("data/processed/previews"),
    "operator_qa_dir": Path("data/processed/operator_qa"),
    "processed_stimulus_dir": Path("data/processed/stimuli"),
    "processed_retinal_dir": Path("data/processed/retinal"),
    "manifest_json": Path("data/processed/asset_manifest.json"),
}


def load_config(path: str | Path, *, project_root: str | Path | None = None) -> dict[str, Any]:
    cfg_path = _resolve_input_path(path)
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Config at {cfg_path} is not a mapping.")

    resolved_project_root = _resolve_project_root(project_root)
    resolved_paths = _resolve_paths_mapping(cfg.get("paths"), project_root=resolved_project_root)

    loaded_cfg = dict(cfg)
    loaded_cfg["paths"] = resolved_paths
    loaded_cfg[CONFIG_METADATA_KEY] = {
        "config_path": str(cfg_path),
        "project_root": str(resolved_project_root),
    }
    if has_stimulus_reference(loaded_cfg):
        resolved_stimulus = resolve_stimulus_spec(loaded_cfg)
        processed_stimulus_dir = resolved_paths["processed_stimulus_dir"]
        loaded_cfg["stimulus"] = resolved_stimulus.stimulus_spec
        loaded_cfg["stimulus_registry_entry"] = resolved_stimulus.registry_entry
        loaded_cfg["stimulus_contract"] = resolved_stimulus.build_contract_metadata(
            processed_stimulus_dir=processed_stimulus_dir
        )
        loaded_cfg["stimulus_bundle"] = resolved_stimulus.build_bundle_metadata(
            processed_stimulus_dir=processed_stimulus_dir
        )
        loaded_cfg["stimulus_bundle_reference"] = resolved_stimulus.build_bundle_reference(
            processed_stimulus_dir=processed_stimulus_dir
        )
        loaded_cfg["stimulus_bundle_metadata_path"] = resolved_stimulus.resolve_bundle_metadata_path(
            processed_stimulus_dir=processed_stimulus_dir
        )
    if has_retinal_geometry_reference(loaded_cfg):
        resolved_retinal_geometry = resolve_retinal_geometry_spec(loaded_cfg)
        loaded_cfg["retinal_geometry"] = resolved_retinal_geometry.retinal_geometry
        loaded_cfg["retinal_geometry_registry_entry"] = resolved_retinal_geometry.registry_entry
    return loaded_cfg


def get_config_path(cfg: dict[str, Any]) -> Path | None:
    metadata = cfg.get(CONFIG_METADATA_KEY, {})
    config_path = metadata.get("config_path")
    return Path(config_path) if config_path else None


def get_project_root(cfg: dict[str, Any]) -> Path | None:
    metadata = cfg.get(CONFIG_METADATA_KEY, {})
    project_root = metadata.get("project_root")
    return Path(project_root) if project_root else None


def _resolve_input_path(path: str | Path) -> Path:
    cfg_path = Path(path).expanduser()
    if not cfg_path.is_absolute():
        cfg_path = Path.cwd() / cfg_path
    return cfg_path.resolve()


def _resolve_project_root(project_root: str | Path | None) -> Path:
    if project_root is None:
        return REPO_ROOT.resolve()
    root = Path(project_root).expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def _resolve_paths_mapping(paths_cfg: Any, *, project_root: Path) -> dict[str, Any]:
    if paths_cfg is None:
        paths_cfg = {}
    if not isinstance(paths_cfg, dict):
        raise ValueError("Config field 'paths' must be a mapping when provided.")

    resolved_paths: dict[str, Any] = {}
    for key, value in paths_cfg.items():
        if isinstance(value, (str, Path)):
            resolved_paths[key] = str(_resolve_project_path(value, project_root))
        else:
            resolved_paths[key] = value

    for key, default_path in DEFAULT_PATHS.items():
        resolved_paths.setdefault(key, str(_resolve_project_path(default_path, project_root)))

    resolved_paths.setdefault(
        "classification_csv",
        str((Path(resolved_paths["codex_raw_dir"]) / "classification.csv").resolve()),
    )
    return resolved_paths


def _resolve_project_path(path: str | Path, project_root: Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()
