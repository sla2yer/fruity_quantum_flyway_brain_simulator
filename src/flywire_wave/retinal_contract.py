from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import write_json
from .retinal_geometry import (
    DEFAULT_EYE_INDEXING,
    DEFAULT_EYE_ORDER,
    DEFAULT_GEOMETRY_FAMILY,
    DEFAULT_GEOMETRY_NAME,
    DEFAULT_LATTICE_FAMILY,
    DEFAULT_LATTICE_VERSION,
    DEFAULT_OMMATIDIAL_ORDERING,
    LEFT_EYE,
    RIGHT_EYE,
    SUPPORTED_EYE_LABELS,
    default_coordinate_frames as default_retinal_coordinate_frames,
    resolve_retinal_geometry_spec,
)
from .stimulus_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    ASSET_STATUS_SKIPPED,
    DEFAULT_HASH_ALGORITHM,
    DEFAULT_TIME_UNIT,
    SAMPLE_HOLD_SAMPLING_MODE,
    SUPPORTED_SAMPLING_MODES,
    _normalize_asset_status,
    _normalize_float,
    _normalize_identifier,
    _normalize_json_mapping,
    _normalize_nonempty_string,
    _normalize_parameter_hash,
    _normalize_positive_float,
    _normalize_positive_int,
    normalize_temporal_sampling,
)


RETINAL_INPUT_BUNDLE_CONTRACT_VERSION = "retinal_input_bundle.v1"
RETINAL_BUNDLE_DESIGN_NOTE = "docs/retinal_bundle_design.md"
RETINAL_BUNDLE_DESIGN_NOTE_VERSION = "retinal_design_note.v1"

DEFAULT_PROCESSED_RETINAL_DIR = Path("data/processed/retinal")

DIRECT_PER_OMMATIDIUM_IRRADIANCE = "direct_per_ommatidium_irradiance"
EYE_IMAGE_RASTER_INTERMEDIATE = "eye_image_raster_intermediate"
RETINOTOPIC_FEATURE_MAP = "retinotopic_feature_map"
RECOGNIZED_RETINAL_REPRESENTATION_FAMILIES = (
    DIRECT_PER_OMMATIDIUM_IRRADIANCE,
    EYE_IMAGE_RASTER_INTERMEDIATE,
    RETINOTOPIC_FEATURE_MAP,
)
SUPPORTED_RETINAL_REPRESENTATION_FAMILIES = (
    DIRECT_PER_OMMATIDIUM_IRRADIANCE,
)
DEFAULT_RETINAL_REPRESENTATION_FAMILY = DIRECT_PER_OMMATIDIUM_IRRADIANCE

DEFAULT_FRAME_LAYOUT = "dense_t_eye_ommatidium"
DEFAULT_FRAME_AXIS_ORDER = ["time", "eye", "ommatidium"]
DEFAULT_VALUE_SEMANTICS = "per_ommatidium_linear_irradiance"

DEFAULT_SIGNAL_ENCODING = "linear_irradiance_unit_interval"
DEFAULT_CONTRAST_SEMANTICS = "signed_delta_from_neutral_gray"
DEFAULT_POSITIVE_POLARITY = "brighter_than_neutral"
DEFAULT_SIGNAL_MINIMUM_VALUE = 0.0
DEFAULT_SIGNAL_NEUTRAL_VALUE = 0.5
DEFAULT_SIGNAL_MAXIMUM_VALUE = 1.0

DEFAULT_SAMPLING_KERNEL_FAMILY = "gaussian_acceptance_weighted_mean"
SUPPORTED_RETINAL_SAMPLING_KERNEL_FAMILIES = (DEFAULT_SAMPLING_KERNEL_FAMILY,)
DEFAULT_KERNEL_NORMALIZATION = "weights_sum_to_one"
SUPPORTED_KERNEL_NORMALIZATIONS = (DEFAULT_KERNEL_NORMALIZATION,)
DEFAULT_OUT_OF_FIELD_POLICY = "fill_background"
SUPPORTED_OUT_OF_FIELD_POLICIES = (DEFAULT_OUT_OF_FIELD_POLICY,)

RETINAL_SIMULATOR_INPUT_VERSION = "retinal_simulator_input.v1"
DEFAULT_SIMULATOR_INPUT_REPRESENTATION = "early_visual_unit_stack"
DEFAULT_SIMULATOR_INPUT_LAYOUT = "dense_t_eye_unit_channel"
DEFAULT_SIMULATOR_INPUT_AXIS_ORDER = ["time", "eye", "unit", "channel"]
DEFAULT_UNIT_AXIS_NAME = "early_visual_unit"
DEFAULT_CHANNEL_AXIS_NAME = "early_visual_channel"
DEFAULT_UNIT_INDEXING = "axis_index_matches_per_eye_unit_table"
DEFAULT_CHANNEL_NAME = "irradiance"
DEFAULT_CHANNEL_SEMANTICS = "per_ommatidium_linear_irradiance"
DEFAULT_CHANNEL_AGGREGATION = "identity"
DEFAULT_CHANNEL_NORMALIZATION = "clip_to_signal_convention_bounds"
DEFAULT_CHANNEL_ADAPTATION = "none"
DEFAULT_CHANNEL_POLARITY = "nonnegative_absolute_irradiance"
DEFAULT_SIMULATOR_MAPPING_FAMILY = "identity_per_ommatidium"
DEFAULT_SIMULATOR_UNIT_KIND = "ommatidial_detector"
DEFAULT_SIMULATOR_IDENTITY_RULE = "unit_index_matches_source_ommatidium_index"

