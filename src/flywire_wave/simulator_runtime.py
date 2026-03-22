from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar

import numpy as np

from .simulator_result_contract import (
    FIXED_STEP_UNIFORM_SAMPLING_MODE,
    normalize_simulator_timebase,
    parse_simulator_arm_reference,
    parse_simulator_manifest_reference,
    parse_simulator_readout_definition,
)
from .stimulus_contract import (
    DEFAULT_RNG_FAMILY,
    DEFAULT_TIME_UNIT,
    _normalize_float,
    _normalize_nonempty_string,
    _normalize_positive_int,
    _normalize_seed,
)


SIMULATOR_RUNTIME_VERSION = "simulator_runtime.v1"

INITIALIZED_EVENT = "initialized"
STEP_COMPLETED_EVENT = "step_completed"
FINALIZED_EVENT = "finalized"
SUPPORTED_LIFECYCLE_EVENTS = (
    INITIALIZED_EVENT,
    STEP_COMPLETED_EVENT,
    FINALIZED_EVENT,
)
SUPPORTED_RNG_FAMILIES = (DEFAULT_RNG_FAMILY,)


EngineStateT = TypeVar("EngineStateT")


@dataclass(frozen=True)
class SimulationTimebase:
    time_origin_ms: float
    dt_ms: float
    duration_ms: float
    sample_count: int
    sampling_mode: str = FIXED_STEP_UNIFORM_SAMPLING_MODE
    time_unit: str = DEFAULT_TIME_UNIT

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> SimulationTimebase:
        normalized = normalize_simulator_timebase(payload)
        return cls(
            time_origin_ms=float(normalized["time_origin_ms"]),
            dt_ms=float(normalized["dt_ms"]),
            duration_ms=float(normalized["duration_ms"]),
            sample_count=int(normalized["sample_count"]),
            sampling_mode=str(normalized["sampling_mode"]),
            time_unit=str(normalized["time_unit"]),
        )

    def time_ms_after_steps(self, completed_steps: int) -> float:
        normalized_steps = _normalize_completed_steps(
            completed_steps,
            sample_count=self.sample_count,
            field_name="completed_steps",
            allow_endpoint=True,
        )
        return float(self.time_origin_ms + normalized_steps * self.dt_ms)

    def sample_times_ms(self) -> np.ndarray:
        sample_indices = np.arange(self.sample_count, dtype=np.float64)
        return np.asarray(
            self.time_origin_ms + sample_indices * self.dt_ms,
            dtype=np.float64,
        )

    def as_mapping(self) -> dict[str, Any]:
        return {
            "time_unit": self.time_unit,
            "time_origin_ms": self.time_origin_ms,
            "dt_ms": self.dt_ms,
            "duration_ms": self.duration_ms,
            "sample_count": self.sample_count,
            "sampling_mode": self.sampling_mode,
        }


@dataclass(frozen=True)
class SimulationDeterminismContext:
    seed: int
    rng_family: str = DEFAULT_RNG_FAMILY
    seed_scope: str = "all_stochastic_simulator_components"

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> SimulationDeterminismContext:
        if not isinstance(payload, Mapping):
            raise ValueError("determinism must be a mapping.")
        seed = _normalize_seed(payload.get("seed"))
        rng_family = _normalize_nonempty_string(
            payload.get("rng_family", DEFAULT_RNG_FAMILY),
            field_name="determinism.rng_family",
        )
        if rng_family not in SUPPORTED_RNG_FAMILIES:
            raise ValueError(
                "Unsupported determinism.rng_family "
                f"{rng_family!r}. Supported families: {list(SUPPORTED_RNG_FAMILIES)!r}."
            )
        seed_scope = _normalize_nonempty_string(
            payload.get("seed_scope", "all_stochastic_simulator_components"),
            field_name="determinism.seed_scope",
        )
        return cls(
            seed=int(seed),
            rng_family=rng_family,
            seed_scope=seed_scope,
        )

    def build_rng(self) -> np.random.Generator:
        if self.rng_family == DEFAULT_RNG_FAMILY:
            return np.random.Generator(np.random.PCG64(self.seed))
        raise ValueError(
            "Unsupported determinism.rng_family "
            f"{self.rng_family!r}. Supported families: {list(SUPPORTED_RNG_FAMILIES)!r}."
        )

    def as_mapping(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "rng_family": self.rng_family,
            "seed_scope": self.seed_scope,
        }


