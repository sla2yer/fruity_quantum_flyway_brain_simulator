from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import write_json


STIMULUS_BUNDLE_CONTRACT_VERSION = "stimulus_bundle.v1"
STIMULUS_BUNDLE_DESIGN_NOTE = "docs/stimulus_bundle_design.md"
STIMULUS_BUNDLE_DESIGN_NOTE_VERSION = "stimulus_design_note.v1"

DEFAULT_PROCESSED_STIMULUS_DIR = Path("data/processed/stimuli")

PROCEDURAL_DESCRIPTOR_ONLY = "procedural_descriptor_only"
CACHED_FRAME_BUNDLE = "cached_frame_bundle"
HYBRID_DESCRIPTOR_PLUS_CACHE = "hybrid_descriptor_plus_cache"
SUPPORTED_REPRESENTATION_FAMILIES = (
    PROCEDURAL_DESCRIPTOR_ONLY,
    CACHED_FRAME_BUNDLE,
    HYBRID_DESCRIPTOR_PLUS_CACHE,
)
DEFAULT_REPRESENTATION_FAMILY = HYBRID_DESCRIPTOR_PLUS_CACHE

METADATA_JSON_KEY = "metadata_json"
FRAME_CACHE_KEY = "frame_cache"
PREVIEW_GIF_KEY = "preview_gif"

ASSET_STATUS_READY = "ready"
ASSET_STATUS_MISSING = "missing"
ASSET_STATUS_SKIPPED = "skipped"
SUPPORTED_ASSET_STATUSES = (
    ASSET_STATUS_READY,
    ASSET_STATUS_MISSING,
    ASSET_STATUS_SKIPPED,
)

DEFAULT_HASH_ALGORITHM = "sha256"
DEFAULT_RNG_FAMILY = "numpy_pcg64"
SAMPLE_HOLD_SAMPLING_MODE = "sample_hold"
SUPPORTED_SAMPLING_MODES = (SAMPLE_HOLD_SAMPLING_MODE,)
DEFAULT_TIME_UNIT = "ms"

DEFAULT_SPATIAL_FRAME_NAME = "visual_field_degrees_centered"
DEFAULT_X_AXIS = "azimuth_deg_positive_right"
DEFAULT_Y_AXIS = "elevation_deg_positive_up"
DEFAULT_ORIGIN = "aperture_center"
DEFAULT_PIXEL_ORIGIN = "pixel_centers"

DEFAULT_LUMINANCE_ENCODING = "linear_luminance_unit_interval"
DEFAULT_CONTRAST_SEMANTICS = "signed_delta_from_neutral_gray"
DEFAULT_POSITIVE_POLARITY = "brighter_than_neutral"
DEFAULT_NEUTRAL_LUMINANCE = 0.5
DEFAULT_MIN_LUMINANCE = 0.0
DEFAULT_MAX_LUMINANCE = 1.0

_IDENTIFIER_RE = re.compile(r"[^a-z0-9._-]+")
_HEX_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class StimulusContractPaths:
    processed_stimulus_dir: Path
    bundle_root_directory: Path
    alias_root_directory: Path


@dataclass(frozen=True)
class StimulusBundlePaths:
    stimulus_family: str
    stimulus_name: str
    parameter_hash: str
    bundle_directory: Path
    metadata_json_path: Path
    frame_cache_path: Path
    preview_gif_path: Path

    @property
    def bundle_id(self) -> str:
        return (
            f"{STIMULUS_BUNDLE_CONTRACT_VERSION}:"
            f"{self.stimulus_family}:{self.stimulus_name}:{self.parameter_hash}"
        )

    def asset_paths(self) -> dict[str, Path]:
        return {
            METADATA_JSON_KEY: self.metadata_json_path,
            FRAME_CACHE_KEY: self.frame_cache_path,
            PREVIEW_GIF_KEY: self.preview_gif_path,
        }


def build_stimulus_contract_paths(
    processed_stimulus_dir: str | Path = DEFAULT_PROCESSED_STIMULUS_DIR,
) -> StimulusContractPaths:
    stimulus_dir = Path(processed_stimulus_dir).resolve()
    return StimulusContractPaths(
        processed_stimulus_dir=stimulus_dir,
        bundle_root_directory=stimulus_dir / "bundles",
        alias_root_directory=stimulus_dir / "aliases",
    )