DEFAULT_FRAME_ARCHIVE_FORMAT = "npz_retinal_frames_and_early_visual_units"

METADATA_JSON_KEY = "metadata_json"
FRAME_ARCHIVE_KEY = "frame_archive"


@dataclass(frozen=True)
class RetinalContractPaths:
    processed_retinal_dir: Path
    bundle_root_directory: Path


@dataclass(frozen=True)
class RetinalBundlePaths:
    source_kind: str
    source_family: str
    source_name: str
    source_hash: str
    retinal_spec_hash: str
    bundle_directory: Path
    metadata_json_path: Path
    frame_archive_path: Path

    @property
    def bundle_id(self) -> str:
        return (
            f"{RETINAL_INPUT_BUNDLE_CONTRACT_VERSION}:"
            f"{self.source_kind}:{self.source_family}:{self.source_name}:"
            f"{self.source_hash}:{self.retinal_spec_hash}"
        )

    def asset_paths(self) -> dict[str, Path]:
        return {
            METADATA_JSON_KEY: self.metadata_json_path,
            FRAME_ARCHIVE_KEY: self.frame_archive_path,
        }


def build_retinal_contract_paths(
    processed_retinal_dir: str | Path = DEFAULT_PROCESSED_RETINAL_DIR,
) -> RetinalContractPaths:
    retinal_dir = Path(processed_retinal_dir).resolve()
    return RetinalContractPaths(
        processed_retinal_dir=retinal_dir,
        bundle_root_directory=retinal_dir / "bundles",
    )


def build_retinal_source_reference(
    *,
    source_kind: str,
    source_contract_version: str,
    source_family: str,
    source_name: str,
    source_id: str,
    source_hash: str,
    source_hash_algorithm: str = DEFAULT_HASH_ALGORITHM,
) -> dict[str, Any]:
    return parse_retinal_source_reference(
        {
            "source_kind": source_kind,
            "source_contract_version": source_contract_version,
            "source_family": source_family,
            "source_name": source_name,
            "source_id": source_id,
            "source_hash": source_hash,
            "source_hash_algorithm": source_hash_algorithm,
        }
    )