@dataclass(frozen=True)
class SimulationReadoutDefinition:
    readout_id: str
    scope: str
    aggregation: str
    units: str
    value_semantics: str
    description: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> SimulationReadoutDefinition:
        normalized = parse_simulator_readout_definition(payload)
        description = normalized.get("description")
        return cls(
            readout_id=str(normalized["readout_id"]),
            scope=str(normalized["scope"]),
            aggregation=str(normalized["aggregation"]),
            units=str(normalized["units"]),
            value_semantics=str(normalized["value_semantics"]),
            description=str(description) if description is not None else None,
        )

    def as_mapping(self) -> dict[str, Any]:
        return {
            "readout_id": self.readout_id,
            "scope": self.scope,
            "aggregation": self.aggregation,
            "units": self.units,
            "value_semantics": self.value_semantics,
            "description": self.description,
        }


@dataclass(frozen=True)
class SimulationRunBlueprint:
    manifest_reference: dict[str, Any]
    arm_reference: dict[str, Any]
    root_ids: tuple[int, ...]
    timebase: SimulationTimebase
    determinism: SimulationDeterminismContext
    readout_catalog: tuple[SimulationReadoutDefinition, ...]
    result_bundle_reference: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_arm_plan(cls, arm_plan: Mapping[str, Any]) -> SimulationRunBlueprint:
        return build_simulation_run_blueprint_from_arm_plan(arm_plan)

    @property
    def readout_id_order(self) -> tuple[str, ...]:
        return tuple(item.readout_id for item in self.readout_catalog)

    @property
    def neuron_count(self) -> int:
        return len(self.root_ids)


@dataclass(frozen=True)
class SimulationStateSummaryRow:
    state_id: str
    scope: str
    summary_stat: str
    value: float
    units: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "state_id",
            _normalize_nonempty_string(self.state_id, field_name="state_summary.state_id"),
        )
        object.__setattr__(
            self,
            "scope",
            _normalize_nonempty_string(self.scope, field_name="state_summary.scope"),
        )
        object.__setattr__(
            self,
            "summary_stat",
            _normalize_nonempty_string(
                self.summary_stat,
                field_name="state_summary.summary_stat",
            ),
        )
        object.__setattr__(
            self,
            "value",
            _normalize_float(self.value, field_name="state_summary.value"),
        )
        object.__setattr__(
            self,
            "units",
            _normalize_nonempty_string(self.units, field_name="state_summary.units"),
        )

    def as_record(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "scope": self.scope,
            "summary_stat": self.summary_stat,
            "value": self.value,
            "units": self.units,
        }