def build_stimulus_bundle_paths(
    *,
    stimulus_family: str,
    stimulus_name: str,
    processed_stimulus_dir: str | Path = DEFAULT_PROCESSED_STIMULUS_DIR,
    parameter_hash: str | None = None,
    parameter_snapshot: Mapping[str, Any] | None = None,
    seed: int | str | None = None,
    temporal_sampling: Mapping[str, Any] | None = None,
    spatial_frame: Mapping[str, Any] | None = None,
    luminance_convention: Mapping[str, Any] | None = None,
    rng_family: str = DEFAULT_RNG_FAMILY,
) -> StimulusBundlePaths:
    normalized_family = _normalize_identifier(stimulus_family, field_name="stimulus_family")
    normalized_name = _normalize_identifier(stimulus_name, field_name="stimulus_name")
    resolved_parameter_hash = _resolve_parameter_hash(
        parameter_hash=parameter_hash,
        parameter_snapshot=parameter_snapshot,
        seed=seed,
        temporal_sampling=temporal_sampling,
        spatial_frame=spatial_frame,
        luminance_convention=luminance_convention,
        rng_family=rng_family,
    )
    contract_paths = build_stimulus_contract_paths(processed_stimulus_dir)
    bundle_directory = (
        contract_paths.bundle_root_directory
        / normalized_family
        / normalized_name
        / resolved_parameter_hash
    )
    return StimulusBundlePaths(
        stimulus_family=normalized_family,
        stimulus_name=normalized_name,
        parameter_hash=resolved_parameter_hash,
        bundle_directory=bundle_directory,
        metadata_json_path=bundle_directory / "stimulus_bundle.json",
        frame_cache_path=bundle_directory / "stimulus_frames.npz",
        preview_gif_path=bundle_directory / "stimulus_preview.gif",
    )


def build_stimulus_alias_path(
    *,
    stimulus_family: str,
    stimulus_name: str,
    parameter_hash: str,
    processed_stimulus_dir: str | Path = DEFAULT_PROCESSED_STIMULUS_DIR,
) -> Path:
    normalized_family = _normalize_identifier(stimulus_family, field_name="stimulus_family")
    normalized_name = _normalize_identifier(stimulus_name, field_name="stimulus_name")
    normalized_hash = _normalize_parameter_hash(parameter_hash)
    contract_paths = build_stimulus_contract_paths(processed_stimulus_dir)
    return (
        contract_paths.alias_root_directory
        / normalized_family
        / normalized_name
        / f"{normalized_hash}.json"
    )


def build_stimulus_contract_manifest_metadata(
    *,
    processed_stimulus_dir: str | Path = DEFAULT_PROCESSED_STIMULUS_DIR,
) -> dict[str, Any]:
    contract_paths = build_stimulus_contract_paths(processed_stimulus_dir)
    return {
        "version": STIMULUS_BUNDLE_CONTRACT_VERSION,
        "design_note": STIMULUS_BUNDLE_DESIGN_NOTE,
        "design_note_version": STIMULUS_BUNDLE_DESIGN_NOTE_VERSION,
        "default_representation_family": DEFAULT_REPRESENTATION_FAMILY,
        "supported_representation_families": list(SUPPORTED_REPRESENTATION_FAMILIES),
        "default_time_unit": DEFAULT_TIME_UNIT,
        "supported_sampling_modes": list(SUPPORTED_SAMPLING_MODES),
        "default_rng_family": DEFAULT_RNG_FAMILY,
        "bundle_root_directory": str(contract_paths.bundle_root_directory),
        "alias_root_directory": str(contract_paths.alias_root_directory),
    }


