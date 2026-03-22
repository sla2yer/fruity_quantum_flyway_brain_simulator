from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from .hybrid_morphology_contract import (
    POINT_NEURON_CLASS,
    SKELETON_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
    build_hybrid_morphology_plan_metadata,
    parse_hybrid_morphology_plan_metadata,
)
from .skeleton_runtime_assets import (
    SkeletonRuntimeAsset,
    load_skeleton_runtime_asset,
    load_skeleton_runtime_asset_metadata,
)
from .simulator_result_contract import SURFACE_WAVE_MODEL_MODE
from .simulator_runtime import (
    SimulationDeterminismContext,
    SimulationReadoutDefinition,
    SimulationStateSummaryRow,
    SimulationTimebase,
)
from .surface_wave_contract import parse_surface_wave_model_metadata
from .surface_wave_execution import (
    CoupledSurfaceWaveRunResult,
    ResolvedSurfaceWaveExecutionPlan,
    resolve_surface_wave_execution_plan,
    resolve_surface_wave_execution_plan_from_arm_plan,
)
from .surface_wave_solver import (
    compute_surface_wave_stability_timestep_ms,
)


MORPHOLOGY_CLASS_RUNTIME_INTERFACE_VERSION = "morphology_class_runtime.v1"
SURFACE_WAVE_MORPHOLOGY_RUNTIME_FAMILY = "surface_wave_surface_runtime_adapter.v1"
SURFACE_WAVE_SKELETON_MORPHOLOGY_RUNTIME_FAMILY = (
    "surface_wave_surface_skeleton_runtime_adapter.v1"
)
SURFACE_WAVE_RUNTIME_SOURCE_INJECTION_STRATEGY = (
    "uniform_surface_fill_from_shared_root_schedule"
)
SKELETON_GRAPH_RUNTIME_SOURCE_INJECTION_STRATEGY = (
    "uniform_skeleton_node_fill_from_shared_root_schedule"
)
SKELETON_GRAPH_STATE_RESOLUTION = "skeleton_graph"
_SUPPORTED_SKELETON_RECOVERY_MODE = "disabled"
_SUPPORTED_SKELETON_NONLINEARITY_MODE = "none"
_SUPPORTED_SKELETON_ANISOTROPY_MODE = "isotropic"
_SUPPORTED_SKELETON_BRANCHING_MODE = "disabled"


@dataclass(frozen=True)
class MorphologyRuntimeDescriptor:
    interface_version: str
    model_mode: str
    runtime_family: str
    hybrid_morphology: dict[str, Any]
    source_injection: dict[str, Any]
    state_export: dict[str, Any]
    readout_export: dict[str, Any]
    coupling_projection: dict[str, Any]
    model_metadata: dict[str, Any] = field(default_factory=dict)
    solver_metadata: dict[str, Any] = field(default_factory=dict)
    coupling_metadata: dict[str, Any] = field(default_factory=dict)

    def as_mapping(self) -> dict[str, Any]:
        return {
            "interface_version": self.interface_version,
            "model_mode": self.model_mode,
            "runtime_family": self.runtime_family,
            "hybrid_morphology": copy.deepcopy(self.hybrid_morphology),
            "source_injection": copy.deepcopy(self.source_injection),
            "state_export": copy.deepcopy(self.state_export),
            "readout_export": copy.deepcopy(self.readout_export),
            "coupling_projection": copy.deepcopy(self.coupling_projection),
            "model_metadata": copy.deepcopy(self.model_metadata),
            "solver_metadata": copy.deepcopy(self.solver_metadata),
            "coupling_metadata": copy.deepcopy(self.coupling_metadata),
        }


class MorphologyRuntimeExecutionResult(Protocol):
    @property
    def descriptor(self) -> MorphologyRuntimeDescriptor: ...

    @property
    def root_ids(self) -> tuple[int, ...]: ...

    @property
    def timebase(self) -> dict[str, Any]: ...

    @property
    def determinism(self) -> dict[str, Any]: ...

    @property
    def runtime_metadata_by_root(self) -> Sequence[Mapping[str, Any]]: ...

    @property
    def initial_state_exports_by_root(self) -> Mapping[int, Mapping[str, Any]]: ...

    @property
    def final_state_exports_by_root(self) -> Mapping[int, Mapping[str, Any]]: ...

    @property
    def coupling_projection_history_by_root(self) -> Mapping[int, np.ndarray]: ...

    @property
    def shared_readout_history(self) -> Sequence[Mapping[str, Any]]: ...

    @property
    def coupling_application_history(self) -> Sequence[Mapping[str, Any]]: ...

    @property
    def substep_count(self) -> int: ...

    @property
    def shared_step_count(self) -> int: ...

    def export_state_summaries(
        self,
        *,
        state_stage: str,
    ) -> tuple[SimulationStateSummaryRow, ...]: ...

    def export_readout_values(
        self,
        *,
        summary: Mapping[str, Any],
        readout_catalog: Sequence[SimulationReadoutDefinition],
    ) -> np.ndarray: ...

    def export_readout_trace_values(
        self,
        *,
        readout_catalog: Sequence[SimulationReadoutDefinition],
        sample_count: int,
    ) -> np.ndarray: ...

    def export_dynamic_state_vector(
        self,
        *,
        summary: Mapping[str, Any],
    ) -> np.ndarray: ...

    def export_projection_trace_payload(self) -> dict[str, np.ndarray]: ...


class MorphologyRuntime(Protocol):
    @property
    def execution_version(self) -> str: ...

    @property
    def model_mode(self) -> str: ...

    @property
    def root_ids(self) -> tuple[int, ...]: ...

    @property
    def timebase(self) -> SimulationTimebase: ...

    @property
    def determinism(self) -> SimulationDeterminismContext: ...

    @property
    def descriptor(self) -> MorphologyRuntimeDescriptor: ...

    def initialize_zero(self) -> Mapping[str, Any]: ...

    def initialize_states(
        self,
        states_by_root: Mapping[int, Any],
    ) -> Mapping[str, Any]: ...

    def inject_sources(
        self,
        source_values_by_root: Mapping[int, float] | None = None,
    ) -> None: ...

    def step_shared(self) -> Mapping[str, Any]: ...

    def finalize(self) -> MorphologyRuntimeExecutionResult: ...


@dataclass(frozen=True)
class SkeletonGraphState:
    resolution: str
    activation: np.ndarray
    velocity: np.ndarray

    def __post_init__(self) -> None:
        resolution = str(self.resolution)
        if resolution != SKELETON_GRAPH_STATE_RESOLUTION:
            raise ValueError(
                "SkeletonGraphState.resolution must be "
                f"{SKELETON_GRAPH_STATE_RESOLUTION!r}, got {resolution!r}."
            )
        activation = np.asarray(self.activation, dtype=np.float64)
        velocity = np.asarray(self.velocity, dtype=np.float64)
        if activation.ndim != 1 or velocity.ndim != 1:
            raise ValueError("SkeletonGraphState activation and velocity must be 1D.")
        if activation.shape != velocity.shape:
            raise ValueError(
                "SkeletonGraphState activation and velocity must share the same shape."
            )
        object.__setattr__(self, "resolution", resolution)
        object.__setattr__(self, "activation", activation.copy())
        object.__setattr__(self, "velocity", velocity.copy())

    @classmethod
    def zeros(cls, node_count: int) -> SkeletonGraphState:
        normalized_node_count = int(node_count)
        if normalized_node_count <= 0:
            raise ValueError("SkeletonGraphState.zeros requires node_count > 0.")
        zeros = np.zeros(normalized_node_count, dtype=np.float64)
        return cls(
            resolution=SKELETON_GRAPH_STATE_RESOLUTION,
            activation=zeros,
            velocity=zeros.copy(),
        )

    def copy(self) -> SkeletonGraphState:
        return SkeletonGraphState(
            resolution=self.resolution,
            activation=self.activation.copy(),
            velocity=self.velocity.copy(),
        )

    def as_mapping(
        self,
        *,
        node_ids: np.ndarray | None = None,
        node_coordinates: np.ndarray | None = None,
        projection_weights: np.ndarray | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "resolution": self.resolution,
            "activation": np.asarray(self.activation, dtype=np.float64).tolist(),
            "velocity": np.asarray(self.velocity, dtype=np.float64).tolist(),
        }
        if node_ids is not None:
            payload["node_ids"] = np.asarray(node_ids, dtype=np.int64).tolist()
        if node_coordinates is not None:
            payload["node_coordinates"] = np.asarray(
                node_coordinates,
                dtype=np.float64,
            ).tolist()
        if projection_weights is not None:
            payload["projection_weights"] = np.asarray(
                projection_weights,
                dtype=np.float64,
            ).tolist()
        return payload


def resolve_morphology_runtime_from_arm_plan(
    arm_plan: Mapping[str, Any],
) -> MorphologyRuntime:
    normalized_arm_plan = _require_mapping(arm_plan, field_name="arm_plan")
    model_configuration = _require_mapping(
        normalized_arm_plan.get("model_configuration"),
        field_name="arm_plan.model_configuration",
    )
    execution_plan = _require_mapping(
        model_configuration.get("surface_wave_execution_plan"),
        field_name="arm_plan.model_configuration.surface_wave_execution_plan",
    )
    hybrid_morphology = parse_hybrid_morphology_plan_metadata(
        _require_mapping(
            execution_plan.get("hybrid_morphology"),
            field_name="surface_wave_execution_plan.hybrid_morphology",
        )
    )
    discovered_classes = list(hybrid_morphology.get("discovered_morphology_classes", ()))
    if discovered_classes == [SURFACE_NEURON_CLASS]:
        resolved = resolve_surface_wave_execution_plan_from_arm_plan(normalized_arm_plan)
        return build_surface_wave_morphology_runtime(resolved)
    if POINT_NEURON_CLASS in discovered_classes:
        raise NotImplementedError(
            "The pluggable morphology runtime does not yet execute "
            f"{POINT_NEURON_CLASS!r} roots. Discovered morphology_classes were "
            f"{discovered_classes!r}."
        )
    if any(
        morphology_class not in {SURFACE_NEURON_CLASS, SKELETON_NEURON_CLASS}
        for morphology_class in discovered_classes
    ):
        raise NotImplementedError(
            "Unsupported morphology classes were requested by the execution plan: "
            f"{discovered_classes!r}."
        )
    return build_surface_skeleton_morphology_runtime_from_arm_plan(normalized_arm_plan)