@dataclass
class PerNeuronRuntimeState:
    root_ids: tuple[int, ...]
    dynamic_state: np.ndarray
    exogenous_drive: np.ndarray
    recurrent_input: np.ndarray
    readout_state: np.ndarray

    def __post_init__(self) -> None:
        self.root_ids = _normalize_root_ids(self.root_ids, field_name="root_ids")
        neuron_count = len(self.root_ids)
        self.dynamic_state = _normalize_vector(
            self.dynamic_state,
            expected_length=neuron_count,
            field_name="dynamic_state",
        )
        self.exogenous_drive = _normalize_vector(
            self.exogenous_drive,
            expected_length=neuron_count,
            field_name="exogenous_drive",
        )
        self.recurrent_input = _normalize_vector(
            self.recurrent_input,
            expected_length=neuron_count,
            field_name="recurrent_input",
        )
        self.readout_state = _normalize_vector(
            self.readout_state,
            expected_length=neuron_count,
            field_name="readout_state",
        )

    @classmethod
    def zeros(cls, root_ids: Sequence[int]) -> PerNeuronRuntimeState:
        normalized_root_ids = _normalize_root_ids(root_ids, field_name="root_ids")
        zeros = np.zeros(len(normalized_root_ids), dtype=np.float64)
        return cls(
            root_ids=normalized_root_ids,
            dynamic_state=zeros.copy(),
            exogenous_drive=zeros.copy(),
            recurrent_input=zeros.copy(),
            readout_state=zeros.copy(),
        )

    @property
    def neuron_count(self) -> int:
        return len(self.root_ids)

    def copy(self) -> PerNeuronRuntimeState:
        return PerNeuronRuntimeState(
            root_ids=self.root_ids,
            dynamic_state=self.dynamic_state.copy(),
            exogenous_drive=self.exogenous_drive.copy(),
            recurrent_input=self.recurrent_input.copy(),
            readout_state=self.readout_state.copy(),
        )

    def clear_inputs(self) -> None:
        self.exogenous_drive.fill(0.0)
        self.recurrent_input.fill(0.0)

    def set_exogenous_drive(self, values: Sequence[float] | np.ndarray) -> None:
        self.exogenous_drive[:] = _normalize_vector(
            values,
            expected_length=self.neuron_count,
            field_name="exogenous_drive",
        )

    def set_recurrent_input(self, values: Sequence[float] | np.ndarray) -> None:
        self.recurrent_input[:] = _normalize_vector(
            values,
            expected_length=self.neuron_count,
            field_name="recurrent_input",
        )

    def total_input(self) -> np.ndarray:
        return np.asarray(
            self.exogenous_drive + self.recurrent_input,
            dtype=np.float64,
        )


@dataclass
class SimulationRuntimeState(Generic[EngineStateT]):
    run_blueprint: SimulationRunBlueprint
    neuron_state: PerNeuronRuntimeState
    engine_state: EngineStateT
    completed_steps: int
    current_time_ms: float

    @property
    def has_pending_steps(self) -> bool:
        return self.completed_steps < self.run_blueprint.timebase.sample_count


@dataclass(frozen=True)
class SimulationStepContext:
    runtime_version: str
    timebase: SimulationTimebase
    determinism: SimulationDeterminismContext
    completed_steps: int
    current_time_ms: float
    event_type: str | None = None

    @property
    def dt_ms(self) -> float:
        return self.timebase.dt_ms

    @property
    def sample_count(self) -> int:
        return self.timebase.sample_count

    @property
    def has_pending_steps(self) -> bool:
        return self.completed_steps < self.timebase.sample_count


@dataclass(frozen=True)
class SimulationSnapshot:
    lifecycle_stage: str
    completed_steps: int
    current_time_ms: float
    dt_ms: float
    root_ids: tuple[int, ...]
    dynamic_state: np.ndarray
    exogenous_drive: np.ndarray
    recurrent_input: np.ndarray
    readout_state: np.ndarray
    readout_ids: tuple[str, ...]
    readout_values: np.ndarray
    state_summaries: tuple[SimulationStateSummaryRow, ...]

    def readout_mapping(self) -> dict[str, float]:
        return {
            readout_id: float(self.readout_values[index])
            for index, readout_id in enumerate(self.readout_ids)
        }

    def state_summary_records(self) -> list[dict[str, Any]]:
        return [row.as_record() for row in self.state_summaries]


@dataclass(frozen=True)
class SimulationLifecycleEvent:
    event_type: str
    context: SimulationStepContext
    snapshot: SimulationSnapshot


@dataclass(frozen=True)
class SimulationReadoutTraces:
    time_ms: np.ndarray
    readout_ids: tuple[str, ...]
    values: np.ndarray
    captured_sample_count: int

    def as_numpy_archive_payload(self) -> dict[str, np.ndarray]:
        return {
            "time_ms": np.asarray(self.time_ms, dtype=np.float64),
            "readout_ids": np.asarray(self.readout_ids),
            "values": np.asarray(self.values, dtype=np.float64),
        }