def build_stimulus_parameter_hash(
    *,
    parameter_snapshot: Mapping[str, Any],
    seed: int | str,
    temporal_sampling: Mapping[str, Any],
    spatial_frame: Mapping[str, Any],
    luminance_convention: Mapping[str, Any] | None = None,
    rng_family: str = DEFAULT_RNG_FAMILY,
) -> str:
    reproducibility_payload = {
        "parameter_snapshot": _normalize_json_mapping(
            parameter_snapshot,
            field_name="parameter_snapshot",
        ),
        "determinism": {
            "seed": _normalize_seed(seed),
            "rng_family": _normalize_nonempty_string(rng_family, field_name="rng_family"),
        },
        "temporal_sampling": normalize_temporal_sampling(temporal_sampling),
        "spatial_frame": normalize_spatial_frame(spatial_frame),
        "luminance_convention": normalize_luminance_convention(luminance_convention),
    }
    serialized = json.dumps(
        reproducibility_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_stimulus_bundle_metadata(
    *,
    stimulus_family: str,
    stimulus_name: str,
    parameter_snapshot: Mapping[str, Any],
    seed: int | str,
    temporal_sampling: Mapping[str, Any],
    spatial_frame: Mapping[str, Any],
    processed_stimulus_dir: str | Path = DEFAULT_PROCESSED_STIMULUS_DIR,
    luminance_convention: Mapping[str, Any] | None = None,
    representation_family: str = DEFAULT_REPRESENTATION_FAMILY,
    frame_cache_status: str = ASSET_STATUS_MISSING,
    preview_gif_status: str = ASSET_STATUS_MISSING,
    compatibility_aliases: Sequence[Mapping[str, Any]] | None = None,
    rng_family: str = DEFAULT_RNG_FAMILY,
) -> dict[str, Any]:
    normalized_representation_family = _normalize_representation_family(representation_family)
    normalized_temporal_sampling = normalize_temporal_sampling(temporal_sampling)
    normalized_spatial_frame = normalize_spatial_frame(spatial_frame)
    normalized_luminance_convention = normalize_luminance_convention(luminance_convention)
    normalized_parameter_snapshot = _normalize_json_mapping(
        parameter_snapshot,
        field_name="parameter_snapshot",
    )
    normalized_seed = _normalize_seed(seed)
    normalized_rng_family = _normalize_nonempty_string(rng_family, field_name="rng_family")
    parameter_hash = build_stimulus_parameter_hash(
        parameter_snapshot=normalized_parameter_snapshot,
        seed=normalized_seed,
        temporal_sampling=normalized_temporal_sampling,
        spatial_frame=normalized_spatial_frame,
        luminance_convention=normalized_luminance_convention,
        rng_family=normalized_rng_family,
    )
    bundle_paths = build_stimulus_bundle_paths(
        stimulus_family=stimulus_family,
        stimulus_name=stimulus_name,
        processed_stimulus_dir=processed_stimulus_dir,
        parameter_hash=parameter_hash,
    )
    normalized_aliases = _normalize_compatibility_aliases(
        compatibility_aliases,
        processed_stimulus_dir=processed_stimulus_dir,
        parameter_hash=parameter_hash,
        canonical_family=bundle_paths.stimulus_family,
        canonical_name=bundle_paths.stimulus_name,
    )
    return {
        "contract_version": STIMULUS_BUNDLE_CONTRACT_VERSION,
        "design_note": STIMULUS_BUNDLE_DESIGN_NOTE,
        "design_note_version": STIMULUS_BUNDLE_DESIGN_NOTE_VERSION,
        "bundle_id": bundle_paths.bundle_id,
        "representation_family": normalized_representation_family,
        "stimulus_family": bundle_paths.stimulus_family,
        "stimulus_name": bundle_paths.stimulus_name,
        "parameter_hash": parameter_hash,
        "parameter_hash_algorithm": DEFAULT_HASH_ALGORITHM,
        "parameter_snapshot": normalized_parameter_snapshot,
        "determinism": {
            "seed": normalized_seed,
            "rng_family": normalized_rng_family,
            "seed_scope": "all_stochastic_generator_branches",
        },
        "spatial_frame": normalized_spatial_frame,
        "temporal_sampling": normalized_temporal_sampling,
        "luminance_convention": normalized_luminance_convention,
        "replay": {
            "time_unit": DEFAULT_TIME_UNIT,
            "sampling_mode": SAMPLE_HOLD_SAMPLING_MODE,
            "authoritative_source": "descriptor_metadata",
            "cache_policy": "cache_optional_descriptor_authoritative",
            "frame_cache_format": "npz_frames_y_x_timestamps_ms",
        },
        "compatibility_aliases": normalized_aliases,
        "assets": {
            METADATA_JSON_KEY: {
                "path": str(bundle_paths.metadata_json_path),
                "status": ASSET_STATUS_READY,
            },
            FRAME_CACHE_KEY: {
                "path": str(bundle_paths.frame_cache_path),
                "status": _normalize_asset_status(frame_cache_status, field_name="frame_cache_status"),
            },
            PREVIEW_GIF_KEY: {
                "path": str(bundle_paths.preview_gif_path),
                "status": _normalize_asset_status(preview_gif_status, field_name="preview_gif_status"),
            },
        },
    }


def build_stimulus_bundle_reference(bundle_metadata: Mapping[str, Any]) -> dict[str, Any]:
    normalized = parse_stimulus_bundle_metadata(bundle_metadata)
    return {
        "contract_version": normalized["contract_version"],
        "stimulus_family": normalized["stimulus_family"],
        "stimulus_name": normalized["stimulus_name"],
        "parameter_hash": normalized["parameter_hash"],
        "bundle_id": normalized["bundle_id"],
    }


def build_stimulus_alias_records(
    bundle_metadata: Mapping[str, Any],
    *,
    metadata_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    normalized = parse_stimulus_bundle_metadata(bundle_metadata)
    resolved_metadata_path = (
        Path(metadata_path).resolve()
        if metadata_path is not None
        else Path(normalized["assets"][METADATA_JSON_KEY]["path"]).resolve()
    )
    alias_records: list[dict[str, Any]] = []
    for alias in normalized["compatibility_aliases"]:
        alias_records.append(
            {
                "contract_version": STIMULUS_BUNDLE_CONTRACT_VERSION,
                "stimulus_family": alias["stimulus_family"],
                "stimulus_name": alias["stimulus_name"],
                "parameter_hash": normalized["parameter_hash"],
                "bundle_id": normalized["bundle_id"],
                "bundle_metadata_path": str(resolved_metadata_path),
                "path": alias["path"],
            }
        )
    return alias_records


def parse_stimulus_bundle_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Stimulus bundle metadata must be a mapping.")

    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "bundle_id",
        "representation_family",
        "stimulus_family",
        "stimulus_name",
        "parameter_hash",
        "parameter_hash_algorithm",
        "parameter_snapshot",
        "determinism",
        "spatial_frame",
        "temporal_sampling",
        "luminance_convention",
        "replay",
        "compatibility_aliases",
        "assets",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"Stimulus bundle metadata is missing required fields: {missing_fields}")
    if normalized["contract_version"] != STIMULUS_BUNDLE_CONTRACT_VERSION:
        raise ValueError(
            "Stimulus bundle metadata contract_version does not match "
            f"{STIMULUS_BUNDLE_CONTRACT_VERSION!r}."
        )
    normalized["representation_family"] = _normalize_representation_family(
        normalized["representation_family"]
    )
    normalized["stimulus_family"] = _normalize_identifier(
        normalized["stimulus_family"],
        field_name="stimulus_family",
    )
    normalized["stimulus_name"] = _normalize_identifier(
        normalized["stimulus_name"],
        field_name="stimulus_name",
    )
    normalized["parameter_hash"] = _normalize_parameter_hash(normalized["parameter_hash"])
    normalized["parameter_hash_algorithm"] = _normalize_nonempty_string(
        normalized["parameter_hash_algorithm"],
        field_name="parameter_hash_algorithm",
    )
    if normalized["parameter_hash_algorithm"] != DEFAULT_HASH_ALGORITHM:
        raise ValueError(
            "Unsupported stimulus parameter_hash_algorithm "
            f"{normalized['parameter_hash_algorithm']!r}."
        )
    normalized["parameter_snapshot"] = _normalize_json_mapping(
        normalized["parameter_snapshot"],
        field_name="parameter_snapshot",
    )
    normalized["determinism"] = _normalize_determinism_payload(normalized["determinism"])
    normalized["spatial_frame"] = normalize_spatial_frame(normalized["spatial_frame"])
    normalized["temporal_sampling"] = normalize_temporal_sampling(normalized["temporal_sampling"])
    normalized["luminance_convention"] = normalize_luminance_convention(
        normalized["luminance_convention"]
    )
    normalized["replay"] = _normalize_replay_payload(normalized["replay"])
    normalized["compatibility_aliases"] = _normalize_serialized_aliases(
        normalized["compatibility_aliases"],
        parameter_hash=normalized["parameter_hash"],
        canonical_family=normalized["stimulus_family"],
        canonical_name=normalized["stimulus_name"],
    )
    normalized["assets"] = _normalize_asset_payloads(normalized["assets"])
    expected_bundle_id = (
        f"{STIMULUS_BUNDLE_CONTRACT_VERSION}:"
        f"{normalized['stimulus_family']}:{normalized['stimulus_name']}:{normalized['parameter_hash']}"
    )
    if normalized["bundle_id"] != expected_bundle_id:
        raise ValueError(
            "Stimulus bundle metadata bundle_id does not match the canonical "
            "family/name/hash tuple."
        )
    return normalized


def parse_stimulus_alias_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Stimulus alias record must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "stimulus_family",
        "stimulus_name",
        "parameter_hash",
        "bundle_id",
        "bundle_metadata_path",
        "path",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"Stimulus alias record is missing required fields: {missing_fields}")
    if normalized["contract_version"] != STIMULUS_BUNDLE_CONTRACT_VERSION:
        raise ValueError(
            "Stimulus alias record contract_version does not match "
            f"{STIMULUS_BUNDLE_CONTRACT_VERSION!r}."
        )
    normalized["stimulus_family"] = _normalize_identifier(
        normalized["stimulus_family"],
        field_name="stimulus_family",
    )
    normalized["stimulus_name"] = _normalize_identifier(
        normalized["stimulus_name"],
        field_name="stimulus_name",
    )
    normalized["parameter_hash"] = _normalize_parameter_hash(normalized["parameter_hash"])
    normalized["bundle_id"] = _normalize_nonempty_string(
        normalized["bundle_id"],
        field_name="bundle_id",
    )
    normalized["bundle_metadata_path"] = str(Path(normalized["bundle_metadata_path"]).resolve())
    normalized["path"] = str(Path(normalized["path"]).resolve())
    return normalized