def build_surface_wave_morphology_runtime(
    resolved: ResolvedSurfaceWaveExecutionPlan,
) -> MorphologyRuntime:
    return SurfaceWaveMorphologyRuntime(resolved)


def build_surface_skeleton_morphology_runtime_from_arm_plan(
    arm_plan: Mapping[str, Any],
) -> MorphologyRuntime:
    return SurfaceSkeletonMorphologyRuntime(arm_plan)


def run_morphology_runtime_shared_schedule(
    runtime: MorphologyRuntime,
    *,
    drive_values: Sequence[Sequence[float] | np.ndarray],
    initial_states_by_root: Mapping[int, Any] | None = None,
) -> tuple[np.ndarray, MorphologyRuntimeExecutionResult]:
    if initial_states_by_root is None:
        runtime.initialize_zero()
    else:
        runtime.initialize_states(initial_states_by_root)

    expected_sample_count = int(runtime.timebase.sample_count)
    if len(drive_values) != expected_sample_count:
        raise ValueError(
            "Morphology runtime drive schedule length must match timebase.sample_count, "
            f"got {len(drive_values)} and {expected_sample_count}."
        )

    last_drive_vector = np.zeros(len(runtime.root_ids), dtype=np.float64)
    for step_index, drive_vector in enumerate(drive_values):
        normalized_drive_vector = _normalize_drive_vector(
            drive_vector,
            expected_length=len(runtime.root_ids),
            field_name=f"drive_values[{step_index}]",
        )
        last_drive_vector = normalized_drive_vector.copy()
        runtime.inject_sources(
            {
                int(root_id): float(normalized_drive_vector[root_index])
                for root_index, root_id in enumerate(runtime.root_ids)
            }
        )
        runtime.step_shared()
    return last_drive_vector, runtime.finalize()


class SurfaceWaveMorphologyRuntime:
    def __init__(self, resolved: ResolvedSurfaceWaveExecutionPlan) -> None:
        self._resolved = resolved
        self._descriptor = _build_surface_wave_runtime_descriptor(resolved)
        self._circuit = resolved.build_circuit()
        self._vertex_count_by_root = {
            int(bundle.root_id): int(bundle.surface_vertex_count)
            for bundle in resolved.operator_bundles
        }
        self._pending_surface_drives_by_root: dict[int, np.ndarray] | None = None

    @property
    def execution_version(self) -> str:
        return str(self._resolved.execution_version)

    @property
    def model_mode(self) -> str:
        return SURFACE_WAVE_MODEL_MODE

    @property
    def root_ids(self) -> tuple[int, ...]:
        return self._resolved.root_ids

    @property
    def timebase(self) -> SimulationTimebase:
        return self._resolved.timebase

    @property
    def determinism(self) -> SimulationDeterminismContext:
        return self._resolved.determinism

    @property
    def descriptor(self) -> MorphologyRuntimeDescriptor:
        return self._descriptor

    def initialize_zero(self) -> Mapping[str, Any]:
        self._pending_surface_drives_by_root = None
        return self._circuit.initialize_zero()

    def initialize_states(
        self,
        states_by_root: Mapping[int, Any],
    ) -> Mapping[str, Any]:
        self._pending_surface_drives_by_root = None
        return self._circuit.initialize_states(states_by_root)

    def inject_sources(
        self,
        source_values_by_root: Mapping[int, float] | None = None,
    ) -> None:
        if source_values_by_root is None:
            self._pending_surface_drives_by_root = None
            return
        unexpected_root_ids = sorted(
            int(root_id)
            for root_id in source_values_by_root
            if int(root_id) not in set(self.root_ids)
        )
        if unexpected_root_ids:
            raise ValueError(
                "surface-wave morphology runtime received source injections for "
                f"unknown root IDs {unexpected_root_ids!r}."
            )
        self._pending_surface_drives_by_root = {
            int(root_id): np.full(
                self._vertex_count_by_root[int(root_id)],
                float(source_values_by_root.get(int(root_id), 0.0)),
                dtype=np.float64,
            )
            for root_id in self.root_ids
        }

    def step_shared(self) -> Mapping[str, Any]:
        surface_drives_by_root = self._pending_surface_drives_by_root
        self._pending_surface_drives_by_root = None
        return self._circuit.step_shared(surface_drives_by_root=surface_drives_by_root)

    def finalize(self) -> MorphologyRuntimeExecutionResult:
        return SurfaceWaveMorphologyRuntimeResult(
            descriptor=self._descriptor,
            resolved=self._resolved,
            surface_result=self._circuit.finalize(),
        )


@dataclass(frozen=True)
class SurfaceWaveMorphologyRuntimeResult:
    descriptor: MorphologyRuntimeDescriptor
    resolved: ResolvedSurfaceWaveExecutionPlan
    surface_result: CoupledSurfaceWaveRunResult

    @property
    def root_ids(self) -> tuple[int, ...]:
        return self.surface_result.root_ids

    @property
    def timebase(self) -> dict[str, Any]:
        return copy.deepcopy(self.surface_result.timebase)

    @property
    def determinism(self) -> dict[str, Any]:
        return copy.deepcopy(self.surface_result.determinism)

    @property
    def runtime_metadata_by_root(self) -> Sequence[Mapping[str, Any]]:
        return self.surface_result.runtime_metadata_by_root

    @property
    def initial_state_exports_by_root(self) -> Mapping[int, Mapping[str, Any]]:
        return self.surface_result.initial_states_by_root

    @property
    def final_state_exports_by_root(self) -> Mapping[int, Mapping[str, Any]]:
        return self.surface_result.final_states_by_root

    @property
    def coupling_projection_history_by_root(self) -> Mapping[int, np.ndarray]:
        return self.surface_result.patch_readout_history_by_root

    @property
    def shared_readout_history(self) -> Sequence[Mapping[str, Any]]:
        return self.surface_result.shared_readout_history

    @property
    def coupling_application_history(self) -> Sequence[Mapping[str, Any]]:
        return self.surface_result.coupling_application_history

    @property
    def substep_count(self) -> int:
        return int(self.surface_result.substep_count)

    @property
    def shared_step_count(self) -> int:
        return int(self.surface_result.shared_step_count)

    def export_state_summaries(
        self,
        *,
        state_stage: str,
    ) -> tuple[SimulationStateSummaryRow, ...]:
        if state_stage == "initial":
            states_by_root = self.initial_state_exports_by_root
            history_index = 0
        elif state_stage == "final":
            states_by_root = self.final_state_exports_by_root
            history_index = -1
        else:
            raise ValueError(
                "state_stage must be 'initial' or 'final', "
                f"got {state_stage!r}."
            )
        return _build_surface_wave_state_summaries(
            root_ids=self.root_ids,
            states_by_root=states_by_root,
            patch_state_by_root={
                int(root_id): np.asarray(
                    self.coupling_projection_history_by_root[int(root_id)][history_index],
                    dtype=np.float64,
                )
                for root_id in self.root_ids
            },
        )

    def export_readout_values(
        self,
        *,
        summary: Mapping[str, Any],
        readout_catalog: Sequence[SimulationReadoutDefinition],
    ) -> np.ndarray:
        return _surface_wave_readout_values(
            summary=summary,
            readout_catalog=readout_catalog,
        )

    def export_readout_trace_values(
        self,
        *,
        readout_catalog: Sequence[SimulationReadoutDefinition],
        sample_count: int,
    ) -> np.ndarray:
        normalized_sample_count = int(sample_count)
        if len(self.shared_readout_history) < normalized_sample_count:
            raise ValueError(
                "surface-wave shared_readout_history is shorter than the declared sample_count."
            )
        values = np.empty(
            (normalized_sample_count, len(readout_catalog)),
            dtype=np.float64,
        )
        for sample_index in range(normalized_sample_count):
            values[sample_index, :] = self.export_readout_values(
                summary=self.shared_readout_history[sample_index],
                readout_catalog=readout_catalog,
            )
        return values

    def export_dynamic_state_vector(
        self,
        *,
        summary: Mapping[str, Any],
    ) -> np.ndarray:
        return _surface_wave_dynamic_state_vector(
            summary=summary,
            root_ids=self.root_ids,
        )

    def export_projection_trace_payload(self) -> dict[str, np.ndarray]:
        history_length = len(
            self.coupling_projection_history_by_root[int(self.root_ids[0])]
        )
        payload: dict[str, np.ndarray] = {
            "substep_time_ms": (
                np.arange(history_length, dtype=np.float64)
                * float(self.resolved.integration_timestep_ms)
                + float(self.resolved.timebase.time_origin_ms)
            ),
            "root_ids": np.asarray(self.root_ids, dtype=np.int64),
        }
        for root_id in self.root_ids:
            payload[f"root_{int(root_id)}_patch_activation"] = np.asarray(
                self.coupling_projection_history_by_root[int(root_id)],
                dtype=np.float64,
            )
        return payload