def build_retinal_source_reference_from_descriptor(
    source_descriptor: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(source_descriptor, Mapping):
        raise ValueError("source_descriptor must be a mapping.")
    normalized_descriptor = _normalize_json_mapping(
        source_descriptor,
        field_name="source_descriptor",
    )
    source_kind = _normalize_identifier(
        normalized_descriptor.get("source_kind"),
        field_name="source_descriptor.source_kind",
    )
    source_contract_version = _normalize_nonempty_string(
        normalized_descriptor.get("source_contract_version"),
        field_name="source_descriptor.source_contract_version",
    )
    source_family = _normalize_identifier(
        normalized_descriptor.get("source_family"),
        field_name="source_descriptor.source_family",
    )
    source_name = _normalize_identifier(
        normalized_descriptor.get("source_name"),
        field_name="source_descriptor.source_name",
    )
    raw_source_hash = normalized_descriptor.get("source_hash")
    if raw_source_hash is None:
        serialized = json.dumps(
            normalized_descriptor,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        source_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    else:
        source_hash = _normalize_parameter_hash(raw_source_hash)
    source_id = normalized_descriptor.get("source_id")
    if source_id is None:
        source_id = (
            f"{source_contract_version}:{source_kind}:{source_family}:{source_name}:{source_hash}"
        )
    return build_retinal_source_reference(
        source_kind=source_kind,
        source_contract_version=source_contract_version,
        source_family=source_family,
        source_name=source_name,
        source_id=source_id,
        source_hash=source_hash,
    )


def build_retinal_bundle_paths(
    *,
    source_reference: Mapping[str, Any],
    processed_retinal_dir: str | Path = DEFAULT_PROCESSED_RETINAL_DIR,
    retinal_spec_hash: str | None = None,
    representation_family: str = DEFAULT_RETINAL_REPRESENTATION_FAMILY,
    eye_sampling: Mapping[str, Any] | None = None,
    temporal_sampling: Mapping[str, Any] | None = None,
    coordinate_frames: Mapping[str, Any] | None = None,
    sampling_kernel: Mapping[str, Any] | None = None,
    signal_convention: Mapping[str, Any] | None = None,
) -> RetinalBundlePaths:
    normalized_source_reference = parse_retinal_source_reference(source_reference)
    resolved_retinal_spec_hash = _resolve_retinal_spec_hash(
        retinal_spec_hash=retinal_spec_hash,
        representation_family=representation_family,
        eye_sampling=eye_sampling,
        temporal_sampling=temporal_sampling,
        coordinate_frames=coordinate_frames,
        sampling_kernel=sampling_kernel,
        signal_convention=signal_convention,
    )
    contract_paths = build_retinal_contract_paths(processed_retinal_dir)
    bundle_directory = (
        contract_paths.bundle_root_directory
        / normalized_source_reference["source_kind"]
        / normalized_source_reference["source_family"]
        / normalized_source_reference["source_name"]
        / normalized_source_reference["source_hash"]
        / resolved_retinal_spec_hash
    )
    return RetinalBundlePaths(
        source_kind=normalized_source_reference["source_kind"],
        source_family=normalized_source_reference["source_family"],
        source_name=normalized_source_reference["source_name"],
        source_hash=normalized_source_reference["source_hash"],
        retinal_spec_hash=resolved_retinal_spec_hash,
        bundle_directory=bundle_directory,
        metadata_json_path=bundle_directory / "retinal_input_bundle.json",
        frame_archive_path=bundle_directory / "retinal_frames.npz",
    )


def build_retinal_contract_manifest_metadata(
    *,
    processed_retinal_dir: str | Path = DEFAULT_PROCESSED_RETINAL_DIR,
) -> dict[str, Any]:
    contract_paths = build_retinal_contract_paths(processed_retinal_dir)
    return {
        "version": RETINAL_INPUT_BUNDLE_CONTRACT_VERSION,
        "design_note": RETINAL_BUNDLE_DESIGN_NOTE,
        "design_note_version": RETINAL_BUNDLE_DESIGN_NOTE_VERSION,
        "default_representation_family": DEFAULT_RETINAL_REPRESENTATION_FAMILY,
        "recognized_representation_families": list(RECOGNIZED_RETINAL_REPRESENTATION_FAMILIES),
        "supported_representation_families": list(SUPPORTED_RETINAL_REPRESENTATION_FAMILIES),
        "default_time_unit": DEFAULT_TIME_UNIT,
        "supported_sampling_modes": list(SUPPORTED_SAMPLING_MODES),
        "default_geometry_family": DEFAULT_GEOMETRY_FAMILY,
        "default_geometry_name": DEFAULT_GEOMETRY_NAME,
        "default_lattice_family": DEFAULT_LATTICE_FAMILY,
        "default_lattice_version": DEFAULT_LATTICE_VERSION,
        "default_eye_order": list(DEFAULT_EYE_ORDER),
        "default_eye_indexing": DEFAULT_EYE_INDEXING,
        "default_ommatidial_ordering": DEFAULT_OMMATIDIAL_ORDERING,
        "default_frame_layout": DEFAULT_FRAME_LAYOUT,
        "default_frame_archive_format": DEFAULT_FRAME_ARCHIVE_FORMAT,
        "default_sampling_kernel_family": DEFAULT_SAMPLING_KERNEL_FAMILY,
        "supported_sampling_kernel_families": list(SUPPORTED_RETINAL_SAMPLING_KERNEL_FAMILIES),
        "default_simulator_input_representation": DEFAULT_SIMULATOR_INPUT_REPRESENTATION,
        "default_simulator_input_layout": DEFAULT_SIMULATOR_INPUT_LAYOUT,
        "default_simulator_mapping_family": DEFAULT_SIMULATOR_MAPPING_FAMILY,
        "preferred_coordinate_frames": default_coordinate_frames(),
        "default_signal_convention": default_signal_convention(),
        "bundle_root_directory": str(contract_paths.bundle_root_directory),
    }


def build_retinal_spec_hash(
    *,
    representation_family: str = DEFAULT_RETINAL_REPRESENTATION_FAMILY,
    eye_sampling: Mapping[str, Any],
    temporal_sampling: Mapping[str, Any],
    coordinate_frames: Mapping[str, Any] | None = None,
    sampling_kernel: Mapping[str, Any] | None = None,
    signal_convention: Mapping[str, Any] | None = None,
) -> str:
    reproducibility_payload = {
        "representation_family": _normalize_representation_family(representation_family),
        "eye_sampling": normalize_retinal_eye_sampling(eye_sampling),
        "temporal_sampling": normalize_temporal_sampling(temporal_sampling),
        "coordinate_frames": normalize_retinal_coordinate_frames(coordinate_frames),
        "sampling_kernel": normalize_retinal_sampling_kernel(sampling_kernel),
        "signal_convention": normalize_retinal_signal_convention(signal_convention),
    }
    serialized = json.dumps(
        reproducibility_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_retinal_bundle_metadata(
    *,
    source_reference: Mapping[str, Any],
    eye_sampling: Mapping[str, Any],
    temporal_sampling: Mapping[str, Any],
    processed_retinal_dir: str | Path = DEFAULT_PROCESSED_RETINAL_DIR,
    coordinate_frames: Mapping[str, Any] | None = None,
    sampling_kernel: Mapping[str, Any] | None = None,
    signal_convention: Mapping[str, Any] | None = None,
    representation_family: str = DEFAULT_RETINAL_REPRESENTATION_FAMILY,
    frame_archive_status: str = ASSET_STATUS_MISSING,
) -> dict[str, Any]:
    normalized_source_reference = parse_retinal_source_reference(source_reference)
    normalized_representation_family = _normalize_representation_family(representation_family)
    normalized_eye_sampling = normalize_retinal_eye_sampling(eye_sampling)
    normalized_temporal_sampling = normalize_temporal_sampling(temporal_sampling)
    normalized_coordinate_frames = normalize_retinal_coordinate_frames(coordinate_frames)
    normalized_sampling_kernel = normalize_retinal_sampling_kernel(sampling_kernel)
    normalized_signal_convention = normalize_retinal_signal_convention(signal_convention)
    simulator_input = _build_default_simulator_input(
        eye_sampling=normalized_eye_sampling,
        signal_convention=normalized_signal_convention,
    )
    retinal_spec_hash = build_retinal_spec_hash(
        representation_family=normalized_representation_family,
        eye_sampling=normalized_eye_sampling,
        temporal_sampling=normalized_temporal_sampling,
        coordinate_frames=normalized_coordinate_frames,
        sampling_kernel=normalized_sampling_kernel,
        signal_convention=normalized_signal_convention,
    )
    bundle_paths = build_retinal_bundle_paths(
        source_reference=normalized_source_reference,
        processed_retinal_dir=processed_retinal_dir,
        retinal_spec_hash=retinal_spec_hash,
    )
    frame_layout = _build_frame_layout(normalized_eye_sampling)
    return {
        "contract_version": RETINAL_INPUT_BUNDLE_CONTRACT_VERSION,
        "design_note": RETINAL_BUNDLE_DESIGN_NOTE,
        "design_note_version": RETINAL_BUNDLE_DESIGN_NOTE_VERSION,
        "bundle_id": bundle_paths.bundle_id,
        "representation_family": normalized_representation_family,
        "source_reference": normalized_source_reference,
        "retinal_spec_hash": retinal_spec_hash,
        "retinal_spec_hash_algorithm": DEFAULT_HASH_ALGORITHM,
        "eye_sampling": normalized_eye_sampling,
        "frame_layout": frame_layout,
        "simulator_input": simulator_input,
        "temporal_sampling": normalized_temporal_sampling,
        "coordinate_frames": normalized_coordinate_frames,
        "sampling_kernel": normalized_sampling_kernel,
        "signal_convention": normalized_signal_convention,
        "replay": {
            "time_unit": DEFAULT_TIME_UNIT,
            "sampling_mode": SAMPLE_HOLD_SAMPLING_MODE,
            "authoritative_source": "retinal_bundle_metadata",
            "frame_layout": DEFAULT_FRAME_LAYOUT,
            "frame_archive_format": DEFAULT_FRAME_ARCHIVE_FORMAT,
        },
        "assets": {
            METADATA_JSON_KEY: {
                "path": str(bundle_paths.metadata_json_path),
                "status": ASSET_STATUS_READY,
            },
            FRAME_ARCHIVE_KEY: {
                "path": str(bundle_paths.frame_archive_path),
                "status": _normalize_asset_status(
                    frame_archive_status,
                    field_name="frame_archive_status",
                ),
            },
        },
    }


def build_retinal_bundle_reference(bundle_metadata: Mapping[str, Any]) -> dict[str, Any]:
    normalized = parse_retinal_bundle_metadata(bundle_metadata)
    source_reference = normalized["source_reference"]
    return {
        "contract_version": normalized["contract_version"],
        "source_kind": source_reference["source_kind"],
        "source_family": source_reference["source_family"],
        "source_name": source_reference["source_name"],
        "source_hash": source_reference["source_hash"],
        "retinal_spec_hash": normalized["retinal_spec_hash"],
        "bundle_id": normalized["bundle_id"],
    }


def parse_retinal_source_reference(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("source_reference must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "source_kind",
        "source_contract_version",
        "source_family",
        "source_name",
        "source_id",
        "source_hash",
        "source_hash_algorithm",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"source_reference is missing required fields: {missing_fields}")
    normalized["source_kind"] = _normalize_identifier(
        normalized["source_kind"],
        field_name="source_reference.source_kind",
    )
    normalized["source_contract_version"] = _normalize_nonempty_string(
        normalized["source_contract_version"],
        field_name="source_reference.source_contract_version",
    )
    normalized["source_family"] = _normalize_identifier(
        normalized["source_family"],
        field_name="source_reference.source_family",
    )
    normalized["source_name"] = _normalize_identifier(
        normalized["source_name"],
        field_name="source_reference.source_name",
    )
    normalized["source_id"] = _normalize_nonempty_string(
        normalized["source_id"],
        field_name="source_reference.source_id",
    )
    normalized["source_hash"] = _normalize_parameter_hash(normalized["source_hash"])
    normalized["source_hash_algorithm"] = _normalize_nonempty_string(
        normalized["source_hash_algorithm"],
        field_name="source_reference.source_hash_algorithm",
    )
    if normalized["source_hash_algorithm"] != DEFAULT_HASH_ALGORITHM:
        raise ValueError(
            "Unsupported source_reference.source_hash_algorithm "
            f"{normalized['source_hash_algorithm']!r}."
        )
    return normalized


def parse_retinal_bundle_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Retinal bundle metadata must be a mapping.")

    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "bundle_id",
        "representation_family",
        "source_reference",
        "retinal_spec_hash",
        "retinal_spec_hash_algorithm",
        "eye_sampling",
        "frame_layout",
        "simulator_input",
        "temporal_sampling",
        "coordinate_frames",
        "sampling_kernel",
        "signal_convention",
        "replay",
        "assets",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"Retinal bundle metadata is missing required fields: {missing_fields}")
    if normalized["contract_version"] != RETINAL_INPUT_BUNDLE_CONTRACT_VERSION:
        raise ValueError(
            "Retinal bundle metadata contract_version does not match "
            f"{RETINAL_INPUT_BUNDLE_CONTRACT_VERSION!r}."
        )
    normalized["representation_family"] = _normalize_representation_family(
        normalized["representation_family"]
    )
    normalized["source_reference"] = parse_retinal_source_reference(normalized["source_reference"])
    normalized["retinal_spec_hash"] = _normalize_parameter_hash(normalized["retinal_spec_hash"])
    normalized["retinal_spec_hash_algorithm"] = _normalize_nonempty_string(
        normalized["retinal_spec_hash_algorithm"],
        field_name="retinal_spec_hash_algorithm",
    )
    if normalized["retinal_spec_hash_algorithm"] != DEFAULT_HASH_ALGORITHM:
        raise ValueError(
            "Unsupported retinal_spec_hash_algorithm "
            f"{normalized['retinal_spec_hash_algorithm']!r}."
        )
    normalized["eye_sampling"] = normalize_retinal_eye_sampling(normalized["eye_sampling"])
    normalized["frame_layout"] = _normalize_frame_layout_payload(
        normalized["frame_layout"],
        eye_sampling=normalized["eye_sampling"],
    )
    normalized["temporal_sampling"] = normalize_temporal_sampling(normalized["temporal_sampling"])
    normalized["coordinate_frames"] = normalize_retinal_coordinate_frames(
        normalized["coordinate_frames"]
    )
    normalized["sampling_kernel"] = normalize_retinal_sampling_kernel(normalized["sampling_kernel"])
    normalized["signal_convention"] = normalize_retinal_signal_convention(
        normalized["signal_convention"]
    )
    normalized["simulator_input"] = _normalize_simulator_input_payload(
        normalized["simulator_input"],
        eye_sampling=normalized["eye_sampling"],
        signal_convention=normalized["signal_convention"],
    )
    normalized["replay"] = _normalize_replay_payload(normalized["replay"])
    normalized["assets"] = _normalize_asset_payloads(normalized["assets"])
    expected_bundle_id = (
        f"{RETINAL_INPUT_BUNDLE_CONTRACT_VERSION}:"
        f"{normalized['source_reference']['source_kind']}:"
        f"{normalized['source_reference']['source_family']}:"
        f"{normalized['source_reference']['source_name']}:"
        f"{normalized['source_reference']['source_hash']}:"
        f"{normalized['retinal_spec_hash']}"
    )
    if normalized["bundle_id"] != expected_bundle_id:
        raise ValueError(
            "Retinal bundle metadata bundle_id does not match the canonical "
            "source-kind/family/name/hash plus retinal-spec-hash tuple."
        )
    return normalized


def load_retinal_bundle_metadata(metadata_path: str | Path) -> dict[str, Any]:
    path = Path(metadata_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_retinal_bundle_metadata(payload)


def write_retinal_bundle_metadata(
    bundle_metadata: Mapping[str, Any],
    metadata_path: str | Path | None = None,
) -> Path:
    normalized = parse_retinal_bundle_metadata(bundle_metadata)
    output_path = (
        Path(metadata_path).resolve()
        if metadata_path is not None
        else Path(normalized["assets"][METADATA_JSON_KEY]["path"]).resolve()
    )
    return write_json(normalized, output_path)


def discover_retinal_bundle_paths(record: Mapping[str, Any]) -> dict[str, Path]:
    retinal_bundle = _extract_retinal_bundle_mapping(record)
    assets = retinal_bundle.get("assets")
    if not isinstance(assets, Mapping):
        raise ValueError("Retinal bundle assets must be a mapping.")

    discovered: dict[str, Path] = {}
    for asset_key in (METADATA_JSON_KEY, FRAME_ARCHIVE_KEY):
        asset_record = assets.get(asset_key)
        if not isinstance(asset_record, Mapping):
            raise ValueError(f"Retinal asset {asset_key!r} is missing from the bundle metadata.")
        asset_path = asset_record.get("path")
        if not isinstance(asset_path, str) or not asset_path:
            raise ValueError(f"Retinal asset {asset_key!r} is missing a usable path.")
        discovered[asset_key] = Path(asset_path)
    return discovered


def resolve_retinal_bundle_metadata_path(
    *,
    source_reference: Mapping[str, Any],
    processed_retinal_dir: str | Path = DEFAULT_PROCESSED_RETINAL_DIR,
    retinal_spec_hash: str | None = None,
    representation_family: str = DEFAULT_RETINAL_REPRESENTATION_FAMILY,
    eye_sampling: Mapping[str, Any] | None = None,
    temporal_sampling: Mapping[str, Any] | None = None,
    coordinate_frames: Mapping[str, Any] | None = None,
    sampling_kernel: Mapping[str, Any] | None = None,
    signal_convention: Mapping[str, Any] | None = None,
) -> Path:
    bundle_paths = build_retinal_bundle_paths(
        source_reference=source_reference,
        processed_retinal_dir=processed_retinal_dir,
        retinal_spec_hash=retinal_spec_hash,
        representation_family=representation_family,
        eye_sampling=eye_sampling,
        temporal_sampling=temporal_sampling,
        coordinate_frames=coordinate_frames,
        sampling_kernel=sampling_kernel,
        signal_convention=signal_convention,
    )
    return bundle_paths.metadata_json_path.resolve()


def default_coordinate_frames() -> dict[str, Any]:
    return default_retinal_coordinate_frames()


def default_signal_convention() -> dict[str, Any]:
    return {
        "encoding": DEFAULT_SIGNAL_ENCODING,
        "minimum_value": DEFAULT_SIGNAL_MINIMUM_VALUE,
        "neutral_value": DEFAULT_SIGNAL_NEUTRAL_VALUE,
        "maximum_value": DEFAULT_SIGNAL_MAXIMUM_VALUE,
        "contrast_semantics": DEFAULT_CONTRAST_SEMANTICS,
        "positive_polarity": DEFAULT_POSITIVE_POLARITY,
    }


def default_simulator_input(
    eye_sampling: Mapping[str, Any],
    signal_convention: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_eye_sampling = normalize_retinal_eye_sampling(eye_sampling)
    normalized_signal_convention = normalize_retinal_signal_convention(signal_convention)
    return _build_default_simulator_input(
        eye_sampling=normalized_eye_sampling,
        signal_convention=normalized_signal_convention,
    )


def default_sampling_kernel() -> dict[str, Any]:
    return {
        "kernel_family": DEFAULT_SAMPLING_KERNEL_FAMILY,
        "acceptance_angle_deg": 5.0,
        "support_radius_deg": 12.5,
        "normalization": DEFAULT_KERNEL_NORMALIZATION,
        "out_of_field_policy": DEFAULT_OUT_OF_FIELD_POLICY,
        "background_fill_value": DEFAULT_SIGNAL_NEUTRAL_VALUE,
    }


def normalize_retinal_eye_sampling(payload: Mapping[str, Any]) -> dict[str, Any]:
    resolved = resolve_retinal_geometry_spec(retinal_geometry=payload)
    return resolved.build_eye_sampling()


def normalize_retinal_coordinate_frames(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    defaults = default_coordinate_frames()
    if payload is None:
        return defaults
    normalized = _normalize_json_mapping(payload, field_name="coordinate_frames")
    expected = _normalize_json_mapping(defaults, field_name="coordinate_frames")
    if normalized != expected:
        raise ValueError(
            "coordinate_frames must match the canonical Milestone 8B retinal frame conventions "
            f"for {RETINAL_INPUT_BUNDLE_CONTRACT_VERSION!r}."
        )
    return defaults


def normalize_retinal_signal_convention(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    defaults = default_signal_convention()
    if payload is None:
        return defaults
    normalized = {
        "encoding": _normalize_nonempty_string(
            payload.get("encoding", defaults["encoding"]),
            field_name="signal_convention.encoding",
        ),
        "minimum_value": _normalize_float(
            payload.get("minimum_value", defaults["minimum_value"]),
            field_name="signal_convention.minimum_value",
        ),
        "neutral_value": _normalize_float(
            payload.get("neutral_value", defaults["neutral_value"]),
            field_name="signal_convention.neutral_value",
        ),
        "maximum_value": _normalize_float(
            payload.get("maximum_value", defaults["maximum_value"]),
            field_name="signal_convention.maximum_value",
        ),
        "contrast_semantics": _normalize_nonempty_string(
            payload.get("contrast_semantics", defaults["contrast_semantics"]),
            field_name="signal_convention.contrast_semantics",
        ),
        "positive_polarity": _normalize_nonempty_string(
            payload.get("positive_polarity", defaults["positive_polarity"]),
            field_name="signal_convention.positive_polarity",
        ),
    }
    if normalized != defaults:
        raise ValueError(
            "signal_convention must match the canonical linear-irradiance convention "
            f"for {RETINAL_INPUT_BUNDLE_CONTRACT_VERSION!r}."
        )
    return defaults


def normalize_retinal_sampling_kernel(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    defaults = default_sampling_kernel()
    if payload is None:
        return defaults
    if not isinstance(payload, Mapping):
        raise ValueError("sampling_kernel must be a mapping when provided.")
    kernel_family = _normalize_nonempty_string(
        payload.get("kernel_family", defaults["kernel_family"]),
        field_name="sampling_kernel.kernel_family",
    )
    if kernel_family not in SUPPORTED_RETINAL_SAMPLING_KERNEL_FAMILIES:
        raise ValueError(
            "Unsupported sampling_kernel.kernel_family "
            f"{kernel_family!r}. Supported families: {list(SUPPORTED_RETINAL_SAMPLING_KERNEL_FAMILIES)!r}."
        )
    normalization = _normalize_nonempty_string(
        payload.get("normalization", defaults["normalization"]),
        field_name="sampling_kernel.normalization",
    )
    if normalization not in SUPPORTED_KERNEL_NORMALIZATIONS:
        raise ValueError(
            "Unsupported sampling_kernel.normalization "
            f"{normalization!r}. Supported modes: {list(SUPPORTED_KERNEL_NORMALIZATIONS)!r}."
        )
    out_of_field_policy = _normalize_nonempty_string(
        payload.get("out_of_field_policy", defaults["out_of_field_policy"]),
        field_name="sampling_kernel.out_of_field_policy",
    )
    if out_of_field_policy not in SUPPORTED_OUT_OF_FIELD_POLICIES:
        raise ValueError(
            "Unsupported sampling_kernel.out_of_field_policy "
            f"{out_of_field_policy!r}. Supported policies: {list(SUPPORTED_OUT_OF_FIELD_POLICIES)!r}."
        )
    background_fill_value = _normalize_float(
        payload.get("background_fill_value", defaults["background_fill_value"]),
        field_name="sampling_kernel.background_fill_value",
    )
    if not (DEFAULT_SIGNAL_MINIMUM_VALUE <= background_fill_value <= DEFAULT_SIGNAL_MAXIMUM_VALUE):
        raise ValueError(
            "sampling_kernel.background_fill_value must stay within the unit interval [0.0, 1.0]."
        )
    return {
        "kernel_family": kernel_family,
        "acceptance_angle_deg": _normalize_positive_float(
            payload.get("acceptance_angle_deg", defaults["acceptance_angle_deg"]),
            field_name="sampling_kernel.acceptance_angle_deg",
        ),
        "support_radius_deg": _normalize_positive_float(
            payload.get("support_radius_deg", defaults["support_radius_deg"]),
            field_name="sampling_kernel.support_radius_deg",
        ),
        "normalization": normalization,
        "out_of_field_policy": out_of_field_policy,
        "background_fill_value": background_fill_value,
    }


def _resolve_retinal_spec_hash(
    *,
    retinal_spec_hash: str | None,
    representation_family: str,
    eye_sampling: Mapping[str, Any] | None,
    temporal_sampling: Mapping[str, Any] | None,
    coordinate_frames: Mapping[str, Any] | None,
    sampling_kernel: Mapping[str, Any] | None,
    signal_convention: Mapping[str, Any] | None,
) -> str:
    if retinal_spec_hash is not None:
        return _normalize_parameter_hash(retinal_spec_hash)
    missing = [
        field_name
        for field_name, value in (
            ("eye_sampling", eye_sampling),
            ("temporal_sampling", temporal_sampling),
        )
        if value is None
    ]
    if missing:
        raise ValueError(
            "retinal_spec_hash was not provided and the following fields are required "
            f"to compute it: {missing}"
        )
    return build_retinal_spec_hash(
        representation_family=representation_family,
        eye_sampling=eye_sampling,
        temporal_sampling=temporal_sampling,
        coordinate_frames=coordinate_frames,
        sampling_kernel=sampling_kernel,
        signal_convention=signal_convention,
    )


def _extract_retinal_bundle_mapping(record: Mapping[str, Any]) -> Mapping[str, Any]:
    retinal_bundle = record.get("retinal_bundle")
    if isinstance(retinal_bundle, Mapping):
        return retinal_bundle
    return record


def _normalize_representation_family(value: Any) -> str:
    representation_family = _normalize_nonempty_string(
        value,
        field_name="representation_family",
    )
    if representation_family not in SUPPORTED_RETINAL_REPRESENTATION_FAMILIES:
        raise ValueError(
            "Unsupported retinal representation_family "
            f"{representation_family!r}. Supported families: {list(SUPPORTED_RETINAL_REPRESENTATION_FAMILIES)!r}."
        )
    return representation_family


def _normalize_eye_label(value: Any) -> str:
    eye_label = _normalize_identifier(value, field_name="eye_sampling.eye_order")
    if eye_label not in SUPPORTED_EYE_LABELS:
        raise ValueError(
            f"eye_sampling.eye_order entries must be one of {list(SUPPORTED_EYE_LABELS)!r}, got {eye_label!r}."
        )
    return eye_label


def _build_frame_layout(eye_sampling: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "layout": DEFAULT_FRAME_LAYOUT,
        "tensor_axis_order": list(DEFAULT_FRAME_AXIS_ORDER),
        "eye_axis_labels": list(eye_sampling["eye_order"]),
        "eye_indexing": str(eye_sampling["eye_indexing"]),
        "ommatidium_count_per_eye": int(eye_sampling["ommatidium_count_per_eye"]),
        "ommatidial_ordering": str(eye_sampling["ommatidial_ordering"]),
        "value_semantics": DEFAULT_VALUE_SEMANTICS,
    }


def _normalize_frame_layout_payload(
    payload: Any,
    *,
    eye_sampling: Mapping[str, Any],
) -> dict[str, Any]:
    expected = _build_frame_layout(eye_sampling)
    if not isinstance(payload, Mapping):
        raise ValueError("frame_layout must be a mapping.")
    normalized = {
        "layout": _normalize_nonempty_string(
            payload.get("layout", expected["layout"]),
            field_name="frame_layout.layout",
        ),
        "tensor_axis_order": [
            _normalize_nonempty_string(value, field_name=f"frame_layout.tensor_axis_order[{index}]")
            for index, value in enumerate(payload.get("tensor_axis_order", expected["tensor_axis_order"]))
        ],
        "eye_axis_labels": [
            _normalize_eye_label(value) for value in payload.get("eye_axis_labels", expected["eye_axis_labels"])
        ],
        "eye_indexing": _normalize_nonempty_string(
            payload.get("eye_indexing", expected["eye_indexing"]),
            field_name="frame_layout.eye_indexing",
        ),
        "ommatidium_count_per_eye": _normalize_positive_int(
            payload.get("ommatidium_count_per_eye", expected["ommatidium_count_per_eye"]),
            field_name="frame_layout.ommatidium_count_per_eye",
        ),
        "ommatidial_ordering": _normalize_nonempty_string(
            payload.get("ommatidial_ordering", expected["ommatidial_ordering"]),
            field_name="frame_layout.ommatidial_ordering",
        ),
        "value_semantics": _normalize_nonempty_string(
            payload.get("value_semantics", expected["value_semantics"]),
            field_name="frame_layout.value_semantics",
        ),
    }
    if normalized != expected:
        raise ValueError(
            "frame_layout must match the canonical dense `time x eye x ommatidium` layout "
            f"for {RETINAL_INPUT_BUNDLE_CONTRACT_VERSION!r}."
        )
    return expected


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
    frame_layout = _normalize_nonempty_string(
        payload.get("frame_layout", DEFAULT_FRAME_LAYOUT),
        field_name="replay.frame_layout",
    )
    if frame_layout != DEFAULT_FRAME_LAYOUT:
        raise ValueError(
            f"replay.frame_layout must be {DEFAULT_FRAME_LAYOUT!r}, got {frame_layout!r}."
        )
    return {
        "time_unit": time_unit,
        "sampling_mode": sampling_mode,
        "authoritative_source": _normalize_nonempty_string(
            payload.get("authoritative_source", "retinal_bundle_metadata"),
            field_name="replay.authoritative_source",
        ),
        "frame_layout": frame_layout,
        "frame_archive_format": _normalize_nonempty_string(
            payload.get("frame_archive_format", DEFAULT_FRAME_ARCHIVE_FORMAT),
            field_name="replay.frame_archive_format",
        ),
    }


def _build_default_simulator_input(
    *,
    eye_sampling: Mapping[str, Any],
    signal_convention: Mapping[str, Any],
) -> dict[str, Any]:
    per_eye_unit_tables: dict[str, list[dict[str, Any]]] = {}
    for eye_label in eye_sampling["eye_order"]:
        detector_table = eye_sampling["per_eye"][eye_label]["detector_table"]
        unit_table: list[dict[str, Any]] = []
        for detector in detector_table:
            ommatidium_index = int(detector["ommatidium_index"])
            unit_table.append(
                {
                    "unit_index": ommatidium_index,
                    "unit_id": f"{eye_label}:ommatidium:{ommatidium_index}",
                    "unit_kind": DEFAULT_SIMULATOR_UNIT_KIND,
                    "source_ommatidium_index": ommatidium_index,
                    "ring_index": int(detector["ring_index"]),
                    "ring_position": int(detector["ring_position"]),
                }
            )
        per_eye_unit_tables[eye_label] = unit_table
    return {
        "version": RETINAL_SIMULATOR_INPUT_VERSION,
        "representation": DEFAULT_SIMULATOR_INPUT_REPRESENTATION,
        "layout": DEFAULT_SIMULATOR_INPUT_LAYOUT,
        "tensor_axis_order": list(DEFAULT_SIMULATOR_INPUT_AXIS_ORDER),
        "eye_axis_labels": list(eye_sampling["eye_order"]),
        "unit_axis_name": DEFAULT_UNIT_AXIS_NAME,
        "unit_count_per_eye": int(eye_sampling["ommatidium_count_per_eye"]),
        "unit_indexing": DEFAULT_UNIT_INDEXING,
        "channel_axis_name": DEFAULT_CHANNEL_AXIS_NAME,
        "channel_count": 1,
        "channel_order": [DEFAULT_CHANNEL_NAME],
        "channels": [
            {
                "channel_name": DEFAULT_CHANNEL_NAME,
                "channel_index": 0,
                "value_semantics": DEFAULT_CHANNEL_SEMANTICS,
                "encoding": str(signal_convention["encoding"]),
                "contrast_semantics": str(signal_convention["contrast_semantics"]),
                "positive_polarity": str(signal_convention["positive_polarity"]),
                "aggregation": DEFAULT_CHANNEL_AGGREGATION,
                "normalization": DEFAULT_CHANNEL_NORMALIZATION,
                "adaptation": DEFAULT_CHANNEL_ADAPTATION,
                "polarity": DEFAULT_CHANNEL_POLARITY,
            }
        ],
        "mapping": {
            "mapping_family": DEFAULT_SIMULATOR_MAPPING_FAMILY,
            "source_layout": DEFAULT_FRAME_LAYOUT,
            "source_value_semantics": DEFAULT_VALUE_SEMANTICS,
            "unit_semantics": DEFAULT_SIMULATOR_UNIT_KIND,
            "aggregation": DEFAULT_CHANNEL_AGGREGATION,
            "normalization": DEFAULT_CHANNEL_NORMALIZATION,
            "adaptation": DEFAULT_CHANNEL_ADAPTATION,
            "identity_rule": DEFAULT_SIMULATOR_IDENTITY_RULE,
            "per_eye_unit_tables": per_eye_unit_tables,
        },
    }


def _normalize_simulator_input_payload(
    payload: Any,
    *,
    eye_sampling: Mapping[str, Any],
    signal_convention: Mapping[str, Any],
) -> dict[str, Any]:
    expected = _build_default_simulator_input(
        eye_sampling=eye_sampling,
        signal_convention=signal_convention,
    )
    normalized = _normalize_json_mapping(payload, field_name="simulator_input")
    expected_normalized = _normalize_json_mapping(expected, field_name="simulator_input")
    if normalized != expected_normalized:
        raise ValueError(
            "simulator_input must match the canonical identity early-visual mapping "
            f"for {RETINAL_INPUT_BUNDLE_CONTRACT_VERSION!r}."
        )
    return expected


def _normalize_asset_payloads(payload: Any) -> dict[str, dict[str, str]]:
    if not isinstance(payload, Mapping):
        raise ValueError("assets must be a mapping.")
    normalized: dict[str, dict[str, str]] = {}
    for asset_key in (METADATA_JSON_KEY, FRAME_ARCHIVE_KEY):
        asset_record = payload.get(asset_key)
        if not isinstance(asset_record, Mapping):
            raise ValueError(f"Retinal asset {asset_key!r} must be a mapping.")
        asset_path = asset_record.get("path")
        if not isinstance(asset_path, str) or not asset_path:
            raise ValueError(f"Retinal asset {asset_key!r} is missing a usable path.")
        normalized[asset_key] = {
            "path": str(Path(asset_path).resolve()),
            "status": _normalize_asset_status(
                asset_record.get("status", ASSET_STATUS_MISSING),
                field_name=f"assets.{asset_key}.status",
            ),
        }
    return normalized
