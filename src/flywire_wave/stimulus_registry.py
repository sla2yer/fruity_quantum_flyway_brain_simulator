from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Any

from .stimulus_contract import (
    ASSET_STATUS_MISSING,
    DEFAULT_CONTRAST_SEMANTICS,
    DEFAULT_PROCESSED_STIMULUS_DIR,
    DEFAULT_POSITIVE_POLARITY,
    DEFAULT_RNG_FAMILY,
    STIMULUS_BUNDLE_CONTRACT_VERSION,
    _normalize_float,
    _normalize_identifier,
    _normalize_nonempty_string,
    _normalize_seed,
    build_stimulus_bundle_metadata,
    build_stimulus_bundle_reference,
    build_stimulus_contract_manifest_metadata,
    build_stimulus_parameter_hash,
    normalize_luminance_convention,
    normalize_spatial_frame,
    normalize_temporal_sampling,
    resolve_stimulus_bundle_metadata_path,
)


STIMULUS_SPEC_VERSION = "stimulus_spec.v1"
DEFAULT_STIMULUS_SEED = 0
DEFAULT_SEED_SCOPE = "all_stochastic_generator_branches"

POLARITY_POSITIVE = "positive"
POLARITY_NEGATIVE = "negative"
SUPPORTED_POLARITIES = (POLARITY_POSITIVE, POLARITY_NEGATIVE)

WAVEFORM_SINE = "sine"
WAVEFORM_SQUARE = "square"
SUPPORTED_WAVEFORMS = (WAVEFORM_SINE, WAVEFORM_SQUARE)

RADIAL_FLOW_EXPANSION = "expansion"
RADIAL_FLOW_CONTRACTION = "contraction"
SUPPORTED_RADIAL_FLOW_SIGNS = (RADIAL_FLOW_EXPANSION, RADIAL_FLOW_CONTRACTION)

ROTATION_CLOCKWISE = "clockwise"
ROTATION_COUNTERCLOCKWISE = "counterclockwise"
SUPPORTED_ROTATION_DIRECTIONS = (
    ROTATION_CLOCKWISE,
    ROTATION_COUNTERCLOCKWISE,
)

TRANSLATED_EDGE_FAMILY = "translated_edge"
MOVING_EDGE_FAMILY_ALIAS = "moving_edge"

DEFAULT_TEMPORAL_SAMPLING = {
    "dt_ms": 10.0,
    "duration_ms": 500.0,
}
DEFAULT_SPATIAL_FRAME = {
    "width_px": 96,
    "height_px": 96,
    "width_deg": 120.0,
    "height_deg": 120.0,
}

_TEMPORAL_KEYS = {
    "dt_ms",
    "duration_ms",
    "frame_count",
    "time_origin_ms",
    "sampling_mode",
}
_SPATIAL_KEYS = {
    "frame_name",
    "origin",
    "x_axis",
    "y_axis",
    "pixel_origin",
    "width_px",
    "height_px",
    "width_deg",
    "height_deg",
}
_LUMINANCE_KEYS = {
    "encoding",
    "minimum_value",
    "neutral_value",
    "maximum_value",
    "contrast_semantics",
    "positive_polarity",
}
_DETERMINISM_KEYS = {
    "seed",
    "rng_family",
    "seed_scope",
}


@dataclass(frozen=True)
class ParameterDefinition:
    name: str
    kind: str
    description: str
    default: Any
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    minimum_inclusive: bool = True
    maximum_inclusive: bool = True
    aliases: tuple[str, ...] = ()
    allowed_values: tuple[str, ...] = ()

    def normalize(self, value: Any, *, field_name: str) -> Any:
        raw_value = self.default if value is None else value
        if self.kind == "float":
            normalized = _normalize_float(raw_value, field_name=field_name)
            self._validate_numeric_bounds(normalized, field_name=field_name)
            return normalized
        if self.kind == "int":
            try:
                normalized = int(raw_value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field_name} must be an integer.") from exc
            self._validate_numeric_bounds(float(normalized), field_name=field_name)
            return normalized
        if self.kind == "enum":
            normalized = _normalize_identifier(raw_value, field_name=field_name)
            if normalized not in self.allowed_values:
                raise ValueError(
                    f"{field_name} must be one of {list(self.allowed_values)!r}, got {normalized!r}."
                )
            return normalized
        raise ValueError(f"Unsupported parameter definition kind {self.kind!r}.")

    def to_registry_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "name": self.name,
            "type": self.kind,
            "description": self.description,
            "default": copy.deepcopy(self.default),
            "aliases": list(self.aliases),
        }
        if self.unit is not None:
            record["unit"] = self.unit
        if self.allowed_values:
            record["allowed_values"] = list(self.allowed_values)
        if self.minimum is not None:
            record["minimum"] = self.minimum
            record["minimum_inclusive"] = self.minimum_inclusive
        if self.maximum is not None:
            record["maximum"] = self.maximum
            record["maximum_inclusive"] = self.maximum_inclusive
        return record

    def _validate_numeric_bounds(self, value: float, *, field_name: str) -> None:
        if self.minimum is not None:
            below_minimum = value < self.minimum or (
                not self.minimum_inclusive and value == self.minimum
            )
            if below_minimum:
                comparator = ">=" if self.minimum_inclusive else ">"
                raise ValueError(f"{field_name} must be {comparator} {self.minimum}.")
        if self.maximum is not None:
            above_maximum = value > self.maximum or (
                not self.maximum_inclusive and value == self.maximum
            )
            if above_maximum:
                comparator = "<=" if self.maximum_inclusive else "<"
                raise ValueError(f"{field_name} must be {comparator} {self.maximum}.")


@dataclass(frozen=True)
class StimulusPresetDefinition:
    name: str
    description: str
    parameter_defaults: Mapping[str, Any]
    temporal_sampling: Mapping[str, Any]
    spatial_frame: Mapping[str, Any]
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    default_seed: int = DEFAULT_STIMULUS_SEED


