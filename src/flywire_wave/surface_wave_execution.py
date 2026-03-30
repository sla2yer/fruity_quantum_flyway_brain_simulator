from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .coupling_contract import (
    DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
    SEPARABLE_RANK_ONE_CLOUD_KERNEL,
    SURFACE_PATCH_CLOUD_MODE,
)
from .experiment_ablation_transforms import (
    apply_experiment_ablation_coupling_perturbation,
    resolve_experiment_ablation_patch_permutations,
)
from .hybrid_morphology_contract import (
    build_hybrid_morphology_plan_metadata,
    parse_hybrid_morphology_plan_metadata,
)
from .simulator_runtime import (
    SimulationDeterminismContext,
    SimulationTimebase,
)
from .surface_wave_contract import parse_surface_wave_model_metadata
from .surface_wave_solver import (
    SingleNeuronSurfaceWaveSolver,
    SurfaceWaveOperatorBundle,
    SurfaceWaveState,
)
from .synapse_mapping import (
    ANCHOR_RESOLUTION_COARSE_PATCH,
    ANCHOR_TYPE_SURFACE_PATCH,
    load_edge_coupling_bundle,
)


SURFACE_WAVE_EXECUTION_VERSION = "surface_wave_execution.v1"

INTACT_TOPOLOGY_CONDITION = "intact"
SHUFFLED_TOPOLOGY_CONDITION = "shuffled"
SUPPORTED_TOPOLOGY_CONDITIONS = (
    INTACT_TOPOLOGY_CONDITION,
    SHUFFLED_TOPOLOGY_CONDITION,
)

POSTSYNAPTIC_PATCH_PERMUTATION_SHUFFLE = "postsynaptic_patch_permutation"

INITIALIZED_STAGE = "initialized"
STEP_COMPLETED_STAGE = "step_completed"
FINALIZED_STAGE = "finalized"

_DELAY_STEP_TOLERANCE = 1.0e-6
_ZERO_TOLERANCE = 1.0e-15


@dataclass(frozen=True)
class SurfaceWavePatchCloud:
    patch_indices: np.ndarray
    weights: np.ndarray

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "patch_indices",
            _freeze_int_array(
                self.patch_indices,
                field_name="surface_wave_patch_cloud.patch_indices",
                ndim=1,
            ),
        )
        object.__setattr__(
            self,
            "weights",
            _freeze_float_array(
                self.weights,
                field_name="surface_wave_patch_cloud.weights",
                ndim=1,
            ),
        )
        if self.patch_indices.shape != self.weights.shape:
            raise ValueError(
                "surface_wave_patch_cloud.patch_indices and weights must share the same shape."
            )
        if self.patch_indices.size < 1:
            raise ValueError("surface_wave_patch_cloud must contain at least one patch.")

    def as_mapping(self) -> dict[str, Any]:
        return {
            "patch_indices": self.patch_indices.tolist(),
            "weights": np.asarray(self.weights, dtype=np.float64).tolist(),
        }


@dataclass(frozen=True)
class SurfaceWaveCouplingComponent:
    component_id: str
    pre_root_id: int
    post_root_id: int
    delay_ms: float
    delay_steps: int
    sign_label: str
    signed_weight_total: float
    kernel_family: str
    aggregation_rule: str
    source_anchor_mode: str
    target_anchor_mode: str
    source_cloud_normalization: str
    target_cloud_normalization: str
    synapse_count: int
    source_cloud: SurfaceWavePatchCloud
    target_cloud: SurfaceWavePatchCloud

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("surface-wave coupling components require a non-empty component_id.")
        if self.delay_steps < 0:
            raise ValueError(
                f"surface-wave coupling component {self.component_id!r} delay_steps must be non-negative."
            )
        if not np.isfinite(self.delay_ms) or self.delay_ms < 0.0:
            raise ValueError(
                f"surface-wave coupling component {self.component_id!r} has unusable delay_ms {self.delay_ms!r}."
            )
        if not np.isfinite(self.signed_weight_total):
            raise ValueError(
                f"surface-wave coupling component {self.component_id!r} has a non-finite signed_weight_total."
            )

    def as_mapping(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "pre_root_id": int(self.pre_root_id),
            "post_root_id": int(self.post_root_id),
            "delay_ms": float(self.delay_ms),
            "delay_steps": int(self.delay_steps),
            "sign_label": self.sign_label,
            "signed_weight_total": float(self.signed_weight_total),
            "kernel_family": self.kernel_family,
            "aggregation_rule": self.aggregation_rule,
            "source_anchor_mode": self.source_anchor_mode,
            "target_anchor_mode": self.target_anchor_mode,
            "source_cloud_normalization": self.source_cloud_normalization,
            "target_cloud_normalization": self.target_cloud_normalization,
            "synapse_count": int(self.synapse_count),
            "source_cloud": self.source_cloud.as_mapping(),
            "target_cloud": self.target_cloud.as_mapping(),
        }


@dataclass(frozen=True)
class SurfaceWaveCouplingPlan:
    root_ids: tuple[int, ...]
    topology_condition: str
    shuffle_scope: str | None
    components: tuple[SurfaceWaveCouplingComponent, ...]
    coupling_hash: str
    target_patch_permutations: dict[int, tuple[int, ...]]

    def __post_init__(self) -> None:
        if self.topology_condition not in SUPPORTED_TOPOLOGY_CONDITIONS:
            raise ValueError(
                "Unsupported topology_condition "
                f"{self.topology_condition!r}. Supported conditions: {list(SUPPORTED_TOPOLOGY_CONDITIONS)!r}."
            )

    @property
    def component_count(self) -> int:
        return len(self.components)

    @property
    def max_delay_steps(self) -> int:
        if not self.components:
            return 0
        return max(int(component.delay_steps) for component in self.components)

    def as_mapping(self) -> dict[str, Any]:
        return {
            "root_ids": [int(root_id) for root_id in self.root_ids],
            "topology_condition": self.topology_condition,
            "shuffle_scope": self.shuffle_scope,
            "component_count": self.component_count,
            "max_delay_steps": self.max_delay_steps,
            "coupling_hash": self.coupling_hash,
            "target_patch_permutations": {
                str(root_id): [int(value) for value in permutation]
                for root_id, permutation in sorted(self.target_patch_permutations.items())
            },
            "components": [
                component.as_mapping()
                for component in self.components
            ],
        }


