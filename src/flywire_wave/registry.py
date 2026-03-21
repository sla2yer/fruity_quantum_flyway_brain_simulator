from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .io_utils import ensure_dir, write_json


REPO_ROOT = Path(__file__).resolve().parents[2]
VENDORED_CODEX_ROOT = REPO_ROOT / "flywire_codex"
if VENDORED_CODEX_ROOT.exists() and str(VENDORED_CODEX_ROOT) not in sys.path:
    sys.path.insert(0, str(VENDORED_CODEX_ROOT))

try:
    from codex.data.catalog import (
        get_cell_types_file_columns,
        get_classification_file_columns,
        get_connections_file_columns,
        get_neurons_file_columns,
    )
    from codex.data.versions import DEFAULT_DATA_SNAPSHOT_VERSION
except Exception:  # pragma: no cover - fallback only matters if vendored Codex is unavailable.
    DEFAULT_DATA_SNAPSHOT_VERSION = "783"

    def get_classification_file_columns() -> list[str]:
        return ["root_id", "flow", "super_class", "class", "sub_class", "hemilineage", "side", "nerve"]

    def get_cell_types_file_columns() -> list[str]:
        return ["root_id", "primary_type", "additional_type(s)"]

    def get_connections_file_columns() -> list[str]:
        return ["pre_root_id", "post_root_id", "neuropil", "syn_count", "nt_type"]

    def get_neurons_file_columns() -> list[str]:
        return [
            "root_id",
            "group",
            "nt_type",
            "nt_type_score",
            "da_avg",
            "ser_avg",
            "gaba_avg",
            "glut_avg",
            "ach_avg",
            "oct_avg",
        ]


ROLE_CONTEXT_ONLY = "context_only"
ROLE_POINT_SIMULATED = "point_simulated"
ROLE_SKELETON_SIMULATED = "skeleton_simulated"
ROLE_SURFACE_SIMULATED = "surface_simulated"
ROLE_PRIORITY = [
    ROLE_SURFACE_SIMULATED,
    ROLE_SKELETON_SIMULATED,
    ROLE_POINT_SIMULATED,
]

DEFAULT_PROJECT_ROLE_RULES = {
    ROLE_SURFACE_SIMULATED: ["T4a", "T5a"],
    ROLE_SKELETON_SIMULATED: [],
    ROLE_POINT_SIMULATED: ["Mi1", "Tm3", "Mi4", "Mi9", "Tm1", "Tm2", "Tm4", "Tm9"],
}

OPTIONAL_SOURCE_CANDIDATES = {
    "cell_types": ["cell_types.csv", "cell_types.csv.gz", "consolidated_cell_types.csv", "consolidated_cell_types.csv.gz"],
    "nt_predictions": ["neurotransmitter_type_predictions.csv", "neurons.csv", "neurons.csv.gz"],
    "connections": ["connections_filtered.csv", "connections.csv", "connections.csv.gz"],
    "visual_annotations": ["visual_neuron_annotations.csv", "visual _neuron_annotations.csv"],
    "visual_columns": ["visual_neuron_columns.csv"],
}

VISUAL_ANNOTATION_COLUMNS = ["root_id", "type", "family", "subsystem", "category", "side"]
VISUAL_COLUMN_COLUMNS = ["root_id", "hemisphere", "type", "column_id", "x", "y", "p", "q"]
NEURON_REGISTRY_COLUMNS = [
    "root_id",
    "cell_type",
    "resolved_type",
    "primary_type",
    "additional_types",
    "visual_type",
    "flow",
    "super_class",
    "class",
    "sub_class",
    "hemilineage",
    "side",
    "nerve",
    "family",
    "subsystem",
    "category",
    "hemisphere",
    "column_id",
    "column_x",
    "column_y",
    "column_p",
    "column_q",
    "nt_type",
    "nt_type_score",
    "group",
    "neuropils",
    "input_neuropils",
    "output_neuropils",
    "proofread_status",
    "snapshot_version",
    "materialization_version",
    "source_file",
    "project_role",
]
CONNECTIVITY_REGISTRY_COLUMNS = [
    "pre_root_id",
    "post_root_id",
    "neuropil",
    "syn_count",
    "nt_type",
    "snapshot_version",
    "materialization_version",
    "source_file",
]
ROOT_SOURCE_COLUMNS = [
    "has_classification_source",
    "has_cell_types_source",
    "has_nt_predictions_source",
    "has_visual_annotations_source",
    "has_visual_columns_source",
    "has_connections_source",
]