@dataclass(frozen=True)
class StimulusFamilyDefinition:
    family: str
    description: str
    parameter_definitions: tuple[ParameterDefinition, ...]
    presets: tuple[StimulusPresetDefinition, ...]
    aliases: tuple[str, ...] = ()

    def parameter_lookup(self) -> dict[str, ParameterDefinition]:
        lookup: dict[str, ParameterDefinition] = {}
        for definition in self.parameter_definitions:
            lookup[definition.name] = definition
            for alias in definition.aliases:
                lookup[alias] = definition
        return lookup


@dataclass(frozen=True)
class ResolvedStimulusSpec:
    stimulus_spec: dict[str, Any]
    registry_entry: dict[str, Any]

    @property
    def stimulus_family(self) -> str:
        return str(self.stimulus_spec["stimulus_family"])

    @property
    def stimulus_name(self) -> str:
        return str(self.stimulus_spec["stimulus_name"])

    def build_bundle_metadata(
        self,
        *,
        processed_stimulus_dir: str | Path = DEFAULT_PROCESSED_STIMULUS_DIR,
    ) -> dict[str, Any]:
        return build_stimulus_bundle_metadata(
            stimulus_family=self.stimulus_family,
            stimulus_name=self.stimulus_name,
            parameter_snapshot=self.stimulus_spec["parameter_snapshot"],
            seed=self.stimulus_spec["determinism"]["seed"],
            temporal_sampling=self.stimulus_spec["temporal_sampling"],
            spatial_frame=self.stimulus_spec["spatial_frame"],
            processed_stimulus_dir=processed_stimulus_dir,
            luminance_convention=self.stimulus_spec["luminance_convention"],
            frame_cache_status=ASSET_STATUS_MISSING,
            preview_gif_status=ASSET_STATUS_MISSING,
            compatibility_aliases=self.registry_entry.get("compatibility_aliases"),
            rng_family=self.stimulus_spec["determinism"]["rng_family"],
        )

    def build_bundle_reference(
        self,
        *,
        processed_stimulus_dir: str | Path = DEFAULT_PROCESSED_STIMULUS_DIR,
    ) -> dict[str, Any]:
        return build_stimulus_bundle_reference(
            self.build_bundle_metadata(processed_stimulus_dir=processed_stimulus_dir)
        )

    def resolve_bundle_metadata_path(
        self,
        *,
        processed_stimulus_dir: str | Path = DEFAULT_PROCESSED_STIMULUS_DIR,
    ) -> str:
        return str(
            resolve_stimulus_bundle_metadata_path(
                stimulus_family=self.stimulus_family,
                stimulus_name=self.stimulus_name,
                processed_stimulus_dir=processed_stimulus_dir,
                parameter_hash=self.stimulus_spec["parameter_hash"],
            )
        )

    def build_contract_metadata(
        self,
        *,
        processed_stimulus_dir: str | Path = DEFAULT_PROCESSED_STIMULUS_DIR,
    ) -> dict[str, Any]:
        return build_stimulus_contract_manifest_metadata(
            processed_stimulus_dir=processed_stimulus_dir
        )


_COMMON_VISUAL_PARAMETERS = (
    ParameterDefinition(
        name="background_level",
        kind="float",
        description="Background luminance level in linear unit-interval space.",
        default=0.5,
        unit="unit_interval",
        minimum=0.0,
        maximum=1.0,
        aliases=("background",),
    ),
    ParameterDefinition(
        name="contrast",
        kind="float",
        description="Signed luminance contrast magnitude relative to neutral gray.",
        default=0.6,
        unit="unit_interval_delta",
        minimum=0.0,
        maximum=1.0,
        aliases=("contrast_delta",),
    ),
    ParameterDefinition(
        name="polarity",
        kind="enum",
        description="Whether positive contrast means brighter or darker structure.",
        default=POLARITY_POSITIVE,
        aliases=("contrast_polarity",),
        allowed_values=SUPPORTED_POLARITIES,
    ),
    ParameterDefinition(
        name="onset_ms",
        kind="float",
        description="Stimulus onset time relative to the bundle time origin.",
        default=50.0,
        unit="ms",
        minimum=0.0,
        aliases=("start_ms",),
    ),
    ParameterDefinition(
        name="offset_ms",
        kind="float",
        description="Stimulus offset time relative to the bundle time origin.",
        default=450.0,
        unit="ms",
        minimum=0.0,
        aliases=("end_ms",),
    ),
    ParameterDefinition(
        name="center_azimuth_deg",
        kind="float",
        description="Horizontal stimulus center relative to the aperture center.",
        default=0.0,
        unit="deg",
        aliases=("center_x_deg", "azimuth_deg"),
    ),
    ParameterDefinition(
        name="center_elevation_deg",
        kind="float",
        description="Vertical stimulus center relative to the aperture center.",
        default=0.0,
        unit="deg",
        aliases=("center_y_deg", "elevation_deg"),
    ),
)