@dataclass(frozen=True)
class ResolvedSurfaceWaveExecutionPlan:
    root_ids: tuple[int, ...]
    timebase: SimulationTimebase
    determinism: SimulationDeterminismContext
    surface_wave_model: dict[str, Any]
    surface_wave_execution_plan: dict[str, Any]
    operator_assets: tuple[dict[str, Any], ...]
    coupling_assets: tuple[dict[str, Any], ...]
    operator_bundles: tuple[SurfaceWaveOperatorBundle, ...]
    coupling_plan: SurfaceWaveCouplingPlan
    execution_version: str = SURFACE_WAVE_EXECUTION_VERSION
    arm_plan: dict[str, Any] | None = None

    @property
    def integration_timestep_ms(self) -> float:
        return float(self.surface_wave_execution_plan["solver"]["integration_timestep_ms"])

    @property
    def shared_output_timestep_ms(self) -> float:
        return float(self.surface_wave_execution_plan["solver"]["shared_output_timestep_ms"])

    @property
    def internal_substep_count(self) -> int:
        return int(self.surface_wave_execution_plan["solver"]["internal_substep_count"])

    def build_circuit(self) -> CoupledSurfaceWaveCircuit:
        return CoupledSurfaceWaveCircuit(self)

    def run_to_completion(
        self,
        *,
        shared_step_count: int | None = None,
        initial_states_by_root: Mapping[int, SurfaceWaveState] | None = None,
    ) -> CoupledSurfaceWaveRunResult:
        circuit = self.build_circuit()
        if initial_states_by_root is None:
            circuit.initialize_zero()
        else:
            circuit.initialize_states(initial_states_by_root)
        return circuit.run_to_completion(shared_step_count=shared_step_count)

    def as_mapping(self) -> dict[str, Any]:
        payload = {
            "execution_version": self.execution_version,
            "root_ids": [int(root_id) for root_id in self.root_ids],
            "timebase": self.timebase.as_mapping(),
            "determinism": self.determinism.as_mapping(),
            "surface_wave_model": copy.deepcopy(self.surface_wave_model),
            "surface_wave_execution_plan": copy.deepcopy(self.surface_wave_execution_plan),
            "operator_assets": [copy.deepcopy(item) for item in self.operator_assets],
            "coupling_assets": [copy.deepcopy(item) for item in self.coupling_assets],
            "coupling_plan": self.coupling_plan.as_mapping(),
        }
        if self.arm_plan is not None:
            payload["arm_plan"] = copy.deepcopy(self.arm_plan)
        return payload


@dataclass(frozen=True)
class CoupledSurfaceWaveRunResult:
    execution_version: str
    root_ids: tuple[int, ...]
    timebase: dict[str, Any]
    determinism: dict[str, Any]
    surface_wave_model: dict[str, Any]
    coupling_plan: dict[str, Any]
    runtime_metadata_by_root: tuple[dict[str, Any], ...]
    initial_states_by_root: dict[int, dict[str, Any]]
    final_states_by_root: dict[int, dict[str, Any]]
    patch_readout_history_by_root: dict[int, np.ndarray]
    shared_readout_history: tuple[dict[str, Any], ...]
    coupling_application_history: tuple[dict[str, Any], ...]
    substep_count: int
    shared_step_count: int

    def as_mapping(self) -> dict[str, Any]:
        return {
            "execution_version": self.execution_version,
            "root_ids": [int(root_id) for root_id in self.root_ids],
            "timebase": copy.deepcopy(self.timebase),
            "determinism": copy.deepcopy(self.determinism),
            "surface_wave_model": copy.deepcopy(self.surface_wave_model),
            "coupling_plan": copy.deepcopy(self.coupling_plan),
            "runtime_metadata_by_root": [copy.deepcopy(item) for item in self.runtime_metadata_by_root],
            "initial_states_by_root": {
                str(root_id): copy.deepcopy(state_mapping)
                for root_id, state_mapping in sorted(self.initial_states_by_root.items())
            },
            "final_states_by_root": {
                str(root_id): copy.deepcopy(state_mapping)
                for root_id, state_mapping in sorted(self.final_states_by_root.items())
            },
            "patch_readout_history_by_root": {
                str(root_id): np.asarray(history, dtype=np.float64).tolist()
                for root_id, history in sorted(self.patch_readout_history_by_root.items())
            },
            "shared_readout_history": [copy.deepcopy(item) for item in self.shared_readout_history],
            "coupling_application_history": [
                copy.deepcopy(item) for item in self.coupling_application_history
            ],
            "substep_count": int(self.substep_count),
            "shared_step_count": int(self.shared_step_count),
        }