class _SingleRootSkeletonGraphRuntime:
    def __init__(
        self,
        *,
        asset: SkeletonRuntimeAsset,
        integration_timestep_ms: float,
        internal_substep_count: int,
        wave_speed_sq_scale: float,
        restoring_strength_per_ms2: float,
        gamma_per_ms: float,
    ) -> None:
        self.asset = asset
        self.integration_timestep_ms = float(integration_timestep_ms)
        self.internal_substep_count = int(internal_substep_count)
        self.wave_speed_sq_scale = float(wave_speed_sq_scale)
        self.restoring_strength_per_ms2 = float(restoring_strength_per_ms2)
        self.gamma_per_ms = float(gamma_per_ms)
        self._pending_source_value = 0.0
        self._current_state: SkeletonGraphState | None = None
        self._initial_state_mapping: dict[str, Any] | None = None
        self._projection_history: list[np.ndarray] = []

    @property
    def root_id(self) -> int:
        return int(self.asset.root_id)

    @property
    def current_state(self) -> SkeletonGraphState:
        if self._current_state is None:
            raise ValueError("Skeleton runtime root has not been initialized.")
        return self._current_state

    @property
    def projection_history(self) -> np.ndarray:
        return np.asarray(self._projection_history, dtype=np.float64)

    @property
    def initial_state_mapping(self) -> dict[str, Any]:
        if self._initial_state_mapping is None:
            raise ValueError("Skeleton runtime root has not been initialized.")
        return copy.deepcopy(self._initial_state_mapping)

    def initialize_zero(self) -> None:
        state = SkeletonGraphState.zeros(self.asset.node_count)
        self.initialize_state(state)

    def initialize_state(self, state: Any) -> None:
        normalized_state = self._normalize_state(state)
        self._current_state = normalized_state
        self._pending_source_value = 0.0
        self._projection_history = [
            np.asarray(normalized_state.activation, dtype=np.float64).copy()
        ]
        self._initial_state_mapping = normalized_state.as_mapping(
            node_ids=self.asset.node_ids,
            node_coordinates=self.asset.node_coordinates,
            projection_weights=self.asset.readout_weights,
        )

    def inject_source(self, value: float | None) -> None:
        self._pending_source_value = 0.0 if value is None else float(value)

    def step_shared(self) -> None:
        state = self.current_state.copy()
        source_value = float(self._pending_source_value)
        source_vector = np.full(self.asset.node_count, source_value, dtype=np.float64)
        operator = self.asset.graph_operator
        for _ in range(self.internal_substep_count):
            acceleration = (
                -self.wave_speed_sq_scale
                * np.asarray(operator @ state.activation, dtype=np.float64)
                - self.restoring_strength_per_ms2 * np.asarray(state.activation, dtype=np.float64)
                - self.gamma_per_ms * np.asarray(state.velocity, dtype=np.float64)
                + source_vector
            )
            updated_velocity = (
                np.asarray(state.velocity, dtype=np.float64)
                + self.integration_timestep_ms * acceleration
            )
            updated_activation = (
                np.asarray(state.activation, dtype=np.float64)
                + self.integration_timestep_ms * updated_velocity
            )
            state = SkeletonGraphState(
                resolution=SKELETON_GRAPH_STATE_RESOLUTION,
                activation=updated_activation,
                velocity=updated_velocity,
            )
        self._current_state = state
        self._pending_source_value = 0.0
        self._projection_history.append(
            np.asarray(self.current_state.activation, dtype=np.float64).copy()
        )

    def export_state_mapping(self) -> dict[str, Any]:
        return self.current_state.as_mapping(
            node_ids=self.asset.node_ids,
            node_coordinates=self.asset.node_coordinates,
            projection_weights=self.asset.readout_weights,
        )

    def runtime_metadata(self) -> dict[str, Any]:
        metadata = load_skeleton_runtime_asset_metadata(
            self.asset.metadata["metadata_path"]
        )
        return {
            "root_id": self.root_id,
            "morphology_class": SKELETON_NEURON_CLASS,
            "state_layout": str(metadata["state_layout"]),
            "projection_surface": str(metadata["projection_surface"]),
            "projection_layout": str(metadata["projection_layout"]),
            "node_count": int(metadata["counts"]["node_count"]),
            "edge_count": int(metadata["counts"]["edge_count"]),
            "asset_hash": str(metadata["asset_hash"]),
            "asset_contract_version": str(metadata["contract_version"]),
            "approximation_family": str(metadata["approximation_family"]),
            "graph_operator_family": str(metadata["graph_operator_family"]),
            "source_injection_strategy": str(metadata["source_injection_strategy"]),
            "spectral_radius": float(metadata["operator"]["spectral_radius"]),
            "integration_timestep_ms": float(self.integration_timestep_ms),
            "internal_substep_count": int(self.internal_substep_count),
        }

    def summary_fragment(self) -> dict[str, Any]:
        state = self.current_state
        weights = np.asarray(self.asset.readout_weights, dtype=np.float64)
        return {
            "mean_activation": float(np.dot(weights, state.activation)),
            "mean_velocity": float(np.dot(weights, state.velocity)),
            "projection": np.asarray(state.activation, dtype=np.float64).copy(),
        }

    def _normalize_state(self, value: Any) -> SkeletonGraphState:
        if isinstance(value, SkeletonGraphState):
            normalized = value.copy()
        elif isinstance(value, Mapping):
            normalized = SkeletonGraphState(
                resolution=str(value.get("resolution", SKELETON_GRAPH_STATE_RESOLUTION)),
                activation=np.asarray(value["activation"], dtype=np.float64),
                velocity=np.asarray(value["velocity"], dtype=np.float64),
            )
        else:
            raise ValueError(
                "Skeleton runtime initialization requires SkeletonGraphState or a "
                "mapping with activation and velocity arrays."
            )
        if normalized.activation.shape[0] != self.asset.node_count:
            raise ValueError(
                "Skeleton runtime initialization state does not match the asset node "
                f"count for root {self.root_id}: got {normalized.activation.shape[0]} "
                f"and expected {self.asset.node_count}."
            )
        return normalized