_FAMILY_DEFINITIONS = (
    StimulusFamilyDefinition(
        family="flash",
        description="Spatially localized luminance flash on the canonical visual field.",
        aliases=(),
        parameter_definitions=(
            *_COMMON_VISUAL_PARAMETERS,
            ParameterDefinition(
                name="radius_deg",
                kind="float",
                description="Flash aperture radius measured in visual-field degrees.",
                default=12.0,
                unit="deg",
                minimum=0.0,
                maximum=None,
                minimum_inclusive=False,
                aliases=("aperture_radius_deg", "radius"),
            ),
            ParameterDefinition(
                name="edge_softness_deg",
                kind="float",
                description="Width of the flash boundary softening ramp.",
                default=0.0,
                unit="deg",
                minimum=0.0,
                aliases=("soften_deg",),
            ),
        ),
        presets=(
            StimulusPresetDefinition(
                name="simple_flash",
                description="Default bright flash used for deterministic bundle tests.",
                parameter_defaults={
                    "contrast": 0.7,
                    "polarity": POLARITY_POSITIVE,
                    "radius_deg": 12.0,
                    "edge_softness_deg": 1.0,
                    "onset_ms": 50.0,
                    "offset_ms": 150.0,
                },
                temporal_sampling={
                    "dt_ms": 10.0,
                    "duration_ms": 250.0,
                },
                spatial_frame=DEFAULT_SPATIAL_FRAME,
                tags=("milestone8a", "flash"),
            ),
        ),
    ),
    StimulusFamilyDefinition(
        family="moving_bar",
        description="Translated bar stimulus with explicit width, direction, and speed.",
        aliases=(),
        parameter_definitions=(
            *_COMMON_VISUAL_PARAMETERS,
            ParameterDefinition(
                name="bar_width_deg",
                kind="float",
                description="Full bar width perpendicular to the motion axis.",
                default=12.0,
                unit="deg",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("bar_width",),
            ),
            ParameterDefinition(
                name="direction_deg",
                kind="float",
                description="Motion direction in visual-field degrees.",
                default=0.0,
                unit="deg",
                minimum=0.0,
                maximum=360.0,
                maximum_inclusive=False,
                aliases=("direction",),
            ),
            ParameterDefinition(
                name="velocity_deg_per_s",
                kind="float",
                description="Bar translation speed in degrees per second.",
                default=45.0,
                unit="deg_per_s",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("speed_deg_per_s", "velocity"),
            ),
            ParameterDefinition(
                name="aperture_radius_deg",
                kind="float",
                description="Circular aperture radius used to clip the translated bar.",
                default=45.0,
                unit="deg",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("aperture_deg",),
            ),
            ParameterDefinition(
                name="edge_softness_deg",
                kind="float",
                description="Width of the bar-edge softening ramp.",
                default=1.0,
                unit="deg",
                minimum=0.0,
                aliases=("soften_deg",),
            ),
        ),
        presets=(
            StimulusPresetDefinition(
                name="simple_moving_bar",
                description="Canonical moving-bar preset for Milestone 8A pipeline wiring.",
                parameter_defaults={
                    "contrast": 0.8,
                    "polarity": POLARITY_POSITIVE,
                    "bar_width_deg": 12.0,
                    "direction_deg": 0.0,
                    "velocity_deg_per_s": 45.0,
                    "aperture_radius_deg": 40.0,
                    "edge_softness_deg": 1.0,
                    "onset_ms": 50.0,
                    "offset_ms": 550.0,
                },
                temporal_sampling={
                    "dt_ms": 10.0,
                    "duration_ms": 600.0,
                },
                spatial_frame=DEFAULT_SPATIAL_FRAME,
                tags=("milestone8a", "moving_bar"),
            ),
        ),
    ),
    StimulusFamilyDefinition(
        family="drifting_grating",
        description="Drifting luminance grating with explicit spatial and temporal frequencies.",
        aliases=(),
        parameter_definitions=(
            *_COMMON_VISUAL_PARAMETERS,
            ParameterDefinition(
                name="spatial_frequency_cpd",
                kind="float",
                description="Grating spatial frequency in cycles per degree.",
                default=0.08,
                unit="cycles_per_deg",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("spatial_freq_cpd", "spatial_frequency"),
            ),
            ParameterDefinition(
                name="temporal_frequency_hz",
                kind="float",
                description="Grating temporal frequency in hertz.",
                default=2.0,
                unit="hz",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("drift_frequency_hz",),
            ),
            ParameterDefinition(
                name="drift_direction_deg",
                kind="float",
                description="Drift direction in visual-field degrees.",
                default=0.0,
                unit="deg",
                minimum=0.0,
                maximum=360.0,
                maximum_inclusive=False,
                aliases=("direction_deg", "direction"),
            ),
            ParameterDefinition(
                name="phase_deg",
                kind="float",
                description="Initial grating phase at the bundle time origin.",
                default=0.0,
                unit="deg",
                minimum=0.0,
                maximum=360.0,
                maximum_inclusive=False,
                aliases=("phase",),
            ),
            ParameterDefinition(
                name="waveform",
                kind="enum",
                description="Waveform family used to synthesize the grating.",
                default=WAVEFORM_SINE,
                aliases=("grating_waveform",),
                allowed_values=SUPPORTED_WAVEFORMS,
            ),
            ParameterDefinition(
                name="aperture_radius_deg",
                kind="float",
                description="Circular aperture radius applied to the grating.",
                default=50.0,
                unit="deg",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("aperture_deg",),
            ),
        ),
        presets=(
            StimulusPresetDefinition(
                name="simple_drifting_grating",
                description="Default drifting grating used for deterministic registry tests.",
                parameter_defaults={
                    "contrast": 0.7,
                    "spatial_frequency_cpd": 0.08,
                    "temporal_frequency_hz": 2.0,
                    "drift_direction_deg": 0.0,
                    "phase_deg": 0.0,
                    "waveform": WAVEFORM_SINE,
                    "aperture_radius_deg": 50.0,
                    "onset_ms": 50.0,
                    "offset_ms": 950.0,
                },
                temporal_sampling={
                    "dt_ms": 20.0,
                    "duration_ms": 1000.0,
                },
                spatial_frame={
                    "width_px": 128,
                    "height_px": 128,
                    "width_deg": 120.0,
                    "height_deg": 120.0,
                },
                tags=("milestone8a", "drifting_grating"),
            ),
        ),
    ),
    StimulusFamilyDefinition(
        family="looming",
        description="Radially expanding disc stimulus defined by explicit initial and final size.",
        aliases=(),
        parameter_definitions=(
            *_COMMON_VISUAL_PARAMETERS,
            ParameterDefinition(
                name="initial_radius_deg",
                kind="float",
                description="Disc radius at stimulus onset.",
                default=2.0,
                unit="deg",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("start_radius_deg",),
            ),
            ParameterDefinition(
                name="final_radius_deg",
                kind="float",
                description="Disc radius at stimulus offset.",
                default=35.0,
                unit="deg",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("end_radius_deg",),
            ),
            ParameterDefinition(
                name="edge_softness_deg",
                kind="float",
                description="Width of the looming-boundary softening ramp.",
                default=1.0,
                unit="deg",
                minimum=0.0,
                aliases=("soften_deg",),
            ),
        ),
        presets=(
            StimulusPresetDefinition(
                name="simple_looming",
                description="Canonical looming preset with a dark expanding object.",
                parameter_defaults={
                    "contrast": 0.85,
                    "polarity": POLARITY_NEGATIVE,
                    "initial_radius_deg": 2.0,
                    "final_radius_deg": 35.0,
                    "edge_softness_deg": 1.0,
                    "onset_ms": 50.0,
                    "offset_ms": 450.0,
                },
                temporal_sampling={
                    "dt_ms": 10.0,
                    "duration_ms": 500.0,
                },
                spatial_frame={
                    "width_px": 128,
                    "height_px": 128,
                    "width_deg": 120.0,
                    "height_deg": 120.0,
                },
                tags=("milestone8a", "looming"),
            ),
        ),
    ),
    StimulusFamilyDefinition(
        family="radial_flow",
        description="Expansion or contraction flow field on the canonical centered aperture.",
        aliases=(),
        parameter_definitions=(
            *_COMMON_VISUAL_PARAMETERS,
            ParameterDefinition(
                name="motion_sign",
                kind="enum",
                description="Whether the optic flow expands outward or contracts inward.",
                default=RADIAL_FLOW_EXPANSION,
                aliases=("flow_sign",),
                allowed_values=SUPPORTED_RADIAL_FLOW_SIGNS,
            ),
            ParameterDefinition(
                name="radial_speed_deg_per_s",
                kind="float",
                description="Radial flow speed in degrees per second.",
                default=40.0,
                unit="deg_per_s",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("speed_deg_per_s", "velocity_deg_per_s"),
            ),
            ParameterDefinition(
                name="radial_spatial_frequency_cpd",
                kind="float",
                description="Carrier spatial frequency in cycles per degree along the radius.",
                default=0.08,
                unit="cycles_per_deg",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("spatial_frequency_cpd", "spatial_freq_cpd"),
            ),
            ParameterDefinition(
                name="phase_deg",
                kind="float",
                description="Initial radial-carrier phase at the bundle time origin.",
                default=0.0,
                unit="deg",
                minimum=0.0,
                maximum=360.0,
                maximum_inclusive=False,
                aliases=("phase",),
            ),
            ParameterDefinition(
                name="waveform",
                kind="enum",
                description="Waveform family used to synthesize the radial-flow carrier.",
                default=WAVEFORM_SINE,
                aliases=("flow_waveform",),
                allowed_values=SUPPORTED_WAVEFORMS,
            ),
            ParameterDefinition(
                name="inner_radius_deg",
                kind="float",
                description="Inner radius of the active annulus.",
                default=4.0,
                unit="deg",
                minimum=0.0,
                aliases=("start_radius_deg",),
            ),
            ParameterDefinition(
                name="outer_radius_deg",
                kind="float",
                description="Outer radius of the active annulus.",
                default=50.0,
                unit="deg",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("end_radius_deg",),
            ),
        ),
        presets=(
            StimulusPresetDefinition(
                name="expanding_flow",
                description="Canonical expanding radial-flow preset.",
                parameter_defaults={
                    "motion_sign": RADIAL_FLOW_EXPANSION,
                    "contrast": 0.6,
                    "radial_speed_deg_per_s": 40.0,
                    "radial_spatial_frequency_cpd": 0.08,
                    "phase_deg": 0.0,
                    "waveform": WAVEFORM_SINE,
                    "inner_radius_deg": 4.0,
                    "outer_radius_deg": 50.0,
                    "onset_ms": 50.0,
                    "offset_ms": 750.0,
                },
                temporal_sampling={
                    "dt_ms": 20.0,
                    "duration_ms": 800.0,
                },
                spatial_frame={
                    "width_px": 128,
                    "height_px": 128,
                    "width_deg": 120.0,
                    "height_deg": 120.0,
                },
                aliases=("expansion_flow",),
                tags=("milestone8a", "radial_flow", "expansion"),
            ),
            StimulusPresetDefinition(
                name="contracting_flow",
                description="Canonical contracting radial-flow preset.",
                parameter_defaults={
                    "motion_sign": RADIAL_FLOW_CONTRACTION,
                    "contrast": 0.6,
                    "radial_speed_deg_per_s": 40.0,
                    "radial_spatial_frequency_cpd": 0.08,
                    "phase_deg": 0.0,
                    "waveform": WAVEFORM_SINE,
                    "inner_radius_deg": 4.0,
                    "outer_radius_deg": 50.0,
                    "onset_ms": 50.0,
                    "offset_ms": 750.0,
                },
                temporal_sampling={
                    "dt_ms": 20.0,
                    "duration_ms": 800.0,
                },
                spatial_frame={
                    "width_px": 128,
                    "height_px": 128,
                    "width_deg": 120.0,
                    "height_deg": 120.0,
                },
                aliases=("contraction_flow",),
                tags=("milestone8a", "radial_flow", "contraction"),
            ),
        ),
    ),
    StimulusFamilyDefinition(
        family="rotating_flow",
        description="Clockwise or counterclockwise rotational flow on the canonical aperture.",
        aliases=(),
        parameter_definitions=(
            *_COMMON_VISUAL_PARAMETERS,
            ParameterDefinition(
                name="rotation_direction",
                kind="enum",
                description="Rotational flow direction.",
                default=ROTATION_CLOCKWISE,
                aliases=("rotation_sign",),
                allowed_values=SUPPORTED_ROTATION_DIRECTIONS,
            ),
            ParameterDefinition(
                name="angular_velocity_deg_per_s",
                kind="float",
                description="Angular speed in degrees per second.",
                default=90.0,
                unit="deg_per_s",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("angular_speed_deg_per_s",),
            ),
            ParameterDefinition(
                name="angular_cycle_count",
                kind="int",
                description="Number of carrier cycles around a full 360-degree rotation.",
                default=6,
                minimum=1.0,
                aliases=("cycle_count",),
            ),
            ParameterDefinition(
                name="phase_deg",
                kind="float",
                description="Initial angular-carrier phase at the bundle time origin.",
                default=0.0,
                unit="deg",
                minimum=0.0,
                maximum=360.0,
                maximum_inclusive=False,
                aliases=("phase",),
            ),
            ParameterDefinition(
                name="waveform",
                kind="enum",
                description="Waveform family used to synthesize the rotating-flow carrier.",
                default=WAVEFORM_SINE,
                aliases=("flow_waveform",),
                allowed_values=SUPPORTED_WAVEFORMS,
            ),
            ParameterDefinition(
                name="inner_radius_deg",
                kind="float",
                description="Inner radius of the active annulus.",
                default=4.0,
                unit="deg",
                minimum=0.0,
                aliases=("start_radius_deg",),
            ),
            ParameterDefinition(
                name="outer_radius_deg",
                kind="float",
                description="Outer radius of the active annulus.",
                default=50.0,
                unit="deg",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("end_radius_deg",),
            ),
        ),
        presets=(
            StimulusPresetDefinition(
                name="clockwise_rotation",
                description="Canonical clockwise rotating-flow preset.",
                parameter_defaults={
                    "rotation_direction": ROTATION_CLOCKWISE,
                    "contrast": 0.6,
                    "angular_velocity_deg_per_s": 90.0,
                    "angular_cycle_count": 6,
                    "phase_deg": 0.0,
                    "waveform": WAVEFORM_SINE,
                    "inner_radius_deg": 4.0,
                    "outer_radius_deg": 50.0,
                    "onset_ms": 50.0,
                    "offset_ms": 750.0,
                },
                temporal_sampling={
                    "dt_ms": 20.0,
                    "duration_ms": 800.0,
                },
                spatial_frame={
                    "width_px": 128,
                    "height_px": 128,
                    "width_deg": 120.0,
                    "height_deg": 120.0,
                },
                aliases=("clockwise_flow",),
                tags=("milestone8a", "rotating_flow", "clockwise"),
            ),
            StimulusPresetDefinition(
                name="counterclockwise_rotation",
                description="Canonical counterclockwise rotating-flow preset.",
                parameter_defaults={
                    "rotation_direction": ROTATION_COUNTERCLOCKWISE,
                    "contrast": 0.6,
                    "angular_velocity_deg_per_s": 90.0,
                    "angular_cycle_count": 6,
                    "phase_deg": 0.0,
                    "waveform": WAVEFORM_SINE,
                    "inner_radius_deg": 4.0,
                    "outer_radius_deg": 50.0,
                    "onset_ms": 50.0,
                    "offset_ms": 750.0,
                },
                temporal_sampling={
                    "dt_ms": 20.0,
                    "duration_ms": 800.0,
                },
                spatial_frame={
                    "width_px": 128,
                    "height_px": 128,
                    "width_deg": 120.0,
                    "height_deg": 120.0,
                },
                aliases=("counterclockwise_flow",),
                tags=("milestone8a", "rotating_flow", "counterclockwise"),
            ),
        ),
    ),
    StimulusFamilyDefinition(
        family=TRANSLATED_EDGE_FAMILY,
        description="Translated edge pattern reserved as the canonical Milestone 8A edge family.",
        aliases=(MOVING_EDGE_FAMILY_ALIAS,),
        parameter_definitions=(
            *_COMMON_VISUAL_PARAMETERS,
            ParameterDefinition(
                name="direction_deg",
                kind="float",
                description="Edge translation direction in visual-field degrees.",
                default=0.0,
                unit="deg",
                minimum=0.0,
                maximum=360.0,
                maximum_inclusive=False,
                aliases=("direction",),
            ),
            ParameterDefinition(
                name="velocity_deg_per_s",
                kind="float",
                description="Edge translation speed in degrees per second.",
                default=60.0,
                unit="deg_per_s",
                minimum=0.0,
                minimum_inclusive=False,
                aliases=("speed_deg_per_s", "velocity"),
            ),
            ParameterDefinition(
                name="edge_width_deg",
                kind="float",
                description="Width of the transition band between background and edge states.",
                default=6.0,
                unit="deg",
                minimum=0.0,
                aliases=("edge_width",),
            ),
            ParameterDefinition(
                name="phase_offset_deg",
                kind="float",
                description="Initial phase offset of the translated edge.",
                default=0.0,
                unit="deg",
                minimum=0.0,
                maximum=360.0,
                maximum_inclusive=False,
                aliases=("phase_deg", "phase"),
            ),
        ),
        presets=(
            StimulusPresetDefinition(
                name="simple_translated_edge",
                description="Canonical translated-edge preset with Milestone 1 moving-edge aliases.",
                parameter_defaults={
                    "contrast": 0.8,
                    "polarity": POLARITY_POSITIVE,
                    "direction_deg": 0.0,
                    "velocity_deg_per_s": 45.0,
                    "edge_width_deg": 8.0,
                    "phase_offset_deg": 0.0,
                    "onset_ms": 50.0,
                    "offset_ms": 450.0,
                },
                temporal_sampling={
                    "dt_ms": 10.0,
                    "duration_ms": 500.0,
                },
                spatial_frame={
                    "width_px": 96,
                    "height_px": 48,
                    "width_deg": 120.0,
                    "height_deg": 60.0,
                },
                aliases=("simple_moving_edge",),
                tags=("milestone8a", "translated_edge", "moving_edge_compat"),
                default_seed=11,
            ),
        ),
    ),
)


