from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .baseline_families import (
    BaselineNeuronFamily,
    DELAY_DISABLED_MODE,
    DELAY_FROM_COUPLING_BUNDLE_MODE,
    P1BaselineParameters,
    resolve_baseline_neuron_family_from_arm_plan,
)
from .retinal_bundle import load_recorded_retinal_bundle
from .retinal_contract import DEFAULT_CHANNEL_NAME
from .simulator_result_contract import (
    BASELINE_MODEL_MODE,
    P1_BASELINE_FAMILY,
)
from .simulator_runtime import (
    SimulationDriveProvider,
    SimulationHook,
    SimulationRecurrentInputProvider,
    SimulationRunBlueprint,
    SimulationRuntimeState,
    SimulationStepContext,
    SimulationTimebase,
    SimulatorRun,
    build_simulation_run_blueprint,
)
from .stimulus_bundle import load_recorded_stimulus_bundle
from .synapse_mapping import load_edge_coupling_bundle


BASELINE_EXECUTION_VERSION = "baseline_execution.v1"

INTACT_TOPOLOGY_CONDITION = "intact"
SHUFFLED_TOPOLOGY_CONDITION = "shuffled"
SUPPORTED_TOPOLOGY_CONDITIONS = (
    INTACT_TOPOLOGY_CONDITION,
    SHUFFLED_TOPOLOGY_CONDITION,
)

STIMULUS_BUNDLE_INPUT_SOURCE = "stimulus_bundle"
RETINAL_BUNDLE_INPUT_SOURCE = "retinal_bundle"
SUPPORTED_CANONICAL_INPUT_SOURCES = (
    STIMULUS_BUNDLE_INPUT_SOURCE,
    RETINAL_BUNDLE_INPUT_SOURCE,
)

STABLE_CONTIGUOUS_MEAN_POOL = "stable_contiguous_mean_pool"
TARGET_ASSIGNMENT_SHUFFLE = "component_target_assignment"

_TIME_TOLERANCE_MS = 1.0e-9
_DELAY_STEP_TOLERANCE = 1.0e-6


@dataclass(frozen=True)
class CanonicalInputStream:
    input_kind: str
    bundle_reference: dict[str, Any]
    metadata_path: Path
    replay_source: str
    time_ms: np.ndarray
    centered_unit_values: np.ndarray
    unit_ids: tuple[str, ...]
    neutral_value: float
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        if self.input_kind not in SUPPORTED_CANONICAL_INPUT_SOURCES:
            raise ValueError(
                "Unsupported canonical input source "
                f"{self.input_kind!r}. Supported sources: {list(SUPPORTED_CANONICAL_INPUT_SOURCES)!r}."
            )
        object.__setattr__(self, "metadata_path", Path(self.metadata_path).resolve())
        time_ms = _freeze_float_array(self.time_ms, field_name="canonical_input_stream.time_ms", ndim=1)
        centered_unit_values = _freeze_float_array(
            self.centered_unit_values,
            field_name="canonical_input_stream.centered_unit_values",
            ndim=2,
        )
        if centered_unit_values.shape[0] != time_ms.shape[0]:
            raise ValueError(
                "canonical_input_stream.centered_unit_values sample axis does not match time_ms."
            )
        if centered_unit_values.shape[1] != len(self.unit_ids):
            raise ValueError(
                "canonical_input_stream.centered_unit_values unit axis does not match unit_ids."
            )
        object.__setattr__(self, "time_ms", time_ms)
        object.__setattr__(self, "centered_unit_values", centered_unit_values)
        object.__setattr__(self, "bundle_reference", copy.deepcopy(dict(self.bundle_reference)))
        object.__setattr__(self, "metadata", copy.deepcopy(dict(self.metadata)))

    @property
    def bundle_id(self) -> str:
        return str(self.bundle_reference["bundle_id"])

    @property
    def sample_count(self) -> int:
        return int(self.time_ms.shape[0])

    @property
    def unit_count(self) -> int:
        return int(self.centered_unit_values.shape[1])


@dataclass(frozen=True)
class BaselineDriveSchedule:
    root_ids: tuple[int, ...]
    strategy: str
    drive_values: np.ndarray
    unit_ids: tuple[str, ...]
    unit_bins: tuple[tuple[int, ...], ...]
    input_stream_bundle_id: str
    drive_schedule_hash: str

    def __post_init__(self) -> None:
        drive_values = _freeze_float_array(
            self.drive_values,
            field_name="baseline_drive_schedule.drive_values",
            ndim=2,
        )
        if drive_values.shape[1] != len(self.root_ids):
            raise ValueError(
                "baseline_drive_schedule.drive_values root axis does not match root_ids."
            )
        if len(self.unit_bins) != len(self.root_ids):
            raise ValueError("baseline_drive_schedule.unit_bins must match root_ids length.")
        object.__setattr__(self, "drive_values", drive_values)

    @property
    def sample_count(self) -> int:
        return int(self.drive_values.shape[0])