@dataclass(frozen=True)
class RegistrySourcePaths:
    classification: Path
    cell_types: Path | None
    nt_predictions: Path | None
    connections: Path | None
    visual_annotations: Path | None
    visual_columns: Path | None


def resolve_registry_source_paths(cfg: dict[str, Any]) -> RegistrySourcePaths:
    paths_cfg = cfg.get("paths", {})
    raw_dir = Path(paths_cfg.get("codex_raw_dir", "data/raw/codex"))
    classification = Path(paths_cfg.get("classification_csv", raw_dir / "classification.csv"))
    if not classification.exists():
        gz_path = classification.with_suffix(classification.suffix + ".gz")
        if gz_path.exists():
            classification = gz_path
    if not classification.exists():
        raise FileNotFoundError(
            f"Could not find classification CSV at {classification}. "
            "Download the FlyWire Codex export and update config.paths.classification_csv if needed."
        )

    return RegistrySourcePaths(
        classification=classification,
        cell_types=_resolve_optional_path(paths_cfg, raw_dir, "cell_types_csv", OPTIONAL_SOURCE_CANDIDATES["cell_types"]),
        nt_predictions=_resolve_optional_path(
            paths_cfg,
            raw_dir,
            "neurotransmitter_predictions_csv",
            OPTIONAL_SOURCE_CANDIDATES["nt_predictions"],
        ),
        connections=_resolve_optional_path(paths_cfg, raw_dir, "connections_csv", OPTIONAL_SOURCE_CANDIDATES["connections"]),
        visual_annotations=_resolve_optional_path(
            paths_cfg,
            raw_dir,
            "visual_annotations_csv",
            OPTIONAL_SOURCE_CANDIDATES["visual_annotations"],
        ),
        visual_columns=_resolve_optional_path(paths_cfg, raw_dir, "visual_columns_csv", OPTIONAL_SOURCE_CANDIDATES["visual_columns"]),
    )