@dataclass(frozen=True)
class SimulationRunResult:
    runtime_version: str
    run_blueprint: SimulationRunBlueprint
    initial_snapshot: SimulationSnapshot
    final_snapshot: SimulationSnapshot
    readout_traces: SimulationReadoutTraces

    @property
    def state_summaries(self) -> tuple[SimulationStateSummaryRow, ...]:
        return self.final_snapshot.state_summaries


SimulationHook = Callable[[SimulationLifecycleEvent], None]


class SimulationEngine(Protocol[EngineStateT]):
    def initialize_state(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        neuron_state: PerNeuronRuntimeState,
        context: SimulationStepContext,
        rng: np.random.Generator,
    ) -> EngineStateT: ...

    def step(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[EngineStateT],
        context: SimulationStepContext,
    ) -> None: ...

    def collect_readouts(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[EngineStateT],
        context: SimulationStepContext,
    ) -> Mapping[str, Any]: ...

    def summarize_state(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[EngineStateT],
        context: SimulationStepContext,
    ) -> Sequence[SimulationStateSummaryRow]: ...

    def finalize(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[EngineStateT],
        context: SimulationStepContext,
    ) -> None: ...


class SimulationDriveProvider(Protocol[EngineStateT]):
    def resolve_exogenous_drive(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[EngineStateT],
        context: SimulationStepContext,
    ) -> Sequence[float] | np.ndarray: ...


class SimulationRecurrentInputProvider(Protocol[EngineStateT]):
    def resolve_recurrent_input(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[EngineStateT],
        context: SimulationStepContext,
    ) -> Sequence[float] | np.ndarray: ...