@dataclass(frozen=True)
class BaselineDelayGroup:
    delay_steps: int
    source_indices: np.ndarray
    target_indices: np.ndarray
    weights: np.ndarray

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_indices",
            _freeze_int_array(
                self.source_indices,
                field_name="baseline_delay_group.source_indices",
                ndim=1,
            ),
        )
        object.__setattr__(
            self,
            "target_indices",
            _freeze_int_array(
                self.target_indices,
                field_name="baseline_delay_group.target_indices",
                ndim=1,
            ),
        )
        object.__setattr__(
            self,
            "weights",
            _freeze_float_array(
                self.weights,
                field_name="baseline_delay_group.weights",
                ndim=1,
            ),
        )
        if self.source_indices.shape != self.target_indices.shape or self.source_indices.shape != self.weights.shape:
            raise ValueError("baseline delay-group arrays must share the same shape.")

    @property
    def component_count(self) -> int:
        return int(self.weights.shape[0])


@dataclass(frozen=True)
class BaselineCouplingPlan:
    root_ids: tuple[int, ...]
    topology_condition: str
    shuffle_scope: str | None
    delay_groups: tuple[BaselineDelayGroup, ...]
    coupling_hash: str

    def __post_init__(self) -> None:
        if self.topology_condition not in SUPPORTED_TOPOLOGY_CONDITIONS:
            raise ValueError(
                "Unsupported topology_condition "
                f"{self.topology_condition!r}. Supported conditions: {list(SUPPORTED_TOPOLOGY_CONDITIONS)!r}."
            )

    @property
    def component_count(self) -> int:
        return int(sum(group.component_count for group in self.delay_groups))

    @property
    def max_delay_steps(self) -> int:
        if not self.delay_groups:
            return 0
        return max(int(group.delay_steps) for group in self.delay_groups)


@dataclass(frozen=True)
class ResolvedBaselineExecutionPlan:
    arm_plan: dict[str, Any]
    run_blueprint: SimulationRunBlueprint
    baseline_family: BaselineNeuronFamily
    canonical_input_stream: CanonicalInputStream
    drive_schedule: BaselineDriveSchedule
    coupling_plan: BaselineCouplingPlan
    execution_version: str = BASELINE_EXECUTION_VERSION

    def build_run(
        self,
        *,
        hooks: Sequence[SimulationHook] | None = None,
    ) -> SimulatorRun[Any]:
        return SimulatorRun(
            run_blueprint=self.run_blueprint,
            engine=self.baseline_family.build_engine(),
            drive_provider=_DriveScheduleProvider(self.drive_schedule),
            recurrent_input_provider=_CouplingPlanProvider(self.coupling_plan),
            hooks=hooks,
        )

    def run_to_completion(
        self,
        *,
        hooks: Sequence[SimulationHook] | None = None,
    ) -> Any:
        return self.build_run(hooks=hooks).run_to_completion()


def resolve_baseline_execution_plan_from_arm_plan(
    arm_plan: Mapping[str, Any],
) -> ResolvedBaselineExecutionPlan:
    normalized_arm_plan = _require_mapping(arm_plan, field_name="arm_plan")
    arm_reference = _require_mapping(
        normalized_arm_plan.get("arm_reference"),
        field_name="arm_plan.arm_reference",
    )
    model_mode = str(arm_reference.get("model_mode"))
    if model_mode != BASELINE_MODEL_MODE:
        raise ValueError(
            "Baseline execution requires arm_reference.model_mode == 'baseline', "
            f"got {model_mode!r}."
        )

    baseline_family = resolve_baseline_neuron_family_from_arm_plan(normalized_arm_plan)
    timebase = _resolve_runtime_timebase(normalized_arm_plan)
    canonical_input_stream = _load_canonical_input_stream(
        arm_plan=normalized_arm_plan,
        timebase=timebase,
    )
    root_ids = _resolve_selected_root_ids(normalized_arm_plan)
    drive_schedule = _build_drive_schedule(
        root_ids=root_ids,
        canonical_input_stream=canonical_input_stream,
    )
    coupling_plan = _build_coupling_plan(
        arm_plan=normalized_arm_plan,
        root_ids=root_ids,
        baseline_family=baseline_family,
        timebase=timebase,
    )
    run_blueprint = _build_run_blueprint(
        arm_plan=normalized_arm_plan,
        timebase=timebase,
        canonical_input_stream=canonical_input_stream,
        drive_schedule=drive_schedule,
        coupling_plan=coupling_plan,
    )
    return ResolvedBaselineExecutionPlan(
        arm_plan=copy.deepcopy(dict(normalized_arm_plan)),
        run_blueprint=run_blueprint,
        baseline_family=baseline_family,
        canonical_input_stream=canonical_input_stream,
        drive_schedule=drive_schedule,
        coupling_plan=coupling_plan,
    )