class SurfaceSkeletonMorphologyRuntime:
    def __init__(self, arm_plan: Mapping[str, Any]) -> None:
        normalized_arm_plan = _require_mapping(arm_plan, field_name="arm_plan")
        self._arm_plan = copy.deepcopy(dict(normalized_arm_plan))
        model_configuration = _require_mapping(
            normalized_arm_plan.get("model_configuration"),
            field_name="arm_plan.model_configuration",
        )
        execution_plan = _require_mapping(
            model_configuration.get("surface_wave_execution_plan"),
            field_name="arm_plan.model_configuration.surface_wave_execution_plan",
        )
        runtime = _require_mapping(
            normalized_arm_plan.get("runtime"),
            field_name="arm_plan.runtime",
        )
        self._surface_wave_model = parse_surface_wave_model_metadata(
            _require_mapping(
                model_configuration.get("surface_wave_model"),
                field_name="arm_plan.model_configuration.surface_wave_model",
            )
        )
        self._hybrid_morphology = parse_hybrid_morphology_plan_metadata(
            _require_mapping(
                execution_plan.get("hybrid_morphology"),
                field_name="surface_wave_execution_plan.hybrid_morphology",
            )
        )
        self._root_ids = tuple(
            int(item["root_id"])
            for item in self._hybrid_morphology["per_root_class_metadata"]
        )
        self._root_class_by_root = {
            int(item["root_id"]): str(item["morphology_class"])
            for item in self._hybrid_morphology["per_root_class_metadata"]
        }
        self._timebase = SimulationTimebase.from_mapping(
            _require_mapping(runtime.get("timebase"), field_name="arm_plan.runtime.timebase")
        )
        self._determinism = SimulationDeterminismContext.from_mapping(
            _require_mapping(
                normalized_arm_plan.get("determinism"),
                field_name="arm_plan.determinism",
            )
        )
        self._validate_supported_configuration()

        self._surface_runtime = _resolve_surface_subset_runtime(
            arm_plan=normalized_arm_plan,
            hybrid_morphology=self._hybrid_morphology,
        )
        self._surface_root_ids = (
            tuple(self._surface_runtime.root_ids)
            if self._surface_runtime is not None
            else ()
        )
        skeleton_root_ids = tuple(
            root_id
            for root_id in self._root_ids
            if self._root_class_by_root[root_id] == SKELETON_NEURON_CLASS
        )
        self._skeleton_runtime_by_root = _resolve_skeleton_root_runtimes(
            execution_plan=execution_plan,
            root_ids=skeleton_root_ids,
            surface_wave_model=self._surface_wave_model,
            shared_output_timestep_ms=float(self._timebase.dt_ms),
        )
        self._require_supported_skeleton_coupling_routes(execution_plan)
        self._descriptor = _build_surface_skeleton_runtime_descriptor(
            arm_plan=normalized_arm_plan,
            hybrid_morphology=self._hybrid_morphology,
            surface_wave_model=self._surface_wave_model,
            surface_runtime=self._surface_runtime,
            skeleton_runtime_by_root=self._skeleton_runtime_by_root,
            timebase=self._timebase,
        )
        self._surface_last_summary: Mapping[str, Any] | None = None
        self._shared_readout_history: list[dict[str, Any]] = []
        self._initialized = False
        self._shared_step_count = 0

    @property
    def execution_version(self) -> str:
        return "surface_wave_surface_skeleton_runtime.v1"

    @property
    def model_mode(self) -> str:
        return SURFACE_WAVE_MODEL_MODE

    @property
    def root_ids(self) -> tuple[int, ...]:
        return self._root_ids

    @property
    def timebase(self) -> SimulationTimebase:
        return self._timebase

    @property
    def determinism(self) -> SimulationDeterminismContext:
        return self._determinism

    @property
    def descriptor(self) -> MorphologyRuntimeDescriptor:
        return self._descriptor

    def initialize_zero(self) -> Mapping[str, Any]:
        if self._surface_runtime is not None:
            self._surface_last_summary = self._surface_runtime.initialize_zero()
        else:
            self._surface_last_summary = None
        for runtime in self._skeleton_runtime_by_root.values():
            runtime.initialize_zero()
        self._initialized = True
        self._shared_step_count = 0
        self._shared_readout_history = [
            _build_shared_summary(
                lifecycle_stage="initialized",
                shared_step_index=0,
                time_ms=float(self._timebase.time_origin_ms),
                root_ids=self._root_ids,
                root_class_by_root=self._root_class_by_root,
                surface_summary=self._surface_last_summary,
                skeleton_runtime_by_root=self._skeleton_runtime_by_root,
            )
        ]
        return copy.deepcopy(self._shared_readout_history[0])

    def initialize_states(
        self,
        states_by_root: Mapping[int, Any],
    ) -> Mapping[str, Any]:
        unknown_root_ids = sorted(
            int(root_id)
            for root_id in states_by_root
            if int(root_id) not in set(self._root_ids)
        )
        if unknown_root_ids:
            raise ValueError(
                "Mixed surface/skeleton runtime initialization contains unknown root "
                f"IDs {unknown_root_ids!r}."
            )
        surface_states = {
            int(root_id): value
            for root_id, value in states_by_root.items()
            if int(root_id) in set(self._surface_root_ids)
        }
        if self._surface_runtime is not None:
            self._surface_last_summary = self._surface_runtime.initialize_states(surface_states)
        else:
            self._surface_last_summary = None
        for root_id, runtime in self._skeleton_runtime_by_root.items():
            state = states_by_root.get(root_id)
            if state is None:
                runtime.initialize_zero()
            else:
                runtime.initialize_state(state)
        self._initialized = True
        self._shared_step_count = 0
        self._shared_readout_history = [
            _build_shared_summary(
                lifecycle_stage="initialized",
                shared_step_index=0,
                time_ms=float(self._timebase.time_origin_ms),
                root_ids=self._root_ids,
                root_class_by_root=self._root_class_by_root,
                surface_summary=self._surface_last_summary,
                skeleton_runtime_by_root=self._skeleton_runtime_by_root,
            )
        ]
        return copy.deepcopy(self._shared_readout_history[0])

    def inject_sources(
        self,
        source_values_by_root: Mapping[int, float] | None = None,
    ) -> None:
        source_values = {} if source_values_by_root is None else {
            int(root_id): float(value)
            for root_id, value in source_values_by_root.items()
        }
        unknown_root_ids = sorted(
            root_id for root_id in source_values if root_id not in set(self._root_ids)
        )
        if unknown_root_ids:
            raise ValueError(
                "Mixed surface/skeleton runtime received source injections for "
                f"unknown root IDs {unknown_root_ids!r}."
            )
        if self._surface_runtime is not None:
            self._surface_runtime.inject_sources(
                {
                    int(root_id): float(source_values.get(int(root_id), 0.0))
                    for root_id in self._surface_root_ids
                }
            )
        for root_id, runtime in self._skeleton_runtime_by_root.items():
            runtime.inject_source(source_values.get(root_id, 0.0))

    def step_shared(self) -> Mapping[str, Any]:
        self._require_initialized()
        if self._surface_runtime is not None:
            self._surface_last_summary = self._surface_runtime.step_shared()
        for runtime in self._skeleton_runtime_by_root.values():
            runtime.step_shared()
        self._shared_step_count += 1
        summary = _build_shared_summary(
            lifecycle_stage="step_completed",
            shared_step_index=self._shared_step_count,
            time_ms=float(self._timebase.time_ms_after_steps(self._shared_step_count)),
            root_ids=self._root_ids,
            root_class_by_root=self._root_class_by_root,
            surface_summary=self._surface_last_summary,
            skeleton_runtime_by_root=self._skeleton_runtime_by_root,
        )
        self._shared_readout_history.append(summary)
        return copy.deepcopy(summary)

    def finalize(self) -> MorphologyRuntimeExecutionResult:
        self._require_initialized()
        surface_result = (
            None if self._surface_runtime is None else self._surface_runtime.finalize()
        )
        final_summary = _build_shared_summary(
            lifecycle_stage="finalized",
            shared_step_index=self._shared_step_count,
            time_ms=float(self._timebase.time_ms_after_steps(self._shared_step_count)),
            root_ids=self._root_ids,
            root_class_by_root=self._root_class_by_root,
            surface_summary=self._surface_last_summary,
            skeleton_runtime_by_root=self._skeleton_runtime_by_root,
        )
        self._shared_readout_history.append(final_summary)
        projection_history_by_root = _build_projection_history_by_root(
            root_ids=self._root_ids,
            root_class_by_root=self._root_class_by_root,
            surface_result=surface_result,
            skeleton_runtime_by_root=self._skeleton_runtime_by_root,
            shared_step_count=self._shared_step_count,
        )
        return SurfaceSkeletonMorphologyRuntimeResult(
            descriptor=self._descriptor,
            root_ids=self._root_ids,
            timebase=self._timebase.as_mapping(),
            determinism=self._determinism.as_mapping(),
            root_class_by_root=self._root_class_by_root,
            runtime_metadata_by_root=_build_runtime_metadata_by_root(
                root_ids=self._root_ids,
                root_class_by_root=self._root_class_by_root,
                surface_result=surface_result,
                skeleton_runtime_by_root=self._skeleton_runtime_by_root,
            ),
            initial_state_exports_by_root=_build_state_exports_by_root(
                root_ids=self._root_ids,
                root_class_by_root=self._root_class_by_root,
                surface_result=surface_result,
                skeleton_runtime_by_root=self._skeleton_runtime_by_root,
                stage="initial",
            ),
            final_state_exports_by_root=_build_state_exports_by_root(
                root_ids=self._root_ids,
                root_class_by_root=self._root_class_by_root,
                surface_result=surface_result,
                skeleton_runtime_by_root=self._skeleton_runtime_by_root,
                stage="final",
            ),
            coupling_projection_history_by_root=projection_history_by_root,
            shared_readout_history=tuple(copy.deepcopy(self._shared_readout_history)),
            coupling_application_history=(
                ()
                if surface_result is None
                else tuple(copy.deepcopy(surface_result.coupling_application_history))
            ),
            substep_count=int(
                max(
                    [self._shared_step_count]
                    + [
                        self._shared_step_count * runtime.internal_substep_count
                        for runtime in self._skeleton_runtime_by_root.values()
                    ]
                    + (
                        []
                        if surface_result is None
                        else [int(surface_result.substep_count)]
                    )
                )
            ),
            shared_step_count=int(self._shared_step_count),
        )

    def _validate_supported_configuration(self) -> None:
        if self._surface_wave_model["recovery_mode"] != _SUPPORTED_SKELETON_RECOVERY_MODE:
            raise ValueError(
                "Skeleton morphology runtime only supports surface_wave.recovery.mode "
                f"{_SUPPORTED_SKELETON_RECOVERY_MODE!r}, got "
                f"{self._surface_wave_model['recovery_mode']!r}."
            )
        if (
            self._surface_wave_model["nonlinearity_mode"]
            != _SUPPORTED_SKELETON_NONLINEARITY_MODE
        ):
            raise ValueError(
                "Skeleton morphology runtime only supports surface_wave.nonlinearity.mode "
                f"{_SUPPORTED_SKELETON_NONLINEARITY_MODE!r}, got "
                f"{self._surface_wave_model['nonlinearity_mode']!r}."
            )
        if self._surface_wave_model["anisotropy_mode"] != _SUPPORTED_SKELETON_ANISOTROPY_MODE:
            raise ValueError(
                "Skeleton morphology runtime only supports surface_wave.anisotropy.mode "
                f"{_SUPPORTED_SKELETON_ANISOTROPY_MODE!r}, got "
                f"{self._surface_wave_model['anisotropy_mode']!r}."
            )
        if self._surface_wave_model["branching_mode"] != _SUPPORTED_SKELETON_BRANCHING_MODE:
            raise ValueError(
                "Skeleton morphology runtime only supports surface_wave.branching.mode "
                f"{_SUPPORTED_SKELETON_BRANCHING_MODE!r}, got "
                f"{self._surface_wave_model['branching_mode']!r}."
            )

    def _require_supported_skeleton_coupling_routes(
        self,
        execution_plan: Mapping[str, Any],
    ) -> None:
        selected_root_skeleton_assets = _require_sequence(
            execution_plan.get("selected_root_skeleton_assets", ()),
            field_name="surface_wave_execution_plan.selected_root_skeleton_assets",
        )
        unsupported_edges: list[str] = []
        for index, asset in enumerate(selected_root_skeleton_assets):
            normalized_asset = _require_mapping(
                asset,
                field_name=f"selected_root_skeleton_assets[{index}]",
            )
            root_id = int(normalized_asset["root_id"])
            for edge_bundle in _require_sequence(
                normalized_asset.get("selected_edge_bundle_paths", ()),
                field_name=(
                    f"selected_root_skeleton_assets[{root_id}].selected_edge_bundle_paths"
                ),
            ):
                edge_mapping = _require_mapping(
                    edge_bundle,
                    field_name=f"selected_root_skeleton_assets[{root_id}].edge_bundle",
                )
                unsupported_edges.append(
                    f"{int(edge_mapping['pre_root_id'])}->{int(edge_mapping['post_root_id'])}"
                )
        if unsupported_edges:
            raise NotImplementedError(
                "Skeleton morphology roots currently expose local graph dynamics and "
                "coupling projections only; execution-time routing for selected edges "
                f"{sorted(unsupported_edges)!r} is deferred to FW-M11-006."
            )

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise ValueError("Mixed surface/skeleton runtime has not been initialized.")