class SimulatorRun(Generic[EngineStateT]):
    def __init__(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        engine: SimulationEngine[EngineStateT],
        drive_provider: SimulationDriveProvider[EngineStateT] | None = None,
        recurrent_input_provider: SimulationRecurrentInputProvider[EngineStateT] | None = None,
        hooks: Sequence[SimulationHook] | None = None,
    ) -> None:
        self._run_blueprint = run_blueprint
        self._engine = engine
        self._drive_provider = drive_provider
        self._recurrent_input_provider = recurrent_input_provider
        self._hooks = tuple(hooks or [])
        self._rng = run_blueprint.determinism.build_rng()
        self._runtime_state: SimulationRuntimeState[EngineStateT] | None = None
        self._initial_snapshot: SimulationSnapshot | None = None
        self._final_result: SimulationRunResult | None = None
        self._captured_sample_count = 0
        self._readout_trace_values = np.full(
            (run_blueprint.timebase.sample_count, len(run_blueprint.readout_catalog)),
            np.nan,
            dtype=np.float64,
        )

    @property
    def run_blueprint(self) -> SimulationRunBlueprint:
        return self._run_blueprint

    @property
    def is_initialized(self) -> bool:
        return self._runtime_state is not None

    @property
    def is_finalized(self) -> bool:
        return self._final_result is not None

    @property
    def completed_steps(self) -> int:
        if self._runtime_state is None:
            return 0
        return self._runtime_state.completed_steps

    @property
    def current_time_ms(self) -> float:
        if self._runtime_state is None:
            return self._run_blueprint.timebase.time_origin_ms
        return self._runtime_state.current_time_ms

    @property
    def has_pending_steps(self) -> bool:
        if self._runtime_state is None:
            return True
        return self._runtime_state.has_pending_steps

    @property
    def runtime_state(self) -> SimulationRuntimeState[EngineStateT]:
        runtime_state = self._runtime_state
        if runtime_state is None:
            raise ValueError("SimulatorRun has not been initialized.")
        return runtime_state

    def current_context(self, *, event_type: str | None = None) -> SimulationStepContext:
        if event_type is not None and event_type not in SUPPORTED_LIFECYCLE_EVENTS:
            raise ValueError(
                "Unsupported event_type "
                f"{event_type!r}. Supported events: {list(SUPPORTED_LIFECYCLE_EVENTS)!r}."
            )
        return SimulationStepContext(
            runtime_version=SIMULATOR_RUNTIME_VERSION,
            timebase=self._run_blueprint.timebase,
            determinism=self._run_blueprint.determinism,
            completed_steps=self.completed_steps,
            current_time_ms=self.current_time_ms,
            event_type=event_type,
        )

    def initialize(self) -> SimulationSnapshot:
        if self._runtime_state is not None:
            raise ValueError("SimulatorRun has already been initialized.")
        initial_context = self.current_context(event_type=INITIALIZED_EVENT)
        neuron_state = PerNeuronRuntimeState.zeros(self._run_blueprint.root_ids)
        engine_state = self._engine.initialize_state(
            run_blueprint=self._run_blueprint,
            neuron_state=neuron_state,
            context=initial_context,
            rng=self._rng,
        )
        self._runtime_state = SimulationRuntimeState(
            run_blueprint=self._run_blueprint,
            neuron_state=neuron_state,
            engine_state=engine_state,
            completed_steps=0,
            current_time_ms=self._run_blueprint.timebase.time_origin_ms,
        )
        self._capture_current_sample()
        initial_snapshot = self._build_snapshot(INITIALIZED_EVENT)
        self._initial_snapshot = initial_snapshot
        self._emit_event(INITIALIZED_EVENT, initial_snapshot)
        return initial_snapshot

    def step(self) -> SimulationSnapshot:
        runtime_state = self.runtime_state
        if self._final_result is not None:
            raise ValueError("SimulatorRun has already been finalized.")
        if not runtime_state.has_pending_steps:
            raise ValueError("SimulatorRun has already completed all configured steps.")

        step_context = self.current_context()
        runtime_state.neuron_state.clear_inputs()
        runtime_state.neuron_state.set_exogenous_drive(
            self._resolve_exogenous_drive(runtime_state, step_context)
        )
        runtime_state.neuron_state.set_recurrent_input(
            self._resolve_recurrent_input(runtime_state, step_context)
        )
        self._engine.step(
            run_blueprint=self._run_blueprint,
            runtime_state=runtime_state,
            context=step_context,
        )
        runtime_state.completed_steps += 1
        runtime_state.current_time_ms = self._run_blueprint.timebase.time_ms_after_steps(
            runtime_state.completed_steps
        )
        if runtime_state.completed_steps < self._run_blueprint.timebase.sample_count:
            self._capture_current_sample()
        snapshot = self._build_snapshot(STEP_COMPLETED_EVENT)
        self._emit_event(STEP_COMPLETED_EVENT, snapshot)
        return snapshot

    def run_to_completion(self) -> SimulationRunResult:
        if self._runtime_state is None:
            self.initialize()
        while self.has_pending_steps:
            self.step()
        return self.finalize()

    def finalize(self) -> SimulationRunResult:
        if self._final_result is not None:
            return self._final_result
        runtime_state = self.runtime_state
        if runtime_state.has_pending_steps:
            raise ValueError("SimulatorRun cannot finalize before all configured steps complete.")
        finalize_context = self.current_context(event_type=FINALIZED_EVENT)
        self._engine.finalize(
            run_blueprint=self._run_blueprint,
            runtime_state=runtime_state,
            context=finalize_context,
        )
        final_snapshot = self._build_snapshot(FINALIZED_EVENT)
        result = SimulationRunResult(
            runtime_version=SIMULATOR_RUNTIME_VERSION,
            run_blueprint=self._run_blueprint,
            initial_snapshot=self._initial_snapshot
            if self._initial_snapshot is not None
            else self._build_snapshot(INITIALIZED_EVENT),
            final_snapshot=final_snapshot,
            readout_traces=self.readout_traces(),
        )
        self._final_result = result
        self._emit_event(FINALIZED_EVENT, final_snapshot)
        return result

    def extract_snapshot(self, *, lifecycle_stage: str = "inspection") -> SimulationSnapshot:
        if self._runtime_state is None:
            raise ValueError("SimulatorRun has not been initialized.")
        return self._build_snapshot(lifecycle_stage)

    def readout_traces(self) -> SimulationReadoutTraces:
        return SimulationReadoutTraces(
            time_ms=_freeze_array(self._run_blueprint.timebase.sample_times_ms()),
            readout_ids=self._run_blueprint.readout_id_order,
            values=_freeze_array(self._readout_trace_values),
            captured_sample_count=self._captured_sample_count,
        )

    def _resolve_exogenous_drive(
        self,
        runtime_state: SimulationRuntimeState[EngineStateT],
        context: SimulationStepContext,
    ) -> np.ndarray:
        if self._drive_provider is None:
            return np.zeros(self._run_blueprint.neuron_count, dtype=np.float64)
        return _normalize_vector(
            self._drive_provider.resolve_exogenous_drive(
                run_blueprint=self._run_blueprint,
                runtime_state=runtime_state,
                context=context,
            ),
            expected_length=self._run_blueprint.neuron_count,
            field_name="exogenous_drive",
        )

    def _resolve_recurrent_input(
        self,
        runtime_state: SimulationRuntimeState[EngineStateT],
        context: SimulationStepContext,
    ) -> np.ndarray:
        if self._recurrent_input_provider is None:
            return np.zeros(self._run_blueprint.neuron_count, dtype=np.float64)
        return _normalize_vector(
            self._recurrent_input_provider.resolve_recurrent_input(
                run_blueprint=self._run_blueprint,
                runtime_state=runtime_state,
                context=context,
            ),
            expected_length=self._run_blueprint.neuron_count,
            field_name="recurrent_input",
        )

    def _capture_current_sample(self) -> None:
        runtime_state = self.runtime_state
        if self._captured_sample_count >= self._run_blueprint.timebase.sample_count:
            return
        readout_values = self._ordered_readout_values(runtime_state)
        self._readout_trace_values[self._captured_sample_count, :] = readout_values
        self._captured_sample_count += 1

    def _build_snapshot(self, lifecycle_stage: str) -> SimulationSnapshot:
        runtime_state = self.runtime_state
        context = self.current_context(
            event_type=lifecycle_stage if lifecycle_stage in SUPPORTED_LIFECYCLE_EVENTS else None
        )
        ordered_readout_values = self._ordered_readout_values(runtime_state)
        state_summaries = tuple(
            sorted(
                (
                    _normalize_state_summary_row(item)
                    for item in self._engine.summarize_state(
                        run_blueprint=self._run_blueprint,
                        runtime_state=runtime_state,
                        context=context,
                    )
                ),
                key=lambda item: (
                    item.scope,
                    item.state_id,
                    item.summary_stat,
                    item.units,
                ),
            )
        )
        return SimulationSnapshot(
            lifecycle_stage=lifecycle_stage,
            completed_steps=runtime_state.completed_steps,
            current_time_ms=runtime_state.current_time_ms,
            dt_ms=self._run_blueprint.timebase.dt_ms,
            root_ids=runtime_state.neuron_state.root_ids,
            dynamic_state=_freeze_array(runtime_state.neuron_state.dynamic_state),
            exogenous_drive=_freeze_array(runtime_state.neuron_state.exogenous_drive),
            recurrent_input=_freeze_array(runtime_state.neuron_state.recurrent_input),
            readout_state=_freeze_array(runtime_state.neuron_state.readout_state),
            readout_ids=self._run_blueprint.readout_id_order,
            readout_values=_freeze_array(ordered_readout_values),
            state_summaries=state_summaries,
        )

    def _ordered_readout_values(
        self,
        runtime_state: SimulationRuntimeState[EngineStateT],
    ) -> np.ndarray:
        context = self.current_context()
        raw_values = self._engine.collect_readouts(
            run_blueprint=self._run_blueprint,
            runtime_state=runtime_state,
            context=context,
        )
        if not isinstance(raw_values, Mapping):
            raise ValueError("engine.collect_readouts must return a mapping keyed by readout_id.")
        normalized_values = {
            str(readout_id): _normalize_float(
                value,
                field_name=f"readout_values.{readout_id}",
            )
            for readout_id, value in raw_values.items()
        }
        missing_ids = [
            readout_id
            for readout_id in self._run_blueprint.readout_id_order
            if readout_id not in normalized_values
        ]
        if missing_ids:
            raise ValueError(
                "engine.collect_readouts did not return values for "
                f"required readout ids: {missing_ids!r}."
            )
        unexpected_ids = sorted(
            set(normalized_values) - set(self._run_blueprint.readout_id_order)
        )
        if unexpected_ids:
            raise ValueError(
                "engine.collect_readouts returned unsupported readout ids: "
                f"{unexpected_ids!r}."
            )
        return np.asarray(
            [
                normalized_values[readout_id]
                for readout_id in self._run_blueprint.readout_id_order
            ],
            dtype=np.float64,
        )

    def _emit_event(self, event_type: str, snapshot: SimulationSnapshot) -> None:
        event = SimulationLifecycleEvent(
            event_type=event_type,
            context=self.current_context(event_type=event_type),
            snapshot=snapshot,
        )
        for hook in self._hooks:
            hook(event)