class CoupledSurfaceWaveCircuit:
    def __init__(self, plan: ResolvedSurfaceWaveExecutionPlan) -> None:
        self._plan = plan
        self._solver_by_root = {
            bundle.root_id: SingleNeuronSurfaceWaveSolver(
                operator_bundle=bundle,
                surface_wave_model=plan.surface_wave_model,
                integration_timestep_ms=plan.integration_timestep_ms,
                shared_output_timestep_ms=plan.shared_output_timestep_ms,
            )
            for bundle in plan.operator_bundles
        }
        self._patch_count_by_root = {
            root_id: self._require_patch_count(self._solver_by_root[root_id], root_id=root_id)
            for root_id in plan.root_ids
        }
        self._substep_index = 0
        self._shared_step_count = 0
        self._patch_readout_history_by_root: dict[int, list[np.ndarray]] = {
            root_id: []
            for root_id in plan.root_ids
        }
        self._shared_readout_history: list[dict[str, Any]] = []
        self._coupling_application_history: list[dict[str, Any]] = []
        self._initial_states_by_root: dict[int, dict[str, Any]] | None = None
        self._final_result: CoupledSurfaceWaveRunResult | None = None

    @property
    def plan(self) -> ResolvedSurfaceWaveExecutionPlan:
        return self._plan

    @property
    def root_ids(self) -> tuple[int, ...]:
        return self._plan.root_ids

    @property
    def current_time_ms(self) -> float:
        first_solver = self._solver_by_root[self.root_ids[0]]
        return float(first_solver.current_time_ms)

    @property
    def substep_index(self) -> int:
        return int(self._substep_index)

    @property
    def shared_step_count(self) -> int:
        return int(self._shared_step_count)

    @property
    def is_initialized(self) -> bool:
        return self._initial_states_by_root is not None

    @property
    def is_finalized(self) -> bool:
        return self._final_result is not None

    def initialize_zero(self) -> dict[str, Any]:
        for solver in self._solver_by_root.values():
            solver.initialize_zero()
        return self._finalize_initialization()

    def initialize_states(
        self,
        states_by_root: Mapping[int, SurfaceWaveState],
    ) -> dict[str, Any]:
        unexpected_root_ids = sorted(
            int(root_id)
            for root_id in states_by_root
            if int(root_id) not in set(self.root_ids)
        )
        if unexpected_root_ids:
            raise ValueError(
                "surface-wave circuit initialization contains unknown root IDs "
                f"{unexpected_root_ids!r}."
            )
        for root_id in self.root_ids:
            solver = self._solver_by_root[root_id]
            state = states_by_root.get(root_id)
            if state is None:
                solver.initialize_zero()
                continue
            solver.initialize_state(state)
        return self._finalize_initialization()

    def initialize_localized_pulses(
        self,
        pulse_specs_by_root: Mapping[int, Mapping[str, Any]],
    ) -> dict[str, Any]:
        unexpected_root_ids = sorted(
            int(root_id)
            for root_id in pulse_specs_by_root
            if int(root_id) not in set(self.root_ids)
        )
        if unexpected_root_ids:
            raise ValueError(
                "surface-wave circuit pulse initialization contains unknown root IDs "
                f"{unexpected_root_ids!r}."
            )
        for root_id in self.root_ids:
            solver = self._solver_by_root[root_id]
            pulse_spec = pulse_specs_by_root.get(root_id)
            if pulse_spec is None:
                solver.initialize_zero()
                continue
            normalized_spec = _require_mapping(
                pulse_spec,
                field_name=f"pulse_specs_by_root[{root_id}]",
            )
            solver.initialize_localized_pulse(
                seed_vertex=normalized_spec.get("seed_vertex"),
                amplitude=float(normalized_spec.get("amplitude", 1.0)),
                support_radius_scale=float(normalized_spec.get("support_radius_scale", 1.5)),
                initial_velocity=normalized_spec.get("initial_velocity"),
            )
        return self._finalize_initialization()

    def substep(
        self,
        *,
        surface_drives_by_root: Mapping[int, Sequence[float] | np.ndarray] | None = None,
        patch_drives_by_root: Mapping[int, Sequence[float] | np.ndarray] | None = None,
    ) -> dict[str, Any]:
        self._require_initialized()
        if self._final_result is not None:
            raise ValueError("surface-wave circuit has already been finalized.")

        coupling_patch_drives = {
            root_id: np.zeros(self._patch_count_by_root[root_id], dtype=np.float64)
            for root_id in self.root_ids
        }
        coupling_events = self._resolve_coupling_patch_drives(coupling_patch_drives)

        snapshots_by_root: dict[int, dict[str, Any]] = {}
        for root_id in self.root_ids:
            surface_drive = self._normalize_surface_drive(
                root_id=root_id,
                drives_by_root=surface_drives_by_root,
            )
            patch_drive = self._normalize_patch_drive(
                root_id=root_id,
                drives_by_root=patch_drives_by_root,
            )
            if patch_drive is None:
                patch_drive = coupling_patch_drives[root_id]
            else:
                patch_drive = patch_drive + coupling_patch_drives[root_id]
            snapshot = self._solver_by_root[root_id].step(
                surface_drive=surface_drive,
                patch_drive=patch_drive,
            )
            snapshots_by_root[root_id] = snapshot.as_mapping()

        self._substep_index += 1
        self._capture_patch_readouts()
        if self._substep_index % self._plan.internal_substep_count == 0:
            self._shared_step_count += 1
            self._shared_readout_history.append(
                self._build_shared_readout_summary(
                    lifecycle_stage=STEP_COMPLETED_STAGE,
                )
            )

        return {
            "lifecycle_stage": STEP_COMPLETED_STAGE,
            "substep_index": int(self._substep_index),
            "time_ms": float(self.current_time_ms),
            "snapshots_by_root": snapshots_by_root,
            "coupling_patch_drives_by_root": {
                str(root_id): np.asarray(coupling_patch_drives[root_id], dtype=np.float64).tolist()
                for root_id in self.root_ids
            },
            "coupling_event_count": len(coupling_events),
        }

    def step_shared(
        self,
        *,
        surface_drives_by_root: Mapping[int, Sequence[float] | np.ndarray] | None = None,
        patch_drives_by_root: Mapping[int, Sequence[float] | np.ndarray] | None = None,
    ) -> dict[str, Any]:
        shared_summary: dict[str, Any] | None = None
        for _ in range(self._plan.internal_substep_count):
            self.substep(
                surface_drives_by_root=surface_drives_by_root,
                patch_drives_by_root=patch_drives_by_root,
            )
            shared_summary = self._shared_readout_history[-1]
        assert shared_summary is not None
        return copy.deepcopy(shared_summary)

    def run_shared_steps(
        self,
        *,
        shared_step_count: int,
        surface_drives_by_root: Mapping[int, Sequence[float] | np.ndarray] | None = None,
        patch_drives_by_root: Mapping[int, Sequence[float] | np.ndarray] | None = None,
    ) -> CoupledSurfaceWaveRunResult:
        self._require_initialized()
        normalized_shared_step_count = int(shared_step_count)
        if normalized_shared_step_count < 0:
            raise ValueError("shared_step_count must be non-negative.")
        for _ in range(normalized_shared_step_count):
            self.step_shared(
                surface_drives_by_root=surface_drives_by_root,
                patch_drives_by_root=patch_drives_by_root,
            )
        return self.finalize()

    def run_to_completion(
        self,
        *,
        shared_step_count: int | None = None,
        surface_drives_by_root: Mapping[int, Sequence[float] | np.ndarray] | None = None,
        patch_drives_by_root: Mapping[int, Sequence[float] | np.ndarray] | None = None,
    ) -> CoupledSurfaceWaveRunResult:
        self._require_initialized()
        if shared_step_count is None:
            shared_step_count = int(self._plan.timebase.sample_count)
        return self.run_shared_steps(
            shared_step_count=shared_step_count,
            surface_drives_by_root=surface_drives_by_root,
            patch_drives_by_root=patch_drives_by_root,
        )

    def finalize(self) -> CoupledSurfaceWaveRunResult:
        self._require_initialized()
        if self._final_result is not None:
            return self._final_result

        runtime_metadata_by_root = tuple(
            self._solver_by_root[root_id].runtime_metadata.as_mapping()
            for root_id in self.root_ids
        )
        final_states_by_root = {
            root_id: self._solver_by_root[root_id].state.as_mapping()
            for root_id in self.root_ids
        }
        self._shared_readout_history.append(
            self._build_shared_readout_summary(
                lifecycle_stage=FINALIZED_STAGE,
            )
        )
        result = CoupledSurfaceWaveRunResult(
            execution_version=self._plan.execution_version,
            root_ids=self.root_ids,
            timebase=self._plan.timebase.as_mapping(),
            determinism=self._plan.determinism.as_mapping(),
            surface_wave_model=copy.deepcopy(self._plan.surface_wave_model),
            coupling_plan=self._plan.coupling_plan.as_mapping(),
            runtime_metadata_by_root=runtime_metadata_by_root,
            initial_states_by_root=copy.deepcopy(self._initial_states_by_root or {}),
            final_states_by_root=final_states_by_root,
            patch_readout_history_by_root={
                root_id: _freeze_float_array(
                    np.vstack(history)
                    if history
                    else np.empty((0, self._patch_count_by_root[root_id]), dtype=np.float64),
                    field_name=f"patch_readout_history_by_root[{root_id}]",
                    ndim=2,
                )
                for root_id, history in self._patch_readout_history_by_root.items()
            },
            shared_readout_history=tuple(copy.deepcopy(self._shared_readout_history)),
            coupling_application_history=tuple(copy.deepcopy(self._coupling_application_history)),
            substep_count=int(self._substep_index),
            shared_step_count=int(self._shared_step_count),
        )
        self._final_result = result
        return result

    def _finalize_initialization(self) -> dict[str, Any]:
        if self._initial_states_by_root is not None:
            raise ValueError("surface-wave circuit has already been initialized.")
        self._capture_patch_readouts()
        self._initial_states_by_root = {
            root_id: self._solver_by_root[root_id].state.as_mapping()
            for root_id in self.root_ids
        }
        initial_summary = self._build_shared_readout_summary(
            lifecycle_stage=INITIALIZED_STAGE,
        )
        self._shared_readout_history = [initial_summary]
        return copy.deepcopy(initial_summary)

    def _resolve_coupling_patch_drives(
        self,
        coupling_patch_drives: dict[int, np.ndarray],
    ) -> list[dict[str, Any]]:
        coupling_events: list[dict[str, Any]] = []
        for component in self._plan.coupling_plan.components:
            source_step_index = int(self._substep_index) - int(component.delay_steps)
            if source_step_index < 0:
                continue
            source_history = self._patch_readout_history_by_root[component.pre_root_id]
            source_patch_values = np.asarray(
                source_history[source_step_index],
                dtype=np.float64,
            )
            sampled_patch_values = source_patch_values[component.source_cloud.patch_indices]
            source_value = float(
                np.dot(
                    sampled_patch_values,
                    component.source_cloud.weights,
                )
            )
            signed_source_value = float(source_value * component.signed_weight_total)
            target_patch_drive = (
                signed_source_value * component.target_cloud.weights
            )
            np.add.at(
                coupling_patch_drives[component.post_root_id],
                component.target_cloud.patch_indices,
                target_patch_drive,
            )
            coupling_events.append(
                {
                    "target_substep_index": int(self._substep_index),
                    "applied_time_ms": float(self.current_time_ms),
                    "source_step_index": int(source_step_index),
                    "source_time_ms": float(
                        source_step_index * self._plan.integration_timestep_ms
                    ),
                    "component_id": component.component_id,
                    "pre_root_id": int(component.pre_root_id),
                    "post_root_id": int(component.post_root_id),
                    "delay_ms": float(component.delay_ms),
                    "delay_steps": int(component.delay_steps),
                    "sign_label": component.sign_label,
                    "signed_weight_total": float(component.signed_weight_total),
                    "source_patch_indices": component.source_cloud.patch_indices.tolist(),
                    "source_cloud_weights": component.source_cloud.weights.tolist(),
                    "source_patch_values": sampled_patch_values.tolist(),
                    "source_value": float(source_value),
                    "signed_source_value": float(signed_source_value),
                    "target_patch_indices": component.target_cloud.patch_indices.tolist(),
                    "target_cloud_weights": component.target_cloud.weights.tolist(),
                    "target_patch_drive": np.asarray(
                        target_patch_drive,
                        dtype=np.float64,
                    ).tolist(),
                }
            )
        self._coupling_application_history.extend(copy.deepcopy(coupling_events))
        return coupling_events

    def _capture_patch_readouts(self) -> None:
        for root_id in self.root_ids:
            patch_state = self._solver_by_root[root_id].current_patch_state()
            self._patch_readout_history_by_root[root_id].append(
                np.asarray(patch_state.activation, dtype=np.float64).copy()
            )

    def _build_shared_readout_summary(
        self,
        *,
        lifecycle_stage: str,
    ) -> dict[str, Any]:
        per_root_mean_activation = {
            str(root_id): float(np.mean(self._solver_by_root[root_id].state.activation))
            for root_id in self.root_ids
        }
        per_root_mean_velocity = {
            str(root_id): float(np.mean(self._solver_by_root[root_id].state.velocity))
            for root_id in self.root_ids
        }
        per_root_patch_activation = {
            str(root_id): np.asarray(
                self._patch_readout_history_by_root[root_id][-1],
                dtype=np.float64,
            ).tolist()
            for root_id in self.root_ids
        }
        return {
            "lifecycle_stage": lifecycle_stage,
            "shared_step_index": int(self._shared_step_count),
            "substep_index": int(self._substep_index),
            "time_ms": float(self.current_time_ms),
            "shared_output_mean": float(
                np.mean(list(per_root_mean_activation.values()), dtype=np.float64)
            ),
            "per_root_mean_activation": per_root_mean_activation,
            "per_root_mean_velocity": per_root_mean_velocity,
            "per_root_patch_activation": per_root_patch_activation,
        }

    def _normalize_surface_drive(
        self,
        *,
        root_id: int,
        drives_by_root: Mapping[int, Sequence[float] | np.ndarray] | None,
    ) -> np.ndarray | None:
        if drives_by_root is None:
            return None
        drive = drives_by_root.get(root_id)
        if drive is None:
            return None
        return _freeze_float_array(
            drive,
            field_name=f"surface_drives_by_root[{root_id}]",
            ndim=1,
            expected_length=int(self._solver_by_root[root_id].runtime_metadata.surface_vertex_count),
        ).copy()

    def _normalize_patch_drive(
        self,
        *,
        root_id: int,
        drives_by_root: Mapping[int, Sequence[float] | np.ndarray] | None,
    ) -> np.ndarray | None:
        if drives_by_root is None:
            return None
        drive = drives_by_root.get(root_id)
        if drive is None:
            return None
        return _freeze_float_array(
            drive,
            field_name=f"patch_drives_by_root[{root_id}]",
            ndim=1,
            expected_length=self._patch_count_by_root[root_id],
        ).copy()

    def _require_initialized(self) -> None:
        if self._initial_states_by_root is None:
            raise ValueError("surface-wave circuit has not been initialized.")

    def _require_patch_count(
        self,
        solver: SingleNeuronSurfaceWaveSolver,
        *,
        root_id: int,
    ) -> int:
        patch_count = solver.runtime_metadata.patch_count
        if patch_count is None:
            raise ValueError(
                f"surface-wave circuit root {root_id} does not expose a patch state space."
            )
        if not solver.kernels.operator_bundle.supports_patch_projection:
            raise ValueError(
                f"surface-wave circuit root {root_id} is missing surface-to-patch transfer operators."
            )
        return int(patch_count)