@dataclass(frozen=True)
class SurfaceSkeletonMorphologyRuntimeResult:
    descriptor: MorphologyRuntimeDescriptor
    root_ids: tuple[int, ...]
    timebase: dict[str, Any]
    determinism: dict[str, Any]
    root_class_by_root: Mapping[int, str]
    runtime_metadata_by_root: tuple[Mapping[str, Any], ...]
    initial_state_exports_by_root: Mapping[int, Mapping[str, Any]]
    final_state_exports_by_root: Mapping[int, Mapping[str, Any]]
    coupling_projection_history_by_root: Mapping[int, np.ndarray]
    shared_readout_history: tuple[Mapping[str, Any], ...]
    coupling_application_history: tuple[Mapping[str, Any], ...]
    substep_count: int
    shared_step_count: int

    def export_state_summaries(
        self,
        *,
        state_stage: str,
    ) -> tuple[SimulationStateSummaryRow, ...]:
        if state_stage == "initial":
            states_by_root = self.initial_state_exports_by_root
            history_index = 0
        elif state_stage == "final":
            states_by_root = self.final_state_exports_by_root
            history_index = -1
        else:
            raise ValueError(
                "state_stage must be 'initial' or 'final', "
                f"got {state_stage!r}."
            )
        return _build_mixed_state_summaries(
            root_ids=self.root_ids,
            root_class_by_root=self.root_class_by_root,
            states_by_root=states_by_root,
            projection_state_by_root={
                int(root_id): np.asarray(
                    self.coupling_projection_history_by_root[int(root_id)][history_index],
                    dtype=np.float64,
                )
                for root_id in self.root_ids
            },
        )

    def export_readout_values(
        self,
        *,
        summary: Mapping[str, Any],
        readout_catalog: Sequence[SimulationReadoutDefinition],
    ) -> np.ndarray:
        return _shared_downstream_readout_values(
            summary=summary,
            readout_catalog=readout_catalog,
        )

    def export_readout_trace_values(
        self,
        *,
        readout_catalog: Sequence[SimulationReadoutDefinition],
        sample_count: int,
    ) -> np.ndarray:
        normalized_sample_count = int(sample_count)
        if len(self.shared_readout_history) < normalized_sample_count:
            raise ValueError(
                "Mixed surface/skeleton shared_readout_history is shorter than the "
                "declared sample_count."
            )
        values = np.empty(
            (normalized_sample_count, len(readout_catalog)),
            dtype=np.float64,
        )
        for sample_index in range(normalized_sample_count):
            values[sample_index, :] = self.export_readout_values(
                summary=self.shared_readout_history[sample_index],
                readout_catalog=readout_catalog,
            )
        return values

    def export_dynamic_state_vector(
        self,
        *,
        summary: Mapping[str, Any],
    ) -> np.ndarray:
        return _shared_dynamic_state_vector(
            summary=summary,
            root_ids=self.root_ids,
        )

    def export_projection_trace_payload(self) -> dict[str, np.ndarray]:
        payload: dict[str, np.ndarray] = {
            "shared_time_ms": (
                np.arange(self.shared_step_count + 1, dtype=np.float64)
                * float(self.timebase["dt_ms"])
                + float(self.timebase["time_origin_ms"])
            ),
            "root_ids": np.asarray(self.root_ids, dtype=np.int64),
        }
        for root_id in self.root_ids:
            projection = np.asarray(
                self.coupling_projection_history_by_root[int(root_id)],
                dtype=np.float64,
            )
            payload[f"root_{int(root_id)}_projection_activation"] = projection
            if self.root_class_by_root[int(root_id)] == SURFACE_NEURON_CLASS:
                payload[f"root_{int(root_id)}_patch_activation"] = projection
            else:
                payload[f"root_{int(root_id)}_skeleton_activation"] = projection
        return payload


def _build_surface_wave_runtime_descriptor(
    resolved: ResolvedSurfaceWaveExecutionPlan,
) -> MorphologyRuntimeDescriptor:
    hybrid_morphology = copy.deepcopy(
        _require_mapping(
            resolved.surface_wave_execution_plan.get("hybrid_morphology"),
            field_name="surface_wave_execution_plan.hybrid_morphology",
        )
    )
    return MorphologyRuntimeDescriptor(
        interface_version=MORPHOLOGY_CLASS_RUNTIME_INTERFACE_VERSION,
        model_mode=SURFACE_WAVE_MODEL_MODE,
        runtime_family=SURFACE_WAVE_MORPHOLOGY_RUNTIME_FAMILY,
        hybrid_morphology=hybrid_morphology,
        source_injection={
            "injection_strategy": SURFACE_WAVE_RUNTIME_SOURCE_INJECTION_STRATEGY,
            "source_value_layout": "per_root_scalar_shared_drive",
            "injection_surface": "surface_vertices",
        },
        state_export={
            "state_field_layout": "state_mapping_by_root",
            "root_state_space": "surface_vertices",
            "shared_dynamic_state_semantics": "per_root_mean_activation",
            "projection_history_field": "coupling_projection_history_by_root",
        },
        readout_export={
            "history_field": "shared_readout_history",
            "shared_readout_value_semantics": "shared_downstream_activation",
            "summary_layout": "per_shared_step_summary_mapping",
        },
        coupling_projection={
            "projection_field": "coupling_projection_history_by_root",
            "projection_layout": "substep_by_patch_activation",
            "projection_surface": "coarse_patch_cloud",
            "outgoing_anchor_resolution": "coarse_patch",
            "incoming_anchor_resolution": "coarse_patch",
        },
        model_metadata={
            "model_family": resolved.surface_wave_model["model_family"],
            "parameter_hash": resolved.surface_wave_model["parameter_hash"],
            "solver_family": resolved.surface_wave_model["solver_family"],
            "surface_wave_model": copy.deepcopy(resolved.surface_wave_model),
            "surface_wave_reference": _surface_wave_reference_from_arm_plan(
                resolved.arm_plan
            ),
        },
        solver_metadata={
            "integration_timestep_ms": float(resolved.integration_timestep_ms),
            "shared_output_timestep_ms": float(resolved.shared_output_timestep_ms),
            "internal_substep_count": int(resolved.internal_substep_count),
        },
        coupling_metadata={
            "topology_condition": resolved.coupling_plan.topology_condition,
            "shuffle_scope": resolved.coupling_plan.shuffle_scope,
            "component_count": resolved.coupling_plan.component_count,
            "max_delay_steps": resolved.coupling_plan.max_delay_steps,
            "coupling_hash": resolved.coupling_plan.coupling_hash,
        },
    )


def _resolve_surface_subset_runtime(
    *,
    arm_plan: Mapping[str, Any],
    hybrid_morphology: Mapping[str, Any],
) -> SurfaceWaveMorphologyRuntime | None:
    surface_root_ids = tuple(
        int(item["root_id"])
        for item in hybrid_morphology["per_root_class_metadata"]
        if str(item["morphology_class"]) == SURFACE_NEURON_CLASS
    )
    if not surface_root_ids:
        return None
    model_configuration = _require_mapping(
        arm_plan.get("model_configuration"),
        field_name="arm_plan.model_configuration",
    )
    execution_plan = _filter_surface_execution_plan_for_surface_roots(
        execution_plan=_require_mapping(
            model_configuration.get("surface_wave_execution_plan"),
            field_name="arm_plan.model_configuration.surface_wave_execution_plan",
        ),
        hybrid_morphology=hybrid_morphology,
        surface_root_ids=surface_root_ids,
    )
    runtime = _require_mapping(
        arm_plan.get("runtime"),
        field_name="arm_plan.runtime",
    )
    resolved = resolve_surface_wave_execution_plan(
        surface_wave_model=_require_mapping(
            model_configuration.get("surface_wave_model"),
            field_name="arm_plan.model_configuration.surface_wave_model",
        ),
        surface_wave_execution_plan=execution_plan,
        root_ids=surface_root_ids,
        timebase=_require_mapping(runtime.get("timebase"), field_name="arm_plan.runtime.timebase"),
        determinism=_require_mapping(
            arm_plan.get("determinism"),
            field_name="arm_plan.determinism",
        ),
        arm_plan=arm_plan,
    )
    return SurfaceWaveMorphologyRuntime(resolved)


def _filter_surface_execution_plan_for_surface_roots(
    *,
    execution_plan: Mapping[str, Any],
    hybrid_morphology: Mapping[str, Any],
    surface_root_ids: Sequence[int],
) -> dict[str, Any]:
    selected_surface_roots = {int(root_id) for root_id in surface_root_ids}
    filtered = copy.deepcopy(dict(execution_plan))
    filtered["hybrid_morphology"] = build_hybrid_morphology_plan_metadata(
        root_records=[
            {
                "root_id": int(item["root_id"]),
                "morphology_class": str(item["morphology_class"]),
            }
            for item in hybrid_morphology["per_root_class_metadata"]
            if int(item["root_id"]) in selected_surface_roots
        ],
        model_mode=SURFACE_WAVE_MODEL_MODE,
    )
    filtered["selected_root_operator_assets"] = [
        copy.deepcopy(dict(asset))
        for asset in _require_sequence(
            execution_plan.get("selected_root_operator_assets"),
            field_name="surface_wave_execution_plan.selected_root_operator_assets",
        )
        if int(_require_mapping(asset, field_name="surface_operator_asset")["root_id"])
        in selected_surface_roots
    ]
    filtered_coupling_assets: list[dict[str, Any]] = []
    for asset in _require_sequence(
        execution_plan.get("selected_root_coupling_assets"),
        field_name="surface_wave_execution_plan.selected_root_coupling_assets",
    ):
        normalized_asset = copy.deepcopy(
            dict(_require_mapping(asset, field_name="surface_coupling_asset"))
        )
        root_id = int(normalized_asset["root_id"])
        if root_id not in selected_surface_roots:
            continue
        normalized_asset["selected_edge_bundle_paths"] = [
            copy.deepcopy(edge_bundle)
            for edge_bundle in _require_sequence(
                normalized_asset.get("selected_edge_bundle_paths"),
                field_name=f"surface_coupling_asset[{root_id}].selected_edge_bundle_paths",
            )
            if int(_require_mapping(edge_bundle, field_name="surface_edge_bundle")["pre_root_id"])
            in selected_surface_roots
            and int(
                _require_mapping(edge_bundle, field_name="surface_edge_bundle")["post_root_id"]
            )
            in selected_surface_roots
        ]
        filtered_coupling_assets.append(normalized_asset)
    filtered["selected_root_coupling_assets"] = filtered_coupling_assets
    filtered["selected_root_operator_assets_scope"] = "all_selected_roots"
    filtered["selected_root_coupling_assets_scope"] = "all_selected_roots"
    filtered["selected_root_skeleton_assets_scope"] = "none"
    filtered["selected_root_skeleton_assets"] = []
    return filtered