def build_simulation_run_blueprint(
    *,
    manifest_reference: Mapping[str, Any],
    arm_reference: Mapping[str, Any],
    root_ids: Sequence[int],
    timebase: Mapping[str, Any] | SimulationTimebase,
    determinism: Mapping[str, Any] | SimulationDeterminismContext,
    readout_catalog: Sequence[Mapping[str, Any] | SimulationReadoutDefinition],
    result_bundle_reference: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> SimulationRunBlueprint:
    normalized_manifest_reference = parse_simulator_manifest_reference(manifest_reference)
    normalized_arm_reference = parse_simulator_arm_reference(arm_reference)
    normalized_root_ids = _normalize_root_ids(root_ids, field_name="root_ids")
    normalized_timebase = (
        timebase
        if isinstance(timebase, SimulationTimebase)
        else SimulationTimebase.from_mapping(timebase)
    )
    normalized_determinism = (
        determinism
        if isinstance(determinism, SimulationDeterminismContext)
        else SimulationDeterminismContext.from_mapping(determinism)
    )
    normalized_readout_catalog = tuple(_normalize_readout_catalog(readout_catalog))
    normalized_bundle_reference = (
        copy.deepcopy(dict(result_bundle_reference))
        if isinstance(result_bundle_reference, Mapping)
        else None
    )
    return SimulationRunBlueprint(
        manifest_reference=copy.deepcopy(normalized_manifest_reference),
        arm_reference=copy.deepcopy(normalized_arm_reference),
        root_ids=normalized_root_ids,
        timebase=normalized_timebase,
        determinism=normalized_determinism,
        readout_catalog=normalized_readout_catalog,
        result_bundle_reference=normalized_bundle_reference,
        metadata=copy.deepcopy(dict(metadata or {})),
    )


def build_simulation_run_blueprint_from_arm_plan(
    arm_plan: Mapping[str, Any],
) -> SimulationRunBlueprint:
    if not isinstance(arm_plan, Mapping):
        raise ValueError("arm_plan must be a mapping.")
    runtime = arm_plan.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ValueError("arm_plan.runtime must be a mapping.")
    selection = arm_plan.get("selection")
    if not isinstance(selection, Mapping):
        raise ValueError("arm_plan.selection must be a mapping.")
    result_bundle = arm_plan.get("result_bundle")
    result_bundle_reference: Mapping[str, Any] | None = None
    if isinstance(result_bundle, Mapping):
        candidate_reference = result_bundle.get("reference")
        if isinstance(candidate_reference, Mapping):
            result_bundle_reference = candidate_reference
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
        timebase=_require_mapping(runtime.get("timebase"), field_name="arm_plan.runtime.timebase"),
        determinism=_require_mapping(arm_plan.get("determinism"), field_name="arm_plan.determinism"),
        readout_catalog=_require_sequence(
            runtime.get("readout_catalog"),
            field_name="arm_plan.runtime.readout_catalog",
        ),
        result_bundle_reference=result_bundle_reference,
        metadata={
            "runtime_config_version": runtime.get("config_version"),
            "time_unit": runtime.get("time_unit", DEFAULT_TIME_UNIT),
        },
    )


