from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from .baseline_families import (
    BaselineFamilySpec,
    P0BaselineParameters,
)
from .coupling_contract import (
    DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
    POINT_IMPULSE_KERNEL,
    POINT_NEURON_LUMPED_MODE,
    SEPARABLE_RANK_ONE_CLOUD_KERNEL,
    SKELETON_SEGMENT_CLOUD_MODE,
    SURFACE_PATCH_CLOUD_MODE,
)
from .experiment_ablation_transforms import (
    apply_experiment_ablation_coupling_perturbation,
)
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
from .synapse_mapping import (
    ANCHOR_RESOLUTION_COARSE_PATCH,
    ANCHOR_RESOLUTION_LUMPED_ROOT_STATE,
    ANCHOR_RESOLUTION_SKELETON_NODE,
    ANCHOR_TYPE_POINT_STATE,
    ANCHOR_TYPE_SKELETON_NODE,
    ANCHOR_TYPE_SURFACE_PATCH,
    load_edge_coupling_bundle,
)


MORPHOLOGY_CLASS_RUNTIME_INTERFACE_VERSION = "morphology_class_runtime.v1"
SURFACE_WAVE_MORPHOLOGY_RUNTIME_FAMILY = "surface_wave_surface_runtime_adapter.v1"
SURFACE_WAVE_SKELETON_MORPHOLOGY_RUNTIME_FAMILY = (
    "surface_wave_surface_skeleton_runtime_adapter.v1"
)
SURFACE_WAVE_MIXED_MORPHOLOGY_RUNTIME_FAMILY = (
    "surface_wave_mixed_morphology_runtime_adapter.v1"
)
SURFACE_WAVE_RUNTIME_SOURCE_INJECTION_STRATEGY = (
    "uniform_surface_fill_from_shared_root_schedule"
)
SKELETON_GRAPH_RUNTIME_SOURCE_INJECTION_STRATEGY = (
    "uniform_skeleton_node_fill_from_shared_root_schedule"
)
POINT_NEURON_RUNTIME_SOURCE_INJECTION_STRATEGY = (
    "uniform_point_state_fill_from_shared_root_schedule"
)
SKELETON_GRAPH_STATE_RESOLUTION = "skeleton_graph"
POINT_NEURON_STATE_RESOLUTION = "point_state"
_SUPPORTED_SKELETON_RECOVERY_MODE = "disabled"
_SUPPORTED_SKELETON_NONLINEARITY_MODE = "none"
_SUPPORTED_SKELETON_ANISOTROPY_MODE = "isotropic"
_SUPPORTED_SKELETON_BRANCHING_MODE = "disabled"
_DELAY_STEP_TOLERANCE = 1.0e-6

_ANCHOR_MODE_BY_CLASS = {
    SURFACE_NEURON_CLASS: SURFACE_PATCH_CLOUD_MODE,
    SKELETON_NEURON_CLASS: SKELETON_SEGMENT_CLOUD_MODE,
    POINT_NEURON_CLASS: POINT_NEURON_LUMPED_MODE,
}
_ANCHOR_TYPE_BY_CLASS = {
    SURFACE_NEURON_CLASS: ANCHOR_TYPE_SURFACE_PATCH,
    SKELETON_NEURON_CLASS: ANCHOR_TYPE_SKELETON_NODE,
    POINT_NEURON_CLASS: ANCHOR_TYPE_POINT_STATE,
}
_ANCHOR_RESOLUTION_BY_CLASS = {
    SURFACE_NEURON_CLASS: ANCHOR_RESOLUTION_COARSE_PATCH,
    SKELETON_NEURON_CLASS: ANCHOR_RESOLUTION_SKELETON_NODE,
    POINT_NEURON_CLASS: ANCHOR_RESOLUTION_LUMPED_ROOT_STATE,
}
_PROJECTION_SURFACE_BY_CLASS = {
    SURFACE_NEURON_CLASS: "coarse_patch_cloud",
    SKELETON_NEURON_CLASS: "skeleton_anchor_cloud",
    POINT_NEURON_CLASS: "root_state_scalar",
}
_PROJECTION_LABEL_BY_CLASS = {
    SURFACE_NEURON_CLASS: "surface_patch",
    SKELETON_NEURON_CLASS: "skeleton_node",
    POINT_NEURON_CLASS: "point_state",
}


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


@dataclass(frozen=True)
class PointNeuronState:
    resolution: str
    activation: np.ndarray
    velocity: np.ndarray

    def __post_init__(self) -> None:
        resolution = str(self.resolution)
        if resolution != POINT_NEURON_STATE_RESOLUTION:
            raise ValueError(
                "PointNeuronState.resolution must be "
                f"{POINT_NEURON_STATE_RESOLUTION!r}, got {resolution!r}."
            )
        activation = np.asarray(self.activation, dtype=np.float64)
        velocity = np.asarray(self.velocity, dtype=np.float64)
        if activation.ndim != 1 or velocity.ndim != 1:
            raise ValueError("PointNeuronState activation and velocity must be 1D.")
        if activation.shape != (1,) or velocity.shape != (1,):
            raise ValueError(
                "PointNeuronState activation and velocity must each contain exactly one value."
            )
        object.__setattr__(self, "resolution", resolution)
        object.__setattr__(self, "activation", activation.copy())
        object.__setattr__(self, "velocity", velocity.copy())

    @classmethod
    def zeros(cls) -> PointNeuronState:
        zeros = np.zeros(1, dtype=np.float64)
        return cls(
            resolution=POINT_NEURON_STATE_RESOLUTION,
            activation=zeros,
            velocity=zeros.copy(),
        )

    def copy(self) -> PointNeuronState:
        return PointNeuronState(
            resolution=self.resolution,
            activation=self.activation.copy(),
            velocity=self.velocity.copy(),
        )

    def as_mapping(self) -> dict[str, Any]:
        return {
            "resolution": self.resolution,
            "activation": np.asarray(self.activation, dtype=np.float64).tolist(),
            "velocity": np.asarray(self.velocity, dtype=np.float64).tolist(),
            "projection_weights": [1.0],
        }


@dataclass(frozen=True)
class HybridCouplingCloud:
    local_indices: np.ndarray
    weights: np.ndarray
    anchor_indices: np.ndarray
    anchor_mode: str
    anchor_type: str
    anchor_resolution: str
    projection_surface: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "local_indices",
            _freeze_int_array(
                self.local_indices,
                field_name="hybrid_coupling_cloud.local_indices",
                ndim=1,
            ),
        )
        object.__setattr__(
            self,
            "weights",
            _freeze_float_array(
                self.weights,
                field_name="hybrid_coupling_cloud.weights",
                ndim=1,
            ),
        )
        object.__setattr__(
            self,
            "anchor_indices",
            _freeze_int_array(
                self.anchor_indices,
                field_name="hybrid_coupling_cloud.anchor_indices",
                ndim=1,
            ),
        )
        if self.local_indices.shape != self.weights.shape:
            raise ValueError(
                "HybridCouplingCloud local_indices and weights must share the same shape."
            )
        if self.local_indices.shape != self.anchor_indices.shape:
            raise ValueError(
                "HybridCouplingCloud anchor_indices must align with local_indices."
            )
        if self.local_indices.size < 1:
            raise ValueError("HybridCouplingCloud must contain at least one local anchor.")

    def as_mapping(self) -> dict[str, Any]:
        return {
            "local_indices": self.local_indices.tolist(),
            "weights": np.asarray(self.weights, dtype=np.float64).tolist(),
            "anchor_indices": self.anchor_indices.tolist(),
            "anchor_mode": str(self.anchor_mode),
            "anchor_type": str(self.anchor_type),
            "anchor_resolution": str(self.anchor_resolution),
            "projection_surface": str(self.projection_surface),
        }