def _resolve_skeleton_root_runtimes(
    *,
    execution_plan: Mapping[str, Any],
    root_ids: Sequence[int],
    surface_wave_model: Mapping[str, Any],
    shared_output_timestep_ms: float,
) -> dict[int, _SingleRootSkeletonGraphRuntime]:
    if not root_ids:
        return {}
    selected_assets = _resolve_selected_root_skeleton_assets(
        execution_plan=execution_plan,
        root_ids=root_ids,
    )
    propagation = _require_mapping(
        surface_wave_model["parameter_bundle"]["propagation"],
        field_name="surface_wave_model.parameter_bundle.propagation",
    )
    damping = _require_mapping(
        surface_wave_model["parameter_bundle"]["damping"],
        field_name="surface_wave_model.parameter_bundle.damping",
    )
    solver = _require_mapping(
        surface_wave_model["parameter_bundle"]["solver"],
        field_name="surface_wave_model.parameter_bundle.solver",
    )
    cfl_safety_factor = float(solver["cfl_safety_factor"])
    wave_speed_sq_scale = float(propagation["wave_speed_sq_scale"])
    restoring_strength_per_ms2 = float(propagation["restoring_strength_per_ms2"])
    gamma_per_ms = float(damping["gamma_per_ms"])

    runtimes: dict[int, _SingleRootSkeletonGraphRuntime] = {}
    for root_id in root_ids:
        asset = load_skeleton_runtime_asset(selected_assets[int(root_id)]["metadata_path"])
        stable_timestep_ms = compute_surface_wave_stability_timestep_ms(
            spectral_radius=float(asset.metadata["operator"]["spectral_radius"]),
            cfl_safety_factor=cfl_safety_factor,
            wave_speed_sq_scale=wave_speed_sq_scale,
            restoring_strength_per_ms2=restoring_strength_per_ms2,
            recovery_coupling_strength_per_ms2=0.0,
        )
        internal_substep_count = max(
            1,
            int(np.ceil(float(shared_output_timestep_ms) / float(stable_timestep_ms))),
        )
        runtimes[int(root_id)] = _SingleRootSkeletonGraphRuntime(
            asset=asset,
            integration_timestep_ms=float(shared_output_timestep_ms)
            / float(internal_substep_count),
            internal_substep_count=internal_substep_count,
            wave_speed_sq_scale=wave_speed_sq_scale,
            restoring_strength_per_ms2=restoring_strength_per_ms2,
            gamma_per_ms=gamma_per_ms,
        )
    return runtimes


def _resolve_selected_root_skeleton_assets(
    *,
    execution_plan: Mapping[str, Any],
    root_ids: Sequence[int],
) -> dict[int, dict[str, Any]]:
    selected_assets = _require_sequence(
        execution_plan.get("selected_root_skeleton_assets"),
        field_name="surface_wave_execution_plan.selected_root_skeleton_assets",
    )
    asset_by_root = {
        int(_require_mapping(asset, field_name="selected_root_skeleton_asset")["root_id"]): copy.deepcopy(
            dict(_require_mapping(asset, field_name="selected_root_skeleton_asset"))
        )
        for asset in selected_assets
    }
    missing_root_ids = [
        int(root_id)
        for root_id in root_ids
        if int(root_id) not in asset_by_root
    ]
    if missing_root_ids:
        raise ValueError(
            "surface-wave mixed execution is missing skeleton runtime assets for "
            f"selected roots {missing_root_ids!r}."
        )
    for root_id in root_ids:
        asset = asset_by_root[int(root_id)]
        metadata_path = Path(str(asset["metadata_path"])).resolve()
        data_path = Path(str(asset["data_path"])).resolve()
        if not metadata_path.exists() or not data_path.exists():
            raise ValueError(
                "surface-wave mixed execution skeleton runtime asset for root "
                f"{root_id} is missing at {metadata_path} or {data_path}."
            )
        metadata = load_skeleton_runtime_asset_metadata(metadata_path)
        if int(metadata["root_id"]) != int(root_id):
            raise ValueError(
                f"Skeleton runtime asset metadata at {metadata_path} belongs to root "
                f"{metadata['root_id']}, expected {root_id}."
            )
        asset["metadata_path"] = str(metadata_path)
        asset["data_path"] = str(data_path)
        asset["path"] = str(metadata_path)
    return asset_by_root


def _build_surface_skeleton_runtime_descriptor(
    *,
    arm_plan: Mapping[str, Any],
    hybrid_morphology: Mapping[str, Any],
    surface_wave_model: Mapping[str, Any],
    surface_runtime: SurfaceWaveMorphologyRuntime | None,
    skeleton_runtime_by_root: Mapping[int, _SingleRootSkeletonGraphRuntime],
    timebase: SimulationTimebase,
) -> MorphologyRuntimeDescriptor:
    surface_root_ids = set() if surface_runtime is None else set(surface_runtime.root_ids)
    per_root_integration_timestep_ms = {
        str(int(item["root_id"])): (
            float(surface_runtime.descriptor.solver_metadata["integration_timestep_ms"])
            if int(item["root_id"]) in surface_root_ids
            else float(
                skeleton_runtime_by_root[int(item["root_id"])].integration_timestep_ms
            )
        )
        for item in hybrid_morphology["per_root_class_metadata"]
    }
    per_root_internal_substep_count = {
        str(int(item["root_id"])): (
            int(surface_runtime.descriptor.solver_metadata["internal_substep_count"])
            if int(item["root_id"]) in surface_root_ids
            else int(
                skeleton_runtime_by_root[int(item["root_id"])].internal_substep_count
            )
        )
        for item in hybrid_morphology["per_root_class_metadata"]
    }
    integration_timestep_ms = min(
        [float(timebase.dt_ms)]
        + [
            float(value)
            for value in per_root_integration_timestep_ms.values()
        ]
    )
    internal_substep_count = max(
        [1]
        + [
            int(value)
            for value in per_root_internal_substep_count.values()
        ]
    )
    component_count = 0
    max_delay_steps = 0
    topology_condition = "intact"
    if surface_runtime is not None:
        component_count = int(surface_runtime.descriptor.coupling_metadata["component_count"])
        max_delay_steps = int(surface_runtime.descriptor.coupling_metadata["max_delay_steps"])
        topology_condition = str(surface_runtime.descriptor.coupling_metadata["topology_condition"])
    return MorphologyRuntimeDescriptor(
        interface_version=MORPHOLOGY_CLASS_RUNTIME_INTERFACE_VERSION,
        model_mode=SURFACE_WAVE_MODEL_MODE,
        runtime_family=SURFACE_WAVE_SKELETON_MORPHOLOGY_RUNTIME_FAMILY,
        hybrid_morphology=copy.deepcopy(hybrid_morphology),
        source_injection={
            "injection_strategy": "per_root_scalar_shared_drive",
            "source_value_layout": "per_root_scalar_shared_drive",
            "surface_injection_strategy": SURFACE_WAVE_RUNTIME_SOURCE_INJECTION_STRATEGY,
            "skeleton_injection_strategy": SKELETON_GRAPH_RUNTIME_SOURCE_INJECTION_STRATEGY,
        },
        state_export={
            "state_field_layout": "mixed_state_mapping_by_root",
            "root_state_spaces": {
                SURFACE_NEURON_CLASS: "surface_vertices",
                SKELETON_NEURON_CLASS: "skeleton_nodes",
            },
            "shared_dynamic_state_semantics": "per_root_mean_activation",
            "projection_history_field": "coupling_projection_history_by_root",
        },
        readout_export={
            "history_field": "shared_readout_history",
            "shared_readout_value_semantics": "shared_downstream_activation",
            "summary_layout": "per_shared_step_summary_mapping",
        },
        coupling_projection={
            "projection_field": "coupling_projection_history_by_root",
            "projection_layout": "shared_step_by_root_local_projection",
            "projection_surface": "per_root_local_anchor_cloud",
            "outgoing_anchor_resolution": "per_root_morphology_class",
            "incoming_anchor_resolution": "per_root_morphology_class",
        },
        model_metadata={
            "model_family": surface_wave_model["model_family"],
            "parameter_hash": surface_wave_model["parameter_hash"],
            "solver_family": surface_wave_model["solver_family"],
            "surface_wave_model": copy.deepcopy(surface_wave_model),
            "surface_wave_reference": _surface_wave_reference_from_arm_plan(arm_plan),
        },
        solver_metadata={
            "integration_timestep_ms": float(integration_timestep_ms),
            "shared_output_timestep_ms": float(timebase.dt_ms),
            "internal_substep_count": int(internal_substep_count),
            "per_root_integration_timestep_ms": per_root_integration_timestep_ms,
            "per_root_internal_substep_count": per_root_internal_substep_count,
        },
        coupling_metadata={
            "topology_condition": topology_condition,
            "shuffle_scope": (
                None
                if surface_runtime is None
                else surface_runtime.descriptor.coupling_metadata["shuffle_scope"]
            ),
            "component_count": int(component_count),
            "max_delay_steps": int(max_delay_steps),
            "cross_class_routing_supported": False,
            "skeleton_selected_edge_execution": "blocked_until_fw_m11_006",
        },
    )