def load_canonical_input_stream_from_arm_plan(
    arm_plan: Mapping[str, Any],
) -> CanonicalInputStream:
    normalized_arm_plan = _require_mapping(arm_plan, field_name="arm_plan")
    return _load_canonical_input_stream(
        arm_plan=normalized_arm_plan,
        timebase=_resolve_runtime_timebase(normalized_arm_plan),
    )


def build_drive_schedule_for_root_ids(
    *,
    root_ids: Sequence[int],
    canonical_input_stream: CanonicalInputStream,
) -> BaselineDriveSchedule:
    return _build_drive_schedule(
        root_ids=root_ids,
        canonical_input_stream=canonical_input_stream,
    )


def build_baseline_simulator_run_from_arm_plan(
    arm_plan: Mapping[str, Any],
    *,
    hooks: Sequence[SimulationHook] | None = None,
) -> SimulatorRun[Any]:
    return resolve_baseline_execution_plan_from_arm_plan(arm_plan).build_run(hooks=hooks)


def run_baseline_simulation_from_arm_plan(
    arm_plan: Mapping[str, Any],
    *,
    hooks: Sequence[SimulationHook] | None = None,
) -> Any:
    return resolve_baseline_execution_plan_from_arm_plan(arm_plan).run_to_completion(hooks=hooks)


class _DriveScheduleProvider(SimulationDriveProvider[Any]):
    def __init__(self, drive_schedule: BaselineDriveSchedule) -> None:
        self._drive_schedule = drive_schedule

    def resolve_exogenous_drive(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[Any],
        context: SimulationStepContext,
    ) -> np.ndarray:
        del run_blueprint, context
        step_index = int(runtime_state.completed_steps)
        if step_index >= self._drive_schedule.sample_count:
            return np.zeros(runtime_state.neuron_state.neuron_count, dtype=np.float64)
        return np.asarray(self._drive_schedule.drive_values[step_index], dtype=np.float64)


class _CouplingPlanProvider(SimulationRecurrentInputProvider[Any]):
    def __init__(self, coupling_plan: BaselineCouplingPlan) -> None:
        self._coupling_plan = coupling_plan
        self._readout_history: list[np.ndarray] = []

    def resolve_recurrent_input(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[Any],
        context: SimulationStepContext,
    ) -> np.ndarray:
        del run_blueprint, context
        self._capture_readout_history(runtime_state)
        recurrent_input = np.zeros(runtime_state.neuron_state.neuron_count, dtype=np.float64)
        if not self._coupling_plan.delay_groups:
            return recurrent_input
        for delay_group in self._coupling_plan.delay_groups:
            source_step_index = int(runtime_state.completed_steps) - int(delay_group.delay_steps)
            if source_step_index < 0:
                continue
            source_values = self._readout_history[source_step_index]
            contributions = source_values[delay_group.source_indices] * delay_group.weights
            np.add.at(recurrent_input, delay_group.target_indices, contributions)
        return recurrent_input

    def _capture_readout_history(
        self,
        runtime_state: SimulationRuntimeState[Any],
    ) -> None:
        completed_steps = int(runtime_state.completed_steps)
        current_readout = np.asarray(runtime_state.neuron_state.readout_state, dtype=np.float64).copy()
        if len(self._readout_history) == completed_steps:
            self._readout_history.append(current_readout)
            return
        if len(self._readout_history) < completed_steps:
            raise ValueError(
                "Coupling-plan history fell behind the simulator step count; "
                "baseline recurrent input resolution is no longer deterministic."
            )
        self._readout_history[completed_steps] = current_readout