def resolve_surface_wave_execution_plan(
    *,
    surface_wave_model: Mapping[str, Any],
    surface_wave_execution_plan: Mapping[str, Any],
    root_ids: Sequence[int],
    timebase: Mapping[str, Any],
    determinism: Mapping[str, Any],
    arm_plan: Mapping[str, Any] | None = None,
) -> ResolvedSurfaceWaveExecutionPlan:
    normalized_model = parse_surface_wave_model_metadata(surface_wave_model)
    normalized_execution_plan = copy.deepcopy(dict(_require_mapping(
        surface_wave_execution_plan,
        field_name="surface_wave_execution_plan",
    )))
    normalized_root_ids = tuple(int(root_id) for root_id in root_ids)
    if not normalized_root_ids:
        raise ValueError("surface-wave execution requires at least one selected root.")
    if len(set(normalized_root_ids)) != len(normalized_root_ids):
        raise ValueError("surface-wave execution root_ids contain duplicates.")
    hybrid_morphology = normalized_execution_plan.get("hybrid_morphology")
    if hybrid_morphology is None:
        hybrid_morphology = build_hybrid_morphology_plan_metadata(
            root_records=[
                {
                    "root_id": int(root_id),
                    "project_role": "surface_simulated",
                }
                for root_id in normalized_root_ids
            ],
            model_mode="surface_wave",
        )
    else:
        hybrid_morphology = parse_hybrid_morphology_plan_metadata(
            _require_mapping(
                hybrid_morphology,
                field_name="surface_wave_execution_plan.hybrid_morphology",
            )
        )
    hybrid_root_ids = tuple(
        int(item["root_id"])
        for item in hybrid_morphology["per_root_class_metadata"]
    )
    if hybrid_root_ids != normalized_root_ids:
        raise ValueError(
            "surface_wave_execution_plan.hybrid_morphology.per_root_class_metadata "
            "must cover the same ordered root_ids as the execution request."
        )
    normalized_execution_plan["hybrid_morphology"] = hybrid_morphology
    normalized_timebase = SimulationTimebase.from_mapping(timebase)
    normalized_determinism = SimulationDeterminismContext.from_mapping(determinism)
    operator_assets = _resolve_operator_assets(
        normalized_execution_plan=normalized_execution_plan,
        root_ids=normalized_root_ids,
    )
    operator_bundles = tuple(
        SurfaceWaveOperatorBundle.from_operator_asset(asset)
        for asset in operator_assets
    )
    coupling_assets = _resolve_coupling_assets(
        normalized_execution_plan=normalized_execution_plan,
        root_ids=normalized_root_ids,
    )
    coupling_plan = _build_coupling_plan(
        operator_bundles=operator_bundles,
        coupling_assets=coupling_assets,
        topology_condition=_normalize_topology_condition(
            normalized_execution_plan.get("topology_condition", INTACT_TOPOLOGY_CONDITION),
            field_name="surface_wave_execution_plan.topology_condition",
        ),
        integration_timestep_ms=float(
            _require_mapping(
                normalized_execution_plan.get("solver"),
                field_name="surface_wave_execution_plan.solver",
            )["integration_timestep_ms"]
        ),
        determinism=normalized_determinism,
        root_ids=normalized_root_ids,
        ablation_transform=(
            None
            if normalized_execution_plan.get("ablation_transform") is None
            else _require_mapping(
                normalized_execution_plan.get("ablation_transform"),
                field_name="surface_wave_execution_plan.ablation_transform",
            )
        ),
    )
    return ResolvedSurfaceWaveExecutionPlan(
        root_ids=normalized_root_ids,
        timebase=normalized_timebase,
        determinism=normalized_determinism,
        surface_wave_model=copy.deepcopy(normalized_model),
        surface_wave_execution_plan=normalized_execution_plan,
        operator_assets=tuple(copy.deepcopy(operator_assets)),
        coupling_assets=tuple(copy.deepcopy(coupling_assets)),
        operator_bundles=operator_bundles,
        coupling_plan=coupling_plan,
        arm_plan=None if arm_plan is None else copy.deepcopy(dict(arm_plan)),
    )