def list_stimulus_families() -> list[dict[str, Any]]:
    return [
        {
            "stimulus_family": family.family,
            "aliases": list(family.aliases),
            "description": family.description,
            "preset_names": [preset.name for preset in family.presets],
        }
        for family in _FAMILY_DEFINITIONS
    ]


def list_stimulus_presets(stimulus_family: str | None = None) -> list[dict[str, Any]]:
    families = (
        [_resolve_family_definition(stimulus_family)[0]]
        if stimulus_family is not None
        else list(_FAMILY_DEFINITIONS)
    )
    entries: list[dict[str, Any]] = []
    for family in families:
        for preset in family.presets:
            entries.append(_build_registry_entry(family, preset))
    return entries


def get_stimulus_registry_entry(
    stimulus_family: str,
    stimulus_name: str,
) -> dict[str, Any]:
    family, _ = _resolve_family_definition(stimulus_family)
    preset, _ = _resolve_preset_definition(family, stimulus_name)
    return _build_registry_entry(family, preset)


def resolve_stimulus_spec(
    stimulus: Mapping[str, Any] | None = None,
    *,
    stimulus_family: str | None = None,
    stimulus_name: str | None = None,
    overrides: Mapping[str, Any] | None = None,
    temporal_sampling: Mapping[str, Any] | None = None,
    spatial_frame: Mapping[str, Any] | None = None,
    luminance_convention: Mapping[str, Any] | None = None,
    determinism: Mapping[str, Any] | None = None,
    seed: int | str | None = None,
) -> ResolvedStimulusSpec:
    root_payload = _normalize_mapping_or_none(stimulus, field_name="stimulus")
    nested_payload = _normalize_mapping_or_none(root_payload.get("stimulus"), field_name="stimulus.stimulus")

    requested_family_raw = _select_first_non_none(
        stimulus_family,
        _get_first(root_payload=nested_payload, fallback_payload=root_payload, keys=("stimulus_family", "family")),
    )
    if requested_family_raw is None:
        raise ValueError("stimulus_family must be provided.")
    family, requested_family = _resolve_family_definition(requested_family_raw)

    requested_name_raw = _select_first_non_none(
        stimulus_name,
        _get_first(
            root_payload=nested_payload,
            fallback_payload=root_payload,
            keys=("stimulus_name", "preset", "name"),
        ),
    )
    if requested_name_raw is None:
        raise ValueError("stimulus_name must be provided.")
    preset, requested_name = _resolve_preset_definition(family, requested_name_raw)

    raw_overrides = _select_mapping_override(
        explicit_mapping=overrides,
        root_payload=nested_payload,
        fallback_payload=root_payload,
        keys=("stimulus_overrides", "parameter_overrides", "overrides", "parameters"),
    )
    normalized_temporal = _resolve_temporal_sampling(
        preset=preset,
        override=_select_mapping_override(
            explicit_mapping=temporal_sampling,
            root_payload=nested_payload,
            fallback_payload=root_payload,
            keys=("temporal_sampling",),
        ),
    )
    normalized_spatial = _resolve_spatial_frame(
        preset=preset,
        override=_select_mapping_override(
            explicit_mapping=spatial_frame,
            root_payload=nested_payload,
            fallback_payload=root_payload,
            keys=("spatial_frame",),
        ),
    )
    normalized_luminance = _resolve_luminance_convention(
        override=_select_mapping_override(
            explicit_mapping=luminance_convention,
            root_payload=nested_payload,
            fallback_payload=root_payload,
            keys=("luminance_convention",),
        )
    )
    normalized_determinism = _resolve_determinism(
        preset=preset,
        determinism_override=_select_mapping_override(
            explicit_mapping=determinism,
            root_payload=nested_payload,
            fallback_payload=root_payload,
            keys=("determinism",),
        ),
        explicit_seed=seed,
        nested_payload=nested_payload,
        root_payload=root_payload,
    )
    normalized_parameters = _normalize_parameter_snapshot(
        family=family,
        preset=preset,
        overrides=raw_overrides,
        temporal_sampling=normalized_temporal,
        spatial_frame=normalized_spatial,
    )

    parameter_hash = build_stimulus_parameter_hash(
        parameter_snapshot=normalized_parameters,
        seed=normalized_determinism["seed"],
        temporal_sampling=normalized_temporal,
        spatial_frame=normalized_spatial,
        luminance_convention=normalized_luminance,
        rng_family=normalized_determinism["rng_family"],
    )
    registry_entry = _build_registry_entry(family, preset)
    stimulus_spec = {
        "spec_version": STIMULUS_SPEC_VERSION,
        "bundle_contract_version": STIMULUS_BUNDLE_CONTRACT_VERSION,
        "requested_stimulus_family": requested_family,
        "requested_stimulus_name": requested_name,
        "stimulus_family": family.family,
        "stimulus_name": preset.name,
        "parameter_hash": parameter_hash,
        "compatibility": {
            "family_alias_used": requested_family != family.family,
            "name_alias_used": requested_name != preset.name,
        },
        "parameter_snapshot": normalized_parameters,
        "temporal_sampling": normalized_temporal,
        "spatial_frame": normalized_spatial,
        "luminance_convention": normalized_luminance,
        "presentation": {
            "background_level": normalized_parameters["background_level"],
            "contrast": normalized_parameters["contrast"],
            "polarity": normalized_parameters["polarity"],
            "contrast_semantics": normalized_luminance["contrast_semantics"],
            "positive_polarity": normalized_luminance["positive_polarity"],
            "clip_mode": "clip_to_unit_interval",
        },
        "determinism": normalized_determinism,
    }
    return ResolvedStimulusSpec(
        stimulus_spec=stimulus_spec,
        registry_entry=registry_entry,
    )