def _load_canonical_input_stream(
    *,
    arm_plan: Mapping[str, Any],
    timebase: SimulationTimebase,
) -> CanonicalInputStream:
    input_reference = _require_mapping(
        arm_plan.get("input_reference"),
        field_name="arm_plan.input_reference",
    )
    input_kind = _require_nonempty_string(
        input_reference.get("selected_input_kind"),
        field_name="arm_plan.input_reference.selected_input_kind",
    )
    metadata_path = Path(
        _require_nonempty_string(
            input_reference.get("selected_input_metadata_path"),
            field_name="arm_plan.input_reference.selected_input_metadata_path",
        )
    ).resolve()
    if not metadata_path.exists():
        raise ValueError(
            f"Baseline execution requires a recorded local input bundle at {metadata_path}."
        )

    if input_kind == STIMULUS_BUNDLE_INPUT_SOURCE:
        replay = load_recorded_stimulus_bundle(metadata_path)
        _validate_input_timing(
            input_kind=input_kind,
            timebase=timebase,
            sample_times_ms=replay.frame_times_ms,
            metadata_path=metadata_path,
        )
        frame_shape = tuple(int(value) for value in replay.frames.shape[1:])
        centered_values = np.asarray(
            replay.frames.reshape(replay.frames.shape[0], -1),
            dtype=np.float64,
        ) - float(replay.bundle_metadata["luminance_convention"]["neutral_value"])
        unit_ids = tuple(
            f"pixel:{y_index}:{x_index}"
            for y_index in range(frame_shape[0])
            for x_index in range(frame_shape[1])
        )
        bundle_reference = _require_mapping(
            input_reference.get("selected_input_reference"),
            field_name="arm_plan.input_reference.selected_input_reference",
        )
        return CanonicalInputStream(
            input_kind=input_kind,
            bundle_reference=bundle_reference,
            metadata_path=metadata_path,
            replay_source=str(replay.replay_source),
            time_ms=replay.frame_times_ms,
            centered_unit_values=centered_values,
            unit_ids=unit_ids,
            neutral_value=float(replay.bundle_metadata["luminance_convention"]["neutral_value"]),
            metadata={
                "frame_shape_y_x": list(frame_shape),
                "x_coordinates_deg": replay.x_coordinates_deg.tolist(),
                "y_coordinates_deg": replay.y_coordinates_deg.tolist(),
            },
        )

    if input_kind == RETINAL_BUNDLE_INPUT_SOURCE:
        replay = load_recorded_retinal_bundle(metadata_path)
        _validate_input_timing(
            input_kind=input_kind,
            timebase=timebase,
            sample_times_ms=replay.frame_times_ms,
            metadata_path=metadata_path,
        )
        simulator_input = replay.bundle_metadata["simulator_input"]
        channel_order = list(simulator_input["channel_order"])
        if channel_order != [DEFAULT_CHANNEL_NAME]:
            raise ValueError(
                "Baseline execution currently supports only the canonical single-channel "
                f"retinal input {DEFAULT_CHANNEL_NAME!r}, got {channel_order!r}."
            )
        eye_axis_labels = list(simulator_input["eye_axis_labels"])
        per_eye_unit_tables = simulator_input["mapping"]["per_eye_unit_tables"]
        unit_ids = tuple(
            str(unit_record["unit_id"])
            for eye_label in eye_axis_labels
            for unit_record in per_eye_unit_tables[eye_label]
        )
        centered_values = np.asarray(
            replay.early_visual_units[..., 0].reshape(replay.early_visual_units.shape[0], -1),
            dtype=np.float64,
        ) - float(replay.bundle_metadata["signal_convention"]["neutral_value"])
        bundle_reference = _require_mapping(
            input_reference.get("selected_input_reference"),
            field_name="arm_plan.input_reference.selected_input_reference",
        )
        return CanonicalInputStream(
            input_kind=input_kind,
            bundle_reference=bundle_reference,
            metadata_path=metadata_path,
            replay_source=str(replay.replay_source),
            time_ms=replay.frame_times_ms,
            centered_unit_values=centered_values,
            unit_ids=unit_ids,
            neutral_value=float(replay.bundle_metadata["signal_convention"]["neutral_value"]),
            metadata={
                "eye_axis_labels": eye_axis_labels,
                "unit_count_per_eye": int(simulator_input["unit_count_per_eye"]),
                "channel_order": channel_order,
            },
        )

    raise ValueError(
        "Unsupported selected_input_kind "
        f"{input_kind!r}. Supported sources: {list(SUPPORTED_CANONICAL_INPUT_SOURCES)!r}."
    )