@dataclass(frozen=True)
class HybridCouplingComponent:
    component_id: str
    component_family_id: str
    pre_root_id: int
    post_root_id: int
    source_morphology_class: str
    target_morphology_class: str
    route_id: str
    projection_route: str
    source_projection_surface: str
    target_injection_surface: str
    topology_family: str
    kernel_family: str
    aggregation_rule: str
    delay_ms: float
    delay_steps: int
    sign_label: str
    signed_weight_total: float
    synapse_count: int
    source_anchor_mode: str
    target_anchor_mode: str
    source_anchor_type: str
    target_anchor_type: str
    source_anchor_resolution: str
    target_anchor_resolution: str
    source_cloud_normalization: str
    target_cloud_normalization: str
    source_fallback_used: bool
    target_fallback_used: bool
    source_fallback_reasons: tuple[str, ...]
    target_fallback_reasons: tuple[str, ...]
    edge_bundle_path: str
    source_cloud: HybridCouplingCloud
    target_cloud: HybridCouplingCloud

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("Hybrid coupling components require a non-empty component_id.")
        if not self.component_family_id:
            raise ValueError(
                "Hybrid coupling components require a non-empty component_family_id."
            )
        if self.delay_steps < 0:
            raise ValueError(
                f"Hybrid coupling component {self.component_id!r} delay_steps must be non-negative."
            )
        if not np.isfinite(self.delay_ms) or self.delay_ms < 0.0:
            raise ValueError(
                f"Hybrid coupling component {self.component_id!r} has unusable delay_ms {self.delay_ms!r}."
            )
        if not np.isfinite(self.signed_weight_total):
            raise ValueError(
                f"Hybrid coupling component {self.component_id!r} has a non-finite signed_weight_total."
            )
        object.__setattr__(
            self,
            "source_fallback_reasons",
            tuple(str(value) for value in self.source_fallback_reasons),
        )
        object.__setattr__(
            self,
            "target_fallback_reasons",
            tuple(str(value) for value in self.target_fallback_reasons),
        )

    def as_mapping(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_family_id": self.component_family_id,
            "pre_root_id": int(self.pre_root_id),
            "post_root_id": int(self.post_root_id),
            "source_morphology_class": str(self.source_morphology_class),
            "target_morphology_class": str(self.target_morphology_class),
            "route_id": str(self.route_id),
            "projection_route": str(self.projection_route),
            "source_projection_surface": str(self.source_projection_surface),
            "target_injection_surface": str(self.target_injection_surface),
            "topology_family": str(self.topology_family),
            "kernel_family": str(self.kernel_family),
            "aggregation_rule": str(self.aggregation_rule),
            "delay_ms": float(self.delay_ms),
            "delay_steps": int(self.delay_steps),
            "sign_label": str(self.sign_label),
            "signed_weight_total": float(self.signed_weight_total),
            "synapse_count": int(self.synapse_count),
            "source_anchor_mode": str(self.source_anchor_mode),
            "target_anchor_mode": str(self.target_anchor_mode),
            "source_anchor_type": str(self.source_anchor_type),
            "target_anchor_type": str(self.target_anchor_type),
            "source_anchor_resolution": str(self.source_anchor_resolution),
            "target_anchor_resolution": str(self.target_anchor_resolution),
            "source_cloud_normalization": str(self.source_cloud_normalization),
            "target_cloud_normalization": str(self.target_cloud_normalization),
            "source_fallback_used": bool(self.source_fallback_used),
            "target_fallback_used": bool(self.target_fallback_used),
            "source_fallback_reasons": list(self.source_fallback_reasons),
            "target_fallback_reasons": list(self.target_fallback_reasons),
            "edge_bundle_path": str(self.edge_bundle_path),
            "source_cloud": self.source_cloud.as_mapping(),
            "target_cloud": self.target_cloud.as_mapping(),
        }


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
    if any(
        morphology_class
        not in {SURFACE_NEURON_CLASS, SKELETON_NEURON_CLASS, POINT_NEURON_CLASS}
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
        self._pending_patch_drives_by_root: dict[int, np.ndarray] | None = None

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
        self._pending_patch_drives_by_root = None
        return self._circuit.initialize_zero()

    def initialize_states(
        self,
        states_by_root: Mapping[int, Any],
    ) -> Mapping[str, Any]:
        self._pending_surface_drives_by_root = None
        self._pending_patch_drives_by_root = None
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

    def inject_patch_drives(
        self,
        patch_drives_by_root: Mapping[int, Sequence[float] | np.ndarray] | None = None,
    ) -> None:
        if patch_drives_by_root is None:
            self._pending_patch_drives_by_root = None
            return
        unexpected_root_ids = sorted(
            int(root_id)
            for root_id in patch_drives_by_root
            if int(root_id) not in set(self.root_ids)
        )
        if unexpected_root_ids:
            raise ValueError(
                "surface-wave morphology runtime received patch drives for unknown "
                f"root IDs {unexpected_root_ids!r}."
            )
        self._pending_patch_drives_by_root = {
            int(root_id): _freeze_float_array(
                patch_drives_by_root.get(
                    int(root_id),
                    np.zeros(self._require_patch_count(int(root_id)), dtype=np.float64),
                ),
                field_name=f"patch_drives_by_root[{int(root_id)}]",
                ndim=1,
                expected_length=self._require_patch_count(root_id),
            ).copy()
            for root_id in self.root_ids
        }

    def step_shared(self) -> Mapping[str, Any]:
        surface_drives_by_root = self._pending_surface_drives_by_root
        patch_drives_by_root = self._pending_patch_drives_by_root
        self._pending_surface_drives_by_root = None
        self._pending_patch_drives_by_root = None
        return self._circuit.step_shared(
            surface_drives_by_root=surface_drives_by_root,
            patch_drives_by_root=patch_drives_by_root,
        )

    def shared_projection_history_by_root(self) -> dict[int, np.ndarray]:
        if not self._circuit.is_initialized:
            raise ValueError("surface-wave morphology runtime has not been initialized.")
        stride = int(self._resolved.internal_substep_count)
        return {
            int(root_id): np.asarray(
                self._circuit._patch_readout_history_by_root[int(root_id)][::stride],
                dtype=np.float64,
            )
            for root_id in self.root_ids
        }

    def finalize(self) -> MorphologyRuntimeExecutionResult:
        return SurfaceWaveMorphologyRuntimeResult(
            descriptor=self._descriptor,
            resolved=self._resolved,
            surface_result=self._circuit.finalize(),
        )

    def _require_patch_count(self, root_id: int) -> int:
        solver = self._circuit._solver_by_root[int(root_id)]
        patch_count = solver.runtime_metadata.patch_count
        if patch_count is None:
            raise ValueError(
                f"surface-wave morphology runtime root {root_id} does not expose a patch state space."
            )
        return int(patch_count)


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
        return tuple(
            {
                **copy.deepcopy(dict(item)),
                "morphology_class": SURFACE_NEURON_CLASS,
            }
            for item in self.surface_result.runtime_metadata_by_root
        )

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
        self._pending_projection_drive: np.ndarray | None = None
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

    @property
    def node_index_by_node_id(self) -> dict[int, int]:
        return {
            int(node_id): index
            for index, node_id in enumerate(self.asset.node_ids.tolist())
        }

    def initialize_zero(self) -> None:
        state = SkeletonGraphState.zeros(self.asset.node_count)
        self.initialize_state(state)

    def initialize_state(self, state: Any) -> None:
        normalized_state = self._normalize_state(state)
        self._current_state = normalized_state
        self._pending_source_value = 0.0
        self._pending_projection_drive = None
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

    def inject_projection_drive(
        self,
        value: Sequence[float] | np.ndarray | None,
    ) -> None:
        if value is None:
            self._pending_projection_drive = None
            return
        self._pending_projection_drive = _freeze_float_array(
            value,
            field_name=f"skeleton_projection_drive[{self.root_id}]",
            ndim=1,
            expected_length=self.asset.node_count,
        ).copy()

    def step_shared(self) -> None:
        state = self.current_state.copy()
        source_value = float(self._pending_source_value)
        source_vector = np.full(self.asset.node_count, source_value, dtype=np.float64)
        if self._pending_projection_drive is not None:
            source_vector = source_vector + np.asarray(
                self._pending_projection_drive,
                dtype=np.float64,
            )
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
        self._pending_projection_drive = None
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


class _SingleRootPointNeuronRuntime:
    def __init__(
        self,
        *,
        root_id: int,
        model_spec: Mapping[str, Any],
        integration_timestep_ms: float,
    ) -> None:
        spec = BaselineFamilySpec.from_mapping(model_spec)
        if spec.family != "P0":
            raise ValueError(
                "Point-neuron placeholders currently support only the canonical "
                "P0 baseline family."
            )
        parameters = spec.parameters
        assert isinstance(parameters, P0BaselineParameters)
        self.root_id = int(root_id)
        self.spec = spec
        self.parameters = parameters
        self.integration_timestep_ms = float(integration_timestep_ms)
        self._pending_source_value = 0.0
        self._pending_projection_drive: np.ndarray | None = None
        self._current_state: PointNeuronState | None = None
        self._initial_state_mapping: dict[str, Any] | None = None
        self._projection_history: list[np.ndarray] = []

    @property
    def current_state(self) -> PointNeuronState:
        if self._current_state is None:
            raise ValueError("Point runtime root has not been initialized.")
        return self._current_state

    @property
    def projection_history(self) -> np.ndarray:
        return np.asarray(self._projection_history, dtype=np.float64)

    @property
    def initial_state_mapping(self) -> dict[str, Any]:
        if self._initial_state_mapping is None:
            raise ValueError("Point runtime root has not been initialized.")
        return copy.deepcopy(self._initial_state_mapping)

    def initialize_zero(self) -> None:
        self.initialize_state(PointNeuronState.zeros())

    def initialize_state(self, state: Any) -> None:
        normalized_state = self._normalize_state(state)
        self._current_state = normalized_state
        self._pending_source_value = 0.0
        self._pending_projection_drive = None
        self._projection_history = [
            np.asarray(normalized_state.activation, dtype=np.float64).copy()
        ]
        self._initial_state_mapping = normalized_state.as_mapping()

    def inject_source(self, value: float | None) -> None:
        self._pending_source_value = 0.0 if value is None else float(value)

    def inject_projection_drive(
        self,
        value: Sequence[float] | np.ndarray | None,
    ) -> None:
        if value is None:
            self._pending_projection_drive = None
            return
        self._pending_projection_drive = _freeze_float_array(
            value,
            field_name=f"point_projection_drive[{self.root_id}]",
            ndim=1,
            expected_length=1,
        ).copy()

    def step_shared(self) -> None:
        state = self.current_state.copy()
        source_value = float(self._pending_source_value)
        if self._pending_projection_drive is not None:
            source_value += float(self._pending_projection_drive[0])
        activation = float(state.activation[0])
        tau_ms = float(self.parameters.membrane_time_constant_ms)
        resting_potential = float(self.parameters.resting_potential)
        input_gain = float(self.parameters.input_gain)
        delta = (
            (-(activation - resting_potential) + input_gain * source_value)
            / tau_ms
        )
        updated_activation = activation + self.integration_timestep_ms * delta
        self._current_state = PointNeuronState(
            resolution=POINT_NEURON_STATE_RESOLUTION,
            activation=np.asarray([updated_activation], dtype=np.float64),
            velocity=np.asarray([delta], dtype=np.float64),
        )
        self._pending_source_value = 0.0
        self._pending_projection_drive = None
        self._projection_history.append(
            np.asarray(self.current_state.activation, dtype=np.float64).copy()
        )

    def export_state_mapping(self) -> dict[str, Any]:
        return self.current_state.as_mapping()

    def runtime_metadata(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "morphology_class": POINT_NEURON_CLASS,
            "state_layout": str(self.spec.state_layout),
            "projection_surface": "root_state_scalar",
            "projection_layout": "single_value_projection",
            "node_count": 1,
            "edge_count": 0,
            "asset_hash": None,
            "asset_contract_version": None,
            "approximation_family": "p0_point_placeholder",
            "graph_operator_family": None,
            "source_injection_strategy": POINT_NEURON_RUNTIME_SOURCE_INJECTION_STRATEGY,
            "integration_timestep_ms": float(self.integration_timestep_ms),
            "internal_substep_count": 1,
            "baseline_family": str(self.spec.family),
            "model_family": str(self.spec.model_family),
            "readout_state": str(self.spec.readout_state),
        }

    def summary_fragment(self) -> dict[str, Any]:
        state = self.current_state
        return {
            "mean_activation": float(state.activation[0]),
            "mean_velocity": float(state.velocity[0]),
            "projection": np.asarray(state.activation, dtype=np.float64).copy(),
        }

    def _normalize_state(self, value: Any) -> PointNeuronState:
        if isinstance(value, PointNeuronState):
            return value.copy()
        if isinstance(value, Mapping):
            return PointNeuronState(
                resolution=str(value.get("resolution", POINT_NEURON_STATE_RESOLUTION)),
                activation=np.asarray(value["activation"], dtype=np.float64),
                velocity=np.asarray(
                    value.get("velocity", np.zeros(1, dtype=np.float64)),
                    dtype=np.float64,
                ),
            )
        raise ValueError(
            "Point runtime initialization requires PointNeuronState or a mapping "
            "with scalar activation and velocity arrays."
        )


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
        mixed_fidelity_payload = execution_plan.get("mixed_fidelity")
        self._mixed_fidelity = (
            {}
            if mixed_fidelity_payload is None
            else copy.deepcopy(
                dict(
                    _require_mapping(
                        mixed_fidelity_payload,
                        field_name="surface_wave_execution_plan.mixed_fidelity",
                    )
                )
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
        self._per_root_assignment_by_root = {
            int(_require_mapping(item, field_name="mixed_fidelity.per_root_assignments")["root_id"]): copy.deepcopy(
                dict(_require_mapping(item, field_name="mixed_fidelity.per_root_assignments"))
            )
            for item in _require_sequence(
                self._mixed_fidelity.get("per_root_assignments", ()),
                field_name="surface_wave_execution_plan.mixed_fidelity.per_root_assignments",
            )
        }
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
        point_root_ids = tuple(
            root_id
            for root_id in self._root_ids
            if self._root_class_by_root[root_id] == POINT_NEURON_CLASS
        )
        self._point_runtime_by_root = _resolve_point_root_runtimes(
            root_ids=point_root_ids,
            point_neuron_model_spec=(
                {}
                if not point_root_ids
                else _resolve_point_neuron_model_spec(self._mixed_fidelity)
            ),
            shared_output_timestep_ms=float(self._timebase.dt_ms),
        )
        self._hybrid_coupling_plan = _resolve_hybrid_coupling_plan(
            execution_plan=execution_plan,
            root_ids=self._root_ids,
            root_class_by_root=self._root_class_by_root,
            surface_runtime=self._surface_runtime,
            skeleton_runtime_by_root=self._skeleton_runtime_by_root,
            point_runtime_by_root=self._point_runtime_by_root,
            timebase=self._timebase,
        )
        self._descriptor = _build_surface_skeleton_runtime_descriptor(
            arm_plan=normalized_arm_plan,
            hybrid_morphology=self._hybrid_morphology,
            surface_wave_model=self._surface_wave_model,
            surface_runtime=self._surface_runtime,
            skeleton_runtime_by_root=self._skeleton_runtime_by_root,
            point_runtime_by_root=self._point_runtime_by_root,
            timebase=self._timebase,
            hybrid_coupling_plan=self._hybrid_coupling_plan,
        )
        self._surface_last_summary: Mapping[str, Any] | None = None
        self._shared_readout_history: list[dict[str, Any]] = []
        self._routed_coupling_application_history: list[dict[str, Any]] = []
        self._initialized = False
        self._shared_step_count = 0

    @property
    def execution_version(self) -> str:
        if self._point_runtime_by_root:
            return "surface_wave_mixed_morphology_runtime.v1"
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
        for runtime in self._point_runtime_by_root.values():
            runtime.initialize_zero()
        self._initialized = True
        self._shared_step_count = 0
        self._routed_coupling_application_history = []
        self._shared_readout_history = [
            _build_shared_summary(
                lifecycle_stage="initialized",
                shared_step_index=0,
                time_ms=float(self._timebase.time_origin_ms),
                root_ids=self._root_ids,
                root_class_by_root=self._root_class_by_root,
                surface_summary=self._surface_last_summary,
                skeleton_runtime_by_root=self._skeleton_runtime_by_root,
                point_runtime_by_root=self._point_runtime_by_root,
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
                "Mixed morphology runtime initialization contains unknown root "
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
        for root_id, runtime in self._point_runtime_by_root.items():
            state = states_by_root.get(root_id)
            if state is None:
                runtime.initialize_zero()
            else:
                runtime.initialize_state(state)
        self._initialized = True
        self._shared_step_count = 0
        self._routed_coupling_application_history = []
        self._shared_readout_history = [
            _build_shared_summary(
                lifecycle_stage="initialized",
                shared_step_index=0,
                time_ms=float(self._timebase.time_origin_ms),
                root_ids=self._root_ids,
                root_class_by_root=self._root_class_by_root,
                surface_summary=self._surface_last_summary,
                skeleton_runtime_by_root=self._skeleton_runtime_by_root,
                point_runtime_by_root=self._point_runtime_by_root,
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
                "Mixed morphology runtime received source injections for "
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
        for root_id, runtime in self._point_runtime_by_root.items():
            runtime.inject_source(source_values.get(root_id, 0.0))

    def step_shared(self) -> Mapping[str, Any]:
        self._require_initialized()
        routed_drives_by_root, routed_events = _resolve_hybrid_coupling_drives(
            hybrid_coupling_plan=self._hybrid_coupling_plan,
            root_ids=self._root_ids,
            root_class_by_root=self._root_class_by_root,
            surface_runtime=self._surface_runtime,
            skeleton_runtime_by_root=self._skeleton_runtime_by_root,
            point_runtime_by_root=self._point_runtime_by_root,
            shared_step_index=self._shared_step_count,
            timebase=self._timebase,
        )
        if self._surface_runtime is not None:
            surface_patch_drives = {
                int(root_id): np.asarray(routed_drives_by_root[int(root_id)], dtype=np.float64)
                for root_id in self._surface_root_ids
                if int(root_id) in routed_drives_by_root
            }
            self._surface_runtime.inject_patch_drives(
                surface_patch_drives or None
            )
        if self._surface_runtime is not None:
            self._surface_last_summary = self._surface_runtime.step_shared()
        for root_id, runtime in self._skeleton_runtime_by_root.items():
            runtime.inject_projection_drive(routed_drives_by_root.get(int(root_id)))
            runtime.step_shared()
        for root_id, runtime in self._point_runtime_by_root.items():
            runtime.inject_projection_drive(routed_drives_by_root.get(int(root_id)))
            runtime.step_shared()
        self._shared_step_count += 1
        self._routed_coupling_application_history.extend(copy.deepcopy(routed_events))
        summary = _build_shared_summary(
            lifecycle_stage="step_completed",
            shared_step_index=self._shared_step_count,
            time_ms=float(self._timebase.time_ms_after_steps(self._shared_step_count)),
            root_ids=self._root_ids,
            root_class_by_root=self._root_class_by_root,
            surface_summary=self._surface_last_summary,
            skeleton_runtime_by_root=self._skeleton_runtime_by_root,
            point_runtime_by_root=self._point_runtime_by_root,
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
            point_runtime_by_root=self._point_runtime_by_root,
        )
        self._shared_readout_history.append(final_summary)
        projection_history_by_root = _build_projection_history_by_root(
            root_ids=self._root_ids,
            root_class_by_root=self._root_class_by_root,
            surface_result=surface_result,
            skeleton_runtime_by_root=self._skeleton_runtime_by_root,
            point_runtime_by_root=self._point_runtime_by_root,
            shared_step_count=self._shared_step_count,
        )
        surface_coupling_events = _augment_surface_coupling_events(
            surface_result=surface_result,
        )
        coupling_application_history = tuple(
            sorted(
                [
                    *surface_coupling_events,
                    *copy.deepcopy(self._routed_coupling_application_history),
                ],
                key=lambda item: (
                    float(item.get("applied_time_ms", 0.0)),
                    int(item.get("source_step_index", -1)),
                    str(item.get("component_id", "")),
                ),
            )
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
                point_runtime_by_root=self._point_runtime_by_root,
            ),
            initial_state_exports_by_root=_build_state_exports_by_root(
                root_ids=self._root_ids,
                root_class_by_root=self._root_class_by_root,
                surface_result=surface_result,
                skeleton_runtime_by_root=self._skeleton_runtime_by_root,
                point_runtime_by_root=self._point_runtime_by_root,
                stage="initial",
            ),
            final_state_exports_by_root=_build_state_exports_by_root(
                root_ids=self._root_ids,
                root_class_by_root=self._root_class_by_root,
                surface_result=surface_result,
                skeleton_runtime_by_root=self._skeleton_runtime_by_root,
                point_runtime_by_root=self._point_runtime_by_root,
                stage="final",
            ),
            coupling_projection_history_by_root=projection_history_by_root,
            shared_readout_history=tuple(copy.deepcopy(self._shared_readout_history)),
            coupling_application_history=coupling_application_history,
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
        if not any(
            morphology_class == SKELETON_NEURON_CLASS
            for morphology_class in self._root_class_by_root.values()
        ):
            return
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

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise ValueError("Mixed morphology runtime has not been initialized.")


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
                "Mixed morphology shared_readout_history is shorter than the "
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
            elif self.root_class_by_root[int(root_id)] == SKELETON_NEURON_CLASS:
                payload[f"root_{int(root_id)}_skeleton_activation"] = projection
            else:
                payload[f"root_{int(root_id)}_point_activation"] = projection
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


def _resolve_point_neuron_model_spec(
    mixed_fidelity: Mapping[str, Any],
) -> dict[str, Any]:
    return copy.deepcopy(
        dict(
            _require_mapping(
                mixed_fidelity.get("point_neuron_model_spec"),
                field_name="surface_wave_execution_plan.mixed_fidelity.point_neuron_model_spec",
            )
        )
    )


def _resolve_point_root_runtimes(
    *,
    root_ids: Sequence[int],
    point_neuron_model_spec: Mapping[str, Any],
    shared_output_timestep_ms: float,
) -> dict[int, _SingleRootPointNeuronRuntime]:
    return {
        int(root_id): _SingleRootPointNeuronRuntime(
            root_id=int(root_id),
            model_spec=point_neuron_model_spec,
            integration_timestep_ms=float(shared_output_timestep_ms),
        )
        for root_id in root_ids
    }


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


def _resolve_hybrid_coupling_plan(
    *,
    execution_plan: Mapping[str, Any],
    root_ids: Sequence[int],
    root_class_by_root: Mapping[int, str],
    surface_runtime: SurfaceWaveMorphologyRuntime | None,
    skeleton_runtime_by_root: Mapping[int, _SingleRootSkeletonGraphRuntime],
    point_runtime_by_root: Mapping[int, _SingleRootPointNeuronRuntime],
    timebase: SimulationTimebase,
) -> dict[str, Any]:
    ablation_transform = (
        None
        if execution_plan.get("ablation_transform") is None
        else _require_mapping(
            execution_plan.get("ablation_transform"),
            field_name="surface_wave_execution_plan.ablation_transform",
        )
    )
    edge_paths = _collect_hybrid_selected_edge_paths(
        execution_plan=execution_plan,
        root_ids=root_ids,
    )
    target_patch_permutations = (
        {}
        if surface_runtime is None
        else {
            int(root_id): np.asarray(permutation, dtype=np.int64)
            for root_id, permutation in surface_runtime._resolved.coupling_plan.target_patch_permutations.items()
        }
    )
    component_families = _surface_subset_component_families(surface_runtime)
    components: list[HybridCouplingComponent] = []
    mixed_component_count = 0
    max_delay_steps = (
        0
        if surface_runtime is None
        else int(surface_runtime._resolved.coupling_plan.max_delay_steps)
    )
    for edge_key in sorted(edge_paths):
        pre_root_id, post_root_id = edge_key
        source_class = str(root_class_by_root[int(pre_root_id)])
        target_class = str(root_class_by_root[int(post_root_id)])
        if (
            source_class == SURFACE_NEURON_CLASS
            and target_class == SURFACE_NEURON_CLASS
        ):
            continue
        bundle_path = edge_paths[edge_key]
        bundle = load_edge_coupling_bundle(bundle_path)
        if bundle.pre_root_id != int(pre_root_id) or bundle.post_root_id != int(post_root_id):
            raise ValueError(
                f"Hybrid morphology coupling bundle at {bundle_path} does not match edge "
                f"{pre_root_id}->{post_root_id}."
            )
        if bundle.kernel_family not in {
            SEPARABLE_RANK_ONE_CLOUD_KERNEL,
            POINT_IMPULSE_KERNEL,
        }:
            raise ValueError(
                "Hybrid morphology routing only supports kernel families "
                f"{[SEPARABLE_RANK_ONE_CLOUD_KERNEL, POINT_IMPULSE_KERNEL]!r}; "
                f"{bundle_path} declares {bundle.kernel_family!r}."
            )
        if bundle.component_table.empty:
            blocked_reasons = _blocked_reason_catalog(bundle)
            if blocked_reasons:
                raise ValueError(
                    "Hybrid morphology routing cannot execute edge "
                    f"{pre_root_id}->{post_root_id} from {bundle_path} because every "
                    f"synapse was blocked: {blocked_reasons!r}."
                )
            continue
        route_id = _route_id_for_classes(source_class, target_class)
        projection_route = _projection_route_for_classes(source_class, target_class)
        component_family_id = (
            f"{int(pre_root_id)}__to__{int(post_root_id)}__{route_id}"
        )
        ordered_components = bundle.component_table.sort_values(
            ["component_index", "component_id"],
            kind="mergesort",
        ).reset_index(drop=True)
        component_ids: list[str] = []
        family_source_fallback_reasons: set[str] = set()
        family_target_fallback_reasons: set[str] = set()
        family_source_fallback_used = False
        family_target_fallback_used = False
        for row in ordered_components.itertuples(index=False):
            sign_label, signed_weight_total, delay_ms = (
                apply_experiment_ablation_coupling_perturbation(
                    ablation_transform,
                    sign_label=str(row.sign_label),
                    signed_weight_total=float(row.signed_weight_total),
                    delay_ms=float(row.delay_ms),
                )
            )
            source_fallback_metadata = _component_fallback_metadata(
                bundle=bundle,
                component_index=int(row.component_index),
                prefix="pre_",
            )
            target_fallback_metadata = _component_fallback_metadata(
                bundle=bundle,
                component_index=int(row.component_index),
                prefix="post_",
            )
            source_cloud = _resolve_hybrid_component_cloud(
                bundle_path=bundle_path,
                component_index=int(row.component_index),
                component_id=str(row.component_id),
                anchor_table=bundle.source_anchor_table,
                cloud_table=bundle.source_cloud_table,
                expected_root_id=int(pre_root_id),
                morphology_class=source_class,
                surface_patch_permutation=None,
                skeleton_runtime=(
                    None
                    if source_class != SKELETON_NEURON_CLASS
                    else skeleton_runtime_by_root[int(pre_root_id)]
                ),
                role="presynaptic",
            )
            target_cloud = _resolve_hybrid_component_cloud(
                bundle_path=bundle_path,
                component_index=int(row.component_index),
                component_id=str(row.component_id),
                anchor_table=bundle.target_anchor_table,
                cloud_table=bundle.target_cloud_table,
                expected_root_id=int(post_root_id),
                morphology_class=target_class,
                surface_patch_permutation=target_patch_permutations.get(int(post_root_id)),
                skeleton_runtime=(
                    None
                    if target_class != SKELETON_NEURON_CLASS
                    else skeleton_runtime_by_root[int(post_root_id)]
                ),
                role="postsynaptic",
            )
            if bundle.kernel_family == POINT_IMPULSE_KERNEL:
                if source_cloud.local_indices.size != 1 or target_cloud.local_indices.size != 1:
                    raise ValueError(
                        f"Hybrid morphology routing requires single-anchor clouds for "
                        f"{POINT_IMPULSE_KERNEL!r}; component {row.component_id!r} in "
                        f"{bundle_path} is ambiguous."
                    )
            delay_steps = _resolve_shared_delay_steps(
                delay_ms=float(delay_ms),
                dt_ms=float(timebase.dt_ms),
                component_id=str(row.component_id),
            )
            component = HybridCouplingComponent(
                component_id=str(row.component_id),
                component_family_id=component_family_id,
                pre_root_id=int(pre_root_id),
                post_root_id=int(post_root_id),
                source_morphology_class=source_class,
                target_morphology_class=target_class,
                route_id=route_id,
                projection_route=projection_route,
                source_projection_surface=_PROJECTION_SURFACE_BY_CLASS[source_class],
                target_injection_surface=_PROJECTION_SURFACE_BY_CLASS[target_class],
                topology_family=str(bundle.topology_family),
                kernel_family=str(row.kernel_family),
                aggregation_rule=str(row.aggregation_rule),
                delay_ms=float(delay_ms),
                delay_steps=delay_steps,
                sign_label=sign_label,
                signed_weight_total=float(signed_weight_total),
                synapse_count=int(row.synapse_count),
                source_anchor_mode=str(row.pre_anchor_mode),
                target_anchor_mode=str(row.post_anchor_mode),
                source_anchor_type=str(source_cloud.anchor_type),
                target_anchor_type=str(target_cloud.anchor_type),
                source_anchor_resolution=str(source_cloud.anchor_resolution),
                target_anchor_resolution=str(target_cloud.anchor_resolution),
                source_cloud_normalization=str(row.source_cloud_normalization),
                target_cloud_normalization=str(row.target_cloud_normalization),
                source_fallback_used=bool(source_fallback_metadata["fallback_used"]),
                target_fallback_used=bool(target_fallback_metadata["fallback_used"]),
                source_fallback_reasons=tuple(source_fallback_metadata["fallback_reasons"]),
                target_fallback_reasons=tuple(target_fallback_metadata["fallback_reasons"]),
                edge_bundle_path=str(bundle_path),
                source_cloud=source_cloud,
                target_cloud=target_cloud,
            )
            components.append(component)
            component_ids.append(component.component_id)
            mixed_component_count += 1
            max_delay_steps = max(max_delay_steps, int(component.delay_steps))
            family_source_fallback_used = (
                family_source_fallback_used or component.source_fallback_used
            )
            family_target_fallback_used = (
                family_target_fallback_used or component.target_fallback_used
            )
            family_source_fallback_reasons.update(component.source_fallback_reasons)
            family_target_fallback_reasons.update(component.target_fallback_reasons)
        blocked_reasons = _blocked_reason_catalog(bundle)
        if not component_ids:
            raise ValueError(
                "Hybrid morphology routing did not resolve any executable components for "
                f"edge {pre_root_id}->{post_root_id} from {bundle_path}. "
                f"Blocked reasons: {blocked_reasons!r}."
            )
        component_families.append(
            {
                "component_family_id": component_family_id,
                "pre_root_id": int(pre_root_id),
                "post_root_id": int(post_root_id),
                "source_morphology_class": source_class,
                "target_morphology_class": target_class,
                "route_id": route_id,
                "projection_route": projection_route,
                "source_projection_surface": _PROJECTION_SURFACE_BY_CLASS[source_class],
                "target_injection_surface": _PROJECTION_SURFACE_BY_CLASS[target_class],
                "source_anchor_mode": _ANCHOR_MODE_BY_CLASS[source_class],
                "target_anchor_mode": _ANCHOR_MODE_BY_CLASS[target_class],
                "source_anchor_type": _ANCHOR_TYPE_BY_CLASS[source_class],
                "target_anchor_type": _ANCHOR_TYPE_BY_CLASS[target_class],
                "source_anchor_resolution": _ANCHOR_RESOLUTION_BY_CLASS[source_class],
                "target_anchor_resolution": _ANCHOR_RESOLUTION_BY_CLASS[target_class],
                "topology_family": str(bundle.topology_family),
                "kernel_family": str(bundle.kernel_family),
                "aggregation_rule": str(bundle.aggregation_rule),
                "edge_bundle_path": str(bundle_path),
                "component_count": len(component_ids),
                "component_ids": sorted(component_ids),
                "blocked_synapse_count": int(len(bundle.blocked_synapse_table)),
                "blocked_reasons": blocked_reasons,
                "source_fallback_used": bool(family_source_fallback_used),
                "target_fallback_used": bool(family_target_fallback_used),
                "source_fallback_reasons": sorted(family_source_fallback_reasons),
                "target_fallback_reasons": sorted(family_target_fallback_reasons),
                "status": str(bundle.status),
            }
        )
    all_component_count = (
        sum(
            int(item["component_count"])
            for item in component_families
        )
    )
    routing_hash = _stable_hash(
        {
            "routing_timebase_ms": float(timebase.dt_ms),
            "component_families": component_families,
            "components": [component.as_mapping() for component in components],
        }
    )
    return {
        "components": tuple(components),
        "component_families": component_families,
        "component_family_count": len(component_families),
        "surface_subset_component_count": int(all_component_count - mixed_component_count),
        "mixed_route_component_count": int(mixed_component_count),
        "component_count": int(all_component_count),
        "max_delay_steps": int(max_delay_steps),
        "routing_hash": routing_hash,
        "non_surface_selected_edge_execution": (
            "enabled_explicit_router_v1"
            if mixed_component_count > 0
            else "no_selected_non_surface_edges"
        ),
    }


def _collect_hybrid_selected_edge_paths(
    *,
    execution_plan: Mapping[str, Any],
    root_ids: Sequence[int],
) -> dict[tuple[int, int], Path]:
    selected_root_ids = {int(root_id) for root_id in root_ids}
    edge_paths: dict[tuple[int, int], Path] = {}

    def register_from_asset(asset: Mapping[str, Any], *, field_name: str) -> None:
        for edge_index, edge_bundle in enumerate(
            _require_sequence(
                asset.get("selected_edge_bundle_paths", ()),
                field_name=f"{field_name}.selected_edge_bundle_paths",
            )
        ):
            normalized_edge_bundle = _require_mapping(
                edge_bundle,
                field_name=f"{field_name}.selected_edge_bundle_paths[{edge_index}]",
            )
            pre_root_id = int(normalized_edge_bundle["pre_root_id"])
            post_root_id = int(normalized_edge_bundle["post_root_id"])
            if (
                pre_root_id not in selected_root_ids
                or post_root_id not in selected_root_ids
            ):
                raise ValueError(
                    "Hybrid morphology routing encountered selected edge bundle "
                    f"{pre_root_id}->{post_root_id} outside the selected root roster."
                )
            path = Path(str(normalized_edge_bundle["path"])).resolve()
            if not path.exists():
                raise ValueError(
                    f"Hybrid morphology selected edge bundle is missing: {path}."
                )
            edge_key = (pre_root_id, post_root_id)
            if edge_key in edge_paths and edge_paths[edge_key] != path:
                raise ValueError(
                    "Hybrid morphology routing encountered conflicting bundle paths for "
                    f"edge {pre_root_id}->{post_root_id}: "
                    f"{edge_paths[edge_key]} != {path}."
                )
            edge_paths[edge_key] = path

    for index, asset in enumerate(
        _require_sequence(
            execution_plan.get("selected_root_coupling_assets", ()),
            field_name="surface_wave_execution_plan.selected_root_coupling_assets",
        )
    ):
        register_from_asset(
            _require_mapping(
                asset,
                field_name=f"selected_root_coupling_assets[{index}]",
            ),
            field_name=f"selected_root_coupling_assets[{index}]",
        )
    for index, asset in enumerate(
        _require_sequence(
            execution_plan.get("selected_root_skeleton_assets", ()),
            field_name="surface_wave_execution_plan.selected_root_skeleton_assets",
        )
    ):
        register_from_asset(
            _require_mapping(
                asset,
                field_name=f"selected_root_skeleton_assets[{index}]",
            ),
            field_name=f"selected_root_skeleton_assets[{index}]",
        )
    mixed_fidelity = execution_plan.get("mixed_fidelity")
    if isinstance(mixed_fidelity, Mapping):
        for index, assignment in enumerate(
            _require_sequence(
                mixed_fidelity.get("per_root_assignments", ()),
                field_name="surface_wave_execution_plan.mixed_fidelity.per_root_assignments",
            )
        ):
            normalized_assignment = _require_mapping(
                assignment,
                field_name=f"mixed_fidelity.per_root_assignments[{index}]",
            )
            coupling_asset = normalized_assignment.get("coupling_asset")
            if not isinstance(coupling_asset, Mapping):
                continue
            register_from_asset(
                _require_mapping(
                    coupling_asset,
                    field_name=(
                        f"mixed_fidelity.per_root_assignments[{index}].coupling_asset"
                    ),
                ),
                field_name=(
                    f"mixed_fidelity.per_root_assignments[{index}].coupling_asset"
                ),
            )
    return edge_paths


def _surface_subset_component_families(
    surface_runtime: SurfaceWaveMorphologyRuntime | None,
) -> list[dict[str, Any]]:
    if surface_runtime is None:
        return []
    grouped_component_ids: dict[tuple[int, int], list[str]] = {}
    for component in surface_runtime._resolved.coupling_plan.components:
        edge_key = (int(component.pre_root_id), int(component.post_root_id))
        grouped_component_ids.setdefault(edge_key, []).append(component.component_id)
    families: list[dict[str, Any]] = []
    for edge_key in sorted(grouped_component_ids):
        pre_root_id, post_root_id = edge_key
        route_id = _route_id_for_classes(SURFACE_NEURON_CLASS, SURFACE_NEURON_CLASS)
        families.append(
            {
                "component_family_id": (
                    f"{pre_root_id}__to__{post_root_id}__{route_id}"
                ),
                "pre_root_id": int(pre_root_id),
                "post_root_id": int(post_root_id),
                "source_morphology_class": SURFACE_NEURON_CLASS,
                "target_morphology_class": SURFACE_NEURON_CLASS,
                "route_id": route_id,
                "projection_route": _projection_route_for_classes(
                    SURFACE_NEURON_CLASS,
                    SURFACE_NEURON_CLASS,
                ),
                "source_projection_surface": _PROJECTION_SURFACE_BY_CLASS[
                    SURFACE_NEURON_CLASS
                ],
                "target_injection_surface": _PROJECTION_SURFACE_BY_CLASS[
                    SURFACE_NEURON_CLASS
                ],
                "source_anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "target_anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "source_anchor_type": ANCHOR_TYPE_SURFACE_PATCH,
                "target_anchor_type": ANCHOR_TYPE_SURFACE_PATCH,
                "source_anchor_resolution": ANCHOR_RESOLUTION_COARSE_PATCH,
                "target_anchor_resolution": ANCHOR_RESOLUTION_COARSE_PATCH,
                "topology_family": DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
                "kernel_family": SEPARABLE_RANK_ONE_CLOUD_KERNEL,
                "aggregation_rule": "sum_over_synapses_preserving_sign_and_delay_bins",
                "edge_bundle_path": None,
                "component_count": len(grouped_component_ids[edge_key]),
                "component_ids": sorted(grouped_component_ids[edge_key]),
                "blocked_synapse_count": 0,
                "blocked_reasons": [],
                "source_fallback_used": False,
                "target_fallback_used": False,
                "source_fallback_reasons": [],
                "target_fallback_reasons": [],
                "status": "ready",
            }
        )
    return families


def _component_fallback_metadata(
    *,
    bundle: Any,
    component_index: int,
    prefix: str,
) -> dict[str, Any]:
    if bundle.synapse_table.empty or bundle.component_synapse_table.empty:
        return {
            "fallback_used": False,
            "fallback_reasons": [],
        }
    component_rows = bundle.component_synapse_table.loc[
        bundle.component_synapse_table["component_index"] == int(component_index)
    ]
    if component_rows.empty:
        return {
            "fallback_used": False,
            "fallback_reasons": [],
        }
    component_synapse_ids = {
        str(value)
        for value in component_rows["synapse_row_id"].tolist()
    }
    synapse_rows = bundle.synapse_table.loc[
        bundle.synapse_table["synapse_row_id"].isin(component_synapse_ids)
    ]
    if synapse_rows.empty:
        return {
            "fallback_used": False,
            "fallback_reasons": [],
        }
    fallback_used_column = f"{prefix}fallback_used"
    fallback_reason_column = f"{prefix}fallback_reason"
    fallback_used = False
    if fallback_used_column in synapse_rows.columns:
        fallback_used = any(bool(value) for value in synapse_rows[fallback_used_column].tolist())
    fallback_reasons = []
    if fallback_reason_column in synapse_rows.columns:
        fallback_reasons = sorted(
            {
                str(value)
                for value in synapse_rows[fallback_reason_column].tolist()
                if str(value) and str(value) != "nan"
            }
        )
    return {
        "fallback_used": bool(fallback_used),
        "fallback_reasons": fallback_reasons,
    }


def _blocked_reason_catalog(bundle: Any) -> list[str]:
    if bundle.blocked_synapse_table.empty:
        return []
    reasons: set[str] = set()
    for column_name in ("pre_blocked_reason", "post_blocked_reason"):
        if column_name not in bundle.blocked_synapse_table.columns:
            continue
        reasons.update(
            str(value)
            for value in bundle.blocked_synapse_table[column_name].tolist()
            if str(value) and str(value) != "nan"
        )
    return sorted(reasons)


def _resolve_hybrid_component_cloud(
    *,
    bundle_path: Path,
    component_index: int,
    component_id: str,
    anchor_table: Any,
    cloud_table: Any,
    expected_root_id: int,
    morphology_class: str,
    surface_patch_permutation: np.ndarray | None,
    skeleton_runtime: _SingleRootSkeletonGraphRuntime | None,
    role: str,
) -> HybridCouplingCloud:
    component_rows = cloud_table.loc[
        cloud_table["component_index"] == int(component_index)
    ].sort_values(
        ["anchor_table_index"],
        kind="mergesort",
    )
    if component_rows.empty:
        raise ValueError(
            f"Hybrid coupling component {component_id!r} in {bundle_path} is missing "
            f"its {role} cloud definition."
        )
    anchor_rows = anchor_table.set_index("anchor_table_index", drop=False)
    local_weights: dict[tuple[int, int], float] = {}
    anchor_mode: str | None = None
    anchor_type: str | None = None
    anchor_resolution: str | None = None
    projection_surface: str | None = None
    for row in component_rows.itertuples(index=False):
        anchor_table_index = int(row.anchor_table_index)
        if anchor_table_index not in anchor_rows.index:
            raise ValueError(
                f"Hybrid coupling component {component_id!r} in {bundle_path} references "
                f"unknown {role} anchor_table_index {anchor_table_index}."
            )
        anchor = anchor_rows.loc[anchor_table_index]
        if int(anchor["root_id"]) != int(expected_root_id):
            raise ValueError(
                f"Hybrid coupling component {component_id!r} in {bundle_path} has a "
                f"{role} anchor on root {int(anchor['root_id'])}, expected {expected_root_id}."
            )
        current_anchor_mode = str(anchor["anchor_mode"])
        current_anchor_type = str(anchor["anchor_type"])
        current_anchor_resolution = str(anchor["anchor_resolution"])
        local_index, resolved_projection_surface = _resolve_runtime_anchor_index(
            component_id=component_id,
            bundle_path=bundle_path,
            expected_root_id=expected_root_id,
            morphology_class=morphology_class,
            anchor_mode=current_anchor_mode,
            anchor_type=current_anchor_type,
            anchor_resolution=current_anchor_resolution,
            anchor_index=int(anchor["anchor_index"]),
            surface_patch_permutation=surface_patch_permutation,
            skeleton_runtime=skeleton_runtime,
            role=role,
        )
        if anchor_mode is None:
            anchor_mode = current_anchor_mode
            anchor_type = current_anchor_type
            anchor_resolution = current_anchor_resolution
            projection_surface = resolved_projection_surface
        elif (
            anchor_mode != current_anchor_mode
            or anchor_type != current_anchor_type
            or anchor_resolution != current_anchor_resolution
            or projection_surface != resolved_projection_surface
        ):
            raise ValueError(
                f"Hybrid coupling component {component_id!r} in {bundle_path} mixes "
                f"incompatible {role} anchor representations, which is ambiguous."
            )
        key = (local_index, int(anchor["anchor_index"]))
        local_weights[key] = local_weights.get(key, 0.0) + float(row.cloud_weight)
    ordered_pairs = sorted(local_weights)
    return HybridCouplingCloud(
        local_indices=np.asarray(
            [local_index for local_index, _anchor_index in ordered_pairs],
            dtype=np.int64,
        ),
        weights=np.asarray(
            [local_weights[pair] for pair in ordered_pairs],
            dtype=np.float64,
        ),
        anchor_indices=np.asarray(
            [_anchor_index for _local_index, _anchor_index in ordered_pairs],
            dtype=np.int64,
        ),
        anchor_mode=str(anchor_mode),
        anchor_type=str(anchor_type),
        anchor_resolution=str(anchor_resolution),
        projection_surface=str(projection_surface),
    )


def _resolve_runtime_anchor_index(
    *,
    component_id: str,
    bundle_path: Path,
    expected_root_id: int,
    morphology_class: str,
    anchor_mode: str,
    anchor_type: str,
    anchor_resolution: str,
    anchor_index: int,
    surface_patch_permutation: np.ndarray | None,
    skeleton_runtime: _SingleRootSkeletonGraphRuntime | None,
    role: str,
) -> tuple[int, str]:
    expected_anchor_mode = _ANCHOR_MODE_BY_CLASS[str(morphology_class)]
    expected_anchor_type = _ANCHOR_TYPE_BY_CLASS[str(morphology_class)]
    expected_anchor_resolution = _ANCHOR_RESOLUTION_BY_CLASS[str(morphology_class)]
    if anchor_mode != expected_anchor_mode:
        raise ValueError(
            f"Hybrid coupling component {component_id!r} in {bundle_path} requires "
            f"{role} anchor_mode {expected_anchor_mode!r} for root {expected_root_id} "
            f"({morphology_class}), got {anchor_mode!r}."
        )
    if anchor_type != expected_anchor_type:
        raise ValueError(
            f"Hybrid coupling component {component_id!r} in {bundle_path} requires "
            f"{role} anchor_type {expected_anchor_type!r} for root {expected_root_id} "
            f"({morphology_class}), got {anchor_type!r}."
        )
    if anchor_resolution != expected_anchor_resolution:
        raise ValueError(
            f"Hybrid coupling component {component_id!r} in {bundle_path} requires "
            f"{role} anchor_resolution {expected_anchor_resolution!r} for root "
            f"{expected_root_id} ({morphology_class}), got {anchor_resolution!r}."
        )
    if morphology_class == SURFACE_NEURON_CLASS:
        local_index = int(anchor_index)
        if local_index < 0:
            raise ValueError(
                f"Hybrid coupling component {component_id!r} in {bundle_path} has an "
                f"invalid {role} surface patch index {anchor_index}."
            )
        if surface_patch_permutation is not None:
            if local_index >= int(surface_patch_permutation.shape[0]):
                raise ValueError(
                    f"Hybrid coupling component {component_id!r} in {bundle_path} has an "
                    f"out-of-range {role} surface patch index {anchor_index}."
                )
            local_index = int(surface_patch_permutation[local_index])
        return local_index, _PROJECTION_SURFACE_BY_CLASS[SURFACE_NEURON_CLASS]
    if morphology_class == SKELETON_NEURON_CLASS:
        if skeleton_runtime is None:
            raise ValueError(
                f"Hybrid coupling component {component_id!r} in {bundle_path} requires "
                f"a skeleton runtime for root {expected_root_id}."
            )
        node_index_by_node_id = skeleton_runtime.node_index_by_node_id
        if int(anchor_index) not in node_index_by_node_id:
            raise ValueError(
                f"Hybrid coupling component {component_id!r} in {bundle_path} references "
                f"unknown skeleton node_id {anchor_index} on root {expected_root_id}."
            )
        return (
            int(node_index_by_node_id[int(anchor_index)]),
            _PROJECTION_SURFACE_BY_CLASS[SKELETON_NEURON_CLASS],
        )
    if int(anchor_index) != 0:
        raise ValueError(
            f"Hybrid coupling component {component_id!r} in {bundle_path} requires the "
            f"point-state anchor_index 0 for root {expected_root_id}, got {anchor_index}."
        )
    return 0, _PROJECTION_SURFACE_BY_CLASS[POINT_NEURON_CLASS]


def _resolve_shared_delay_steps(
    *,
    delay_ms: float,
    dt_ms: float,
    component_id: str,
) -> int:
    if not np.isfinite(delay_ms) or delay_ms < 0.0:
        raise ValueError(
            f"Hybrid coupling component {component_id!r} has unusable delay_ms {delay_ms!r}."
        )
    delay_steps_float = float(delay_ms) / float(dt_ms)
    delay_steps = int(round(delay_steps_float))
    if abs(delay_steps_float - delay_steps) > _DELAY_STEP_TOLERANCE:
        raise ValueError(
            f"Hybrid coupling component {component_id!r} delay_ms={delay_ms} cannot "
            f"be represented on the mixed shared timestep {dt_ms} ms."
        )
    return delay_steps


def _route_id_for_classes(source_class: str, target_class: str) -> str:
    return f"{source_class}_to_{target_class}"


def _projection_route_for_classes(source_class: str, target_class: str) -> str:
    return (
        f"{_PROJECTION_LABEL_BY_CLASS[str(source_class)]}_projection_to_"
        f"{_PROJECTION_LABEL_BY_CLASS[str(target_class)]}_injection"
    )


def _resolve_hybrid_coupling_drives(
    *,
    hybrid_coupling_plan: Mapping[str, Any],
    root_ids: Sequence[int],
    root_class_by_root: Mapping[int, str],
    surface_runtime: SurfaceWaveMorphologyRuntime | None,
    skeleton_runtime_by_root: Mapping[int, _SingleRootSkeletonGraphRuntime],
    point_runtime_by_root: Mapping[int, _SingleRootPointNeuronRuntime],
    shared_step_index: int,
    timebase: SimulationTimebase,
) -> tuple[dict[int, np.ndarray], list[dict[str, Any]]]:
    routed_drives_by_root = _empty_local_drives_by_root(
        root_ids=root_ids,
        root_class_by_root=root_class_by_root,
        surface_runtime=surface_runtime,
        skeleton_runtime_by_root=skeleton_runtime_by_root,
    )
    projection_history_by_root = _shared_projection_history_by_root(
        root_ids=root_ids,
        root_class_by_root=root_class_by_root,
        surface_runtime=surface_runtime,
        skeleton_runtime_by_root=skeleton_runtime_by_root,
        point_runtime_by_root=point_runtime_by_root,
    )
    coupling_events: list[dict[str, Any]] = []
    for component in hybrid_coupling_plan["components"]:
        assert isinstance(component, HybridCouplingComponent)
        source_step_index = int(shared_step_index) - int(component.delay_steps)
        if source_step_index < 0:
            continue
        source_history = np.asarray(
            projection_history_by_root[int(component.pre_root_id)],
            dtype=np.float64,
        )
        if source_step_index >= int(source_history.shape[0]):
            raise ValueError(
                "Hybrid morphology routing source history is shorter than expected "
                f"for component {component.component_id!r}."
            )
        source_projection = np.asarray(
            source_history[source_step_index],
            dtype=np.float64,
        )
        sampled_values = source_projection[component.source_cloud.local_indices]
        source_value = float(
            np.dot(
                sampled_values,
                component.source_cloud.weights,
            )
        )
        signed_source_value = float(source_value * component.signed_weight_total)
        target_projection_drive = (
            signed_source_value * component.target_cloud.weights
        )
        np.add.at(
            routed_drives_by_root[int(component.post_root_id)],
            component.target_cloud.local_indices,
            target_projection_drive,
        )
        coupling_events.append(
            {
                "target_shared_step_index": int(shared_step_index),
                "resulting_shared_step_index": int(shared_step_index + 1),
                "applied_time_ms": float(timebase.time_ms_after_steps(shared_step_index)),
                "source_step_index": int(source_step_index),
                "source_time_ms": float(timebase.time_ms_after_steps(source_step_index)),
                "component_id": component.component_id,
                "component_family_id": component.component_family_id,
                "pre_root_id": int(component.pre_root_id),
                "post_root_id": int(component.post_root_id),
                "source_morphology_class": component.source_morphology_class,
                "target_morphology_class": component.target_morphology_class,
                "route_id": component.route_id,
                "projection_route": component.projection_route,
                "source_projection_surface": component.source_projection_surface,
                "target_injection_surface": component.target_injection_surface,
                "topology_family": component.topology_family,
                "kernel_family": component.kernel_family,
                "aggregation_rule": component.aggregation_rule,
                "delay_ms": float(component.delay_ms),
                "delay_steps": int(component.delay_steps),
                "sign_label": component.sign_label,
                "signed_weight_total": float(component.signed_weight_total),
                "synapse_count": int(component.synapse_count),
                "source_anchor_mode": component.source_anchor_mode,
                "target_anchor_mode": component.target_anchor_mode,
                "source_anchor_type": component.source_anchor_type,
                "target_anchor_type": component.target_anchor_type,
                "source_anchor_resolution": component.source_anchor_resolution,
                "target_anchor_resolution": component.target_anchor_resolution,
                "source_cloud_normalization": component.source_cloud_normalization,
                "target_cloud_normalization": component.target_cloud_normalization,
                "source_local_indices": component.source_cloud.local_indices.tolist(),
                "source_anchor_indices": component.source_cloud.anchor_indices.tolist(),
                "source_cloud_weights": component.source_cloud.weights.tolist(),
                "source_projection_values": sampled_values.tolist(),
                "source_value": float(source_value),
                "signed_source_value": float(signed_source_value),
                "target_local_indices": component.target_cloud.local_indices.tolist(),
                "target_anchor_indices": component.target_cloud.anchor_indices.tolist(),
                "target_cloud_weights": component.target_cloud.weights.tolist(),
                "target_projection_drive": np.asarray(
                    target_projection_drive,
                    dtype=np.float64,
                ).tolist(),
                "source_fallback_used": bool(component.source_fallback_used),
                "target_fallback_used": bool(component.target_fallback_used),
                "source_fallback_reasons": list(component.source_fallback_reasons),
                "target_fallback_reasons": list(component.target_fallback_reasons),
                "blocked_reasons": [],
                "edge_bundle_path": component.edge_bundle_path,
            }
        )
    return routed_drives_by_root, coupling_events


def _empty_local_drives_by_root(
    *,
    root_ids: Sequence[int],
    root_class_by_root: Mapping[int, str],
    surface_runtime: SurfaceWaveMorphologyRuntime | None,
    skeleton_runtime_by_root: Mapping[int, _SingleRootSkeletonGraphRuntime],
) -> dict[int, np.ndarray]:
    routed_drives_by_root: dict[int, np.ndarray] = {}
    surface_patch_count_by_root: dict[int, int] = {}
    if surface_runtime is not None:
        surface_patch_count_by_root = {
            int(root_id): int(history.shape[1])
            for root_id, history in surface_runtime.shared_projection_history_by_root().items()
        }
    for root_id in root_ids:
        morphology_class = str(root_class_by_root[int(root_id)])
        if morphology_class == SURFACE_NEURON_CLASS:
            patch_count = surface_patch_count_by_root.get(int(root_id))
            if patch_count is None:
                raise ValueError(
                    f"Hybrid morphology routing is missing the surface patch count for root {root_id}."
                )
            routed_drives_by_root[int(root_id)] = np.zeros(
                patch_count,
                dtype=np.float64,
            )
        elif morphology_class == SKELETON_NEURON_CLASS:
            routed_drives_by_root[int(root_id)] = np.zeros(
                skeleton_runtime_by_root[int(root_id)].asset.node_count,
                dtype=np.float64,
            )
        else:
            routed_drives_by_root[int(root_id)] = np.zeros(1, dtype=np.float64)
    return routed_drives_by_root


def _shared_projection_history_by_root(
    *,
    root_ids: Sequence[int],
    root_class_by_root: Mapping[int, str],
    surface_runtime: SurfaceWaveMorphologyRuntime | None,
    skeleton_runtime_by_root: Mapping[int, _SingleRootSkeletonGraphRuntime],
    point_runtime_by_root: Mapping[int, _SingleRootPointNeuronRuntime],
) -> dict[int, np.ndarray]:
    history_by_root: dict[int, np.ndarray] = {}
    surface_history_by_root = (
        {}
        if surface_runtime is None
        else surface_runtime.shared_projection_history_by_root()
    )
    for root_id in root_ids:
        morphology_class = str(root_class_by_root[int(root_id)])
        if morphology_class == SURFACE_NEURON_CLASS:
            history_by_root[int(root_id)] = np.asarray(
                surface_history_by_root[int(root_id)],
                dtype=np.float64,
            )
        elif morphology_class == SKELETON_NEURON_CLASS:
            history_by_root[int(root_id)] = np.asarray(
                skeleton_runtime_by_root[int(root_id)].projection_history,
                dtype=np.float64,
            )
        else:
            history_by_root[int(root_id)] = np.asarray(
                point_runtime_by_root[int(root_id)].projection_history,
                dtype=np.float64,
            )
    return history_by_root


def _augment_surface_coupling_events(
    *,
    surface_result: SurfaceWaveMorphologyRuntimeResult | None,
) -> list[dict[str, Any]]:
    if surface_result is None:
        return []
    component_by_id = {
        str(component["component_id"]): copy.deepcopy(dict(component))
        for component in _require_sequence(
            surface_result.surface_result.coupling_plan.get("components", ()),
            field_name="surface_result.coupling_plan.components",
        )
    }
    route_id = _route_id_for_classes(SURFACE_NEURON_CLASS, SURFACE_NEURON_CLASS)
    projection_route = _projection_route_for_classes(
        SURFACE_NEURON_CLASS,
        SURFACE_NEURON_CLASS,
    )
    events: list[dict[str, Any]] = []
    for event in surface_result.coupling_application_history:
        mapping = copy.deepcopy(dict(_require_mapping(
            event,
            field_name="surface_result.coupling_application_history",
        )))
        component = component_by_id.get(str(mapping.get("component_id", "")), {})
        mapping.update(
            {
                "component_family_id": (
                    f"{int(mapping['pre_root_id'])}__to__{int(mapping['post_root_id'])}"
                    f"__{route_id}"
                ),
                "source_morphology_class": SURFACE_NEURON_CLASS,
                "target_morphology_class": SURFACE_NEURON_CLASS,
                "route_id": route_id,
                "projection_route": projection_route,
                "source_projection_surface": _PROJECTION_SURFACE_BY_CLASS[
                    SURFACE_NEURON_CLASS
                ],
                "target_injection_surface": _PROJECTION_SURFACE_BY_CLASS[
                    SURFACE_NEURON_CLASS
                ],
                "topology_family": component.get(
                    "topology_family",
                    DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
                ),
                "source_anchor_type": ANCHOR_TYPE_SURFACE_PATCH,
                "target_anchor_type": ANCHOR_TYPE_SURFACE_PATCH,
                "source_anchor_resolution": ANCHOR_RESOLUTION_COARSE_PATCH,
                "target_anchor_resolution": ANCHOR_RESOLUTION_COARSE_PATCH,
                "source_local_indices": mapping.get("source_patch_indices", []),
                "target_local_indices": mapping.get("target_patch_indices", []),
                "source_anchor_indices": mapping.get("source_patch_indices", []),
                "target_anchor_indices": mapping.get("target_patch_indices", []),
                "source_projection_values": mapping.get("source_patch_values", []),
                "target_projection_drive": mapping.get("target_patch_drive", []),
                "source_fallback_used": False,
                "target_fallback_used": False,
                "source_fallback_reasons": [],
                "target_fallback_reasons": [],
                "blocked_reasons": [],
                "edge_bundle_path": None,
            }
        )
        events.append(mapping)
    return events


def _build_surface_skeleton_runtime_descriptor(
    *,
    arm_plan: Mapping[str, Any],
    hybrid_morphology: Mapping[str, Any],
    surface_wave_model: Mapping[str, Any],
    surface_runtime: SurfaceWaveMorphologyRuntime | None,
    skeleton_runtime_by_root: Mapping[int, _SingleRootSkeletonGraphRuntime],
    point_runtime_by_root: Mapping[int, _SingleRootPointNeuronRuntime],
    timebase: SimulationTimebase,
    hybrid_coupling_plan: Mapping[str, Any],
) -> MorphologyRuntimeDescriptor:
    surface_root_ids = set() if surface_runtime is None else set(surface_runtime.root_ids)
    per_root_integration_timestep_ms = {
        str(int(item["root_id"])): (
            float(surface_runtime.descriptor.solver_metadata["integration_timestep_ms"])
            if int(item["root_id"]) in surface_root_ids
            else (
                float(
                    skeleton_runtime_by_root[int(item["root_id"])].integration_timestep_ms
                )
                if int(item["root_id"]) in skeleton_runtime_by_root
                else float(
                    point_runtime_by_root[int(item["root_id"])].integration_timestep_ms
                )
            )
        )
        for item in hybrid_morphology["per_root_class_metadata"]
    }
    per_root_internal_substep_count = {
        str(int(item["root_id"])): (
            int(surface_runtime.descriptor.solver_metadata["internal_substep_count"])
            if int(item["root_id"]) in surface_root_ids
            else (
                int(
                    skeleton_runtime_by_root[int(item["root_id"])].internal_substep_count
                )
                if int(item["root_id"]) in skeleton_runtime_by_root
                else int(
                    point_runtime_by_root[int(item["root_id"])].runtime_metadata()[
                        "internal_substep_count"
                    ]
                )
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
    component_count = int(hybrid_coupling_plan["component_count"])
    max_delay_steps = int(hybrid_coupling_plan["max_delay_steps"])
    topology_condition = "intact"
    if surface_runtime is not None:
        topology_condition = str(surface_runtime.descriptor.coupling_metadata["topology_condition"])
    runtime_family = (
        SURFACE_WAVE_MIXED_MORPHOLOGY_RUNTIME_FAMILY
        if point_runtime_by_root
        else SURFACE_WAVE_SKELETON_MORPHOLOGY_RUNTIME_FAMILY
    )
    return MorphologyRuntimeDescriptor(
        interface_version=MORPHOLOGY_CLASS_RUNTIME_INTERFACE_VERSION,
        model_mode=SURFACE_WAVE_MODEL_MODE,
        runtime_family=runtime_family,
        hybrid_morphology=copy.deepcopy(hybrid_morphology),
        source_injection={
            "injection_strategy": "per_root_scalar_shared_drive",
            "source_value_layout": "per_root_scalar_shared_drive",
            "surface_injection_strategy": SURFACE_WAVE_RUNTIME_SOURCE_INJECTION_STRATEGY,
            "skeleton_injection_strategy": SKELETON_GRAPH_RUNTIME_SOURCE_INJECTION_STRATEGY,
            "point_injection_strategy": POINT_NEURON_RUNTIME_SOURCE_INJECTION_STRATEGY,
        },
        state_export={
            "state_field_layout": "mixed_state_mapping_by_root",
            "root_state_spaces": {
                SURFACE_NEURON_CLASS: "surface_vertices",
                SKELETON_NEURON_CLASS: "skeleton_nodes",
                POINT_NEURON_CLASS: "root_state_scalar",
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
            "surface_subset_component_count": int(
                hybrid_coupling_plan["surface_subset_component_count"]
            ),
            "mixed_route_component_count": int(
                hybrid_coupling_plan["mixed_route_component_count"]
            ),
            "component_family_count": int(hybrid_coupling_plan["component_family_count"]),
            "routing_timebase_ms": float(timebase.dt_ms),
            "routing_timebase_mode": "shared_output_timebase_for_non_surface_routes",
            "routing_hash": str(hybrid_coupling_plan["routing_hash"]),
            "component_families": copy.deepcopy(
                hybrid_coupling_plan["component_families"]
            ),
            "cross_class_routing_supported": True,
            "non_surface_selected_edge_execution": str(
                hybrid_coupling_plan["non_surface_selected_edge_execution"]
            ),
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
    point_runtime_by_root: Mapping[int, _SingleRootPointNeuronRuntime],
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

    for root_id in root_ids:
        if root_class_by_root[int(root_id)] != POINT_NEURON_CLASS:
            continue
        fragment = point_runtime_by_root[int(root_id)].summary_fragment()
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
    point_runtime_by_root: Mapping[int, _SingleRootPointNeuronRuntime],
    shared_step_count: int,
) -> dict[int, np.ndarray]:
    projection_history_by_root: dict[int, np.ndarray] = {}
    for root_id in root_ids:
        morphology_class = root_class_by_root[int(root_id)]
        if morphology_class == SURFACE_NEURON_CLASS:
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
        if morphology_class == SKELETON_NEURON_CLASS:
            projection_history_by_root[int(root_id)] = np.asarray(
                skeleton_runtime_by_root[int(root_id)].projection_history,
                dtype=np.float64,
            )
            continue
        projection_history_by_root[int(root_id)] = np.asarray(
            point_runtime_by_root[int(root_id)].projection_history,
            dtype=np.float64,
        )
    return projection_history_by_root


def _build_runtime_metadata_by_root(
    *,
    root_ids: Sequence[int],
    root_class_by_root: Mapping[int, str],
    surface_result: MorphologyRuntimeExecutionResult | None,
    skeleton_runtime_by_root: Mapping[int, _SingleRootSkeletonGraphRuntime],
    point_runtime_by_root: Mapping[int, _SingleRootPointNeuronRuntime],
) -> tuple[dict[str, Any], ...]:
    surface_metadata_by_root = {}
    if surface_result is not None:
        surface_metadata_by_root = {
            int(item["root_id"]): copy.deepcopy(dict(item))
            for item in surface_result.runtime_metadata_by_root
        }
    rows: list[dict[str, Any]] = []
    for root_id in root_ids:
        morphology_class = root_class_by_root[int(root_id)]
        if morphology_class == SURFACE_NEURON_CLASS:
            rows.append(copy.deepcopy(surface_metadata_by_root[int(root_id)]))
        elif morphology_class == SKELETON_NEURON_CLASS:
            rows.append(skeleton_runtime_by_root[int(root_id)].runtime_metadata())
        else:
            rows.append(point_runtime_by_root[int(root_id)].runtime_metadata())
    return tuple(rows)


def _build_state_exports_by_root(
    *,
    root_ids: Sequence[int],
    root_class_by_root: Mapping[int, str],
    surface_result: MorphologyRuntimeExecutionResult | None,
    skeleton_runtime_by_root: Mapping[int, _SingleRootSkeletonGraphRuntime],
    point_runtime_by_root: Mapping[int, _SingleRootPointNeuronRuntime],
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
        morphology_class = root_class_by_root[int(root_id)]
        if morphology_class == SURFACE_NEURON_CLASS:
            exports[int(root_id)] = copy.deepcopy(dict(surface_states_by_root[int(root_id)]))
        elif morphology_class == SKELETON_NEURON_CLASS and stage == "initial":
            exports[int(root_id)] = skeleton_runtime_by_root[int(root_id)].initial_state_mapping
        elif morphology_class == SKELETON_NEURON_CLASS:
            exports[int(root_id)] = skeleton_runtime_by_root[int(root_id)].export_state_mapping()
        elif stage == "initial":
            exports[int(root_id)] = point_runtime_by_root[int(root_id)].initial_state_mapping
        else:
            exports[int(root_id)] = point_runtime_by_root[int(root_id)].export_state_mapping()
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
    elif classes_present == {POINT_NEURON_CLASS}:
        circuit_activation_state_id = "circuit_point_activation_state"
        circuit_velocity_state_id = "circuit_point_velocity_state"
        circuit_projection_state_id = "circuit_point_projection_state"
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

        morphology_class = root_class_by_root[int(root_id)]
        if morphology_class == SURFACE_NEURON_CLASS:
            activation_state_id = f"root_{int(root_id)}_surface_activation_state"
            velocity_state_id = f"root_{int(root_id)}_surface_velocity_state"
            projection_state_id = f"root_{int(root_id)}_patch_activation_state"
        elif morphology_class == SKELETON_NEURON_CLASS:
            activation_state_id = f"root_{int(root_id)}_skeleton_activation_state"
            velocity_state_id = f"root_{int(root_id)}_skeleton_velocity_state"
            projection_state_id = f"root_{int(root_id)}_skeleton_projection_state"
        else:
            activation_state_id = f"root_{int(root_id)}_point_activation_state"
            velocity_state_id = f"root_{int(root_id)}_point_velocity_state"
            projection_state_id = f"root_{int(root_id)}_point_projection_state"

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


def _freeze_float_array(
    value: Sequence[float] | np.ndarray,
    *,
    field_name: str,
    ndim: int,
    expected_length: int | None = None,
) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != ndim:
        raise ValueError(f"{field_name} must be a {ndim}D float array.")
    if expected_length is not None and int(array.shape[0]) != int(expected_length):
        raise ValueError(
            f"{field_name} must have leading length {expected_length}, got {array.shape[0]}."
        )
    frozen = np.asarray(array, dtype=np.float64).copy()
    frozen.setflags(write=False)
    return frozen


def _freeze_int_array(
    value: Sequence[int] | np.ndarray,
    *,
    field_name: str,
    ndim: int,
) -> np.ndarray:
    array = np.asarray(value, dtype=np.int64)
    if array.ndim != ndim:
        raise ValueError(f"{field_name} must be a {ndim}D integer array.")
    frozen = np.asarray(array, dtype=np.int64).copy()
    frozen.setflags(write=False)
    return frozen


def _stable_hash(payload: Mapping[str, Any] | Sequence[Any]) -> str:
    normalized_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized_json.encode("utf-8")).hexdigest()


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