def has_stimulus_reference(payload: Mapping[str, Any] | None) -> bool:
    if not isinstance(payload, Mapping):
        return False
    nested = payload.get("stimulus")
    if isinstance(nested, Mapping) and (
        nested.get("stimulus_family") is not None or nested.get("stimulus_name") is not None
    ):
        return True
    return payload.get("stimulus_family") is not None or payload.get("stimulus_name") is not None


def _resolve_family_definition(raw_family: Any) -> tuple[StimulusFamilyDefinition, str]:
    normalized = _normalize_identifier(raw_family, field_name="stimulus_family")
    for family in _FAMILY_DEFINITIONS:
        if normalized == family.family or normalized in family.aliases:
            return family, normalized
    suggestion = _suggest_identifier(
        normalized,
        [family.family for family in _FAMILY_DEFINITIONS]
        + [alias for family in _FAMILY_DEFINITIONS for alias in family.aliases],
    )
    known = sorted(family.family for family in _FAMILY_DEFINITIONS)
    suffix = f" Did you mean {suggestion!r}?" if suggestion else ""
    raise ValueError(
        f"Unknown stimulus_family {normalized!r}. Known canonical families: {known!r}.{suffix}"
    )


def _resolve_preset_definition(
    family: StimulusFamilyDefinition,
    raw_name: Any,
) -> tuple[StimulusPresetDefinition, str]:
    normalized = _normalize_identifier(raw_name, field_name="stimulus_name")
    for preset in family.presets:
        if normalized == preset.name or normalized in preset.aliases:
            return preset, normalized
    suggestion = _suggest_identifier(
        normalized,
        [preset.name for preset in family.presets]
        + [alias for preset in family.presets for alias in preset.aliases],
    )
    canonical_names = sorted(preset.name for preset in family.presets)
    suffix = f" Did you mean {suggestion!r}?" if suggestion else ""
    raise ValueError(
        f"Unknown stimulus_name {normalized!r} for family {family.family!r}. "
        f"Known canonical presets: {canonical_names!r}.{suffix}"
    )