def _validate_input_timing(
    *,
    input_kind: str,
    timebase: SimulationTimebase,
    sample_times_ms: np.ndarray,
    metadata_path: Path,
) -> None:
    expected_times = timebase.sample_times_ms()
    actual_times = np.asarray(sample_times_ms, dtype=np.float64)
    if expected_times.shape != actual_times.shape or not np.allclose(
        expected_times,
        actual_times,
        atol=_TIME_TOLERANCE_MS,
        rtol=0.0,
    ):
        raise ValueError(
            f"{input_kind} timing at {metadata_path} does not match the simulation timebase."
        )


def _build_drive_schedule(
    *,
    root_ids: Sequence[int],
    canonical_input_stream: CanonicalInputStream,
) -> BaselineDriveSchedule:
    normalized_root_ids = tuple(int(root_id) for root_id in root_ids)
    unit_count = canonical_input_stream.unit_count
    root_count = len(normalized_root_ids)
    unit_bins = tuple(
        tuple(int(index) for index in chunk.tolist())
        for chunk in np.array_split(np.arange(unit_count, dtype=np.int64), root_count)
    )
    if not unit_bins or any(not unit_bin for unit_bin in unit_bins):
        raise ValueError(
            "Canonical input stream unit count "
            f"{unit_count} is incompatible with selected-root roster length {root_count} "
            f"under {STABLE_CONTIGUOUS_MEAN_POOL!r}."
        )
    drive_values = np.empty(
        (canonical_input_stream.sample_count, root_count),
        dtype=np.float64,
    )
    for root_index, unit_bin in enumerate(unit_bins):
        drive_values[:, root_index] = np.mean(
            canonical_input_stream.centered_unit_values[:, list(unit_bin)],
            axis=1,
            dtype=np.float64,
        )
    drive_schedule_hash = _stable_hash(
        {
            "bundle_id": canonical_input_stream.bundle_id,
            "strategy": STABLE_CONTIGUOUS_MEAN_POOL,
            "root_ids": list(normalized_root_ids),
            "unit_bins": [list(unit_bin) for unit_bin in unit_bins],
            "drive_values": np.round(drive_values, decimals=12).tolist(),
        }
    )
    return BaselineDriveSchedule(
        root_ids=normalized_root_ids,
        strategy=STABLE_CONTIGUOUS_MEAN_POOL,
        drive_values=drive_values,
        unit_ids=canonical_input_stream.unit_ids,
        unit_bins=unit_bins,
        input_stream_bundle_id=canonical_input_stream.bundle_id,
        drive_schedule_hash=drive_schedule_hash,
    )