def _build_shared_summary(
    *,
    lifecycle_stage: str,
    shared_step_index: int,
    time_ms: float,
    root_ids: Sequence[int],
    root_class_by_root: Mapping[int, str],
    surface_summary: Mapping[str, Any] | None,
    skeleton_runtime_by_root: Mapping[int, _SingleRootSkeletonGraphRuntime],
) -> dict[str, Any]:
    per_root_mean_activation: dict[str, float] = {}
    per_root_mean_velocity: dict[str, float] = {}
    per_root_projection_activation: dict[str, list[float]] = {}

    if surface_summary is not None:
        surface_activation = _require_mapping(
            surface_summary.get("per_root_mean_activation"),
            field_name="surface_summary.per_root_mean_activation",
        )
        surface_velocity = _require_mapping(
            surface_summary.get("per_root_mean_velocity"),
            field_name="surface_summary.per_root_mean_velocity",
        )
        surface_projection = _require_mapping(
            surface_summary.get("per_root_patch_activation"),
            field_name="surface_summary.per_root_patch_activation",
        )
        for root_id in root_ids:
            if root_class_by_root[int(root_id)] != SURFACE_NEURON_CLASS:
                continue
            root_key = str(int(root_id))
            per_root_mean_activation[root_key] = float(surface_activation[root_key])
            per_root_mean_velocity[root_key] = float(surface_velocity[root_key])
            per_root_projection_activation[root_key] = [
                float(value)
                for value in surface_projection[root_key]
            ]

    for root_id in root_ids:
        if root_class_by_root[int(root_id)] != SKELETON_NEURON_CLASS:
            continue
        fragment = skeleton_runtime_by_root[int(root_id)].summary_fragment()
        root_key = str(int(root_id))
        per_root_mean_activation[root_key] = float(fragment["mean_activation"])
        per_root_mean_velocity[root_key] = float(fragment["mean_velocity"])
        per_root_projection_activation[root_key] = [
            float(value)
            for value in np.asarray(fragment["projection"], dtype=np.float64)
        ]

    shared_output_mean = (
        float(np.mean(list(per_root_mean_activation.values())))
        if per_root_mean_activation
        else 0.0
    )
    return {
        "lifecycle_stage": lifecycle_stage,
        "shared_step_index": int(shared_step_index),
        "substep_index": int(shared_step_index),
        "time_ms": float(time_ms),
        "shared_output_mean": float(shared_output_mean),
        "per_root_mean_activation": per_root_mean_activation,
        "per_root_mean_velocity": per_root_mean_velocity,
        "per_root_projection_activation": per_root_projection_activation,
        "per_root_patch_activation": copy.deepcopy(per_root_projection_activation),
    }


def _build_projection_history_by_root(
    *,
    root_ids: Sequence[int],
    root_class_by_root: Mapping[int, str],
    surface_result: MorphologyRuntimeExecutionResult | None,
    skeleton_runtime_by_root: Mapping[int, _SingleRootSkeletonGraphRuntime],
    shared_step_count: int,
) -> dict[int, np.ndarray]:
    projection_history_by_root: dict[int, np.ndarray] = {}
    for root_id in root_ids:
        if root_class_by_root[int(root_id)] == SURFACE_NEURON_CLASS:
            if surface_result is None:
                raise ValueError(
                    f"Mixed runtime expected a surface result for root {root_id}."
                )
            history = np.asarray(
                surface_result.shared_readout_history[: shared_step_count + 1],
                dtype=object,
            )
            projection_history_by_root[int(root_id)] = np.asarray(
                [
                    np.asarray(
                        _require_mapping(
                            _require_mapping(
                                item,
                                field_name="surface_shared_summary",
                            ).get("per_root_patch_activation"),
                            field_name="surface_shared_summary.per_root_patch_activation",
                        )[str(int(root_id))],
                        dtype=np.float64,
                    )
                    for item in history
                ],
                dtype=np.float64,
            )
            continue
        projection_history_by_root[int(root_id)] = np.asarray(
            skeleton_runtime_by_root[int(root_id)].projection_history,
            dtype=np.float64,
        )
    return projection_history_by_root


def _build_runtime_metadata_by_root(
    *,
    root_ids: Sequence[int],
    root_class_by_root: Mapping[int, str],
    surface_result: MorphologyRuntimeExecutionResult | None,
    skeleton_runtime_by_root: Mapping[int, _SingleRootSkeletonGraphRuntime],
) -> tuple[dict[str, Any], ...]:
    surface_metadata_by_root = {}
    if surface_result is not None:
        surface_metadata_by_root = {
            int(item["root_id"]): copy.deepcopy(dict(item))
            for item in surface_result.runtime_metadata_by_root
        }
    rows: list[dict[str, Any]] = []
    for root_id in root_ids:
        if root_class_by_root[int(root_id)] == SURFACE_NEURON_CLASS:
            rows.append(copy.deepcopy(surface_metadata_by_root[int(root_id)]))
        else:
            rows.append(skeleton_runtime_by_root[int(root_id)].runtime_metadata())
    return tuple(rows)


def _build_state_exports_by_root(
    *,
    root_ids: Sequence[int],
    root_class_by_root: Mapping[int, str],
    surface_result: MorphologyRuntimeExecutionResult | None,
    skeleton_runtime_by_root: Mapping[int, _SingleRootSkeletonGraphRuntime],
    stage: str,
) -> dict[int, dict[str, Any]]:
    if stage not in {"initial", "final"}:
        raise ValueError(f"Unsupported stage {stage!r}.")
    surface_states_by_root: Mapping[int, Mapping[str, Any]] = {}
    if surface_result is not None:
        surface_states_by_root = (
            surface_result.initial_state_exports_by_root
            if stage == "initial"
            else surface_result.final_state_exports_by_root
        )
    exports: dict[int, dict[str, Any]] = {}
    for root_id in root_ids:
        if root_class_by_root[int(root_id)] == SURFACE_NEURON_CLASS:
            exports[int(root_id)] = copy.deepcopy(dict(surface_states_by_root[int(root_id)]))
        elif stage == "initial":
            exports[int(root_id)] = skeleton_runtime_by_root[int(root_id)].initial_state_mapping
        else:
            exports[int(root_id)] = skeleton_runtime_by_root[int(root_id)].export_state_mapping()
    return exports