def _build_registry_entry(
    family: StimulusFamilyDefinition,
    preset: StimulusPresetDefinition,
) -> dict[str, Any]:
    default_temporal = _resolve_temporal_sampling(preset=preset, override=None)
    default_spatial = _resolve_spatial_frame(preset=preset, override=None)
    default_luminance = normalize_luminance_convention(None)
    default_determinism = {
        "seed": _normalize_seed(preset.default_seed),
        "rng_family": DEFAULT_RNG_FAMILY,
        "seed_scope": DEFAULT_SEED_SCOPE,
        "seed_source": "preset_default",
    }
    default_parameters = _normalize_parameter_snapshot(
        family=family,
        preset=preset,
        overrides=None,
        temporal_sampling=default_temporal,
        spatial_frame=default_spatial,
    )
    return {
        "spec_version": STIMULUS_SPEC_VERSION,
        "bundle_contract_version": STIMULUS_BUNDLE_CONTRACT_VERSION,
        "stimulus_family": family.family,
        "stimulus_name": preset.name,
        "family_aliases": list(family.aliases),
        "name_aliases": list(preset.aliases),
        "compatibility_aliases": _build_compatibility_aliases(family, preset),
        "family_description": family.description,
        "preset_description": preset.description,
        "tags": list(preset.tags),
        "parameter_schema": [
            definition.to_registry_record() for definition in family.parameter_definitions
        ],
        "default_parameter_snapshot": default_parameters,
        "default_temporal_sampling": default_temporal,
        "default_spatial_frame": default_spatial,
        "default_luminance_convention": default_luminance,
        "default_determinism": default_determinism,
    }