def _build_coupling_plan(
    *,
    arm_plan: Mapping[str, Any],
    root_ids: Sequence[int],
    baseline_family: BaselineNeuronFamily,
    timebase: SimulationTimebase,
) -> BaselineCouplingPlan:
    normalized_root_ids = tuple(int(root_id) for root_id in root_ids)
    root_index_by_id = {root_id: index for index, root_id in enumerate(normalized_root_ids)}
    edge_paths = _collect_selected_edge_paths(
        arm_plan=arm_plan,
        root_index_by_id=root_index_by_id,
    )

    component_records: list[dict[str, Any]] = []
    for pre_root_id, post_root_id in sorted(edge_paths):
        bundle_path = edge_paths[(pre_root_id, post_root_id)]
        if not bundle_path.exists():
            raise ValueError(
                "Selected circuit is missing the coupling bundle required for "
                f"{pre_root_id}->{post_root_id}: {bundle_path}."
            )
        bundle = load_edge_coupling_bundle(bundle_path)
        if bundle.pre_root_id != pre_root_id or bundle.post_root_id != post_root_id:
            raise ValueError(
                f"Coupling bundle at {bundle_path} does not match the expected edge "
                f"{pre_root_id}->{post_root_id}."
            )
        if bundle.component_table.empty:
            continue
        ordered_components = bundle.component_table.sort_values(
            ["component_index", "component_id"],
            kind="mergesort",
        ).reset_index(drop=True)
        for row in ordered_components.itertuples(index=False):
            weight = float(row.signed_weight_total)
            if not np.isfinite(weight):
                raise ValueError(
                    f"Coupling component {row.component_id!r} from {bundle_path} has a non-finite weight."
                )
            if abs(weight) <= 1.0e-15:
                continue
            component_records.append(
                {
                    "component_id": str(row.component_id),
                    "source_index": int(root_index_by_id[pre_root_id]),
                    "target_index": int(root_index_by_id[post_root_id]),
                    "source_root_id": int(pre_root_id),
                    "target_root_id": int(post_root_id),
                    "weight": weight,
                    "delay_steps": _resolve_delay_steps(
                        baseline_family=baseline_family,
                        delay_ms=float(row.delay_ms),
                        dt_ms=float(timebase.dt_ms),
                        component_id=str(row.component_id),
                    ),
                }
            )

    topology_condition = _require_nonempty_string(
        arm_plan.get("topology_condition", INTACT_TOPOLOGY_CONDITION),
        field_name="arm_plan.topology_condition",
    )
    if topology_condition not in SUPPORTED_TOPOLOGY_CONDITIONS:
        raise ValueError(
            "Unsupported arm_plan.topology_condition "
            f"{topology_condition!r}. Supported conditions: {list(SUPPORTED_TOPOLOGY_CONDITIONS)!r}."
        )
    if topology_condition == SHUFFLED_TOPOLOGY_CONDITION and len(component_records) > 1:
        shuffled_targets = _shuffle_target_assignments(
            component_records=component_records,
            seed=int(
                _require_mapping(
                    arm_plan.get("determinism"),
                    field_name="arm_plan.determinism",
                )["seed"]
            ),
        )
        for record, shuffled_target in zip(component_records, shuffled_targets, strict=True):
            record["target_index"] = int(shuffled_target)
            record["target_root_id"] = int(normalized_root_ids[int(shuffled_target)])

    delay_groups: list[BaselineDelayGroup] = []
    if component_records:
        records_by_delay: dict[int, list[dict[str, Any]]] = {}
        for record in component_records:
            records_by_delay.setdefault(int(record["delay_steps"]), []).append(record)
        for delay_steps in sorted(records_by_delay):
            delay_records = records_by_delay[delay_steps]
            delay_groups.append(
                BaselineDelayGroup(
                    delay_steps=delay_steps,
                    source_indices=np.asarray(
                        [record["source_index"] for record in delay_records],
                        dtype=np.int64,
                    ),
                    target_indices=np.asarray(
                        [record["target_index"] for record in delay_records],
                        dtype=np.int64,
                    ),
                    weights=np.asarray(
                        [record["weight"] for record in delay_records],
                        dtype=np.float64,
                    ),
                )
            )
    coupling_hash = _stable_hash(
        {
            "root_ids": list(normalized_root_ids),
            "topology_condition": topology_condition,
            "delay_groups": [
                {
                    "delay_steps": group.delay_steps,
                    "source_indices": group.source_indices.tolist(),
                    "target_indices": group.target_indices.tolist(),
                    "weights": np.round(group.weights, decimals=12).tolist(),
                }
                for group in delay_groups
            ],
        }
    )
    return BaselineCouplingPlan(
        root_ids=normalized_root_ids,
        topology_condition=topology_condition,
        shuffle_scope=(
            TARGET_ASSIGNMENT_SHUFFLE
            if topology_condition == SHUFFLED_TOPOLOGY_CONDITION and len(component_records) > 1
            else None
        ),
        delay_groups=tuple(delay_groups),
        coupling_hash=coupling_hash,
    )


def _collect_selected_edge_paths(
    *,
    arm_plan: Mapping[str, Any],
    root_index_by_id: Mapping[int, int],
) -> dict[tuple[int, int], Path]:
    circuit_assets = _require_mapping(
        arm_plan.get("circuit_assets"),
        field_name="arm_plan.circuit_assets",
    )
    selected_root_assets = _require_sequence(
        circuit_assets.get("selected_root_assets"),
        field_name="arm_plan.circuit_assets.selected_root_assets",
    )
    selected_root_ids = set(root_index_by_id)
    asset_root_ids: set[int] = set()
    edge_paths: dict[tuple[int, int], Path] = {}
    for index, asset in enumerate(selected_root_assets):
        root_asset = _require_mapping(
            asset,
            field_name=f"arm_plan.circuit_assets.selected_root_assets[{index}]",
        )
        root_id = int(root_asset.get("root_id"))
        if root_id not in selected_root_ids:
            raise ValueError(
                "circuit_assets.selected_root_assets contains root_id "
                f"{root_id} that is not present in selection.selected_root_ids."
            )
        asset_root_ids.add(root_id)
        for edge_index, edge_bundle in enumerate(
            _require_sequence(
                root_asset.get("edge_bundle_paths", []),
                field_name=(
                    f"arm_plan.circuit_assets.selected_root_assets[{index}].edge_bundle_paths"
                ),
            )
        ):
            edge_record = _require_mapping(
                edge_bundle,
                field_name=(
                    "arm_plan.circuit_assets.selected_root_assets"
                    f"[{index}].edge_bundle_paths[{edge_index}]"
                ),
            )
            if not bool(edge_record.get("selected_peer", False)):
                continue
            pre_root_id = int(edge_record.get("pre_root_id"))
            post_root_id = int(edge_record.get("post_root_id"))
            if pre_root_id not in selected_root_ids or post_root_id not in selected_root_ids:
                raise ValueError(
                    "Selected circuit edge "
                    f"{pre_root_id}->{post_root_id} is incompatible with the selected-root roster."
                )
            status = _require_nonempty_string(
                edge_record.get("status"),
                field_name="edge_bundle.status",
            )
            if status not in {"ready", "partial"}:
                raise ValueError(
                    "Selected circuit edge "
                    f"{pre_root_id}->{post_root_id} has unusable coupling status {status!r}."
                )
            edge_paths[(pre_root_id, post_root_id)] = Path(
                _require_nonempty_string(edge_record.get("path"), field_name="edge_bundle.path")
            ).resolve()
    if asset_root_ids != selected_root_ids:
        raise ValueError(
            "circuit_assets.selected_root_assets does not match selection.selected_root_ids."
        )
    return edge_paths