def resolve_surface_wave_execution_plan_from_arm_plan(
    arm_plan: Mapping[str, Any],
) -> ResolvedSurfaceWaveExecutionPlan:
    normalized_arm_plan = _require_mapping(arm_plan, field_name="arm_plan")
    arm_reference = _require_mapping(
        normalized_arm_plan.get("arm_reference"),
        field_name="arm_plan.arm_reference",
    )
    model_mode = _normalize_nonempty_string(
        arm_reference.get("model_mode"),
        field_name="arm_plan.arm_reference.model_mode",
    )
    if model_mode != "surface_wave":
        raise ValueError(
            "surface-wave execution requires arm_reference.model_mode == 'surface_wave', "
            f"got {model_mode!r}."
        )
    model_configuration = _require_mapping(
        normalized_arm_plan.get("model_configuration"),
        field_name="arm_plan.model_configuration",
    )
    runtime = _require_mapping(
        normalized_arm_plan.get("runtime"),
        field_name="arm_plan.runtime",
    )
    selection = _require_mapping(
        normalized_arm_plan.get("selection"),
        field_name="arm_plan.selection",
    )
    return resolve_surface_wave_execution_plan(
        surface_wave_model=_require_mapping(
            model_configuration.get("surface_wave_model"),
            field_name="arm_plan.model_configuration.surface_wave_model",
        ),
        surface_wave_execution_plan=_require_mapping(
            model_configuration.get("surface_wave_execution_plan"),
            field_name="arm_plan.model_configuration.surface_wave_execution_plan",
        ),
        root_ids=_require_sequence(
            selection.get("selected_root_ids"),
            field_name="arm_plan.selection.selected_root_ids",
        ),
        timebase=_require_mapping(
            runtime.get("timebase"),
            field_name="arm_plan.runtime.timebase",
        ),
        determinism=_require_mapping(
            normalized_arm_plan.get("determinism"),
            field_name="arm_plan.determinism",
        ),
        arm_plan=normalized_arm_plan,
    )


def build_surface_wave_circuit_from_arm_plan(
    arm_plan: Mapping[str, Any],
) -> CoupledSurfaceWaveCircuit:
    return resolve_surface_wave_execution_plan_from_arm_plan(arm_plan).build_circuit()


def run_surface_wave_circuit_from_arm_plan(
    arm_plan: Mapping[str, Any],
    *,
    shared_step_count: int | None = None,
    initial_states_by_root: Mapping[int, SurfaceWaveState] | None = None,
) -> CoupledSurfaceWaveRunResult:
    return resolve_surface_wave_execution_plan_from_arm_plan(arm_plan).run_to_completion(
        shared_step_count=shared_step_count,
        initial_states_by_root=initial_states_by_root,
    )


