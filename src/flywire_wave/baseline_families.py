"""Canonical Milestone 9 baseline neuron families.

The library-owned software realizations are:

- P0: tau_m * dV/dt = -(V - V_rest) + g_in * U + g_rec * R
- P1: tau_s * dI/dt = -I + g_in * U + g_rec * R
       tau_m * dV/dt = -(V - V_rest) + I

Both families expose the same shared readout source: the membrane-state
readout `V`. This keeps downstream shared-observable comparisons on one fair
surface instead of family-specific decoders.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from .simulator_result_contract import (
    P0_BASELINE_FAMILY,
    P1_BASELINE_FAMILY,
)
from .simulator_runtime import (
    PerNeuronRuntimeState,
    SimulationEngine,
    SimulationReadoutDefinition,
    SimulationRunBlueprint,
    SimulationRuntimeState,
    SimulationStateSummaryRow,
    SimulationStepContext,
)
from .stimulus_contract import (
    _normalize_float,
    _normalize_identifier,
    _normalize_nonempty_string,
    _normalize_positive_float,
    _normalize_positive_int,
)


P0_MODEL_FAMILY = "passive_linear_single_compartment"
P1_MODEL_FAMILY = "reduced_linear_with_synaptic_current"

P0_STATE_LAYOUT = "scalar_state_per_selected_root"
P1_STATE_LAYOUT = "membrane_state_and_synaptic_current_per_selected_root"

FORWARD_EULER_INTEGRATION = "forward_euler"
ZERO_INITIAL_STATE = "all_zero"
MEMBRANE_READOUT_STATE = "membrane_state"
SYNAPTIC_CURRENT_STATE = "synaptic_current_state"

DELAY_DISABLED_MODE = "disabled"
DELAY_FROM_COUPLING_BUNDLE_MODE = "from_coupling_bundle"
SUPPORTED_P1_DELAY_MODES = (
    DELAY_DISABLED_MODE,
    DELAY_FROM_COUPLING_BUNDLE_MODE,
)

SHARED_DOWNSTREAM_ACTIVATION = "shared_downstream_activation"
SUPPORTED_SHARED_READOUT_SEMANTICS = (SHARED_DOWNSTREAM_ACTIVATION,)
SUPPORTED_SHARED_READOUT_AGGREGATIONS = (
    "identity",
    "max_over_root_ids",
    "mean_over_root_ids",
    "sum_over_root_ids",
)
ACTIVATION_UNITS = "activation_au"

_SPEC_REQUIRED_KEYS = {
    "family",
    "model_family",
    "state_layout",
    "integration_scheme",
    "readout_state",
    "initial_state",
    "parameters",
}
_P0_PARAMETER_KEYS = {
    "membrane_time_constant_ms",
    "resting_potential",
    "input_gain",
    "recurrent_gain",
}
_P1_PARAMETER_KEYS = {
    "membrane_time_constant_ms",
    "synaptic_current_time_constant_ms",
    "resting_potential",
    "input_gain",
    "recurrent_gain",
    "delay_handling",
}
_P1_DELAY_HANDLING_KEYS = {
    "mode",
    "max_supported_delay_steps",
}


@dataclass(frozen=True)
class P0BaselineParameters:
    membrane_time_constant_ms: float
    resting_potential: float
    input_gain: float
    recurrent_gain: float


@dataclass(frozen=True)
class P1DelayHandling:
    mode: str
    max_supported_delay_steps: int


@dataclass(frozen=True)
class P1BaselineParameters:
    membrane_time_constant_ms: float
    synaptic_current_time_constant_ms: float
    resting_potential: float
    input_gain: float
    recurrent_gain: float
    delay_handling: P1DelayHandling


@dataclass(frozen=True)
class BaselineStateVariable:
    state_id: str
    units: str
    description: str


@dataclass(frozen=True)
class BaselineReadoutMapping:
    readout_id: str
    source_state: str
    aggregation: str
    units: str
    value_semantics: str
    description: str | None = None


@dataclass(frozen=True)
class BaselineFamilySpec:
    family: str
    model_family: str
    state_layout: str
    integration_scheme: str
    readout_state: str
    initial_state: str
    parameters: P0BaselineParameters | P1BaselineParameters

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> BaselineFamilySpec:
        if not isinstance(payload, Mapping):
            raise ValueError("baseline model_spec must be a mapping.")
        raw_payload = dict(payload)
        unknown_keys = sorted(set(raw_payload) - _SPEC_REQUIRED_KEYS)
        if unknown_keys:
            raise ValueError(
                "baseline model_spec contains unsupported keys: "
                f"{unknown_keys!r}."
            )
        missing_keys = sorted(_SPEC_REQUIRED_KEYS - set(raw_payload))
        if missing_keys:
            raise ValueError(
                "baseline model_spec is missing required keys: "
                f"{missing_keys!r}."
            )

        family = _normalize_nonempty_string(
            raw_payload["family"],
            field_name="model_spec.family",
        )
        model_family = _normalize_identifier(
            raw_payload["model_family"],
            field_name="model_spec.model_family",
        )
        state_layout = _normalize_identifier(
            raw_payload["state_layout"],
            field_name="model_spec.state_layout",
        )
        integration_scheme = _normalize_identifier(
            raw_payload["integration_scheme"],
            field_name="model_spec.integration_scheme",
        )
        readout_state = _normalize_identifier(
            raw_payload["readout_state"],
            field_name="model_spec.readout_state",
        )
        initial_state = _normalize_identifier(
            raw_payload["initial_state"],
            field_name="model_spec.initial_state",
        )
        raw_parameters = raw_payload["parameters"]
        if not isinstance(raw_parameters, Mapping):
            raise ValueError("model_spec.parameters must be a mapping.")

        if family == P0_BASELINE_FAMILY:
            parameters = _normalize_p0_parameters(raw_parameters)
            _validate_supported_layout(
                family=family,
                model_family=model_family,
                expected_model_family=P0_MODEL_FAMILY,
                state_layout=state_layout,
                expected_state_layout=P0_STATE_LAYOUT,
                integration_scheme=integration_scheme,
                readout_state=readout_state,
                initial_state=initial_state,
            )
        elif family == P1_BASELINE_FAMILY:
            parameters = _normalize_p1_parameters(raw_parameters)
            _validate_supported_layout(
                family=family,
                model_family=model_family,
                expected_model_family=P1_MODEL_FAMILY,
                state_layout=state_layout,
                expected_state_layout=P1_STATE_LAYOUT,
                integration_scheme=integration_scheme,
                readout_state=readout_state,
                initial_state=initial_state,
            )
        else:
            raise ValueError(
                "Unsupported baseline family "
                f"{family!r}. Supported families: {[P0_BASELINE_FAMILY, P1_BASELINE_FAMILY]!r}."
            )

        # The Milestone 9 normalized family specs only support zero-initialized
        # runs. A nonzero resting potential would silently introduce a hidden
        # initial offset, so reject that configuration instead of mutating it.
        if parameters.resting_potential != 0.0:
            raise ValueError(
                "baseline model_spec.initial_state='all_zero' requires "
                "parameters.resting_potential == 0.0."
            )

        return cls(
            family=family,
            model_family=model_family,
            state_layout=state_layout,
            integration_scheme=integration_scheme,
            readout_state=readout_state,
            initial_state=initial_state,
            parameters=parameters,
        )

    @property
    def state_variables(self) -> tuple[BaselineStateVariable, ...]:
        if self.family == P0_BASELINE_FAMILY:
            return (
                BaselineStateVariable(
                    state_id=MEMBRANE_READOUT_STATE,
                    units=ACTIVATION_UNITS,
                    description=(
                        "Per-neuron passive membrane state used for the shared readout."
                    ),
                ),
            )
        return (
            BaselineStateVariable(
                state_id=MEMBRANE_READOUT_STATE,
                units=ACTIVATION_UNITS,
                description=(
                    "Per-neuron membrane state used for the shared readout."
                ),
            ),
            BaselineStateVariable(
                state_id=SYNAPTIC_CURRENT_STATE,
                units=ACTIVATION_UNITS,
                description=(
                    "Per-neuron synaptic integration current for the reduced P1 baseline."
                ),
            ),
        )


@dataclass(frozen=True)
class BaselineNeuronFamily:
    spec: BaselineFamilySpec
    state_variables: tuple[BaselineStateVariable, ...]
    shared_readout_mappings: tuple[BaselineReadoutMapping, ...]

    def build_engine(self) -> SimulationEngine[Any]:
        if self.spec.family == P0_BASELINE_FAMILY:
            return _P0BaselineEngine(
                spec=self.spec,
                readout_mappings=self.shared_readout_mappings,
            )
        return _P1BaselineEngine(
            spec=self.spec,
            readout_mappings=self.shared_readout_mappings,
        )


@dataclass
class _P0EngineState:
    readout_mappings: tuple[BaselineReadoutMapping, ...]


@dataclass
class _P1EngineState:
    synaptic_current: np.ndarray
    readout_mappings: tuple[BaselineReadoutMapping, ...]
    delay_handling: P1DelayHandling


def resolve_baseline_neuron_family(
    model_spec: Mapping[str, Any],
    *,
    readout_catalog: Sequence[Mapping[str, Any] | SimulationReadoutDefinition],
) -> BaselineNeuronFamily:
    spec = BaselineFamilySpec.from_mapping(model_spec)
    shared_readout_mappings = _normalize_shared_readout_mappings(readout_catalog)
    return BaselineNeuronFamily(
        spec=spec,
        state_variables=spec.state_variables,
        shared_readout_mappings=shared_readout_mappings,
    )


def resolve_baseline_neuron_family_from_arm_plan(
    arm_plan: Mapping[str, Any],
) -> BaselineNeuronFamily:
    if not isinstance(arm_plan, Mapping):
        raise ValueError("arm_plan must be a mapping.")
    model_configuration = arm_plan.get("model_configuration")
    if not isinstance(model_configuration, Mapping):
        raise ValueError("arm_plan.model_configuration must be a mapping.")
    runtime = arm_plan.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ValueError("arm_plan.runtime must be a mapping.")
    baseline_parameters = model_configuration.get("baseline_parameters")
    if not isinstance(baseline_parameters, Mapping):
        raise ValueError(
            "arm_plan.model_configuration.baseline_parameters must be a mapping."
        )
    readout_catalog = runtime.get("readout_catalog")
    if not isinstance(readout_catalog, Sequence) or isinstance(
        readout_catalog,
        (str, bytes),
    ):
        raise ValueError("arm_plan.runtime.readout_catalog must be a sequence.")
    return resolve_baseline_neuron_family(
        baseline_parameters,
        readout_catalog=readout_catalog,
    )


class _BaseBaselineEngine(SimulationEngine[Any]):
    def __init__(
        self,
        *,
        spec: BaselineFamilySpec,
        readout_mappings: Sequence[BaselineReadoutMapping],
    ) -> None:
        self._spec = spec
        self._readout_mappings = tuple(readout_mappings)

    def collect_readouts(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[Any],
        context: SimulationStepContext,
    ) -> Mapping[str, Any]:
        del run_blueprint, context
        readout_state = runtime_state.neuron_state.readout_state
        return {
            mapping.readout_id: _aggregate_shared_readout(
                readout_state=readout_state,
                aggregation=mapping.aggregation,
            )
            for mapping in self._readout_mappings
        }

    def finalize(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[Any],
        context: SimulationStepContext,
    ) -> None:
        del run_blueprint, runtime_state, context

    def _validate_timebase(self, context: SimulationStepContext, *, max_dt_ms: float) -> None:
        dt_ms = float(context.dt_ms)
        if dt_ms > max_dt_ms:
            raise ValueError(
                "baseline forward_euler integration requires "
                f"timebase.dt_ms <= {max_dt_ms}, got {dt_ms}."
            )


class _P0BaselineEngine(_BaseBaselineEngine):
    def initialize_state(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        neuron_state: PerNeuronRuntimeState,
        context: SimulationStepContext,
        rng: np.random.Generator,
    ) -> _P0EngineState:
        del run_blueprint, rng
        parameters = self._p0_parameters
        self._validate_timebase(
            context,
            max_dt_ms=parameters.membrane_time_constant_ms,
        )
        neuron_state.dynamic_state.fill(0.0)
        neuron_state.readout_state.fill(0.0)
        return _P0EngineState(readout_mappings=self._readout_mappings)

    def step(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[_P0EngineState],
        context: SimulationStepContext,
    ) -> None:
        del run_blueprint
        parameters = self._p0_parameters
        state = runtime_state.neuron_state
        total_drive = (
            parameters.input_gain * state.exogenous_drive
            + parameters.recurrent_gain * state.recurrent_input
        )
        membrane = state.dynamic_state
        membrane[:] = membrane + (
            context.dt_ms / parameters.membrane_time_constant_ms
        ) * (
            parameters.resting_potential
            - membrane
            + total_drive
        )
        state.readout_state[:] = membrane

    def summarize_state(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[_P0EngineState],
        context: SimulationStepContext,
    ) -> Sequence[SimulationStateSummaryRow]:
        del context
        return _build_vector_state_summary_rows(
            root_ids=run_blueprint.root_ids,
            values=runtime_state.neuron_state.dynamic_state,
            state_prefix=MEMBRANE_READOUT_STATE,
        )

    @property
    def _p0_parameters(self) -> P0BaselineParameters:
        parameters = self._spec.parameters
        assert isinstance(parameters, P0BaselineParameters)
        return parameters


class _P1BaselineEngine(_BaseBaselineEngine):
    def initialize_state(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        neuron_state: PerNeuronRuntimeState,
        context: SimulationStepContext,
        rng: np.random.Generator,
    ) -> _P1EngineState:
        del run_blueprint, rng
        parameters = self._p1_parameters
        self._validate_timebase(
            context,
            max_dt_ms=min(
                parameters.membrane_time_constant_ms,
                parameters.synaptic_current_time_constant_ms,
            ),
        )
        neuron_state.dynamic_state.fill(0.0)
        neuron_state.readout_state.fill(0.0)
        return _P1EngineState(
            synaptic_current=np.zeros(neuron_state.neuron_count, dtype=np.float64),
            readout_mappings=self._readout_mappings,
            delay_handling=parameters.delay_handling,
        )

    def step(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[_P1EngineState],
        context: SimulationStepContext,
    ) -> None:
        del run_blueprint
        parameters = self._p1_parameters
        state = runtime_state.neuron_state
        total_drive = (
            parameters.input_gain * state.exogenous_drive
            + parameters.recurrent_gain * state.recurrent_input
        )
        synaptic_current = runtime_state.engine_state.synaptic_current
        synaptic_current[:] = synaptic_current + (
            context.dt_ms / parameters.synaptic_current_time_constant_ms
        ) * (
            -synaptic_current + total_drive
        )
        membrane = state.dynamic_state
        membrane[:] = membrane + (
            context.dt_ms / parameters.membrane_time_constant_ms
        ) * (
            parameters.resting_potential
            - membrane
            + synaptic_current
        )
        state.readout_state[:] = membrane

    def summarize_state(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[_P1EngineState],
        context: SimulationStepContext,
    ) -> Sequence[SimulationStateSummaryRow]:
        del context
        rows = list(
            _build_vector_state_summary_rows(
                root_ids=run_blueprint.root_ids,
                values=runtime_state.neuron_state.dynamic_state,
                state_prefix=MEMBRANE_READOUT_STATE,
            )
        )
        rows.extend(
            _build_vector_state_summary_rows(
                root_ids=run_blueprint.root_ids,
                values=runtime_state.engine_state.synaptic_current,
                state_prefix=SYNAPTIC_CURRENT_STATE,
            )
        )
        return rows

    @property
    def _p1_parameters(self) -> P1BaselineParameters:
        parameters = self._spec.parameters
        assert isinstance(parameters, P1BaselineParameters)
        return parameters


def _normalize_p0_parameters(payload: Mapping[str, Any]) -> P0BaselineParameters:
    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - _P0_PARAMETER_KEYS)
    if unknown_keys:
        raise ValueError(
            "P0 parameters contain unsupported keys: "
            f"{unknown_keys!r}."
        )
    missing_keys = sorted(_P0_PARAMETER_KEYS - set(raw_payload))
    if missing_keys:
        raise ValueError(f"P0 parameters are missing required keys: {missing_keys!r}.")
    return P0BaselineParameters(
        membrane_time_constant_ms=_normalize_positive_float(
            raw_payload["membrane_time_constant_ms"],
            field_name="P0.parameters.membrane_time_constant_ms",
        ),
        resting_potential=_normalize_float(
            raw_payload["resting_potential"],
            field_name="P0.parameters.resting_potential",
        ),
        input_gain=_normalize_float(
            raw_payload["input_gain"],
            field_name="P0.parameters.input_gain",
        ),
        recurrent_gain=_normalize_float(
            raw_payload["recurrent_gain"],
            field_name="P0.parameters.recurrent_gain",
        ),
    )


def _normalize_p1_parameters(payload: Mapping[str, Any]) -> P1BaselineParameters:
    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - _P1_PARAMETER_KEYS)
    if unknown_keys:
        raise ValueError(
            "P1 parameters contain unsupported keys: "
            f"{unknown_keys!r}."
        )
    missing_keys = sorted(_P1_PARAMETER_KEYS - set(raw_payload))
    if missing_keys:
        raise ValueError(f"P1 parameters are missing required keys: {missing_keys!r}.")
    delay_handling = raw_payload["delay_handling"]
    if not isinstance(delay_handling, Mapping):
        raise ValueError("P1.parameters.delay_handling must be a mapping.")
    return P1BaselineParameters(
        membrane_time_constant_ms=_normalize_positive_float(
            raw_payload["membrane_time_constant_ms"],
            field_name="P1.parameters.membrane_time_constant_ms",
        ),
        synaptic_current_time_constant_ms=_normalize_positive_float(
            raw_payload["synaptic_current_time_constant_ms"],
            field_name="P1.parameters.synaptic_current_time_constant_ms",
        ),
        resting_potential=_normalize_float(
            raw_payload["resting_potential"],
            field_name="P1.parameters.resting_potential",
        ),
        input_gain=_normalize_float(
            raw_payload["input_gain"],
            field_name="P1.parameters.input_gain",
        ),
        recurrent_gain=_normalize_float(
            raw_payload["recurrent_gain"],
            field_name="P1.parameters.recurrent_gain",
        ),
        delay_handling=_normalize_p1_delay_handling(delay_handling),
    )


def _normalize_p1_delay_handling(payload: Mapping[str, Any]) -> P1DelayHandling:
    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - _P1_DELAY_HANDLING_KEYS)
    if unknown_keys:
        raise ValueError(
            "P1 delay_handling contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    missing_keys = sorted(_P1_DELAY_HANDLING_KEYS - set(raw_payload))
    if missing_keys:
        raise ValueError(
            "P1 delay_handling is missing required keys: "
            f"{missing_keys!r}."
        )
    mode = _normalize_identifier(raw_payload["mode"], field_name="P1.delay_handling.mode")
    if mode not in SUPPORTED_P1_DELAY_MODES:
        raise ValueError(
            "Unsupported P1.delay_handling.mode "
            f"{mode!r}. Supported modes: {list(SUPPORTED_P1_DELAY_MODES)!r}."
        )
    return P1DelayHandling(
        mode=mode,
        max_supported_delay_steps=_normalize_positive_int(
            raw_payload["max_supported_delay_steps"],
            field_name="P1.delay_handling.max_supported_delay_steps",
        ),
    )


def _validate_supported_layout(
    *,
    family: str,
    model_family: str,
    expected_model_family: str,
    state_layout: str,
    expected_state_layout: str,
    integration_scheme: str,
    readout_state: str,
    initial_state: str,
) -> None:
    if model_family != expected_model_family:
        raise ValueError(
            f"{family} model_spec.model_family must be {expected_model_family!r}, "
            f"got {model_family!r}."
        )
    if state_layout != expected_state_layout:
        raise ValueError(
            f"{family} model_spec.state_layout must be {expected_state_layout!r}, "
            f"got {state_layout!r}."
        )
    if integration_scheme != FORWARD_EULER_INTEGRATION:
        raise ValueError(
            f"{family} model_spec.integration_scheme must be "
            f"{FORWARD_EULER_INTEGRATION!r}, got {integration_scheme!r}."
        )
    if readout_state != MEMBRANE_READOUT_STATE:
        raise ValueError(
            f"{family} model_spec.readout_state must be "
            f"{MEMBRANE_READOUT_STATE!r}, got {readout_state!r}."
        )
    if initial_state != ZERO_INITIAL_STATE:
        raise ValueError(
            f"{family} model_spec.initial_state must be {ZERO_INITIAL_STATE!r}, "
            f"got {initial_state!r}."
        )


def _normalize_shared_readout_mappings(
    readout_catalog: Sequence[Mapping[str, Any] | SimulationReadoutDefinition],
) -> tuple[BaselineReadoutMapping, ...]:
    if not isinstance(readout_catalog, Sequence) or isinstance(readout_catalog, (str, bytes)):
        raise ValueError("readout_catalog must be a sequence.")
    normalized: list[BaselineReadoutMapping] = []
    for item in readout_catalog:
        readout = (
            item
            if isinstance(item, SimulationReadoutDefinition)
            else SimulationReadoutDefinition.from_mapping(item)
        )
        if readout.value_semantics not in SUPPORTED_SHARED_READOUT_SEMANTICS:
            raise ValueError(
                "Baseline families support only shared readout semantics "
                f"{list(SUPPORTED_SHARED_READOUT_SEMANTICS)!r}; got "
                f"{readout.value_semantics!r} for readout_id {readout.readout_id!r}."
            )
        if readout.aggregation not in SUPPORTED_SHARED_READOUT_AGGREGATIONS:
            raise ValueError(
                "Unsupported shared readout aggregation "
                f"{readout.aggregation!r} for readout_id {readout.readout_id!r}. "
                f"Supported aggregations: {list(SUPPORTED_SHARED_READOUT_AGGREGATIONS)!r}."
            )
        if readout.units != ACTIVATION_UNITS:
            raise ValueError(
                "Baseline shared readouts must use units "
                f"{ACTIVATION_UNITS!r}; got {readout.units!r} "
                f"for readout_id {readout.readout_id!r}."
            )
        normalized.append(
            BaselineReadoutMapping(
                readout_id=readout.readout_id,
                source_state=MEMBRANE_READOUT_STATE,
                aggregation=readout.aggregation,
                units=readout.units,
                value_semantics=readout.value_semantics,
                description=readout.description,
            )
        )
    if not normalized:
        raise ValueError("readout_catalog must contain at least one shared readout.")
    return tuple(normalized)


def _aggregate_shared_readout(
    *,
    readout_state: np.ndarray,
    aggregation: str,
) -> float:
    if aggregation == "mean_over_root_ids":
        return float(np.mean(readout_state))
    if aggregation == "sum_over_root_ids":
        return float(np.sum(readout_state))
    if aggregation == "max_over_root_ids":
        return float(np.max(readout_state))
    if aggregation == "identity":
        if readout_state.shape[0] != 1:
            raise ValueError(
                "shared readout aggregation 'identity' requires exactly one selected root."
            )
        return float(readout_state[0])
    raise ValueError(f"Unsupported shared readout aggregation {aggregation!r}.")


def _build_vector_state_summary_rows(
    *,
    root_ids: Sequence[int],
    values: np.ndarray,
    state_prefix: str,
) -> list[SimulationStateSummaryRow]:
    rows = [
        SimulationStateSummaryRow(
            state_id=f"circuit_{state_prefix}",
            scope="circuit_output",
            summary_stat="mean",
            value=float(np.mean(values)),
            units=ACTIVATION_UNITS,
        )
    ]
    for root_id, value in zip(root_ids, values, strict=True):
        rows.append(
            SimulationStateSummaryRow(
                state_id=f"root_{int(root_id)}_{state_prefix}",
                scope="per_neuron",
                summary_stat="final",
                value=float(value),
                units=ACTIVATION_UNITS,
            )
        )
    return rows


__all__ = [
    "ACTIVATION_UNITS",
    "BaselineFamilySpec",
    "BaselineNeuronFamily",
    "BaselineReadoutMapping",
    "BaselineStateVariable",
    "DELAY_DISABLED_MODE",
    "DELAY_FROM_COUPLING_BUNDLE_MODE",
    "FORWARD_EULER_INTEGRATION",
    "MEMBRANE_READOUT_STATE",
    "P0BaselineParameters",
    "P1BaselineParameters",
    "P1DelayHandling",
    "SHARED_DOWNSTREAM_ACTIVATION",
    "SYNAPTIC_CURRENT_STATE",
    "resolve_baseline_neuron_family",
    "resolve_baseline_neuron_family_from_arm_plan",
]