def _build_compatibility_aliases(
    family: StimulusFamilyDefinition,
    preset: StimulusPresetDefinition,
) -> list[dict[str, str]]:
    aliases: list[dict[str, str]] = []
    family_candidates = (family.family, *family.aliases)
    preset_candidates = (preset.name, *preset.aliases)
    for family_candidate in family_candidates:
        for preset_candidate in preset_candidates:
            if family_candidate == family.family and preset_candidate == preset.name:
                continue
            aliases.append(
                {
                    "stimulus_family": family_candidate,
                    "stimulus_name": preset_candidate,
                }
            )
    return aliases


def _normalize_parameter_snapshot(
    *,
    family: StimulusFamilyDefinition,
    preset: StimulusPresetDefinition,
    overrides: Mapping[str, Any] | None,
    temporal_sampling: Mapping[str, Any],
    spatial_frame: Mapping[str, Any],
) -> dict[str, Any]:
    parameter_lookup = family.parameter_lookup()
    canonical_overrides: dict[str, Any] = {}
    seen_keys: dict[str, str] = {}
    if overrides is not None:
        if not isinstance(overrides, Mapping):
            raise ValueError("stimulus_overrides must be a mapping when provided.")
        for raw_key, raw_value in overrides.items():
            normalized_key = _normalize_identifier(raw_key, field_name="stimulus_overrides key")
            definition = parameter_lookup.get(normalized_key)
            if definition is None:
                suggestion = _suggest_identifier(normalized_key, sorted(parameter_lookup))
                suffix = f" Did you mean {suggestion!r}?" if suggestion else ""
                raise ValueError(
                    f"Unknown stimulus override {raw_key!r} for family {family.family!r}.{suffix}"
                )
            previous_key = seen_keys.get(definition.name)
            if previous_key is not None:
                raise ValueError(
                    f"Stimulus override {raw_key!r} duplicates {previous_key!r} for canonical "
                    f"parameter {definition.name!r}."
                )
            seen_keys[definition.name] = str(raw_key)
            canonical_overrides[definition.name] = raw_value

    merged_values: dict[str, Any] = {
        definition.name: copy.deepcopy(definition.default) for definition in family.parameter_definitions
    }
    for key, value in preset.parameter_defaults.items():
        merged_values[key] = copy.deepcopy(value)
    merged_values.update(canonical_overrides)

    normalized: dict[str, Any] = {}
    for definition in family.parameter_definitions:
        normalized[definition.name] = definition.normalize(
            merged_values.get(definition.name),
            field_name=f"stimulus_overrides.{definition.name}",
        )

    _validate_common_parameter_relationships(
        parameters=normalized,
        temporal_sampling=temporal_sampling,
        spatial_frame=spatial_frame,
    )
    _validate_family_parameter_relationships(
        family=family.family,
        parameters=normalized,
    )
    return normalized


def _validate_common_parameter_relationships(
    *,
    parameters: Mapping[str, Any],
    temporal_sampling: Mapping[str, Any],
    spatial_frame: Mapping[str, Any],
) -> None:
    onset_ms = float(parameters["onset_ms"])
    offset_ms = float(parameters["offset_ms"])
    duration_ms = float(temporal_sampling["duration_ms"])
    if onset_ms >= offset_ms:
        raise ValueError("stimulus_overrides.onset_ms must be less than stimulus_overrides.offset_ms.")
    if offset_ms > duration_ms:
        raise ValueError(
            "stimulus_overrides.offset_ms must be less than or equal to temporal_sampling.duration_ms."
        )

    half_width = float(spatial_frame["width_deg"]) / 2.0
    half_height = float(spatial_frame["height_deg"]) / 2.0
    center_azimuth = abs(float(parameters["center_azimuth_deg"]))
    center_elevation = abs(float(parameters["center_elevation_deg"]))
    if center_azimuth > half_width:
        raise ValueError(
            "stimulus_overrides.center_azimuth_deg must stay within the configured spatial_frame width."
        )
    if center_elevation > half_height:
        raise ValueError(
            "stimulus_overrides.center_elevation_deg must stay within the configured spatial_frame height."
        )


def _validate_family_parameter_relationships(
    *,
    family: str,
    parameters: Mapping[str, Any],
) -> None:
    if family == "looming":
        if float(parameters["final_radius_deg"]) <= float(parameters["initial_radius_deg"]):
            raise ValueError(
                "stimulus_overrides.final_radius_deg must be greater than "
                "stimulus_overrides.initial_radius_deg."
            )
        return
    if family in {"radial_flow", "rotating_flow"}:
        if float(parameters["outer_radius_deg"]) <= float(parameters["inner_radius_deg"]):
            raise ValueError(
                "stimulus_overrides.outer_radius_deg must be greater than "
                "stimulus_overrides.inner_radius_deg."
            )
        return