def load_neuron_registry(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    _require_columns(df, ["root_id", "project_role", "snapshot_version", "materialization_version"], Path(path))
    df["root_id"] = _normalize_int_series(df["root_id"], "root_id")
    return df


def load_connectivity_registry(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    _require_columns(df, ["pre_root_id", "post_root_id", "syn_count"], Path(path))
    df["pre_root_id"] = _normalize_int_series(df["pre_root_id"], "pre_root_id")
    df["post_root_id"] = _normalize_int_series(df["post_root_id"], "post_root_id")
    df["syn_count"] = _normalize_int_series(df["syn_count"], "syn_count")
    return df


def build_registry(cfg: dict[str, Any]) -> dict[str, Any]:
    source_paths = resolve_registry_source_paths(cfg)
    paths_cfg = cfg.get("paths", {})
    registry_cfg = cfg.get("registry", {})

    neuron_registry_path = Path(paths_cfg.get("neuron_registry_csv", "data/interim/registry/neuron_registry.csv"))
    connectivity_registry_path = Path(
        paths_cfg.get("connectivity_registry_csv", "data/interim/registry/connectivity_registry.csv")
    )
    provenance_path = Path(paths_cfg.get("registry_provenance_json", "data/interim/registry/registry_provenance.json"))

    snapshot_version = str(
        registry_cfg.get("snapshot_version")
        or cfg.get("dataset", {}).get("codex_snapshot_version")
        or cfg.get("dataset", {}).get("materialization_version")
        or DEFAULT_DATA_SNAPSHOT_VERSION
    )
    materialization_version = str(cfg.get("dataset", {}).get("materialization_version", snapshot_version))
    project_role_rules = _resolve_project_role_rules(registry_cfg.get("project_roles", {}))

    classification_df = _load_classification_table(source_paths.classification)
    cell_types_df = _load_cell_types_table(source_paths.cell_types)
    nt_df = _load_nt_predictions_table(source_paths.nt_predictions)
    connections_df = _load_connections_table(source_paths.connections)
    visual_annotations_df = _load_visual_annotations_table(source_paths.visual_annotations)
    visual_columns_df = _load_visual_columns_table(source_paths.visual_columns)

    neuron_registry = _build_neuron_registry(
        classification_df=classification_df,
        cell_types_df=cell_types_df,
        nt_df=nt_df,
        connections_df=connections_df,
        visual_annotations_df=visual_annotations_df,
        visual_columns_df=visual_columns_df,
        source_paths=source_paths,
        snapshot_version=snapshot_version,
        materialization_version=materialization_version,
        project_role_rules=project_role_rules,
    )
    connectivity_registry = _build_connectivity_registry(
        connections_df=connections_df,
        source_paths=source_paths,
        snapshot_version=snapshot_version,
        materialization_version=materialization_version,
    )

    ensure_dir(neuron_registry_path.parent)
    ensure_dir(connectivity_registry_path.parent)
    ensure_dir(provenance_path.parent)
    neuron_registry.to_csv(neuron_registry_path, index=False)
    connectivity_registry.to_csv(connectivity_registry_path, index=False)

    provenance = _build_provenance_payload(
        source_paths=source_paths,
        neuron_registry_path=neuron_registry_path,
        connectivity_registry_path=connectivity_registry_path,
        snapshot_version=snapshot_version,
        materialization_version=materialization_version,
        project_role_rules=project_role_rules,
    )
    write_json(provenance, provenance_path)

    return {
        "snapshot_version": snapshot_version,
        "materialization_version": materialization_version,
        "neuron_registry_path": str(neuron_registry_path),
        "connectivity_registry_path": str(connectivity_registry_path),
        "provenance_path": str(provenance_path),
        "neuron_count": int(len(neuron_registry)),
        "connection_count": int(len(connectivity_registry)),
        "missing_optional_sources": sorted(
            name
            for name, path in {
                "cell_types": source_paths.cell_types,
                "nt_predictions": source_paths.nt_predictions,
                "connections": source_paths.connections,
                "visual_annotations": source_paths.visual_annotations,
                "visual_columns": source_paths.visual_columns,
            }.items()
            if path is None
        ),
    }


def _resolve_optional_path(
    paths_cfg: dict[str, Any],
    raw_dir: Path,
    override_key: str,
    candidate_names: list[str],
) -> Path | None:
    if override_key in paths_cfg:
        override = paths_cfg[override_key]
        candidate = Path(override)
        if candidate.exists():
            return candidate
        raise FileNotFoundError(
            f"Config override paths.{override_key} points to a missing file: {candidate}"
        )

    for name in candidate_names:
        candidate = raw_dir / name
        if candidate.exists():
            return candidate
    return None


def _load_classification_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = get_classification_file_columns()
    _require_columns(df, expected, path)
    df = df.loc[:, expected].copy()
    df["root_id"] = _normalize_int_series(df["root_id"], "root_id")
    for column in expected:
        if column != "root_id":
            df[column] = _clean_text_series(df[column])
    df = df.drop_duplicates(subset=["root_id"]).reset_index(drop=True)
    df["has_classification_source"] = True
    return df


def _load_cell_types_table(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame(columns=["root_id", "primary_type", "additional_types", "has_cell_types_source"])
    df = pd.read_csv(path)
    expected = get_cell_types_file_columns()
    _require_columns(df, expected, path)
    df = df.loc[:, expected].rename(columns={"additional_type(s)": "additional_types"}).copy()
    df["root_id"] = _normalize_int_series(df["root_id"], "root_id")
    df["primary_type"] = _clean_text_series(df["primary_type"])
    df["additional_types"] = _clean_text_series(df["additional_types"])
    df = df.drop_duplicates(subset=["root_id"]).reset_index(drop=True)
    df["has_cell_types_source"] = True
    return df


def _load_nt_predictions_table(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame(columns=["root_id", "group", "nt_type", "nt_type_score", "has_nt_predictions_source"])
    df = pd.read_csv(path)
    expected = get_neurons_file_columns()
    _require_columns(df, expected, path)
    keep_columns = ["root_id", "group", "nt_type", "nt_type_score"]
    df = df.loc[:, keep_columns].copy()
    df["root_id"] = _normalize_int_series(df["root_id"], "root_id")
    df["group"] = _clean_text_series(df["group"])
    df["nt_type"] = _clean_text_series(df["nt_type"]).str.upper()
    df["nt_type_score"] = pd.to_numeric(df["nt_type_score"], errors="coerce")
    df = df.drop_duplicates(subset=["root_id"]).reset_index(drop=True)
    df["has_nt_predictions_source"] = True
    return df


def _load_connections_table(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame(
            columns=[
                "pre_root_id",
                "post_root_id",
                "neuropil",
                "syn_count",
                "nt_type",
                "has_connections_source",
            ]
        )
    df = pd.read_csv(path)
    expected = get_connections_file_columns()
    _require_columns(df, expected, path)
    df = df.loc[:, expected].copy()
    df["pre_root_id"] = _normalize_int_series(df["pre_root_id"], "pre_root_id")
    df["post_root_id"] = _normalize_int_series(df["post_root_id"], "post_root_id")
    df["neuropil"] = _clean_text_series(df["neuropil"])
    df["syn_count"] = _normalize_int_series(df["syn_count"], "syn_count")
    df["nt_type"] = _clean_text_series(df["nt_type"]).str.upper()
    df["has_connections_source"] = True
    return df


def _load_visual_annotations_table(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame(
            columns=[
                "root_id",
                "visual_type",
                "family",
                "subsystem",
                "category",
                "visual_side",
                "has_visual_annotations_source",
            ]
        )
    df = pd.read_csv(path)
    _require_columns(df, VISUAL_ANNOTATION_COLUMNS, path)
    df = df.loc[:, VISUAL_ANNOTATION_COLUMNS].rename(
        columns={"type": "visual_type", "side": "visual_side"}
    )
    df["root_id"] = _normalize_int_series(df["root_id"], "root_id")
    for column in ["visual_type", "family", "subsystem", "category", "visual_side"]:
        df[column] = _clean_text_series(df[column])
    df = df.drop_duplicates(subset=["root_id"]).reset_index(drop=True)
    df["has_visual_annotations_source"] = True
    return df


def _load_visual_columns_table(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame(
            columns=[
                "root_id",
                "hemisphere",
                "column_type",
                "column_id",
                "column_x",
                "column_y",
                "column_p",
                "column_q",
                "has_visual_columns_source",
            ]
        )
    df = pd.read_csv(path)
    _require_columns(df, VISUAL_COLUMN_COLUMNS, path)
    df = df.loc[:, VISUAL_COLUMN_COLUMNS].rename(
        columns={
            "type": "column_type",
            "x": "column_x",
            "y": "column_y",
            "p": "column_p",
            "q": "column_q",
        }
    )
    df["root_id"] = _normalize_int_series(df["root_id"], "root_id")
    df["hemisphere"] = _clean_text_series(df["hemisphere"])
    df["column_type"] = _clean_text_series(df["column_type"])
    for column in ["column_id", "column_x", "column_y", "column_p", "column_q"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")
    df = df.drop_duplicates(subset=["root_id"]).reset_index(drop=True)
    df["has_visual_columns_source"] = True
    return df


def _build_neuron_registry(
    *,
    classification_df: pd.DataFrame,
    cell_types_df: pd.DataFrame,
    nt_df: pd.DataFrame,
    connections_df: pd.DataFrame,
    visual_annotations_df: pd.DataFrame,
    visual_columns_df: pd.DataFrame,
    source_paths: RegistrySourcePaths,
    snapshot_version: str,
    materialization_version: str,
    project_role_rules: dict[str, list[str]],
) -> pd.DataFrame:
    root_id_frames = [
        classification_df[["root_id"]],
        cell_types_df[["root_id"]],
        nt_df[["root_id"]],
        visual_annotations_df[["root_id"]],
        visual_columns_df[["root_id"]],
    ]
    if not connections_df.empty:
        root_id_frames.extend(
            [
                connections_df[["pre_root_id"]].rename(columns={"pre_root_id": "root_id"}),
                connections_df[["post_root_id"]].rename(columns={"post_root_id": "root_id"}),
            ]
        )

    root_ids = pd.concat(root_id_frames, ignore_index=True)
    root_ids = root_ids.dropna(subset=["root_id"]).drop_duplicates().sort_values("root_id").reset_index(drop=True)

    registry = root_ids.merge(classification_df, on="root_id", how="left")
    registry = registry.merge(cell_types_df, on="root_id", how="left")
    registry = registry.merge(nt_df, on="root_id", how="left")
    registry = registry.merge(visual_annotations_df, on="root_id", how="left")
    registry = registry.merge(visual_columns_df, on="root_id", how="left")
    registry = registry.merge(_aggregate_neuropils(connections_df), on="root_id", how="left")
    registry = registry.merge(_connections_membership(connections_df), on="root_id", how="left")

    for column in ROOT_SOURCE_COLUMNS:
        if column not in registry.columns:
            registry[column] = False
        registry[column] = registry[column].astype("boolean").fillna(False).astype(bool)

    registry["cell_type"] = _first_non_empty(registry, ["primary_type", "visual_type", "column_type"])
    registry["resolved_type"] = _first_non_empty(
        registry,
        ["cell_type", "sub_class", "class", "super_class"],
    )
    registry["side"] = _first_non_empty(registry, ["side", "visual_side", "hemisphere"])
    registry["proofread_status"] = pd.Series("proofread", index=registry.index, dtype="string")
    registry["snapshot_version"] = pd.Series(snapshot_version, index=registry.index, dtype="string")
    registry["materialization_version"] = pd.Series(materialization_version, index=registry.index, dtype="string")
    registry["project_role"] = _assign_project_roles(registry, project_role_rules)

    source_file_map = {
        "has_classification_source": source_paths.classification.name,
        "has_cell_types_source": source_paths.cell_types.name if source_paths.cell_types else None,
        "has_nt_predictions_source": source_paths.nt_predictions.name if source_paths.nt_predictions else None,
        "has_visual_annotations_source": source_paths.visual_annotations.name if source_paths.visual_annotations else None,
        "has_visual_columns_source": source_paths.visual_columns.name if source_paths.visual_columns else None,
        "has_connections_source": source_paths.connections.name if source_paths.connections else None,
    }
    registry["source_file"] = registry.apply(
        lambda row: _join_unique(
            source_file_map[column]
            for column in ROOT_SOURCE_COLUMNS
            if bool(row[column]) and source_file_map[column]
        ),
        axis=1,
    )

    registry = registry.drop(columns=[column for column in ROOT_SOURCE_COLUMNS if column in registry.columns])
    if "visual_side" in registry.columns:
        registry = registry.drop(columns=["visual_side"])
    if "column_type" in registry.columns:
        registry = registry.drop(columns=["column_type"])

    for column in NEURON_REGISTRY_COLUMNS:
        if column not in registry.columns:
            registry[column] = pd.NA

    registry = registry.loc[:, NEURON_REGISTRY_COLUMNS].sort_values("root_id").reset_index(drop=True)
    return registry


def _build_connectivity_registry(
    *,
    connections_df: pd.DataFrame,
    source_paths: RegistrySourcePaths,
    snapshot_version: str,
    materialization_version: str,
) -> pd.DataFrame:
    if connections_df.empty:
        return pd.DataFrame(columns=CONNECTIVITY_REGISTRY_COLUMNS)

    registry = connections_df.loc[:, ["pre_root_id", "post_root_id", "neuropil", "syn_count", "nt_type"]].copy()
    registry["snapshot_version"] = pd.Series(snapshot_version, index=registry.index, dtype="string")
    registry["materialization_version"] = pd.Series(materialization_version, index=registry.index, dtype="string")
    registry["source_file"] = pd.Series(source_paths.connections.name if source_paths.connections else "", index=registry.index)
    return registry.loc[:, CONNECTIVITY_REGISTRY_COLUMNS]


def _aggregate_neuropils(connections_df: pd.DataFrame) -> pd.DataFrame:
    if connections_df.empty:
        return pd.DataFrame(columns=["root_id", "input_neuropils", "output_neuropils", "neuropils"])

    outgoing = (
        connections_df.groupby("pre_root_id")["neuropil"]
        .agg(_join_unique)
        .reset_index()
        .rename(columns={"pre_root_id": "root_id", "neuropil": "output_neuropils"})
    )
    incoming = (
        connections_df.groupby("post_root_id")["neuropil"]
        .agg(_join_unique)
        .reset_index()
        .rename(columns={"post_root_id": "root_id", "neuropil": "input_neuropils"})
    )
    merged = outgoing.merge(incoming, on="root_id", how="outer")
    merged["neuropils"] = merged.apply(
        lambda row: _join_unique_from_joined_values(row.get("input_neuropils"), row.get("output_neuropils")),
        axis=1,
    )
    return merged


def _connections_membership(connections_df: pd.DataFrame) -> pd.DataFrame:
    if connections_df.empty:
        return pd.DataFrame(columns=["root_id", "has_connections_source"])

    root_ids = pd.concat(
        [
            connections_df[["pre_root_id"]].rename(columns={"pre_root_id": "root_id"}),
            connections_df[["post_root_id"]].rename(columns={"post_root_id": "root_id"}),
        ],
        ignore_index=True,
    )
    root_ids = root_ids.drop_duplicates().reset_index(drop=True)
    root_ids["has_connections_source"] = True
    return root_ids


def _resolve_project_role_rules(config_rules: dict[str, Any]) -> dict[str, list[str]]:
    resolved = {role: list(values) for role, values in DEFAULT_PROJECT_ROLE_RULES.items()}
    for role, values in (config_rules or {}).items():
        if role not in resolved:
            raise ValueError(f"Unknown registry project role: {role}")
        if not isinstance(values, list):
            raise ValueError(f"registry.project_roles.{role} must be a list of labels.")
        resolved[role] = [str(value).strip() for value in values if str(value).strip()]
    return resolved


def _assign_project_roles(df: pd.DataFrame, project_role_rules: dict[str, list[str]]) -> pd.Series:
    role_series = pd.Series(ROLE_CONTEXT_ONLY, index=df.index, dtype="string")
    match_columns = ["cell_type", "resolved_type", "primary_type", "visual_type", "class", "sub_class"]

    for role in ROLE_PRIORITY:
        labels = {label.lower() for label in project_role_rules.get(role, [])}
        if not labels:
            continue
        mask = pd.Series(False, index=df.index)
        for column in match_columns:
            if column not in df.columns:
                continue
            mask = mask | df[column].fillna("").astype(str).str.lower().isin(labels)
        role_series = role_series.mask(mask & role_series.eq(ROLE_CONTEXT_ONLY), role)

    return role_series


def _build_provenance_payload(
    *,
    source_paths: RegistrySourcePaths,
    neuron_registry_path: Path,
    connectivity_registry_path: Path,
    snapshot_version: str,
    materialization_version: str,
    project_role_rules: dict[str, list[str]],
) -> dict[str, Any]:
    input_files = {
        name: _file_provenance(path)
        for name, path in {
            "classification": source_paths.classification,
            "cell_types": source_paths.cell_types,
            "nt_predictions": source_paths.nt_predictions,
            "connections": source_paths.connections,
            "visual_annotations": source_paths.visual_annotations,
            "visual_columns": source_paths.visual_columns,
        }.items()
    }
    return {
        "built_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "snapshot_version": snapshot_version,
        "materialization_version": materialization_version,
        "proofread_status_semantics": (
            "Derived from FlyWire Codex snapshot membership. Vendored Codex FAQ states that static "
            "Codex releases include only cells marked as proofread."
        ),
        "project_role_rules": project_role_rules,
        "inputs": input_files,
        "outputs": {
            "neuron_registry": str(neuron_registry_path),
            "connectivity_registry": str(connectivity_registry_path),
        },
    }


def _file_provenance(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None

    df = pd.read_csv(path, nrows=5)
    stat = path.stat()
    return {
        "path": str(path),
        "size_bytes": int(stat.st_size),
        "sha256": _sha256_file(path),
        "column_names": list(df.columns),
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat(),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_columns(df: pd.DataFrame, required_columns: list[str], path: Path) -> None:
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")


def _normalize_int_series(series: pd.Series, column_name: str) -> pd.Series:
    normalized = pd.to_numeric(series, errors="coerce")
    invalid = series[normalized.isna() & series.notna()]
    if not invalid.empty:
        sample = invalid.astype(str).head(5).tolist()
        raise ValueError(f"Column {column_name} contains non-numeric values: {sample}")
    return normalized.astype("Int64")


def _clean_text_series(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip()
    return cleaned.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})


def _first_non_empty(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    result = pd.Series(pd.NA, index=df.index, dtype="string")
    for column in columns:
        if column not in df.columns:
            continue
        result = result.fillna(_clean_text_series(df[column]))
    return result


def _join_unique(values: Any) -> str:
    items = [str(value).strip() for value in values if pd.notna(value) and str(value).strip()]
    return ";".join(sorted(dict.fromkeys(items)))


def _join_unique_from_joined_values(*joined_values: Any) -> str:
    values: list[str] = []
    for joined in joined_values:
        if pd.isna(joined) or not str(joined).strip():
            continue
        values.extend(part for part in str(joined).split(";") if part)
    return _join_unique(values)