def _normalize_root_ids(value: Any, *, field_name: str) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of root IDs.")
    normalized = [int(_normalize_positive_int(item, field_name=field_name)) for item in value]
    if not normalized:
        raise ValueError(f"{field_name} must contain at least one root ID.")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} contains duplicate root IDs.")
    return tuple(normalized)


def _normalize_vector(
    values: Any,
    *,
    expected_length: int,
    field_name: str,
) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{field_name} must be a 1D vector.")
    if array.shape[0] != expected_length:
        raise ValueError(
            f"{field_name} must have length {expected_length}, got {array.shape[0]}."
        )
    return np.asarray(array, dtype=np.float64).copy()


def _freeze_array(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64).copy()
    array.setflags(write=False)
    return array


def _normalize_completed_steps(
    value: Any,
    *,
    sample_count: int,
    field_name: str,
    allow_endpoint: bool,
) -> int:
    normalized = int(_normalize_positive_int(int(value) + 1, field_name=field_name) - 1)
    maximum = sample_count if allow_endpoint else sample_count - 1
    if normalized < 0 or normalized > maximum:
        comparator = "<=" if allow_endpoint else "<"
        raise ValueError(
            f"{field_name} must satisfy 0 <= value {comparator} {maximum}."
        )
    return normalized


def _normalize_readout_catalog(
    payload: Sequence[Mapping[str, Any] | SimulationReadoutDefinition],
) -> list[SimulationReadoutDefinition]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("readout_catalog must be a sequence.")
    normalized = [
        item if isinstance(item, SimulationReadoutDefinition) else SimulationReadoutDefinition.from_mapping(item)
        for item in payload
    ]
    if not normalized:
        raise ValueError("readout_catalog must contain at least one readout definition.")
    sorted_catalog = sorted(
        normalized,
        key=lambda item: (item.readout_id, item.scope, item.aggregation),
    )
    seen_readout_ids: set[str] = set()
    for item in sorted_catalog:
        if item.readout_id in seen_readout_ids:
            raise ValueError(
                f"readout_catalog contains duplicate readout_id {item.readout_id!r}."
            )
        seen_readout_ids.add(item.readout_id)
    return sorted_catalog


