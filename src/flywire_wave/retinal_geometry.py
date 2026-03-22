from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Any

import numpy as np

from .stimulus_contract import (
    _normalize_float,
    _normalize_identifier,
    _normalize_nonempty_string,
    _normalize_positive_float,
)


RETINAL_GEOMETRY_SPEC_VERSION = "retinal_geometry_spec.v1"
RETINAL_GEOMETRY_VERSION = "retinal_geometry.v1"

LEFT_EYE = "left"
RIGHT_EYE = "right"
SUPPORTED_EYE_LABELS = (LEFT_EYE, RIGHT_EYE)
DEFAULT_EYE_ORDER = [LEFT_EYE, RIGHT_EYE]
DEFAULT_EYE_INDEXING = "axis_index_matches_eye_order"
DEFAULT_OMMATIDIAL_ORDERING = "stable_eye_local_ommatidium_index"

DEFAULT_GEOMETRY_FAMILY = "compound_eye_geometry"
DEFAULT_GEOMETRY_FAMILY_ALIASES = ("ommatidial_lattice",)

DEFAULT_LATTICE_FAMILY = "hexagonal_angular_lattice"
DEFAULT_LATTICE_VERSION = "hexagonal_angular_lattice.v1"
DEFAULT_LATTICE_COORDINATE_SYSTEM = "continuous_axial_hex_coordinates"
DEFAULT_LATTICE_COORDINATE_SPACE = "eye_local_angular_degrees"
DEFAULT_LATTICE_PROJECTION = "azimuth_elevation_eye_sphere"
DEFAULT_LATTICE_BIN_LOOKUP = "nearest_detector_center"
DEFAULT_INDEXING_FAMILY = "ring_major_clockwise_from_dorsal"
DEFAULT_INDEXING_CLOCKWISE_VIEW = "looking_outward_along_positive_optical_axis"

DEFAULT_WORLD_TO_BODY_ROTATION_PARAMETERIZATION = "body_to_world_r_zyx_yaw_pitch_roll_deg"
DEFAULT_BODY_TO_HEAD_ROTATION_PARAMETERIZATION = "head_to_body_r_zyx_yaw_pitch_roll_deg"
DEFAULT_EYE_ROTATION_PARAMETERIZATION = "eye_axes_embedded_in_head_frame"

DEFAULT_WORLD_TO_BODY_TRANSLATION_MM = [0.0, 0.0, 0.0]
DEFAULT_WORLD_TO_BODY_YAW_PITCH_ROLL_DEG = [0.0, 0.0, 0.0]
DEFAULT_BODY_TO_HEAD_TRANSLATION_MM = [0.35, 0.0, 0.12]
DEFAULT_BODY_TO_HEAD_YAW_PITCH_ROLL_DEG = [0.0, 0.0, 0.0]

DEFAULT_SYMMETRY_MODE = "mirror_across_head_sagittal_plane"
EXPLICIT_SYMMETRY_MODE = "explicit_per_eye"
SUPPORTED_SYMMETRY_MODES = (DEFAULT_SYMMETRY_MODE, EXPLICIT_SYMMETRY_MODE)
DEFAULT_MIRROR_AXIS = "head_y"

DEFAULT_DORSAL_REFERENCE_HEAD = [0.0, 0.0, 1.0]
DEFAULT_LEFT_EYE_CENTER_HEAD_MM = [0.18, 0.29, 0.02]
DEFAULT_LEFT_EYE_OPTICAL_AXIS_HEAD = [0.3420201433256687, 0.9396926207859084, 0.0]
DEFAULT_LEFT_EYE_TORSION_DEG = 0.0

DEFAULT_GEOMETRY_NAME = "canonical_hex_91"
DEFAULT_GEOMETRY_NAME_ALIASES = ("default", "canonical", "scientific_review_default")
FIXTURE_GEOMETRY_NAME = "fixture_hex_19"
FIXTURE_GEOMETRY_NAME_ALIASES = ("fixture", "test")

_FLOAT_ABS_TOL = 1.0e-9
_BASIS_SQRT3_OVER_2 = math.sqrt(3.0) * 0.5