def _resolve_operator_assets(
    *,
    normalized_execution_plan: Mapping[str, Any],
    root_ids: Sequence[int],
) -> list[dict[str, Any]]:
    selected_root_operator_assets = _require_sequence(
        normalized_execution_plan.get("selected_root_operator_assets"),
        field_name="surface_wave_execution_plan.selected_root_operator_assets",
    )
    asset_by_root: dict[int, dict[str, Any]] = {}
    for index, asset in enumerate(selected_root_operator_assets):
        normalized_asset = copy.deepcopy(dict(_require_mapping(
            asset,
            field_name=f"surface_wave_execution_plan.selected_root_operator_assets[{index}]",
        )))
        root_id = int(normalized_asset.get("root_id"))
        asset_by_root[root_id] = normalized_asset
    missing_root_ids = [
        int(root_id)
        for root_id in root_ids
        if int(root_id) not in asset_by_root
    ]
    if missing_root_ids:
        raise ValueError(
            "surface-wave execution is missing operator assets for selected roots "
            f"{missing_root_ids!r}."
        )

    resolved: list[dict[str, Any]] = []
    for root_id in root_ids:
        asset = copy.deepcopy(asset_by_root[int(root_id)])
        for field_name in (
            "fine_operator_path",
            "coarse_operator_path",
            "transfer_operator_path",
            "operator_metadata_path",
        ):
            path = Path(_normalize_nonempty_string(asset.get(field_name), field_name=f"operator_asset.{field_name}")).resolve()
            if not path.exists():
                raise ValueError(
                    f"surface-wave execution operator asset {field_name} for root {root_id} is missing: {path}."
                )
            asset[field_name] = str(path)
        descriptor_sidecar = asset.get("descriptor_sidecar_path")
        if descriptor_sidecar is not None:
            asset["descriptor_sidecar_path"] = str(Path(str(descriptor_sidecar)).resolve())
        resolved.append(asset)
    return resolved


def _resolve_coupling_assets(
    *,
    normalized_execution_plan: Mapping[str, Any],
    root_ids: Sequence[int],
) -> list[dict[str, Any]]:
    selected_root_coupling_assets = _require_sequence(
        normalized_execution_plan.get("selected_root_coupling_assets"),
        field_name="surface_wave_execution_plan.selected_root_coupling_assets",
    )
    asset_by_root: dict[int, dict[str, Any]] = {}
    for index, asset in enumerate(selected_root_coupling_assets):
        normalized_asset = copy.deepcopy(dict(_require_mapping(
            asset,
            field_name=f"surface_wave_execution_plan.selected_root_coupling_assets[{index}]",
        )))
        root_id = int(normalized_asset.get("root_id"))
        asset_by_root[root_id] = normalized_asset
    missing_root_ids = [
        int(root_id)
        for root_id in root_ids
        if int(root_id) not in asset_by_root
    ]
    if missing_root_ids:
        raise ValueError(
            "surface-wave execution is missing coupling assets for selected roots "
            f"{missing_root_ids!r}."
        )

    resolved: list[dict[str, Any]] = []
    for root_id in root_ids:
        asset = copy.deepcopy(asset_by_root[int(root_id)])
        for field_name in (
            "local_synapse_registry_path",
            "incoming_anchor_map_path",
            "outgoing_anchor_map_path",
            "coupling_index_path",
        ):
            path = Path(_normalize_nonempty_string(asset.get(field_name), field_name=f"coupling_asset.{field_name}")).resolve()
            if not path.exists():
                raise ValueError(
                    f"surface-wave execution coupling asset {field_name} for root {root_id} is missing: {path}."
                )
            asset[field_name] = str(path)
        normalized_edge_bundle_paths: list[dict[str, Any]] = []
        for edge_index, edge_bundle in enumerate(
            _require_sequence(
                asset.get("selected_edge_bundle_paths"),
                field_name=f"coupling_asset[{root_id}].selected_edge_bundle_paths",
            )
        ):
            normalized_edge_bundle = copy.deepcopy(dict(_require_mapping(
                edge_bundle,
                field_name=(
                    f"coupling_asset[{root_id}].selected_edge_bundle_paths[{edge_index}]"
                ),
            )))
            path = Path(
                _normalize_nonempty_string(
                    normalized_edge_bundle.get("path"),
                    field_name="selected_edge_bundle.path",
                )
            ).resolve()
            if not path.exists():
                raise ValueError(
                    f"surface-wave execution selected edge bundle for root {root_id} is missing: {path}."
                )
            normalized_edge_bundle["path"] = str(path)
            normalized_edge_bundle_paths.append(normalized_edge_bundle)
        asset["selected_edge_bundle_paths"] = normalized_edge_bundle_paths
        resolved.append(asset)
    return resolved