def _resolve_delay_steps(
    *,
    baseline_family: BaselineNeuronFamily,
    delay_ms: float,
    dt_ms: float,
    component_id: str,
) -> int:
    if baseline_family.spec.family != P1_BASELINE_FAMILY:
        return 0
    parameters = baseline_family.spec.parameters
    assert isinstance(parameters, P1BaselineParameters)
    if parameters.delay_handling.mode == DELAY_DISABLED_MODE:
        return 0
    if parameters.delay_handling.mode != DELAY_FROM_COUPLING_BUNDLE_MODE:
        raise ValueError(
            "Unsupported baseline P1 delay-handling mode "
            f"{parameters.delay_handling.mode!r}."
        )
    if not np.isfinite(delay_ms) or delay_ms < 0.0:
        raise ValueError(
            f"Coupling component {component_id!r} has an unusable delay_ms {delay_ms!r}."
        )
    delay_steps_float = float(delay_ms) / float(dt_ms)
    delay_steps = int(round(delay_steps_float))
    if abs(delay_steps_float - delay_steps) > _DELAY_STEP_TOLERANCE:
        raise ValueError(
            f"Coupling component {component_id!r} delay_ms={delay_ms} cannot be represented "
            f"on timebase.dt_ms={dt_ms}."
        )
    if delay_steps > int(parameters.delay_handling.max_supported_delay_steps):
        raise ValueError(
            f"Coupling component {component_id!r} delay_steps={delay_steps} exceeds the "
            "configured P1 maximum supported delay steps."
        )
    return delay_steps


def _shuffle_target_assignments(
    *,
    component_records: Sequence[Mapping[str, Any]],
    seed: int,
) -> np.ndarray:
    target_indices = np.asarray(
        [int(record["target_index"]) for record in component_records],
        dtype=np.int64,
    )
    if target_indices.size <= 1:
        return target_indices
    rng = np.random.Generator(np.random.PCG64(int(seed)))
    permutation = np.asarray(rng.permutation(target_indices.size), dtype=np.int64)
    if np.array_equal(permutation, np.arange(target_indices.size, dtype=np.int64)):
        permutation = np.roll(permutation, 1)
    return target_indices[permutation]