@dataclass(frozen=True)
class RetinalGeometryPresetDefinition:
    name: str
    description: str
    lattice_defaults: Mapping[str, Any]
    body_to_head_defaults: Mapping[str, Any]
    left_eye_defaults: Mapping[str, Any]
    name_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class RigidTransform:
    source_frame: str
    target_frame: str
    rotation_matrix: np.ndarray
    translation_vector: np.ndarray

    def __post_init__(self) -> None:
        rotation = np.asarray(self.rotation_matrix, dtype=np.float64)
        translation = np.asarray(self.translation_vector, dtype=np.float64)
        if rotation.shape != (3, 3):
            raise ValueError("RigidTransform.rotation_matrix must have shape (3, 3).")
        if translation.shape != (3,):
            raise ValueError("RigidTransform.translation_vector must have shape (3,).")
        object.__setattr__(self, "rotation_matrix", rotation)
        object.__setattr__(self, "translation_vector", translation)

    def apply_to_points(self, points: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
        array = _as_matrix3(points, field_name="points")
        return (self.rotation_matrix @ array.T).T + self.translation_vector

    def apply_to_directions(self, directions: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
        array = _as_matrix3(directions, field_name="directions")
        return (self.rotation_matrix @ array.T).T

    def inverse(self) -> RigidTransform:
        inverse_rotation = self.rotation_matrix.T
        return RigidTransform(
            source_frame=self.target_frame,
            target_frame=self.source_frame,
            rotation_matrix=inverse_rotation,
            translation_vector=-(inverse_rotation @ self.translation_vector),
        )


@dataclass(frozen=True)
class ResolvedRetinalGeometry:
    retinal_geometry: dict[str, Any]
    registry_entry: dict[str, Any]

    @property
    def geometry_family(self) -> str:
        return str(self.retinal_geometry["geometry_family"])

    @property
    def geometry_name(self) -> str:
        return str(self.retinal_geometry["geometry_name"])

    @property
    def ommatidium_count_per_eye(self) -> int:
        return int(self.retinal_geometry["ommatidium_count_per_eye"])

    def build_eye_sampling(self) -> dict[str, Any]:
        return copy.deepcopy(self.retinal_geometry)

    def build_coordinate_frames(self) -> dict[str, Any]:
        return copy.deepcopy(self.retinal_geometry["coordinate_frames"])

    def build_world_to_body_transform(
        self,
        body_pose: Mapping[str, Any] | None = None,
    ) -> RigidTransform:
        return build_world_to_body_transform(body_pose)

    def build_body_to_head_transform(
        self,
        *,
        pose: Mapping[str, Any] | None = None,
    ) -> RigidTransform:
        return build_body_to_head_transform(self.retinal_geometry, pose=pose)

    def build_head_to_eye_transform(self, eye_label: str) -> RigidTransform:
        return build_head_to_eye_transform(self.retinal_geometry, eye_label)

    def build_eye_to_head_transform(self, eye_label: str) -> RigidTransform:
        return build_eye_to_head_transform(self.retinal_geometry, eye_label)

    def build_world_to_eye_transform(
        self,
        eye_label: str,
        *,
        body_pose: Mapping[str, Any] | None = None,
        head_pose: Mapping[str, Any] | None = None,
    ) -> RigidTransform:
        return compose_rigid_transforms(
            build_world_to_body_transform(body_pose),
            build_body_to_head_transform(self.retinal_geometry, pose=head_pose),
            build_head_to_eye_transform(self.retinal_geometry, eye_label),
        )

    def eye_direction_to_lattice(
        self,
        direction_eye: Sequence[float] | np.ndarray,
    ) -> dict[str, float]:
        return eye_direction_to_lattice_coordinates(self.retinal_geometry, direction_eye)

    def lattice_to_eye_direction(
        self,
        lattice_local: Mapping[str, Any] | Sequence[float],
    ) -> np.ndarray:
        return lattice_coordinates_to_eye_direction(self.retinal_geometry, lattice_local)

    def find_nearest_ommatidium(
        self,
        eye_label: str,
        *,
        direction_eye: Sequence[float] | np.ndarray | None = None,
        lattice_local: Mapping[str, Any] | Sequence[float] | None = None,
    ) -> dict[str, Any]:
        return find_nearest_ommatidium(
            self.retinal_geometry,
            eye_label,
            direction_eye=direction_eye,
            lattice_local=lattice_local,
        )


_PRESET_DEFINITIONS = (
    RetinalGeometryPresetDefinition(
        name=DEFAULT_GEOMETRY_NAME,
        description=(
            "Symmetric binocular hexagonal angular lattice with 91 detectors per eye, "
            "shared eye-local indexing, and mirrored left-right head embedding."
        ),
        lattice_defaults={
            "ring_count": 5,
            "interommatidial_angle_deg": 4.8,
        },
        body_to_head_defaults={
            "translation_body_mm": DEFAULT_BODY_TO_HEAD_TRANSLATION_MM,
            "yaw_pitch_roll_deg": DEFAULT_BODY_TO_HEAD_YAW_PITCH_ROLL_DEG,
        },
        left_eye_defaults={
            "center_head_mm": DEFAULT_LEFT_EYE_CENTER_HEAD_MM,
            "optical_axis_head": DEFAULT_LEFT_EYE_OPTICAL_AXIS_HEAD,
            "torsion_deg": DEFAULT_LEFT_EYE_TORSION_DEG,
            "dorsal_reference_head": DEFAULT_DORSAL_REFERENCE_HEAD,
        },
        name_aliases=DEFAULT_GEOMETRY_NAME_ALIASES,
    ),
    RetinalGeometryPresetDefinition(
        name=FIXTURE_GEOMETRY_NAME,
        description=(
            "Small deterministic fixture lattice with 19 detectors per eye for unit tests "
            "and offline transform checks."
        ),
        lattice_defaults={
            "ring_count": 2,
            "interommatidial_angle_deg": 6.0,
        },
        body_to_head_defaults={
            "translation_body_mm": [0.32, 0.0, 0.10],
            "yaw_pitch_roll_deg": DEFAULT_BODY_TO_HEAD_YAW_PITCH_ROLL_DEG,
        },
        left_eye_defaults={
            "center_head_mm": [0.16, 0.27, 0.03],
            "optical_axis_head": [0.3090169943749474, 0.9510565162951535, 0.0],
            "torsion_deg": 2.5,
            "dorsal_reference_head": DEFAULT_DORSAL_REFERENCE_HEAD,
        },
        name_aliases=FIXTURE_GEOMETRY_NAME_ALIASES,
    ),
)


def default_coordinate_frames() -> dict[str, Any]:
    return {
        "world_frame": {
            "frame_name": "world_cartesian",
            "handedness": "right_handed",
            "origin": "scene_defined_world_origin",
            "x_axis": "forward",
            "y_axis": "left",
            "z_axis": "up",
        },
        "body_frame": {
            "frame_name": "fly_body",
            "handedness": "right_handed",
            "origin": "thorax_center",
            "x_axis": "anterior",
            "y_axis": "left",
            "z_axis": "dorsal",
        },
        "head_frame": {
            "frame_name": "fly_head",
            "handedness": "right_handed",
            "origin": "head_center",
            "x_axis": "anterior",
            "y_axis": "left",
            "z_axis": "dorsal",
            "zero_pose_alignment": "aligned_with_body_frame",
        },
        "eye_frame": {
            "frame_name": "compound_eye_local",
            "handedness": "right_handed",
            "origin": "eye_center",
            "x_axis": "dorsal",
            "y_axis": "completes_right_handed_frame",
            "z_axis": "optical_axis_outward",
            "positive_azimuth": "toward_positive_y",
            "positive_elevation": "toward_positive_x",
        },
        "lattice_local_frame": {
            "frame_name": "retinotopic_lattice_local",
            "coordinate_space": DEFAULT_LATTICE_COORDINATE_SPACE,
            "coordinate_system": DEFAULT_LATTICE_COORDINATE_SYSTEM,
            "u_axis": "axial_q_toward_positive_azimuth_and_positive_elevation",
            "v_axis": "axial_r_toward_positive_elevation",
            "positive_azimuth": "toward_positive_y",
            "positive_elevation": "toward_positive_x",
        },
    }


def has_retinal_geometry_reference(payload: Mapping[str, Any]) -> bool:
    if not isinstance(payload, Mapping):
        return False
    if isinstance(payload.get("retinal_geometry"), Mapping):
        return True
    keys = {
        "geometry_family",
        "geometry_name",
        "retinal_geometry_family",
        "retinal_geometry_name",
        "lattice",
        "eyes",
        "body_to_head",
        "world_to_body_defaults",
    }
    return any(key in payload for key in keys)


def list_retinal_geometry_presets(geometry_family: str | None = None) -> list[dict[str, Any]]:
    canonical_family, _ = _resolve_geometry_family(geometry_family or DEFAULT_GEOMETRY_FAMILY)
    if canonical_family != DEFAULT_GEOMETRY_FAMILY:
        raise ValueError(f"Unsupported retinal geometry family {canonical_family!r}.")
    return [get_retinal_geometry_registry_entry(canonical_family, preset.name) for preset in _PRESET_DEFINITIONS]


def get_retinal_geometry_registry_entry(
    geometry_family: str,
    geometry_name: str,
) -> dict[str, Any]:
    canonical_family, _ = _resolve_geometry_family(geometry_family)
    preset, _ = _resolve_geometry_name(geometry_name)
    return {
        "geometry_family": canonical_family,
        "geometry_name": preset.name,
        "description": preset.description,
        "family_aliases": list(DEFAULT_GEOMETRY_FAMILY_ALIASES),
        "name_aliases": list(preset.name_aliases),
        "geometry_version": RETINAL_GEOMETRY_VERSION,
        "lattice_family": DEFAULT_LATTICE_FAMILY,
        "lattice_version": DEFAULT_LATTICE_VERSION,
        "default_eye_order": list(DEFAULT_EYE_ORDER),
        "default_eye_indexing": DEFAULT_EYE_INDEXING,
        "default_ommatidial_ordering": DEFAULT_OMMATIDIAL_ORDERING,
        "default_coordinate_frames": default_coordinate_frames(),
        "supported_symmetry_modes": list(SUPPORTED_SYMMETRY_MODES),
        "default_symmetry_mode": DEFAULT_SYMMETRY_MODE,
        "compatibility_aliases": [
            {
                "geometry_family": alias,
                "geometry_name": alias_name,
            }
            for alias in DEFAULT_GEOMETRY_FAMILY_ALIASES
            for alias_name in preset.name_aliases
        ],
    }


def resolve_retinal_geometry_spec(
    payload: Mapping[str, Any] | None = None,
    *,
    retinal_geometry: Mapping[str, Any] | None = None,
    geometry_family: str | None = None,
    geometry_name: str | None = None,
) -> ResolvedRetinalGeometry:
    source = _extract_retinal_geometry_mapping(payload, retinal_geometry=retinal_geometry)
    canonical_family, _family_alias_used = _resolve_geometry_family(
        geometry_family
        or source.get("geometry_family")
        or source.get("retinal_geometry_family")
        or DEFAULT_GEOMETRY_FAMILY
    )
    preset, _name_alias_used = _resolve_geometry_name(
        geometry_name
        or source.get("geometry_name")
        or source.get("retinal_geometry_name")
        or DEFAULT_GEOMETRY_NAME
    )
    registry_entry = get_retinal_geometry_registry_entry(canonical_family, preset.name)

    coordinate_frames = default_coordinate_frames()
    provided_coordinate_frames = source.get("coordinate_frames")
    if provided_coordinate_frames is not None:
        normalized_coordinate_frames = _normalize_json_mapping_like(
            provided_coordinate_frames,
            field_name="retinal_geometry.coordinate_frames",
        )
        expected_coordinate_frames = _normalize_json_mapping_like(
            coordinate_frames,
            field_name="retinal_geometry.coordinate_frames",
        )
        if normalized_coordinate_frames != expected_coordinate_frames:
            raise ValueError(
                "retinal_geometry.coordinate_frames must match the canonical Milestone 8B "
                "world/body/head/eye/lattice frame conventions."
            )

    world_to_body_defaults = _normalize_pose_defaults(
        source.get("world_to_body_defaults"),
        default_translation_mm=DEFAULT_WORLD_TO_BODY_TRANSLATION_MM,
        default_yaw_pitch_roll_deg=DEFAULT_WORLD_TO_BODY_YAW_PITCH_ROLL_DEG,
        field_name="retinal_geometry.world_to_body_defaults",
        rotation_parameterization=DEFAULT_WORLD_TO_BODY_ROTATION_PARAMETERIZATION,
        source_frame="world_cartesian",
        target_frame="fly_body",
        translation_label="translation_world_mm",
    )
    body_to_head = _normalize_pose_defaults(
        source.get("body_to_head"),
        default_translation_mm=preset.body_to_head_defaults["translation_body_mm"],
        default_yaw_pitch_roll_deg=preset.body_to_head_defaults["yaw_pitch_roll_deg"],
        field_name="retinal_geometry.body_to_head",
        rotation_parameterization=DEFAULT_BODY_TO_HEAD_ROTATION_PARAMETERIZATION,
        source_frame="fly_body",
        target_frame="fly_head",
        translation_label="translation_body_mm",
    )

    lattice_payload = source.get("lattice")
    lattice = _normalize_lattice_payload(lattice_payload, preset=preset)

    eye_order = _normalize_eye_order(source.get("eye_order", DEFAULT_EYE_ORDER))
    if set(eye_order) != set(DEFAULT_EYE_ORDER):
        raise ValueError(
            "retinal_geometry.eye_order must contain both left and right exactly once for Milestone 8B."
        )

    eyes_payload = source.get("eyes")
    if eyes_payload is None:
        eyes_payload = {}
    if not isinstance(eyes_payload, Mapping):
        raise ValueError("retinal_geometry.eyes must be a mapping when provided.")
    symmetry = _normalize_symmetry_payload(eyes_payload.get("symmetry") or source.get("symmetry"))

    left_eye = _normalize_eye_payload(
        eye_label=LEFT_EYE,
        payload=eyes_payload.get(LEFT_EYE),
        defaults=preset.left_eye_defaults,
        field_name="retinal_geometry.eyes.left",
    )

    if symmetry["mode"] == DEFAULT_SYMMETRY_MODE:
        right_payload = eyes_payload.get(RIGHT_EYE)
        if right_payload is not None and (
            not isinstance(right_payload, Mapping)
            or str(right_payload.get("symmetry_source", "")) != "mirrored_from_left"
        ):
            raise ValueError(
                "retinal_geometry.eyes.right may not be provided when symmetry.mode mirrors the right eye "
                "from the left eye."
            )
        right_eye = _mirror_eye_payload(left_eye, eye_label=RIGHT_EYE)
        right_eye["symmetry_source"] = "mirrored_from_left"
    else:
        if eyes_payload.get(RIGHT_EYE) is None:
            raise ValueError(
                "retinal_geometry.eyes.right must be provided when symmetry.mode is explicit_per_eye."
            )
        right_defaults = _mirror_eye_payload(
            _normalize_eye_payload(
                eye_label=LEFT_EYE,
                payload=None,
                defaults=preset.left_eye_defaults,
                field_name="retinal_geometry.eyes.left",
            ),
            eye_label=RIGHT_EYE,
        )
        right_eye = _normalize_eye_payload(
            eye_label=RIGHT_EYE,
            payload=eyes_payload.get(RIGHT_EYE),
            defaults=right_defaults,
            field_name="retinal_geometry.eyes.right",
        )

    normalized_eyes = {
        LEFT_EYE: left_eye,
        RIGHT_EYE: right_eye,
    }

    detector_layout = _build_detector_layout(lattice)
    per_eye = {
        eye_label: _build_per_eye_spec(
            eye_label=eye_label,
            eye_payload=normalized_eyes[eye_label],
            detector_layout=detector_layout,
        )
        for eye_label in DEFAULT_EYE_ORDER
    }

    if per_eye[LEFT_EYE]["detector_table"] and per_eye[RIGHT_EYE]["detector_table"]:
        if per_eye[LEFT_EYE]["detector_table"][0]["ommatidium_index"] != 0:
            raise AssertionError("Detector layout generation must start at index 0.")
        if per_eye[RIGHT_EYE]["detector_table"][0]["ommatidium_index"] != 0:
            raise AssertionError("Detector layout generation must be shared across eyes.")

    compatibility_aliases = [
        {
            "geometry_family": alias_family,
            "geometry_name": alias_name,
        }
        for alias_family in DEFAULT_GEOMETRY_FAMILY_ALIASES
        for alias_name in preset.name_aliases
    ]
    lattice_id = _build_lattice_id(preset.name, lattice)
    _validate_optional_lattice_identity(source, lattice_id=lattice_id)

    retinal_geometry_spec = {
        "geometry_spec_version": RETINAL_GEOMETRY_SPEC_VERSION,
        "geometry_family": canonical_family,
        "geometry_name": preset.name,
        "geometry_version": RETINAL_GEOMETRY_VERSION,
        "geometry_description": preset.description,
        "compatibility_aliases": compatibility_aliases,
        "lattice_family": DEFAULT_LATTICE_FAMILY,
        "lattice_id": lattice_id,
        "lattice_version": DEFAULT_LATTICE_VERSION,
        "eye_order": list(eye_order),
        "eye_indexing": DEFAULT_EYE_INDEXING,
        "ommatidium_count_per_eye": len(detector_layout),
        "ommatidial_ordering": DEFAULT_OMMATIDIAL_ORDERING,
        "world_to_body_defaults": world_to_body_defaults,
        "body_to_head": body_to_head,
        "symmetry": symmetry,
        "eyes": {
            LEFT_EYE: left_eye,
            RIGHT_EYE: right_eye,
        },
        "lattice": lattice,
        "lattice_indexing": _build_lattice_indexing(detector_layout, lattice["ring_count"]),
        "per_eye": per_eye,
        "coordinate_frames": coordinate_frames,
    }
    return ResolvedRetinalGeometry(
        retinal_geometry=retinal_geometry_spec,
        registry_entry=registry_entry,
    )


def compose_rigid_transforms(*transforms: RigidTransform) -> RigidTransform:
    if not transforms:
        raise ValueError("compose_rigid_transforms requires at least one transform.")
    result = transforms[0]
    for transform in transforms[1:]:
        if result.target_frame != transform.source_frame:
            raise ValueError(
                "Cannot compose transforms when frames do not line up: "
                f"{result.target_frame!r} != {transform.source_frame!r}."
            )
        result = RigidTransform(
            source_frame=result.source_frame,
            target_frame=transform.target_frame,
            rotation_matrix=transform.rotation_matrix @ result.rotation_matrix,
            translation_vector=transform.rotation_matrix @ result.translation_vector + transform.translation_vector,
        )
    return result


def build_world_to_body_transform(body_pose: Mapping[str, Any] | None = None) -> RigidTransform:
    normalized = _normalize_pose_defaults(
        body_pose,
        default_translation_mm=DEFAULT_WORLD_TO_BODY_TRANSLATION_MM,
        default_yaw_pitch_roll_deg=DEFAULT_WORLD_TO_BODY_YAW_PITCH_ROLL_DEG,
        field_name="body_pose",
        rotation_parameterization=DEFAULT_WORLD_TO_BODY_ROTATION_PARAMETERIZATION,
        source_frame="world_cartesian",
        target_frame="fly_body",
        translation_label="translation_world_mm",
    )
    body_to_world_rotation = _rotation_matrix_from_yaw_pitch_roll_deg(
        normalized["yaw_pitch_roll_deg"],
    )
    rotation_matrix = body_to_world_rotation.T
    translation_vector = -rotation_matrix @ np.asarray(normalized["translation_world_mm"], dtype=np.float64)
    return RigidTransform(
        source_frame="world_cartesian",
        target_frame="fly_body",
        rotation_matrix=rotation_matrix,
        translation_vector=translation_vector,
    )


def build_body_to_head_transform(
    retinal_geometry: Mapping[str, Any] | ResolvedRetinalGeometry,
    *,
    pose: Mapping[str, Any] | None = None,
) -> RigidTransform:
    geometry = _extract_geometry_spec(retinal_geometry)
    source_payload = pose if pose is not None else geometry["body_to_head"]
    normalized = _normalize_pose_defaults(
        source_payload,
        default_translation_mm=geometry["body_to_head"]["translation_body_mm"],
        default_yaw_pitch_roll_deg=geometry["body_to_head"]["yaw_pitch_roll_deg"],
        field_name="body_to_head",
        rotation_parameterization=DEFAULT_BODY_TO_HEAD_ROTATION_PARAMETERIZATION,
        source_frame="fly_body",
        target_frame="fly_head",
        translation_label="translation_body_mm",
    )
    head_to_body_rotation = _rotation_matrix_from_yaw_pitch_roll_deg(normalized["yaw_pitch_roll_deg"])
    rotation_matrix = head_to_body_rotation.T
    translation_vector = -rotation_matrix @ np.asarray(normalized["translation_body_mm"], dtype=np.float64)
    return RigidTransform(
        source_frame="fly_body",
        target_frame="fly_head",
        rotation_matrix=rotation_matrix,
        translation_vector=translation_vector,
    )


def build_head_to_eye_transform(
    retinal_geometry: Mapping[str, Any] | ResolvedRetinalGeometry,
    eye_label: str,
) -> RigidTransform:
    geometry = _extract_geometry_spec(retinal_geometry)
    normalized_eye_label = _normalize_eye_label(eye_label, field_name="eye_label")
    eye_spec = geometry["per_eye"][normalized_eye_label]
    rotation_matrix = np.asarray(eye_spec["rotation_head_to_eye"], dtype=np.float64)
    center_head = np.asarray(eye_spec["center_head_mm"], dtype=np.float64)
    return RigidTransform(
        source_frame="fly_head",
        target_frame="compound_eye_local",
        rotation_matrix=rotation_matrix,
        translation_vector=-(rotation_matrix @ center_head),
    )


def build_eye_to_head_transform(
    retinal_geometry: Mapping[str, Any] | ResolvedRetinalGeometry,
    eye_label: str,
) -> RigidTransform:
    geometry = _extract_geometry_spec(retinal_geometry)
    normalized_eye_label = _normalize_eye_label(eye_label, field_name="eye_label")
    eye_spec = geometry["per_eye"][normalized_eye_label]
    return RigidTransform(
        source_frame="compound_eye_local",
        target_frame="fly_head",
        rotation_matrix=np.asarray(eye_spec["rotation_eye_to_head"], dtype=np.float64),
        translation_vector=np.asarray(eye_spec["center_head_mm"], dtype=np.float64),
    )


def eye_direction_to_lattice_coordinates(
    retinal_geometry: Mapping[str, Any] | ResolvedRetinalGeometry,
    direction_eye: Sequence[float] | np.ndarray,
) -> dict[str, float]:
    geometry = _extract_geometry_spec(retinal_geometry)
    unit_direction = _normalize_unit_vector(direction_eye, field_name="direction_eye")
    azimuth_deg, elevation_deg = eye_direction_to_angles_deg(unit_direction)
    pitch_deg = float(geometry["lattice"]["interommatidial_angle_deg"])
    axial_q = azimuth_deg / (pitch_deg * _BASIS_SQRT3_OVER_2)
    axial_r = (elevation_deg / pitch_deg) - (0.5 * axial_q)
    return {
        "axial_q": _rounded_float(axial_q),
        "axial_r": _rounded_float(axial_r),
        "azimuth_deg": _rounded_float(azimuth_deg),
        "elevation_deg": _rounded_float(elevation_deg),
    }


def lattice_coordinates_to_eye_direction(
    retinal_geometry: Mapping[str, Any] | ResolvedRetinalGeometry,
    lattice_local: Mapping[str, Any] | Sequence[float],
) -> np.ndarray:
    geometry = _extract_geometry_spec(retinal_geometry)
    axial_q, axial_r = _normalize_lattice_local_coordinates(lattice_local)
    pitch_deg = float(geometry["lattice"]["interommatidial_angle_deg"])
    azimuth_deg = pitch_deg * _BASIS_SQRT3_OVER_2 * axial_q
    elevation_deg = pitch_deg * (0.5 * axial_q + axial_r)
    return angles_deg_to_eye_direction(azimuth_deg=azimuth_deg, elevation_deg=elevation_deg)


def eye_direction_to_angles_deg(direction_eye: Sequence[float] | np.ndarray) -> tuple[float, float]:
    unit_direction = _normalize_unit_vector(direction_eye, field_name="direction_eye")
    azimuth_deg = math.degrees(math.atan2(float(unit_direction[1]), float(unit_direction[2])))
    elevation_deg = math.degrees(
        math.atan2(float(unit_direction[0]), math.hypot(float(unit_direction[1]), float(unit_direction[2])))
    )
    return azimuth_deg, elevation_deg


def angles_deg_to_eye_direction(*, azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    azimuth_rad = math.radians(float(azimuth_deg))
    elevation_rad = math.radians(float(elevation_deg))
    cos_elevation = math.cos(elevation_rad)
    direction = np.asarray(
        [
            math.sin(elevation_rad),
            cos_elevation * math.sin(azimuth_rad),
            cos_elevation * math.cos(azimuth_rad),
        ],
        dtype=np.float64,
    )
    return direction / np.linalg.norm(direction)


def find_nearest_ommatidium(
    retinal_geometry: Mapping[str, Any] | ResolvedRetinalGeometry,
    eye_label: str,
    *,
    direction_eye: Sequence[float] | np.ndarray | None = None,
    lattice_local: Mapping[str, Any] | Sequence[float] | None = None,
) -> dict[str, Any]:
    geometry = _extract_geometry_spec(retinal_geometry)
    normalized_eye_label = _normalize_eye_label(eye_label, field_name="eye_label")
    if (direction_eye is None) == (lattice_local is None):
        raise ValueError("Provide exactly one of direction_eye or lattice_local.")
    if direction_eye is not None:
        query = eye_direction_to_lattice_coordinates(geometry, direction_eye)
    else:
        axial_q, axial_r = _normalize_lattice_local_coordinates(lattice_local)
        query = {"axial_q": axial_q, "axial_r": axial_r}
    detector_table = geometry["per_eye"][normalized_eye_label]["detector_table"]
    best = min(
        detector_table,
        key=lambda detector: (
            (float(detector["axial_q"]) - float(query["axial_q"])) ** 2
            + (float(detector["axial_r"]) - float(query["axial_r"])) ** 2,
            int(detector["ommatidium_index"]),
        ),
    )
    return copy.deepcopy(best)


def _extract_retinal_geometry_mapping(
    payload: Mapping[str, Any] | None,
    *,
    retinal_geometry: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if retinal_geometry is not None:
        if not isinstance(retinal_geometry, Mapping):
            raise ValueError("retinal_geometry must be a mapping when provided.")
        return retinal_geometry
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError("retinal_geometry payload must be a mapping.")
    nested = payload.get("retinal_geometry")
    if isinstance(nested, Mapping):
        return nested
    return payload


def _resolve_geometry_family(value: Any) -> tuple[str, bool]:
    canonical = _normalize_identifier(value, field_name="retinal_geometry.geometry_family")
    if canonical == DEFAULT_GEOMETRY_FAMILY:
        return canonical, False
    if canonical in DEFAULT_GEOMETRY_FAMILY_ALIASES:
        return DEFAULT_GEOMETRY_FAMILY, True
    allowed = [DEFAULT_GEOMETRY_FAMILY, *DEFAULT_GEOMETRY_FAMILY_ALIASES]
    raise ValueError(
        "Unsupported retinal_geometry.geometry_family "
        f"{canonical!r}. Supported values: {allowed!r}."
    )


def _resolve_geometry_name(value: Any) -> tuple[RetinalGeometryPresetDefinition, bool]:
    canonical = _normalize_identifier(value, field_name="retinal_geometry.geometry_name")
    for preset in _PRESET_DEFINITIONS:
        if canonical == preset.name:
            return preset, False
        if canonical in preset.name_aliases:
            return preset, True
    available = [preset.name for preset in _PRESET_DEFINITIONS]
    matches = get_close_matches(canonical, available, n=1)
    suggestion = f" Did you mean {matches[0]!r}?" if matches else ""
    raise ValueError(
        "Unsupported retinal_geometry.geometry_name "
        f"{canonical!r}. Supported values: {available!r}.{suggestion}"
    )


def _normalize_lattice_payload(
    payload: Any,
    *,
    preset: RetinalGeometryPresetDefinition,
) -> dict[str, Any]:
    if payload is None:
        payload = {}
    if not isinstance(payload, Mapping):
        raise ValueError("retinal_geometry.lattice must be a mapping when provided.")
    lattice_family = _normalize_nonempty_string(
        payload.get("lattice_family", DEFAULT_LATTICE_FAMILY),
        field_name="retinal_geometry.lattice.lattice_family",
    )
    if lattice_family != DEFAULT_LATTICE_FAMILY:
        raise ValueError(
            f"retinal_geometry.lattice.lattice_family must be {DEFAULT_LATTICE_FAMILY!r}, got {lattice_family!r}."
        )
    lattice_version = _normalize_nonempty_string(
        payload.get("lattice_version", DEFAULT_LATTICE_VERSION),
        field_name="retinal_geometry.lattice.lattice_version",
    )
    if lattice_version != DEFAULT_LATTICE_VERSION:
        raise ValueError(
            f"retinal_geometry.lattice.lattice_version must be {DEFAULT_LATTICE_VERSION!r}, got {lattice_version!r}."
        )
    coordinate_system = _normalize_nonempty_string(
        payload.get("coordinate_system", DEFAULT_LATTICE_COORDINATE_SYSTEM),
        field_name="retinal_geometry.lattice.coordinate_system",
    )
    if coordinate_system != DEFAULT_LATTICE_COORDINATE_SYSTEM:
        raise ValueError(
            "retinal_geometry.lattice.coordinate_system must be "
            f"{DEFAULT_LATTICE_COORDINATE_SYSTEM!r}, got {coordinate_system!r}."
        )
    coordinate_space = _normalize_nonempty_string(
        payload.get("coordinate_space", DEFAULT_LATTICE_COORDINATE_SPACE),
        field_name="retinal_geometry.lattice.coordinate_space",
    )
    if coordinate_space != DEFAULT_LATTICE_COORDINATE_SPACE:
        raise ValueError(
            "retinal_geometry.lattice.coordinate_space must be "
            f"{DEFAULT_LATTICE_COORDINATE_SPACE!r}, got {coordinate_space!r}."
        )
    projection_model = _normalize_nonempty_string(
        payload.get("projection_model", DEFAULT_LATTICE_PROJECTION),
        field_name="retinal_geometry.lattice.projection_model",
    )
    if projection_model != DEFAULT_LATTICE_PROJECTION:
        raise ValueError(
            "retinal_geometry.lattice.projection_model must be "
            f"{DEFAULT_LATTICE_PROJECTION!r}, got {projection_model!r}."
        )
    ring_count = _normalize_nonnegative_int(
        payload.get("ring_count", preset.lattice_defaults["ring_count"]),
        field_name="retinal_geometry.lattice.ring_count",
    )
    pitch_deg = _normalize_positive_float(
        payload.get(
            "interommatidial_angle_deg",
            preset.lattice_defaults["interommatidial_angle_deg"],
        ),
        field_name="retinal_geometry.lattice.interommatidial_angle_deg",
    )
    detector_count = 1 + 3 * ring_count * (ring_count + 1)
    coverage_radius_deg = max(
        pitch_deg * ring_count,
        pitch_deg * (ring_count + 0.5),
    )
    return {
        "lattice_family": DEFAULT_LATTICE_FAMILY,
        "lattice_version": DEFAULT_LATTICE_VERSION,
        "coordinate_system": DEFAULT_LATTICE_COORDINATE_SYSTEM,
        "coordinate_space": DEFAULT_LATTICE_COORDINATE_SPACE,
        "projection_model": DEFAULT_LATTICE_PROJECTION,
        "ring_count": ring_count,
        "interommatidial_angle_deg": _rounded_float(pitch_deg),
        "detector_count": detector_count,
        "coverage_radius_deg": _rounded_float(coverage_radius_deg),
        "bin_lookup_rule": DEFAULT_LATTICE_BIN_LOOKUP,
        "neighbor_spacing_rule": "nearest_neighbor_center_distance_matches_interommatidial_angle",
    }


def _normalize_eye_order(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("retinal_geometry.eye_order must be a non-empty list.")
    eye_order = [_normalize_eye_label(item, field_name="retinal_geometry.eye_order") for item in value]
    if len(set(eye_order)) != len(eye_order):
        raise ValueError("retinal_geometry.eye_order may not contain duplicate eye labels.")
    return eye_order


def _normalize_symmetry_payload(payload: Any) -> dict[str, Any]:
    if payload is None:
        payload = {}
    if not isinstance(payload, Mapping):
        raise ValueError("retinal_geometry.eyes.symmetry must be a mapping when provided.")
    mode = _normalize_nonempty_string(
        payload.get("mode", DEFAULT_SYMMETRY_MODE),
        field_name="retinal_geometry.eyes.symmetry.mode",
    )
    if mode not in SUPPORTED_SYMMETRY_MODES:
        raise ValueError(
            "Unsupported retinal_geometry.eyes.symmetry.mode "
            f"{mode!r}. Supported modes: {list(SUPPORTED_SYMMETRY_MODES)!r}."
        )
    mirror_axis = _normalize_nonempty_string(
        payload.get("mirror_axis", DEFAULT_MIRROR_AXIS),
        field_name="retinal_geometry.eyes.symmetry.mirror_axis",
    )
    if mirror_axis != DEFAULT_MIRROR_AXIS:
        raise ValueError(
            f"retinal_geometry.eyes.symmetry.mirror_axis must be {DEFAULT_MIRROR_AXIS!r}, got {mirror_axis!r}."
        )
    source_eye = _normalize_eye_label(
        payload.get("source_eye", LEFT_EYE),
        field_name="retinal_geometry.eyes.symmetry.source_eye",
    )
    generated_eye = _normalize_eye_label(
        payload.get("generated_eye", RIGHT_EYE),
        field_name="retinal_geometry.eyes.symmetry.generated_eye",
    )
    if source_eye == generated_eye:
        raise ValueError("retinal_geometry.eyes.symmetry.source_eye and generated_eye must differ.")
    return {
        "mode": mode,
        "source_eye": source_eye,
        "generated_eye": generated_eye,
        "mirror_axis": mirror_axis,
        "shared_lattice": True,
        "shared_eye_local_axes": True,
        "shared_detector_indexing": True,
    }


def _normalize_eye_payload(
    *,
    eye_label: str,
    payload: Any,
    defaults: Mapping[str, Any],
    field_name: str,
) -> dict[str, Any]:
    if payload is None:
        payload = {}
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping when provided.")
    center_head_mm = _normalize_vector3(
        payload.get("center_head_mm", defaults["center_head_mm"]),
        field_name=f"{field_name}.center_head_mm",
    )
    optical_axis_head = _normalize_unit_vector(
        payload.get("optical_axis_head", defaults["optical_axis_head"]),
        field_name=f"{field_name}.optical_axis_head",
    )
    dorsal_reference_head = _normalize_unit_vector(
        payload.get("dorsal_reference_head", defaults["dorsal_reference_head"]),
        field_name=f"{field_name}.dorsal_reference_head",
    )
    torsion_deg = _normalize_float(
        payload.get("torsion_deg", defaults["torsion_deg"]),
        field_name=f"{field_name}.torsion_deg",
    )
    return {
        "eye_label": eye_label,
        "center_head_mm": _vector_to_list(center_head_mm),
        "optical_axis_head": _vector_to_list(optical_axis_head),
        "dorsal_reference_head": _vector_to_list(dorsal_reference_head),
        "torsion_deg": _rounded_float(torsion_deg),
        "symmetry_source": "explicit",
    }


def _mirror_eye_payload(payload: Mapping[str, Any], *, eye_label: str) -> dict[str, Any]:
    return {
        "eye_label": eye_label,
        "center_head_mm": [
            _rounded_float(float(payload["center_head_mm"][0])),
            _rounded_float(-float(payload["center_head_mm"][1])),
            _rounded_float(float(payload["center_head_mm"][2])),
        ],
        "optical_axis_head": [
            _rounded_float(float(payload["optical_axis_head"][0])),
            _rounded_float(-float(payload["optical_axis_head"][1])),
            _rounded_float(float(payload["optical_axis_head"][2])),
        ],
        "dorsal_reference_head": [
            _rounded_float(float(payload["dorsal_reference_head"][0])),
            _rounded_float(-float(payload["dorsal_reference_head"][1])),
            _rounded_float(float(payload["dorsal_reference_head"][2])),
        ],
        "torsion_deg": _rounded_float(-float(payload["torsion_deg"])),
        "symmetry_source": "mirrored_from_left",
    }


def _build_detector_layout(lattice: Mapping[str, Any]) -> list[dict[str, Any]]:
    ring_count = int(lattice["ring_count"])
    pitch_deg = float(lattice["interommatidial_angle_deg"])
    detectors: list[dict[str, Any]] = []
    for axial_q in range(-ring_count, ring_count + 1):
        for axial_r in range(-ring_count, ring_count + 1):
            axial_s = -axial_q - axial_r
            ring_index = max(abs(axial_q), abs(axial_r), abs(axial_s))
            if ring_index > ring_count:
                continue
            azimuth_deg = pitch_deg * _BASIS_SQRT3_OVER_2 * axial_q
            elevation_deg = pitch_deg * (0.5 * axial_q + axial_r)
            angle = math.degrees(math.atan2(azimuth_deg, elevation_deg))
            clockwise_angle_deg = (angle + 360.0) % 360.0
            detectors.append(
                {
                    "axial_q": axial_q,
                    "axial_r": axial_r,
                    "ring_index": ring_index,
                    "sort_angle_deg": 0.0 if ring_index == 0 else clockwise_angle_deg,
                    "azimuth_deg": _rounded_float(azimuth_deg),
                    "elevation_deg": _rounded_float(elevation_deg),
                    "direction_eye": _vector_to_list(
                        angles_deg_to_eye_direction(
                            azimuth_deg=azimuth_deg,
                            elevation_deg=elevation_deg,
                        )
                    ),
                }
            )
    detectors.sort(
        key=lambda detector: (
            int(detector["ring_index"]),
            float(detector["sort_angle_deg"]),
            int(detector["axial_q"]),
            int(detector["axial_r"]),
        )
    )
    ring_positions: dict[int, int] = {}
    normalized: list[dict[str, Any]] = []
    for index, detector in enumerate(detectors):
        ring_index = int(detector["ring_index"])
        ring_position = ring_positions.get(ring_index, 0)
        ring_positions[ring_index] = ring_position + 1
        normalized.append(
            {
                "ommatidium_index": index,
                "ring_index": ring_index,
                "ring_position": ring_position,
                "axial_q": int(detector["axial_q"]),
                "axial_r": int(detector["axial_r"]),
                "lattice_local_azimuth_deg": _rounded_float(detector["azimuth_deg"]),
                "lattice_local_elevation_deg": _rounded_float(detector["elevation_deg"]),
                "eye_azimuth_deg": _rounded_float(detector["azimuth_deg"]),
                "eye_elevation_deg": _rounded_float(detector["elevation_deg"]),
                "direction_eye": list(detector["direction_eye"]),
            }
        )
    return normalized


def _build_lattice_indexing(
    detector_layout: Sequence[Mapping[str, Any]],
    ring_count: int,
) -> dict[str, Any]:
    ring_detector_counts = [1]
    for ring_index in range(1, ring_count + 1):
        ring_detector_counts.append(6 * ring_index)
    return {
        "indexing_family": DEFAULT_INDEXING_FAMILY,
        "clockwise_view": DEFAULT_INDEXING_CLOCKWISE_VIEW,
        "center_index": 0,
        "ring_count": ring_count,
        "ring_detector_counts": ring_detector_counts,
        "ring_index_by_detector": [int(detector["ring_index"]) for detector in detector_layout],
        "ring_position_by_detector": [int(detector["ring_position"]) for detector in detector_layout],
    }


def _build_per_eye_spec(
    *,
    eye_label: str,
    eye_payload: Mapping[str, Any],
    detector_layout: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    center_head = _normalize_vector3(
        eye_payload["center_head_mm"],
        field_name=f"retinal_geometry.eyes.{eye_label}.center_head_mm",
    )
    optical_axis_head = _normalize_unit_vector(
        eye_payload["optical_axis_head"],
        field_name=f"retinal_geometry.eyes.{eye_label}.optical_axis_head",
    )
    dorsal_reference_head = _normalize_unit_vector(
        eye_payload["dorsal_reference_head"],
        field_name=f"retinal_geometry.eyes.{eye_label}.dorsal_reference_head",
    )
    torsion_deg = float(eye_payload["torsion_deg"])

    x_axis_head, y_axis_head, z_axis_head = _build_eye_axes(
        optical_axis_head=optical_axis_head,
        dorsal_reference_head=dorsal_reference_head,
        torsion_deg=torsion_deg,
        field_name=f"retinal_geometry.eyes.{eye_label}",
    )
    rotation_eye_to_head = np.column_stack([x_axis_head, y_axis_head, z_axis_head])
    rotation_head_to_eye = rotation_eye_to_head.T

    detector_table: list[dict[str, Any]] = []
    for detector in detector_layout:
        direction_eye = np.asarray(detector["direction_eye"], dtype=np.float64)
        direction_head = rotation_eye_to_head @ direction_eye
        detector_table.append(
            {
                **copy.deepcopy(dict(detector)),
                "direction_head": _vector_to_list(direction_head),
            }
        )

    return {
        "eye_label": eye_label,
        "symmetry_source": str(eye_payload["symmetry_source"]),
        "center_head_mm": _vector_to_list(center_head),
        "optical_axis_head": _vector_to_list(optical_axis_head),
        "dorsal_reference_head": _vector_to_list(dorsal_reference_head),
        "torsion_deg": _rounded_float(torsion_deg),
        "eye_axes_in_head": {
            "x": _vector_to_list(x_axis_head),
            "y": _vector_to_list(y_axis_head),
            "z": _vector_to_list(z_axis_head),
        },
        "rotation_parameterization": DEFAULT_EYE_ROTATION_PARAMETERIZATION,
        "rotation_eye_to_head": _matrix_to_list(rotation_eye_to_head),
        "rotation_head_to_eye": _matrix_to_list(rotation_head_to_eye),
        "detector_table": detector_table,
    }


def _build_eye_axes(
    *,
    optical_axis_head: np.ndarray,
    dorsal_reference_head: np.ndarray,
    torsion_deg: float,
    field_name: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z_axis = optical_axis_head / np.linalg.norm(optical_axis_head)
    dorsal_projection = dorsal_reference_head - np.dot(dorsal_reference_head, z_axis) * z_axis
    norm = float(np.linalg.norm(dorsal_projection))
    if norm <= _FLOAT_ABS_TOL:
        raise ValueError(
            f"{field_name}.dorsal_reference_head is parallel to the optical axis, so the eye frame would be ambiguous."
        )
    x_axis = dorsal_projection / norm
    if not math.isclose(torsion_deg, 0.0, rel_tol=0.0, abs_tol=_FLOAT_ABS_TOL):
        x_axis = _rotate_about_axis(x_axis, z_axis, math.radians(torsion_deg))
        x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)
    y_axis = y_axis / np.linalg.norm(y_axis)
    reconstructed = np.cross(x_axis, y_axis)
    if not np.allclose(reconstructed, z_axis, atol=1.0e-9, rtol=0.0):
        raise ValueError(f"{field_name} produced a non-right-handed eye frame.")
    return x_axis, y_axis, z_axis


def _validate_optional_lattice_identity(payload: Mapping[str, Any], *, lattice_id: str) -> None:
    raw_lattice_id = payload.get("lattice_id")
    if raw_lattice_id is None and isinstance(payload.get("lattice"), Mapping):
        raw_lattice_id = payload["lattice"].get("lattice_id")
    if raw_lattice_id is None:
        return
    normalized = _normalize_identifier(raw_lattice_id, field_name="retinal_geometry.lattice_id")
    if normalized != lattice_id:
        raise ValueError(
            "retinal_geometry.lattice_id does not match the canonical lattice identity "
            f"{lattice_id!r} for the resolved geometry."
        )


def _build_lattice_id(geometry_name: str, lattice: Mapping[str, Any]) -> str:
    pitch = str(lattice["interommatidial_angle_deg"]).replace(".", "p")
    return _normalize_identifier(
        f"{geometry_name}_r{lattice['ring_count']}_pitch{pitch}deg",
        field_name="retinal_geometry.lattice_id",
    )


def _normalize_pose_defaults(
    payload: Any,
    *,
    default_translation_mm: Sequence[float],
    default_yaw_pitch_roll_deg: Sequence[float],
    field_name: str,
    rotation_parameterization: str,
    source_frame: str,
    target_frame: str,
    translation_label: str,
) -> dict[str, Any]:
    if payload is None:
        payload = {}
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping when provided.")
    translation = _normalize_vector3(
        payload.get(translation_label, default_translation_mm),
        field_name=f"{field_name}.{translation_label}",
    )
    yaw_pitch_roll = _normalize_vector3(
        payload.get("yaw_pitch_roll_deg", default_yaw_pitch_roll_deg),
        field_name=f"{field_name}.yaw_pitch_roll_deg",
    )
    raw_parameterization = _normalize_nonempty_string(
        payload.get("rotation_parameterization", rotation_parameterization),
        field_name=f"{field_name}.rotation_parameterization",
    )
    if raw_parameterization != rotation_parameterization:
        raise ValueError(
            f"{field_name}.rotation_parameterization must be {rotation_parameterization!r}, got {raw_parameterization!r}."
        )
    return {
        "source_frame": source_frame,
        "target_frame": target_frame,
        translation_label: _vector_to_list(translation),
        "yaw_pitch_roll_deg": _vector_to_list(yaw_pitch_roll),
        "rotation_parameterization": rotation_parameterization,
    }


def _rotation_matrix_from_yaw_pitch_roll_deg(yaw_pitch_roll_deg: Sequence[float]) -> np.ndarray:
    yaw_rad, pitch_rad, roll_rad = [math.radians(float(value)) for value in yaw_pitch_roll_deg]
    rotation_z = np.asarray(
        [
            [math.cos(yaw_rad), -math.sin(yaw_rad), 0.0],
            [math.sin(yaw_rad), math.cos(yaw_rad), 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    rotation_y = np.asarray(
        [
            [math.cos(pitch_rad), 0.0, math.sin(pitch_rad)],
            [0.0, 1.0, 0.0],
            [-math.sin(pitch_rad), 0.0, math.cos(pitch_rad)],
        ],
        dtype=np.float64,
    )
    rotation_x = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.0, math.cos(roll_rad), -math.sin(roll_rad)],
            [0.0, math.sin(roll_rad), math.cos(roll_rad)],
        ],
        dtype=np.float64,
    )
    return rotation_z @ rotation_y @ rotation_x


def _rotate_about_axis(vector: np.ndarray, axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = axis / np.linalg.norm(axis)
    cos_angle = math.cos(angle_rad)
    sin_angle = math.sin(angle_rad)
    return (
        vector * cos_angle
        + np.cross(axis, vector) * sin_angle
        + axis * np.dot(axis, vector) * (1.0 - cos_angle)
    )


def _normalize_lattice_local_coordinates(
    lattice_local: Mapping[str, Any] | Sequence[float],
) -> tuple[float, float]:
    if isinstance(lattice_local, Mapping):
        axial_q = _normalize_float(lattice_local.get("axial_q"), field_name="lattice_local.axial_q")
        axial_r = _normalize_float(lattice_local.get("axial_r"), field_name="lattice_local.axial_r")
        return axial_q, axial_r
    if isinstance(lattice_local, Sequence) and len(lattice_local) == 2:
        return (
            _normalize_float(lattice_local[0], field_name="lattice_local[0]"),
            _normalize_float(lattice_local[1], field_name="lattice_local[1]"),
        )
    raise ValueError("lattice_local must be a mapping with axial_q/axial_r or a two-value sequence.")


def _normalize_eye_label(value: Any, *, field_name: str) -> str:
    eye_label = _normalize_identifier(value, field_name=field_name)
    if eye_label not in SUPPORTED_EYE_LABELS:
        raise ValueError(f"{field_name} must be one of {list(SUPPORTED_EYE_LABELS)!r}, got {eye_label!r}.")
    return eye_label


def _normalize_nonnegative_int(value: Any, *, field_name: str) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a non-negative integer.") from exc
    if normalized < 0:
        raise ValueError(f"{field_name} must be >= 0.")
    return normalized


def _normalize_vector3(value: Any, *, field_name: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (3,):
        raise ValueError(f"{field_name} must be a three-value sequence.")
    return np.asarray(
        [
            _normalize_float(array[0], field_name=f"{field_name}[0]"),
            _normalize_float(array[1], field_name=f"{field_name}[1]"),
            _normalize_float(array[2], field_name=f"{field_name}[2]"),
        ],
        dtype=np.float64,
    )


def _normalize_unit_vector(value: Any, *, field_name: str) -> np.ndarray:
    vector = _normalize_vector3(value, field_name=field_name)
    norm = float(np.linalg.norm(vector))
    if norm <= _FLOAT_ABS_TOL:
        raise ValueError(f"{field_name} must not be the zero vector.")
    return vector / norm


def _normalize_json_mapping_like(payload: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        normalized[str(key)] = _normalize_json_value_like(value, field_name=f"{field_name}.{key}")
    return normalized


def _normalize_json_value_like(value: Any, *, field_name: str) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return _rounded_float(value)
    if isinstance(value, Mapping):
        return _normalize_json_mapping_like(value, field_name=field_name)
    if isinstance(value, list):
        return [_normalize_json_value_like(item, field_name=field_name) for item in value]
    raise ValueError(f"{field_name} contains a non-JSON-serializable value {type(value).__name__!r}.")


def _extract_geometry_spec(
    retinal_geometry: Mapping[str, Any] | ResolvedRetinalGeometry,
) -> Mapping[str, Any]:
    if isinstance(retinal_geometry, ResolvedRetinalGeometry):
        return retinal_geometry.retinal_geometry
    if not isinstance(retinal_geometry, Mapping):
        raise ValueError("retinal_geometry must be a mapping or ResolvedRetinalGeometry instance.")
    return retinal_geometry


def _vector_to_list(vector: Sequence[float] | np.ndarray) -> list[float]:
    array = np.asarray(vector, dtype=np.float64)
    return [_rounded_float(value) for value in array.tolist()]


def _matrix_to_list(matrix: np.ndarray) -> list[list[float]]:
    array = np.asarray(matrix, dtype=np.float64)
    return [[_rounded_float(value) for value in row] for row in array.tolist()]


def _rounded_float(value: float) -> float:
    return float(round(float(value), 12))


def _as_matrix3(values: Sequence[Sequence[float]] | np.ndarray, *, field_name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim == 1:
        if array.shape != (3,):
            raise ValueError(f"{field_name} must have shape (3,) or (N, 3).")
        array = array[None, :]
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError(f"{field_name} must have shape (3,) or (N, 3).")
    return array