def _build_coupling_plan(
    *,
    operator_bundles: Sequence[SurfaceWaveOperatorBundle],
    coupling_assets: Sequence[Mapping[str, Any]],
    topology_condition: str,
    integration_timestep_ms: float,
    determinism: SimulationDeterminismContext,
    root_ids: Sequence[int],
    ablation_transform: Mapping[str, Any] | None = None,
) -> SurfaceWaveCouplingPlan:
    operator_bundle_by_root = {
        int(bundle.root_id): bundle
        for bundle in operator_bundles
    }
    selected_root_ids = tuple(int(root_id) for root_id in root_ids)
    edge_paths = _collect_selected_edge_paths(
        coupling_assets=coupling_assets,
        root_ids=selected_root_ids,
    )
    target_patch_permutations = _build_target_patch_permutations(
        topology_condition=topology_condition,
        determinism=determinism,
        operator_bundle_by_root=operator_bundle_by_root,
        root_ids=selected_root_ids,
        ablation_transform=ablation_transform,
    )

    components: list[SurfaceWaveCouplingComponent] = []
    for pre_root_id, post_root_id in sorted(edge_paths):
        bundle_path = edge_paths[(pre_root_id, post_root_id)]
        bundle = load_edge_coupling_bundle(bundle_path)
        if bundle.pre_root_id != int(pre_root_id) or bundle.post_root_id != int(post_root_id):
            raise ValueError(
                f"Coupling bundle at {bundle_path} does not match expected edge {pre_root_id}->{post_root_id}."
            )
        if bundle.topology_family != DISTRIBUTED_PATCH_CLOUD_TOPOLOGY:
            raise ValueError(
                f"surface-wave execution requires topology_family {DISTRIBUTED_PATCH_CLOUD_TOPOLOGY!r}, "
                f"but {bundle_path} declares {bundle.topology_family!r}."
            )
        if bundle.kernel_family != SEPARABLE_RANK_ONE_CLOUD_KERNEL:
            raise ValueError(
                f"surface-wave execution requires kernel_family {SEPARABLE_RANK_ONE_CLOUD_KERNEL!r}, "
                f"but {bundle_path} declares {bundle.kernel_family!r}."
            )
        if bundle.component_table.empty:
            continue
        ordered_components = bundle.component_table.sort_values(
            ["component_index", "component_id"],
            kind="mergesort",
        ).reset_index(drop=True)
        for row in ordered_components.itertuples(index=False):
            sign_label, signed_weight_total, delay_ms = (
                apply_experiment_ablation_coupling_perturbation(
                    ablation_transform,
                    sign_label=str(row.sign_label),
                    signed_weight_total=float(row.signed_weight_total),
                    delay_ms=float(row.delay_ms),
                )
            )
            if not np.isfinite(signed_weight_total):
                raise ValueError(
                    f"Coupling component {row.component_id!r} from {bundle_path} has a non-finite signed weight."
                )
            if abs(signed_weight_total) <= _ZERO_TOLERANCE:
                continue
            source_cloud = _resolve_component_cloud(
                component_index=int(row.component_index),
                component_id=str(row.component_id),
                anchor_table=bundle.source_anchor_table,
                cloud_table=bundle.source_cloud_table,
                expected_root_id=int(pre_root_id),
                root_patch_count=_require_patch_count(
                    operator_bundle_by_root[int(pre_root_id)],
                    root_id=int(pre_root_id),
                ),
                permutation=None,
                role="presynaptic",
            )
            target_cloud = _resolve_component_cloud(
                component_index=int(row.component_index),
                component_id=str(row.component_id),
                anchor_table=bundle.target_anchor_table,
                cloud_table=bundle.target_cloud_table,
                expected_root_id=int(post_root_id),
                root_patch_count=_require_patch_count(
                    operator_bundle_by_root[int(post_root_id)],
                    root_id=int(post_root_id),
                ),
                permutation=target_patch_permutations.get(int(post_root_id)),
                role="postsynaptic",
            )
            components.append(
                SurfaceWaveCouplingComponent(
                    component_id=str(row.component_id),
                    pre_root_id=int(pre_root_id),
                    post_root_id=int(post_root_id),
                    delay_ms=float(delay_ms),
                    delay_steps=_resolve_delay_steps(
                        delay_ms=float(delay_ms),
                        dt_ms=float(integration_timestep_ms),
                        component_id=str(row.component_id),
                    ),
                    sign_label=sign_label,
                    signed_weight_total=signed_weight_total,
                    kernel_family=str(row.kernel_family),
                    aggregation_rule=str(row.aggregation_rule),
                    source_anchor_mode=str(row.pre_anchor_mode),
                    target_anchor_mode=str(row.post_anchor_mode),
                    source_cloud_normalization=str(row.source_cloud_normalization),
                    target_cloud_normalization=str(row.target_cloud_normalization),
                    synapse_count=int(row.synapse_count),
                    source_cloud=source_cloud,
                    target_cloud=target_cloud,
                )
            )

    coupling_hash = _stable_hash(
        {
            "root_ids": list(selected_root_ids),
            "topology_condition": topology_condition,
            "target_patch_permutations": {
                str(root_id): [int(value) for value in permutation]
                for root_id, permutation in sorted(target_patch_permutations.items())
            },
            "components": [
                component.as_mapping()
                for component in components
            ],
        }
    )
    return SurfaceWaveCouplingPlan(
        root_ids=selected_root_ids,
        topology_condition=topology_condition,
        shuffle_scope=(
            POSTSYNAPTIC_PATCH_PERMUTATION_SHUFFLE
            if topology_condition == SHUFFLED_TOPOLOGY_CONDITION
            else None
        ),
        components=tuple(components),
        coupling_hash=coupling_hash,
        target_patch_permutations={
            int(root_id): tuple(int(value) for value in permutation)
            for root_id, permutation in target_patch_permutations.items()
        },
    )


def _collect_selected_edge_paths(
    *,
    coupling_assets: Sequence[Mapping[str, Any]],
    root_ids: Sequence[int],
) -> dict[tuple[int, int], Any]:
    selected_root_ids = set(int(root_id) for root_id in root_ids)
    asset_root_ids: set[int] = set()
    edge_paths: dict[tuple[int, int], Any] = {}
    for index, asset in enumerate(coupling_assets):
        coupling_asset = _require_mapping(
            asset,
            field_name=f"coupling_assets[{index}]",
        )
        root_id = int(coupling_asset.get("root_id"))
        if root_id not in selected_root_ids:
            raise ValueError(
                f"coupling_assets contains unexpected root_id {root_id}."
            )
        asset_root_ids.add(root_id)
        for edge_index, edge_bundle in enumerate(
            _require_sequence(
                coupling_asset.get("selected_edge_bundle_paths"),
                field_name=f"coupling_assets[{root_id}].selected_edge_bundle_paths",
            )
        ):
            normalized_edge_bundle = _require_mapping(
                edge_bundle,
                field_name=f"coupling_assets[{root_id}].selected_edge_bundle_paths[{edge_index}]",
            )
            pre_root_id = int(normalized_edge_bundle.get("pre_root_id"))
            post_root_id = int(normalized_edge_bundle.get("post_root_id"))
            if pre_root_id not in selected_root_ids or post_root_id not in selected_root_ids:
                raise ValueError(
                    "surface-wave execution selected edge bundle "
                    f"{pre_root_id}->{post_root_id} is incompatible with the selected root roster."
                )
            edge_key = (pre_root_id, post_root_id)
            edge_path = Path(
                _normalize_nonempty_string(
                    normalized_edge_bundle.get("path"),
                    field_name="selected_edge_bundle.path",
                )
            ).resolve()
            if edge_key in edge_paths and edge_paths[edge_key] != edge_path:
                raise ValueError(
                    "surface-wave execution encountered conflicting paths for edge "
                    f"{pre_root_id}->{post_root_id}: {edge_paths[edge_key]} != {edge_path}."
                )
            edge_paths[edge_key] = edge_path
    if asset_root_ids != selected_root_ids:
        raise ValueError("surface-wave execution coupling assets do not cover all selected roots.")
    return edge_paths