def _resolve_temporal_sampling(
    *,
    preset: StimulusPresetDefinition,
    override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = copy.deepcopy(DEFAULT_TEMPORAL_SAMPLING)
    merged.update(copy.deepcopy(dict(preset.temporal_sampling)))
    if override is not None:
        _validate_allowed_keys(
            override,
            field_name="temporal_sampling",
            allowed_keys=_TEMPORAL_KEYS,
        )
        merged.update(copy.deepcopy(dict(override)))
    return normalize_temporal_sampling(merged)


def _resolve_spatial_frame(
    *,
    preset: StimulusPresetDefinition,
    override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = copy.deepcopy(DEFAULT_SPATIAL_FRAME)
    merged.update(copy.deepcopy(dict(preset.spatial_frame)))
    if override is not None:
        _validate_allowed_keys(
            override,
            field_name="spatial_frame",
            allowed_keys=_SPATIAL_KEYS,
        )
        merged.update(copy.deepcopy(dict(override)))
    return normalize_spatial_frame(merged)


def _resolve_luminance_convention(
    *,
    override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if override is not None:
        _validate_allowed_keys(
            override,
            field_name="luminance_convention",
            allowed_keys=_LUMINANCE_KEYS,
        )
    normalized = normalize_luminance_convention(override)
    if normalized["contrast_semantics"] != DEFAULT_CONTRAST_SEMANTICS:
        raise ValueError(
            "luminance_convention.contrast_semantics must remain "
            f"{DEFAULT_CONTRAST_SEMANTICS!r}."
        )
    if normalized["positive_polarity"] != DEFAULT_POSITIVE_POLARITY:
        raise ValueError(
            "luminance_convention.positive_polarity must remain "
            f"{DEFAULT_POSITIVE_POLARITY!r}."
        )
    return normalized


def _resolve_determinism(
    *,
    preset: StimulusPresetDefinition,
    determinism_override: Mapping[str, Any] | None,
    explicit_seed: int | str | None,
    nested_payload: Mapping[str, Any],
    root_payload: Mapping[str, Any],
) -> dict[str, Any]:
    if determinism_override is not None:
        _validate_allowed_keys(
            determinism_override,
            field_name="determinism",
            allowed_keys=_DETERMINISM_KEYS,
        )

    seed_source = "preset_default"
    seed_value: Any = preset.default_seed
    if determinism_override and determinism_override.get("seed") is not None:
        seed_value = determinism_override["seed"]
        seed_source = "determinism.seed"

    manifest_seed = _get_first(
        root_payload=nested_payload,
        fallback_payload=root_payload,
        keys=("random_seed", "seed"),
    )
    if manifest_seed is not None:
        seed_value = manifest_seed
        seed_source = "random_seed"
    if explicit_seed is not None:
        seed_value = explicit_seed
        seed_source = "explicit_seed"

    rng_family = DEFAULT_RNG_FAMILY
    if determinism_override and determinism_override.get("rng_family") is not None:
        rng_family = _normalize_nonempty_string(
            determinism_override.get("rng_family"),
            field_name="determinism.rng_family",
        )
    if rng_family != DEFAULT_RNG_FAMILY:
        raise ValueError(f"determinism.rng_family must be {DEFAULT_RNG_FAMILY!r}.")

    seed_scope = DEFAULT_SEED_SCOPE
    if determinism_override and determinism_override.get("seed_scope") is not None:
        seed_scope = _normalize_nonempty_string(
            determinism_override.get("seed_scope"),
            field_name="determinism.seed_scope",
        )
    if seed_scope != DEFAULT_SEED_SCOPE:
        raise ValueError(f"determinism.seed_scope must be {DEFAULT_SEED_SCOPE!r}.")

    return {
        "seed": _normalize_seed(seed_value),
        "rng_family": rng_family,
        "seed_scope": seed_scope,
        "seed_source": seed_source,
    }


def _normalize_mapping_or_none(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping when provided.")
    return dict(value)


def _select_mapping_override(
    *,
    explicit_mapping: Mapping[str, Any] | None,
    root_payload: Mapping[str, Any],
    fallback_payload: Mapping[str, Any],
    keys: tuple[str, ...],
) -> dict[str, Any] | None:
    if explicit_mapping is not None:
        if not isinstance(explicit_mapping, Mapping):
            raise ValueError(f"{keys[0]} must be a mapping when provided.")
        return dict(explicit_mapping)
    candidate = _get_first(root_payload=root_payload, fallback_payload=fallback_payload, keys=keys)
    if candidate is None:
        return None
    if not isinstance(candidate, Mapping):
        raise ValueError(f"{keys[0]} must be a mapping when provided.")
    return dict(candidate)


def _get_first(
    *,
    root_payload: Mapping[str, Any],
    fallback_payload: Mapping[str, Any],
    keys: tuple[str, ...],
) -> Any:
    for key in keys:
        if key in root_payload and root_payload[key] is not None:
            return root_payload[key]
    for key in keys:
        if key in fallback_payload and fallback_payload[key] is not None:
            return fallback_payload[key]
    return None


def _select_first_non_none(primary: Any, secondary: Any) -> Any:
    return primary if primary is not None else secondary


def _validate_allowed_keys(
    payload: Mapping[str, Any],
    *,
    field_name: str,
    allowed_keys: set[str],
) -> None:
    normalized_allowed_keys = sorted(allowed_keys)
    for raw_key in payload:
        normalized_key = _normalize_identifier(raw_key, field_name=f"{field_name} key")
        if normalized_key not in allowed_keys:
            suggestion = _suggest_identifier(normalized_key, normalized_allowed_keys)
            suffix = f" Did you mean {suggestion!r}?" if suggestion else ""
            raise ValueError(f"Unknown {field_name} field {raw_key!r}.{suffix}")


def _suggest_identifier(value: str, options: list[str]) -> str | None:
    matches = get_close_matches(value, options, n=1, cutoff=0.6)
    return matches[0] if matches else None