def _build_run_blueprint(
    *,
    arm_plan: Mapping[str, Any],
    timebase: SimulationTimebase,
    canonical_input_stream: CanonicalInputStream,
    drive_schedule: BaselineDriveSchedule,
    coupling_plan: BaselineCouplingPlan,
) -> SimulationRunBlueprint:
    runtime = _require_mapping(arm_plan.get("runtime"), field_name="arm_plan.runtime")
    selection = _require_mapping(arm_plan.get("selection"), field_name="arm_plan.selection")
    result_bundle_reference: Mapping[str, Any] | None = None
    result_bundle = arm_plan.get("result_bundle")
    if isinstance(result_bundle, Mapping):
        reference = result_bundle.get("reference")
        if isinstance(reference, Mapping):
            result_bundle_reference = reference
    metadata = {
        "execution_version": BASELINE_EXECUTION_VERSION,
        "runtime_config_version": runtime.get("config_version"),
        "time_unit": runtime.get("time_unit"),
        "selected_root_ids_hash": _stable_hash(list(selection.get("selected_root_ids", []))),
        "canonical_input": {
            "input_kind": canonical_input_stream.input_kind,
            "bundle_id": canonical_input_stream.bundle_id,
            "metadata_path": str(canonical_input_stream.metadata_path),
            "replay_source": canonical_input_stream.replay_source,
            "unit_count": canonical_input_stream.unit_count,
            "neutral_value": canonical_input_stream.neutral_value,
            "binding_strategy": drive_schedule.strategy,
            "drive_schedule_hash": drive_schedule.drive_schedule_hash,
        },
        "recurrent_coupling": {
            "topology_condition": coupling_plan.topology_condition,
            "shuffle_scope": coupling_plan.shuffle_scope,
            "component_count": coupling_plan.component_count,
            "max_delay_steps": coupling_plan.max_delay_steps,
            "coupling_hash": coupling_plan.coupling_hash,
        },
    }
    return build_simulation_run_blueprint(
        manifest_reference=_require_mapping(
            arm_plan.get("manifest_reference"),
            field_name="arm_plan.manifest_reference",
        ),
        arm_reference=_require_mapping(
            arm_plan.get("arm_reference"),
            field_name="arm_plan.arm_reference",
        ),
        root_ids=selection.get("selected_root_ids"),
        timebase=timebase,
        determinism=_require_mapping(
            arm_plan.get("determinism"),
            field_name="arm_plan.determinism",
        ),
        readout_catalog=_require_sequence(
            runtime.get("shared_readout_catalog", runtime.get("readout_catalog")),
            field_name="arm_plan.runtime.shared_readout_catalog",
        ),
        result_bundle_reference=result_bundle_reference,
        metadata=metadata,
    )


def _resolve_runtime_timebase(arm_plan: Mapping[str, Any]) -> SimulationTimebase:
    runtime = _require_mapping(arm_plan.get("runtime"), field_name="arm_plan.runtime")
    return SimulationTimebase.from_mapping(
        _require_mapping(runtime.get("timebase"), field_name="arm_plan.runtime.timebase")
    )


def _resolve_selected_root_ids(arm_plan: Mapping[str, Any]) -> tuple[int, ...]:
    selection = _require_mapping(arm_plan.get("selection"), field_name="arm_plan.selection")
    root_ids = selection.get("selected_root_ids")
    if not isinstance(root_ids, Sequence) or isinstance(root_ids, (str, bytes)):
        raise ValueError("arm_plan.selection.selected_root_ids must be a sequence.")
    normalized = tuple(int(root_id) for root_id in root_ids)
    if not normalized:
        raise ValueError("arm_plan.selection.selected_root_ids must contain at least one root ID.")
    if len(set(normalized)) != len(normalized):
        raise ValueError("arm_plan.selection.selected_root_ids contains duplicate root IDs.")
    return normalized


def _freeze_float_array(values: Any, *, field_name: str, ndim: int) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64).copy()
    if array.ndim != ndim:
        raise ValueError(f"{field_name} must be a {ndim}D float array.")
    array.setflags(write=False)
    return array


def _freeze_int_array(values: Any, *, field_name: str, ndim: int) -> np.ndarray:
    array = np.asarray(values, dtype=np.int64).copy()
    if array.ndim != ndim:
        raise ValueError(f"{field_name} must be a {ndim}D integer array.")
    array.setflags(write=False)
    return array


def _stable_hash(payload: Any) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


def _require_sequence(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence.")
    return value


def _require_nonempty_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


__all__ = [
    "BASELINE_EXECUTION_VERSION",
    "BaselineCouplingPlan",
    "BaselineDelayGroup",
    "BaselineDriveSchedule",
    "CanonicalInputStream",
    "INTACT_TOPOLOGY_CONDITION",
    "ResolvedBaselineExecutionPlan",
    "RETINAL_BUNDLE_INPUT_SOURCE",
    "SHUFFLED_TOPOLOGY_CONDITION",
    "STABLE_CONTIGUOUS_MEAN_POOL",
    "STIMULUS_BUNDLE_INPUT_SOURCE",
    "SUPPORTED_CANONICAL_INPUT_SOURCES",
    "SUPPORTED_TOPOLOGY_CONDITIONS",
    "TARGET_ASSIGNMENT_SHUFFLE",
    "build_drive_schedule_for_root_ids",
    "build_baseline_simulator_run_from_arm_plan",
    "load_canonical_input_stream_from_arm_plan",
    "resolve_baseline_execution_plan_from_arm_plan",
    "run_baseline_simulation_from_arm_plan",
]