def _build_target_patch_permutations(
    *,
    topology_condition: str,
    determinism: SimulationDeterminismContext,
    operator_bundle_by_root: Mapping[int, SurfaceWaveOperatorBundle],
    root_ids: Sequence[int],
    ablation_transform: Mapping[str, Any] | None = None,
) -> dict[int, np.ndarray]:
    precomputed = resolve_experiment_ablation_patch_permutations(ablation_transform)
    if precomputed is not None:
        permutations: dict[int, np.ndarray] = {}
        for root_id in root_ids:
            if int(root_id) not in precomputed:
                raise ValueError(
                    "surface-wave ablation patch permutations do not cover root_id "
                    f"{root_id}."
                )
            expected_patch_count = _require_patch_count(
                operator_bundle_by_root[int(root_id)],
                root_id=int(root_id),
            )
            permutation = np.asarray(precomputed[int(root_id)], dtype=np.int64)
            if permutation.shape != (expected_patch_count,):
                raise ValueError(
                    "surface-wave ablation patch permutation for root "
                    f"{root_id} has shape {tuple(permutation.shape)!r}, expected "
                    f"({expected_patch_count},)."
                )
            permutations[int(root_id)] = permutation
        return permutations
    if topology_condition == INTACT_TOPOLOGY_CONDITION:
        return {
            int(root_id): np.arange(
                _require_patch_count(operator_bundle_by_root[int(root_id)], root_id=int(root_id)),
                dtype=np.int64,
            )
            for root_id in root_ids
        }
    rng = determinism.build_rng()
    permutations: dict[int, np.ndarray] = {}
    for root_id in root_ids:
        patch_count = _require_patch_count(
            operator_bundle_by_root[int(root_id)],
            root_id=int(root_id),
        )
        permutation = np.asarray(rng.permutation(patch_count), dtype=np.int64)
        if patch_count > 1 and np.array_equal(
            permutation,
            np.arange(patch_count, dtype=np.int64),
        ):
            permutation = np.roll(permutation, 1)
        permutations[int(root_id)] = permutation
    return permutations


def _resolve_component_cloud(
    *,
    component_index: int,
    component_id: str,
    anchor_table: Any,
    cloud_table: Any,
    expected_root_id: int,
    root_patch_count: int,
    permutation: np.ndarray | None,
    role: str,
) -> SurfaceWavePatchCloud:
    component_rows = cloud_table.loc[
        cloud_table["component_index"] == int(component_index)
    ].sort_values(
        ["anchor_table_index"],
        kind="mergesort",
    )
    if component_rows.empty:
        raise ValueError(
            f"Coupling component {component_id!r} is missing its {role} cloud definition."
        )
    anchor_rows = anchor_table.set_index("anchor_table_index", drop=False)
    patch_weights: dict[int, float] = {}
    for row in component_rows.itertuples(index=False):
        anchor_table_index = int(row.anchor_table_index)
        if anchor_table_index not in anchor_rows.index:
            raise ValueError(
                f"Coupling component {component_id!r} references unknown {role} anchor_table_index "
                f"{anchor_table_index}."
            )
        anchor = anchor_rows.loc[anchor_table_index]
        if int(anchor["root_id"]) != int(expected_root_id):
            raise ValueError(
                f"Coupling component {component_id!r} has a {role} anchor on root "
                f"{int(anchor['root_id'])}, expected {expected_root_id}."
            )
        anchor_mode = _normalize_nonempty_string(
            anchor["anchor_mode"],
            field_name=f"{component_id}.{role}.anchor_mode",
        )
        anchor_type = _normalize_nonempty_string(
            anchor["anchor_type"],
            field_name=f"{component_id}.{role}.anchor_type",
        )
        anchor_resolution = _normalize_nonempty_string(
            anchor["anchor_resolution"],
            field_name=f"{component_id}.{role}.anchor_resolution",
        )
        if anchor_mode != SURFACE_PATCH_CLOUD_MODE:
            raise ValueError(
                f"Coupling component {component_id!r} requires {role} anchor_mode "
                f"{SURFACE_PATCH_CLOUD_MODE!r}, got {anchor_mode!r}."
            )
        if anchor_type != ANCHOR_TYPE_SURFACE_PATCH:
            raise ValueError(
                f"Coupling component {component_id!r} requires {role} anchor_type "
                f"{ANCHOR_TYPE_SURFACE_PATCH!r}, got {anchor_type!r}."
            )
        if anchor_resolution != ANCHOR_RESOLUTION_COARSE_PATCH:
            raise ValueError(
                f"Coupling component {component_id!r} requires {role} anchor_resolution "
                f"{ANCHOR_RESOLUTION_COARSE_PATCH!r}, got {anchor_resolution!r}."
            )
        patch_index = int(anchor["anchor_index"])
        if patch_index < 0 or patch_index >= int(root_patch_count):
            raise ValueError(
                f"Coupling component {component_id!r} has out-of-range {role} patch index "
                f"{patch_index} for patch_count {root_patch_count}."
            )
        if permutation is not None:
            patch_index = int(permutation[patch_index])
        patch_weights[patch_index] = patch_weights.get(patch_index, 0.0) + float(row.cloud_weight)
    ordered_patch_indices = np.asarray(sorted(patch_weights), dtype=np.int64)
    ordered_weights = np.asarray(
        [patch_weights[int(index)] for index in ordered_patch_indices.tolist()],
        dtype=np.float64,
    )
    return SurfaceWavePatchCloud(
        patch_indices=ordered_patch_indices,
        weights=ordered_weights,
    )


def _resolve_delay_steps(
    *,
    delay_ms: float,
    dt_ms: float,
    component_id: str,
) -> int:
    if not np.isfinite(delay_ms) or delay_ms < 0.0:
        raise ValueError(
            f"Coupling component {component_id!r} has an unusable delay_ms {delay_ms!r}."
        )
    delay_steps_float = float(delay_ms) / float(dt_ms)
    delay_steps = int(round(delay_steps_float))
    if abs(delay_steps_float - delay_steps) > _DELAY_STEP_TOLERANCE:
        raise ValueError(
            f"Coupling component {component_id!r} delay_ms={delay_ms} cannot be represented "
            f"on integration_timestep_ms={dt_ms}."
        )
    return delay_steps


def _require_patch_count(
    operator_bundle: SurfaceWaveOperatorBundle,
    *,
    root_id: int,
) -> int:
    patch_count = operator_bundle.patch_count
    if patch_count is None:
        raise ValueError(
            f"surface-wave execution root {root_id} does not expose patch metadata."
        )
    if not operator_bundle.supports_patch_projection:
        raise ValueError(
            f"surface-wave execution root {root_id} is missing surface-to-patch transfer operators."
        )
    return int(patch_count)


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
    if expected_length is not None and array.shape[0] != int(expected_length):
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


def _normalize_topology_condition(value: Any, *, field_name: str) -> str:
    normalized = _normalize_nonempty_string(value, field_name=field_name)
    if normalized not in SUPPORTED_TOPOLOGY_CONDITIONS:
        raise ValueError(
            f"{field_name} must be one of {list(SUPPORTED_TOPOLOGY_CONDITIONS)!r}, got {normalized!r}."
        )
    return normalized


def _normalize_nonempty_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a non-empty string.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return normalized


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


def _require_sequence(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be a list.")
    return value


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _json_ready(subvalue)
            for key, subvalue in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, np.ndarray):
        return _json_ready(value.tolist())
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def _stable_hash(payload: Any) -> str:
    serialized = json.dumps(
        _json_ready(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