def _build_surface_wave_state_summaries(
    *,
    root_ids: Sequence[int],
    states_by_root: Mapping[int, Mapping[str, Any]],
    patch_state_by_root: Mapping[int, np.ndarray],
) -> tuple[SimulationStateSummaryRow, ...]:
    rows: list[SimulationStateSummaryRow] = []
    all_activation: list[np.ndarray] = []
    all_velocity: list[np.ndarray] = []
    all_patch_activation: list[np.ndarray] = []

    for root_id in root_ids:
        state_mapping = _require_mapping(
            states_by_root[int(root_id)],
            field_name=f"states_by_root[{root_id}]",
        )
        activation = np.asarray(state_mapping["activation"], dtype=np.float64)
        velocity = np.asarray(state_mapping["velocity"], dtype=np.float64)
        patch_activation = np.asarray(patch_state_by_root[int(root_id)], dtype=np.float64)
        all_activation.append(activation)
        all_velocity.append(velocity)
        all_patch_activation.append(patch_activation)

        rows.extend(
            [
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_surface_activation_state",
                    scope="root_state",
                    summary_stat="mean",
                    value=float(np.mean(activation)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_surface_activation_state",
                    scope="root_state",
                    summary_stat="min",
                    value=float(np.min(activation)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_surface_activation_state",
                    scope="root_state",
                    summary_stat="max",
                    value=float(np.max(activation)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_surface_velocity_state",
                    scope="root_state",
                    summary_stat="mean",
                    value=float(np.mean(velocity)),
                    units="activation_au_per_ms",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_surface_velocity_state",
                    scope="root_state",
                    summary_stat="min",
                    value=float(np.min(velocity)),
                    units="activation_au_per_ms",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_surface_velocity_state",
                    scope="root_state",
                    summary_stat="max",
                    value=float(np.max(velocity)),
                    units="activation_au_per_ms",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_patch_activation_state",
                    scope="root_state",
                    summary_stat="mean",
                    value=float(np.mean(patch_activation)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_patch_activation_state",
                    scope="root_state",
                    summary_stat="min",
                    value=float(np.min(patch_activation)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_patch_activation_state",
                    scope="root_state",
                    summary_stat="max",
                    value=float(np.max(patch_activation)),
                    units="activation_au",
                ),
            ]
        )

        recovery = state_mapping.get("recovery")
        if recovery is not None:
            recovery_values = np.asarray(recovery, dtype=np.float64)
            rows.extend(
                [
                    _state_summary_row(
                        state_id=f"root_{int(root_id)}_recovery_state",
                        scope="root_state",
                        summary_stat="mean",
                        value=float(np.mean(recovery_values)),
                        units="unitless",
                    ),
                    _state_summary_row(
                        state_id=f"root_{int(root_id)}_recovery_state",
                        scope="root_state",
                        summary_stat="max",
                        value=float(np.max(recovery_values)),
                        units="unitless",
                    ),
                ]
            )

    circuit_activation = np.concatenate(all_activation)
    circuit_velocity = np.concatenate(all_velocity)
    circuit_patch_activation = np.concatenate(all_patch_activation)
    rows.extend(
        [
            _state_summary_row(
                state_id="circuit_surface_activation_state",
                scope="circuit_state",
                summary_stat="mean",
                value=float(np.mean(circuit_activation)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id="circuit_surface_activation_state",
                scope="circuit_state",
                summary_stat="min",
                value=float(np.min(circuit_activation)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id="circuit_surface_activation_state",
                scope="circuit_state",
                summary_stat="max",
                value=float(np.max(circuit_activation)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id="circuit_surface_velocity_state",
                scope="circuit_state",
                summary_stat="mean",
                value=float(np.mean(circuit_velocity)),
                units="activation_au_per_ms",
            ),
            _state_summary_row(
                state_id="circuit_surface_velocity_state",
                scope="circuit_state",
                summary_stat="min",
                value=float(np.min(circuit_velocity)),
                units="activation_au_per_ms",
            ),
            _state_summary_row(
                state_id="circuit_surface_velocity_state",
                scope="circuit_state",
                summary_stat="max",
                value=float(np.max(circuit_velocity)),
                units="activation_au_per_ms",
            ),
            _state_summary_row(
                state_id="circuit_patch_activation_state",
                scope="circuit_state",
                summary_stat="mean",
                value=float(np.mean(circuit_patch_activation)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id="circuit_patch_activation_state",
                scope="circuit_state",
                summary_stat="min",
                value=float(np.min(circuit_patch_activation)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id="circuit_patch_activation_state",
                scope="circuit_state",
                summary_stat="max",
                value=float(np.max(circuit_patch_activation)),
                units="activation_au",
            ),
        ]
    )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.scope,
                row.state_id,
                row.summary_stat,
                row.units,
            ),
        )
    )


def _surface_wave_dynamic_state_vector(
    *,
    summary: Mapping[str, Any],
    root_ids: Sequence[int],
) -> np.ndarray:
    per_root_mean_activation = _require_mapping(
        summary.get("per_root_mean_activation"),
        field_name="surface_wave_summary.per_root_mean_activation",
    )
    return np.asarray(
        [
            float(per_root_mean_activation[str(int(root_id))])
            for root_id in root_ids
        ],
        dtype=np.float64,
    )


def _surface_wave_readout_values(
    *,
    summary: Mapping[str, Any],
    readout_catalog: Sequence[SimulationReadoutDefinition],
) -> np.ndarray:
    shared_output_mean = float(summary["shared_output_mean"])
    values = []
    for definition in readout_catalog:
        if str(definition.value_semantics) != "shared_downstream_activation":
            raise ValueError(
                "surface-wave morphology runtime only supports shared readouts with "
                "value_semantics 'shared_downstream_activation'."
            )
        values.append(shared_output_mean)
    return np.asarray(values, dtype=np.float64)


def _shared_dynamic_state_vector(
    *,
    summary: Mapping[str, Any],
    root_ids: Sequence[int],
) -> np.ndarray:
    per_root_mean_activation = _require_mapping(
        summary.get("per_root_mean_activation"),
        field_name="shared_summary.per_root_mean_activation",
    )
    return np.asarray(
        [
            float(per_root_mean_activation[str(int(root_id))])
            for root_id in root_ids
        ],
        dtype=np.float64,
    )


def _shared_downstream_readout_values(
    *,
    summary: Mapping[str, Any],
    readout_catalog: Sequence[SimulationReadoutDefinition],
) -> np.ndarray:
    shared_output_mean = float(summary["shared_output_mean"])
    values = []
    for definition in readout_catalog:
        if str(definition.value_semantics) != "shared_downstream_activation":
            raise ValueError(
                "Mixed morphology runtime only supports shared readouts with "
                "value_semantics 'shared_downstream_activation'."
            )
        values.append(shared_output_mean)
    return np.asarray(values, dtype=np.float64)


def _build_mixed_state_summaries(
    *,
    root_ids: Sequence[int],
    root_class_by_root: Mapping[int, str],
    states_by_root: Mapping[int, Mapping[str, Any]],
    projection_state_by_root: Mapping[int, np.ndarray],
) -> tuple[SimulationStateSummaryRow, ...]:
    rows: list[SimulationStateSummaryRow] = []
    all_activation: list[np.ndarray] = []
    all_velocity: list[np.ndarray] = []
    all_projection: list[np.ndarray] = []

    classes_present = {
        str(root_class_by_root[int(root_id)])
        for root_id in root_ids
    }
    if classes_present == {SURFACE_NEURON_CLASS}:
        circuit_activation_state_id = "circuit_surface_activation_state"
        circuit_velocity_state_id = "circuit_surface_velocity_state"
        circuit_projection_state_id = "circuit_patch_activation_state"
    elif classes_present == {SKELETON_NEURON_CLASS}:
        circuit_activation_state_id = "circuit_skeleton_activation_state"
        circuit_velocity_state_id = "circuit_skeleton_velocity_state"
        circuit_projection_state_id = "circuit_skeleton_projection_state"
    else:
        circuit_activation_state_id = "circuit_morphology_activation_state"
        circuit_velocity_state_id = "circuit_morphology_velocity_state"
        circuit_projection_state_id = "circuit_projection_activation_state"

    for root_id in root_ids:
        state_mapping = _require_mapping(
            states_by_root[int(root_id)],
            field_name=f"states_by_root[{root_id}]",
        )
        activation = np.asarray(state_mapping["activation"], dtype=np.float64)
        velocity = np.asarray(state_mapping["velocity"], dtype=np.float64)
        projection = np.asarray(projection_state_by_root[int(root_id)], dtype=np.float64)
        all_activation.append(activation)
        all_velocity.append(velocity)
        all_projection.append(projection)

        if root_class_by_root[int(root_id)] == SURFACE_NEURON_CLASS:
            activation_state_id = f"root_{int(root_id)}_surface_activation_state"
            velocity_state_id = f"root_{int(root_id)}_surface_velocity_state"
            projection_state_id = f"root_{int(root_id)}_patch_activation_state"
        else:
            activation_state_id = f"root_{int(root_id)}_skeleton_activation_state"
            velocity_state_id = f"root_{int(root_id)}_skeleton_velocity_state"
            projection_state_id = f"root_{int(root_id)}_skeleton_projection_state"

        rows.extend(
            [
                _state_summary_row(
                    state_id=activation_state_id,
                    scope="root_state",
                    summary_stat="mean",
                    value=float(np.mean(activation)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=activation_state_id,
                    scope="root_state",
                    summary_stat="min",
                    value=float(np.min(activation)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=activation_state_id,
                    scope="root_state",
                    summary_stat="max",
                    value=float(np.max(activation)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=velocity_state_id,
                    scope="root_state",
                    summary_stat="mean",
                    value=float(np.mean(velocity)),
                    units="activation_au_per_ms",
                ),
                _state_summary_row(
                    state_id=velocity_state_id,
                    scope="root_state",
                    summary_stat="min",
                    value=float(np.min(velocity)),
                    units="activation_au_per_ms",
                ),
                _state_summary_row(
                    state_id=velocity_state_id,
                    scope="root_state",
                    summary_stat="max",
                    value=float(np.max(velocity)),
                    units="activation_au_per_ms",
                ),
                _state_summary_row(
                    state_id=projection_state_id,
                    scope="root_state",
                    summary_stat="mean",
                    value=float(np.mean(projection)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=projection_state_id,
                    scope="root_state",
                    summary_stat="min",
                    value=float(np.min(projection)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=projection_state_id,
                    scope="root_state",
                    summary_stat="max",
                    value=float(np.max(projection)),
                    units="activation_au",
                ),
            ]
        )

    circuit_activation = np.concatenate(all_activation)
    circuit_velocity = np.concatenate(all_velocity)
    circuit_projection = np.concatenate(all_projection)
    rows.extend(
        [
            _state_summary_row(
                state_id=circuit_activation_state_id,
                scope="circuit_state",
                summary_stat="mean",
                value=float(np.mean(circuit_activation)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id=circuit_activation_state_id,
                scope="circuit_state",
                summary_stat="min",
                value=float(np.min(circuit_activation)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id=circuit_activation_state_id,
                scope="circuit_state",
                summary_stat="max",
                value=float(np.max(circuit_activation)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id=circuit_velocity_state_id,
                scope="circuit_state",
                summary_stat="mean",
                value=float(np.mean(circuit_velocity)),
                units="activation_au_per_ms",
            ),
            _state_summary_row(
                state_id=circuit_velocity_state_id,
                scope="circuit_state",
                summary_stat="min",
                value=float(np.min(circuit_velocity)),
                units="activation_au_per_ms",
            ),
            _state_summary_row(
                state_id=circuit_velocity_state_id,
                scope="circuit_state",
                summary_stat="max",
                value=float(np.max(circuit_velocity)),
                units="activation_au_per_ms",
            ),
            _state_summary_row(
                state_id=circuit_projection_state_id,
                scope="circuit_state",
                summary_stat="mean",
                value=float(np.mean(circuit_projection)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id=circuit_projection_state_id,
                scope="circuit_state",
                summary_stat="min",
                value=float(np.min(circuit_projection)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id=circuit_projection_state_id,
                scope="circuit_state",
                summary_stat="max",
                value=float(np.max(circuit_projection)),
                units="activation_au",
            ),
        ]
    )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.scope,
                row.state_id,
                row.summary_stat,
                row.units,
            ),
        )
    )


def _surface_wave_reference_from_arm_plan(
    arm_plan: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(arm_plan, Mapping):
        return None
    model_configuration = arm_plan.get("model_configuration")
    if isinstance(model_configuration, Mapping):
        reference = model_configuration.get("surface_wave_reference")
        if isinstance(reference, Mapping):
            return copy.deepcopy(dict(reference))
    return None


def _state_summary_row(
    *,
    state_id: str,
    scope: str,
    summary_stat: str,
    value: float,
    units: str,
) -> SimulationStateSummaryRow:
    return SimulationStateSummaryRow(
        state_id=state_id,
        scope=scope,
        summary_stat=summary_stat,
        value=value,
        units=units,
    )


def _normalize_drive_vector(
    value: Sequence[float] | np.ndarray,
    *,
    expected_length: int,
    field_name: str,
) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float64)
    if vector.ndim != 1 or int(vector.shape[0]) != int(expected_length):
        raise ValueError(
            f"{field_name} must be a length-{expected_length} vector."
        )
    return vector


def _require_sequence(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence.")
    return value


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value