def load_stimulus_bundle_metadata(metadata_path: str | Path) -> dict[str, Any]:
    path = Path(metadata_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_stimulus_bundle_metadata(payload)


def load_stimulus_alias_record(alias_path: str | Path) -> dict[str, Any]:
    path = Path(alias_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_stimulus_alias_record(payload)


def write_stimulus_bundle_metadata(
    bundle_metadata: Mapping[str, Any],
    metadata_path: str | Path | None = None,
    *,
    write_aliases: bool = True,
) -> Path:
    normalized = parse_stimulus_bundle_metadata(bundle_metadata)
    output_path = (
        Path(metadata_path).resolve()
        if metadata_path is not None
        else Path(normalized["assets"][METADATA_JSON_KEY]["path"]).resolve()
    )
    written_path = write_json(normalized, output_path)
    if write_aliases:
        for alias_record in build_stimulus_alias_records(normalized, metadata_path=output_path):
            write_json(alias_record, alias_record["path"])
    return written_path


def discover_stimulus_bundle_paths(record: Mapping[str, Any]) -> dict[str, Path]:
    stimulus_bundle = _extract_stimulus_bundle_mapping(record)
    assets = stimulus_bundle.get("assets")
    if not isinstance(assets, Mapping):
        raise ValueError("Stimulus bundle assets must be a mapping.")

    discovered: dict[str, Path] = {}
    for asset_key in (METADATA_JSON_KEY, FRAME_CACHE_KEY, PREVIEW_GIF_KEY):
        asset_record = assets.get(asset_key)
        if not isinstance(asset_record, Mapping):
            raise ValueError(f"Stimulus asset {asset_key!r} is missing from the bundle metadata.")
        asset_path = asset_record.get("path")
        if not isinstance(asset_path, str) or not asset_path:
            raise ValueError(f"Stimulus asset {asset_key!r} is missing a usable path.")
        discovered[asset_key] = Path(asset_path)
    return discovered


def discover_stimulus_alias_paths(record: Mapping[str, Any]) -> list[Path]:
    stimulus_bundle = _extract_stimulus_bundle_mapping(record)
    compatibility_aliases = stimulus_bundle.get("compatibility_aliases")
    if not isinstance(compatibility_aliases, list):
        raise ValueError("Stimulus bundle compatibility_aliases must be a list.")
    discovered: list[Path] = []
    for alias in compatibility_aliases:
        if not isinstance(alias, Mapping):
            raise ValueError("Stimulus bundle compatibility alias entries must be mappings.")
        alias_path = alias.get("path")
        if not isinstance(alias_path, str) or not alias_path:
            raise ValueError("Stimulus bundle compatibility alias is missing a usable path.")
        discovered.append(Path(alias_path))
    return discovered


def resolve_stimulus_bundle_metadata_path(
    *,
    stimulus_family: str,
    stimulus_name: str,
    processed_stimulus_dir: str | Path = DEFAULT_PROCESSED_STIMULUS_DIR,
    parameter_hash: str | None = None,
    parameter_snapshot: Mapping[str, Any] | None = None,
    seed: int | str | None = None,
    temporal_sampling: Mapping[str, Any] | None = None,
    spatial_frame: Mapping[str, Any] | None = None,
    luminance_convention: Mapping[str, Any] | None = None,
    rng_family: str = DEFAULT_RNG_FAMILY,
) -> Path:
    bundle_paths = build_stimulus_bundle_paths(
        stimulus_family=stimulus_family,
        stimulus_name=stimulus_name,
        processed_stimulus_dir=processed_stimulus_dir,
        parameter_hash=parameter_hash,
        parameter_snapshot=parameter_snapshot,
        seed=seed,
        temporal_sampling=temporal_sampling,
        spatial_frame=spatial_frame,
        luminance_convention=luminance_convention,
        rng_family=rng_family,
    )
    if bundle_paths.metadata_json_path.exists():
        return bundle_paths.metadata_json_path
    alias_path = build_stimulus_alias_path(
        stimulus_family=stimulus_family,
        stimulus_name=stimulus_name,
        parameter_hash=bundle_paths.parameter_hash,
        processed_stimulus_dir=processed_stimulus_dir,
    )
    if alias_path.exists():
        alias_record = load_stimulus_alias_record(alias_path)
        return Path(alias_record["bundle_metadata_path"]).resolve()
    return bundle_paths.metadata_json_path


def normalize_temporal_sampling(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("temporal_sampling must be a mapping.")
    dt_ms = _normalize_positive_float(payload.get("dt_ms"), field_name="temporal_sampling.dt_ms")
    duration_ms = _normalize_positive_float(
        payload.get("duration_ms"),
        field_name="temporal_sampling.duration_ms",
    )
    time_origin_ms = _normalize_float(
        payload.get("time_origin_ms", 0.0),
        field_name="temporal_sampling.time_origin_ms",
    )
    sampling_mode = str(payload.get("sampling_mode", SAMPLE_HOLD_SAMPLING_MODE))
    if sampling_mode not in SUPPORTED_SAMPLING_MODES:
        raise ValueError(
            "Unsupported temporal_sampling.sampling_mode "
            f"{sampling_mode!r}. Supported modes: {list(SUPPORTED_SAMPLING_MODES)!r}."
        )
    frame_count = payload.get("frame_count")
    if frame_count is None:
        inferred_frame_count = duration_ms / dt_ms
        rounded = int(round(inferred_frame_count))
        if not math.isclose(inferred_frame_count, rounded, rel_tol=0.0, abs_tol=1.0e-9):
            raise ValueError(
                "temporal_sampling.duration_ms must be an integer multiple of "
                "temporal_sampling.dt_ms when frame_count is omitted."
            )
        frame_count = rounded
    normalized_frame_count = _normalize_positive_int(
        frame_count,
        field_name="temporal_sampling.frame_count",
    )
    expected_duration = normalized_frame_count * dt_ms
    if not math.isclose(expected_duration, duration_ms, rel_tol=0.0, abs_tol=1.0e-9):
        raise ValueError(
            "temporal_sampling.frame_count * temporal_sampling.dt_ms must equal "
            "temporal_sampling.duration_ms."
        )
    return {
        "time_unit": DEFAULT_TIME_UNIT,
        "time_origin_ms": time_origin_ms,
        "dt_ms": dt_ms,
        "duration_ms": duration_ms,
        "frame_count": normalized_frame_count,
        "sampling_mode": sampling_mode,
    }


def normalize_spatial_frame(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("spatial_frame must be a mapping.")
    frame_name = str(payload.get("frame_name", DEFAULT_SPATIAL_FRAME_NAME))
    if frame_name != DEFAULT_SPATIAL_FRAME_NAME:
        raise ValueError(
            "Unsupported spatial_frame.frame_name "
            f"{frame_name!r}. Supported frame: {DEFAULT_SPATIAL_FRAME_NAME!r}."
        )
    origin = str(payload.get("origin", DEFAULT_ORIGIN))
    if origin != DEFAULT_ORIGIN:
        raise ValueError(
            f"spatial_frame.origin must be {DEFAULT_ORIGIN!r}, got {origin!r}."
        )
    x_axis = str(payload.get("x_axis", DEFAULT_X_AXIS))
    if x_axis != DEFAULT_X_AXIS:
        raise ValueError(
            f"spatial_frame.x_axis must be {DEFAULT_X_AXIS!r}, got {x_axis!r}."
        )
    y_axis = str(payload.get("y_axis", DEFAULT_Y_AXIS))
    if y_axis != DEFAULT_Y_AXIS:
        raise ValueError(
            f"spatial_frame.y_axis must be {DEFAULT_Y_AXIS!r}, got {y_axis!r}."
        )
    pixel_origin = str(payload.get("pixel_origin", DEFAULT_PIXEL_ORIGIN))
    if pixel_origin != DEFAULT_PIXEL_ORIGIN:
        raise ValueError(
            "spatial_frame.pixel_origin must be "
            f"{DEFAULT_PIXEL_ORIGIN!r}, got {pixel_origin!r}."
        )
    return {
        "frame_name": frame_name,
        "origin": origin,
        "x_axis": x_axis,
        "y_axis": y_axis,
        "pixel_origin": pixel_origin,
        "width_px": _normalize_positive_int(
            payload.get("width_px"),
            field_name="spatial_frame.width_px",
        ),
        "height_px": _normalize_positive_int(
            payload.get("height_px"),
            field_name="spatial_frame.height_px",
        ),
        "width_deg": _normalize_positive_float(
            payload.get("width_deg"),
            field_name="spatial_frame.width_deg",
        ),
        "height_deg": _normalize_positive_float(
            payload.get("height_deg"),
            field_name="spatial_frame.height_deg",
        ),
    }


def normalize_luminance_convention(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = {
        "encoding": DEFAULT_LUMINANCE_ENCODING,
        "minimum_value": DEFAULT_MIN_LUMINANCE,
        "neutral_value": DEFAULT_NEUTRAL_LUMINANCE,
        "maximum_value": DEFAULT_MAX_LUMINANCE,
        "contrast_semantics": DEFAULT_CONTRAST_SEMANTICS,
        "positive_polarity": DEFAULT_POSITIVE_POLARITY,
    }
    if payload is None:
        return normalized
    if not isinstance(payload, Mapping):
        raise ValueError("luminance_convention must be a mapping when provided.")
    for key, expected_value in normalized.items():
        value = payload.get(key, expected_value)
        if isinstance(expected_value, float):
            value = _normalize_float(value, field_name=f"luminance_convention.{key}")
            if not math.isclose(value, expected_value, rel_tol=0.0, abs_tol=1.0e-12):
                raise ValueError(
                    f"luminance_convention.{key} must be {expected_value!r}, got {value!r}."
                )
        else:
            if str(value) != str(expected_value):
                raise ValueError(
                    f"luminance_convention.{key} must be {expected_value!r}, got {value!r}."
                )
    return normalized


def _resolve_parameter_hash(
    *,
    parameter_hash: str | None,
    parameter_snapshot: Mapping[str, Any] | None,
    seed: int | str | None,
    temporal_sampling: Mapping[str, Any] | None,
    spatial_frame: Mapping[str, Any] | None,
    luminance_convention: Mapping[str, Any] | None,
    rng_family: str,
) -> str:
    if parameter_hash is not None:
        return _normalize_parameter_hash(parameter_hash)
    missing = [
        field_name
        for field_name, value in (
            ("parameter_snapshot", parameter_snapshot),
            ("seed", seed),
            ("temporal_sampling", temporal_sampling),
            ("spatial_frame", spatial_frame),
        )
        if value is None
    ]
    if missing:
        raise ValueError(
            "parameter_hash was not provided and the following fields are required "
            f"to compute it: {missing}"
        )
    return build_stimulus_parameter_hash(
        parameter_snapshot=parameter_snapshot,
        seed=seed,
        temporal_sampling=temporal_sampling,
        spatial_frame=spatial_frame,
        luminance_convention=luminance_convention,
        rng_family=rng_family,
    )


def _extract_stimulus_bundle_mapping(record: Mapping[str, Any]) -> Mapping[str, Any]:
    stimulus_bundle = record.get("stimulus_bundle")
    if isinstance(stimulus_bundle, Mapping):
        return stimulus_bundle
    return record


def _normalize_representation_family(value: Any) -> str:
    representation_family = _normalize_nonempty_string(
        value,
        field_name="representation_family",
    )
    if representation_family not in SUPPORTED_REPRESENTATION_FAMILIES:
        raise ValueError(
            "Unsupported stimulus representation_family "
            f"{representation_family!r}. Supported families: {list(SUPPORTED_REPRESENTATION_FAMILIES)!r}."
        )
    return representation_family


def _normalize_determinism_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("determinism must be a mapping.")
    return {
        "seed": _normalize_seed(payload.get("seed")),
        "rng_family": _normalize_nonempty_string(
            payload.get("rng_family", DEFAULT_RNG_FAMILY),
            field_name="determinism.rng_family",
        ),
        "seed_scope": _normalize_nonempty_string(
            payload.get("seed_scope", "all_stochastic_generator_branches"),
            field_name="determinism.seed_scope",
        ),
    }


def _normalize_replay_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("replay must be a mapping.")
    time_unit = _normalize_nonempty_string(
        payload.get("time_unit", DEFAULT_TIME_UNIT),
        field_name="replay.time_unit",
    )
    if time_unit != DEFAULT_TIME_UNIT:
        raise ValueError(f"replay.time_unit must be {DEFAULT_TIME_UNIT!r}, got {time_unit!r}.")
    sampling_mode = _normalize_nonempty_string(
        payload.get("sampling_mode", SAMPLE_HOLD_SAMPLING_MODE),
        field_name="replay.sampling_mode",
    )
    if sampling_mode != SAMPLE_HOLD_SAMPLING_MODE:
        raise ValueError(
            f"replay.sampling_mode must be {SAMPLE_HOLD_SAMPLING_MODE!r}, got {sampling_mode!r}."
        )
    return {
        "time_unit": time_unit,
        "sampling_mode": sampling_mode,
        "authoritative_source": _normalize_nonempty_string(
            payload.get("authoritative_source", "descriptor_metadata"),
            field_name="replay.authoritative_source",
        ),
        "cache_policy": _normalize_nonempty_string(
            payload.get("cache_policy", "cache_optional_descriptor_authoritative"),
            field_name="replay.cache_policy",
        ),
        "frame_cache_format": _normalize_nonempty_string(
            payload.get("frame_cache_format", "npz_frames_y_x_timestamps_ms"),
            field_name="replay.frame_cache_format",
        ),
    }


def _normalize_serialized_aliases(
    payload: Any,
    *,
    parameter_hash: str,
    canonical_family: str,
    canonical_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("compatibility_aliases must be a list.")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError("compatibility_aliases entries must be mappings.")
        alias_family = _normalize_identifier(
            item.get("stimulus_family"),
            field_name=f"compatibility_aliases[{index}].stimulus_family",
        )
        alias_name = _normalize_identifier(
            item.get("stimulus_name"),
            field_name=f"compatibility_aliases[{index}].stimulus_name",
        )
        if (alias_family, alias_name) == (canonical_family, canonical_name):
            raise ValueError("compatibility_aliases may not repeat the canonical stimulus family/name.")
        if (alias_family, alias_name) in seen:
            raise ValueError("compatibility_aliases may not contain duplicate entries.")
        seen.add((alias_family, alias_name))
        alias_path = item.get("path")
        if not isinstance(alias_path, str) or not alias_path:
            raise ValueError("compatibility_aliases entries must include a usable path.")
        expected_path = build_stimulus_alias_path(
            stimulus_family=alias_family,
            stimulus_name=alias_name,
            parameter_hash=parameter_hash,
            processed_stimulus_dir=Path(alias_path).resolve().parents[3],
        )
        if Path(alias_path).resolve() != expected_path:
            raise ValueError("compatibility_aliases entry path does not match the canonical alias location.")
        normalized.append(
            {
                "stimulus_family": alias_family,
                "stimulus_name": alias_name,
                "path": str(expected_path),
            }
        )
    return normalized


def _normalize_compatibility_aliases(
    payload: Sequence[Mapping[str, Any]] | None,
    *,
    processed_stimulus_dir: str | Path,
    parameter_hash: str,
    canonical_family: str,
    canonical_name: str,
) -> list[dict[str, Any]]:
    if payload is None:
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError("compatibility_aliases entries must be mappings.")
        alias_family = _normalize_identifier(
            item.get("stimulus_family"),
            field_name=f"compatibility_aliases[{index}].stimulus_family",
        )
        alias_name = _normalize_identifier(
            item.get("stimulus_name"),
            field_name=f"compatibility_aliases[{index}].stimulus_name",
        )
        if (alias_family, alias_name) == (canonical_family, canonical_name):
            raise ValueError("compatibility_aliases may not repeat the canonical stimulus family/name.")
        if (alias_family, alias_name) in seen:
            raise ValueError("compatibility_aliases may not contain duplicate entries.")
        seen.add((alias_family, alias_name))
        normalized.append(
            {
                "stimulus_family": alias_family,
                "stimulus_name": alias_name,
                "path": str(
                    build_stimulus_alias_path(
                        stimulus_family=alias_family,
                        stimulus_name=alias_name,
                        parameter_hash=parameter_hash,
                        processed_stimulus_dir=processed_stimulus_dir,
                    )
                ),
            }
        )
    return normalized


def _normalize_asset_payloads(payload: Any) -> dict[str, dict[str, str]]:
    if not isinstance(payload, Mapping):
        raise ValueError("assets must be a mapping.")
    normalized: dict[str, dict[str, str]] = {}
    for asset_key in (METADATA_JSON_KEY, FRAME_CACHE_KEY, PREVIEW_GIF_KEY):
        asset_record = payload.get(asset_key)
        if not isinstance(asset_record, Mapping):
            raise ValueError(f"Stimulus asset {asset_key!r} must be a mapping.")
        asset_path = asset_record.get("path")
        if not isinstance(asset_path, str) or not asset_path:
            raise ValueError(f"Stimulus asset {asset_key!r} is missing a usable path.")
        normalized[asset_key] = {
            "path": str(Path(asset_path).resolve()),
            "status": _normalize_asset_status(
                asset_record.get("status"),
                field_name=f"assets.{asset_key}.status",
            ),
        }
    return normalized


def _normalize_json_mapping(payload: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    normalized: dict[str, Any] = {}
    for key in sorted(payload):
        key_str = str(key)
        if not key_str:
            raise ValueError(f"{field_name} contains an empty key.")
        normalized[key_str] = _normalize_json_value(payload[key], field_name=f"{field_name}.{key_str}")
    return normalized


def _normalize_json_value(value: Any, *, field_name: str) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} must be finite.")
        if value == 0.0:
            return 0.0
        return float(value)
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return _normalize_json_mapping(value, field_name=field_name)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _normalize_json_value(item, field_name=f"{field_name}[{index}]")
            for index, item in enumerate(value)
        ]
    raise ValueError(f"{field_name} must contain JSON-serializable scalar, list, or mapping values.")


def _normalize_identifier(value: Any, *, field_name: str) -> str:
    normalized = _normalize_nonempty_string(value, field_name=field_name).lower()
    normalized = _IDENTIFIER_RE.sub("_", normalized).strip("._-")
    if not normalized:
        raise ValueError(f"{field_name} must contain at least one alphanumeric character.")
    return normalized


def _normalize_nonempty_string(value: Any, *, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} must be a non-empty string.")
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return text


def _normalize_parameter_hash(value: Any) -> str:
    parameter_hash = _normalize_nonempty_string(value, field_name="parameter_hash").lower()
    if not _HEX_HASH_RE.fullmatch(parameter_hash):
        raise ValueError("parameter_hash must be a 64-character lowercase hexadecimal sha256 digest.")
    return parameter_hash


def _normalize_seed(value: Any) -> int:
    if value is None:
        raise ValueError("seed must be provided.")
    try:
        seed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("seed must be an integer.") from exc
    if seed < 0:
        raise ValueError("seed must be non-negative.")
    return seed


def _normalize_asset_status(value: Any, *, field_name: str) -> str:
    status = _normalize_nonempty_string(value, field_name=field_name)
    if status not in SUPPORTED_ASSET_STATUSES:
        raise ValueError(
            f"{field_name} must be one of {list(SUPPORTED_ASSET_STATUSES)!r}, got {status!r}."
        )
    return status


def _normalize_positive_int(value: Any, *, field_name: str) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc
    if normalized <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _normalize_positive_float(value: Any, *, field_name: str) -> float:
    normalized = _normalize_float(value, field_name=field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _normalize_float(value: Any, *, field_name: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a float.") from exc
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    if normalized == 0.0:
        return 0.0
    return normalized