def _normalize_state_summary_row(
    value: SimulationStateSummaryRow | Mapping[str, Any],
) -> SimulationStateSummaryRow:
    if isinstance(value, SimulationStateSummaryRow):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("state summary rows must be SimulationStateSummaryRow instances or mappings.")
    return SimulationStateSummaryRow(
        state_id=value.get("state_id"),
        scope=value.get("scope"),
        summary_stat=value.get("summary_stat"),
        value=value.get("value"),
        units=value.get("units"),
    )


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


def _require_sequence(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence.")
    return value


__all__ = [
    "FINALIZED_EVENT",
    "INITIALIZED_EVENT",
    "PerNeuronRuntimeState",
    "SIMULATOR_RUNTIME_VERSION",
    "STEP_COMPLETED_EVENT",
    "SUPPORTED_LIFECYCLE_EVENTS",
    "SUPPORTED_RNG_FAMILIES",
    "SimulationDeterminismContext",
    "SimulationDriveProvider",
    "SimulationEngine",
    "SimulationHook",
    "SimulationLifecycleEvent",
    "SimulationReadoutDefinition",
    "SimulationReadoutTraces",
    "SimulationRecurrentInputProvider",
    "SimulationRunBlueprint",
    "SimulationRunResult",
    "SimulationRuntimeState",
    "SimulationSnapshot",
    "SimulationStateSummaryRow",
    "SimulationStepContext",
    "SimulationTimebase",
    "SimulatorRun",
    "build_simulation_run_blueprint",
    "build_simulation_run_blueprint_from_arm_plan",
]
