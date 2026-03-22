from __future__ import annotations

import sys
import unittest
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.simulator_result_contract import (
    P0_BASELINE_FAMILY,
    build_simulator_arm_reference,
    build_simulator_determinism,
    build_simulator_manifest_reference,
    build_simulator_readout_definition,
)
from flywire_wave.simulator_runtime import (
    FINALIZED_EVENT,
    INITIALIZED_EVENT,
    STEP_COMPLETED_EVENT,
    PerNeuronRuntimeState,
    SimulationLifecycleEvent,
    SimulationRunBlueprint,
    SimulationRuntimeState,
    SimulationStateSummaryRow,
    SimulationStepContext,
    SimulatorRun,
)


class SimulatorRuntimeTest(unittest.TestCase):
    def test_manual_lifecycle_exposes_snapshots_hooks_and_finalization_boundary(self) -> None:
        blueprint = _build_fixture_run_blueprint()
        event_log: list[tuple[str, int, float, int]] = []
        run = SimulatorRun(
            run_blueprint=blueprint,
            engine=_FixtureEngine(),
            drive_provider=_FixtureDriveProvider(),
            recurrent_input_provider=_FixtureRecurrentInputProvider(),
            hooks=[_record_event(event_log)],
        )

        with self.assertRaises(ValueError):
            run.extract_snapshot()

        initial_snapshot = run.initialize()
        self.assertEqual(initial_snapshot.lifecycle_stage, INITIALIZED_EVENT)
        self.assertEqual(initial_snapshot.root_ids, (202, 101))
        self.assertEqual(initial_snapshot.current_time_ms, 0.0)
        np.testing.assert_allclose(initial_snapshot.dynamic_state, [0.0, 0.0])
        np.testing.assert_allclose(initial_snapshot.exogenous_drive, [0.0, 0.0])
        np.testing.assert_allclose(initial_snapshot.recurrent_input, [0.0, 0.0])
        np.testing.assert_allclose(initial_snapshot.readout_values, [0.0, 0.0])
        self.assertEqual(run.readout_traces().captured_sample_count, 1)

        with self.assertRaises(ValueError):
            run.finalize()

        first_step_snapshot = run.step()
        self.assertEqual(first_step_snapshot.lifecycle_stage, STEP_COMPLETED_EVENT)
        self.assertEqual(first_step_snapshot.completed_steps, 1)
        self.assertEqual(first_step_snapshot.current_time_ms, 1.0)
        np.testing.assert_allclose(first_step_snapshot.dynamic_state, [1.0, 0.0])
        np.testing.assert_allclose(first_step_snapshot.exogenous_drive, [1.0, 0.0])
        np.testing.assert_allclose(first_step_snapshot.recurrent_input, [0.0, 0.0])

        second_step_snapshot = run.step()
        self.assertEqual(second_step_snapshot.completed_steps, 2)
        np.testing.assert_allclose(second_step_snapshot.dynamic_state, [0.5, 0.7])
        np.testing.assert_allclose(second_step_snapshot.exogenous_drive, [0.0, 0.5])
        np.testing.assert_allclose(second_step_snapshot.recurrent_input, [0.0, 0.2])

        inspection_snapshot = run.extract_snapshot()
        self.assertEqual(inspection_snapshot.lifecycle_stage, "inspection")
        self.assertEqual(
            inspection_snapshot.readout_mapping(),
            {
                "ordered_activity_gap": -0.19999999999999996,
                "shared_output_mean": 0.6,
            },
        )

        run.step()
        run.step()
        result = run.finalize()

        self.assertEqual(result.runtime_version, "simulator_runtime.v1")
        self.assertEqual(result.run_blueprint.arm_reference["arm_id"], "baseline_fixture")
        np.testing.assert_allclose(
            result.readout_traces.time_ms,
            [0.0, 1.0, 2.0, 3.0],
        )
        self.assertEqual(
            result.readout_traces.readout_ids,
            ("ordered_activity_gap", "shared_output_mean"),
        )
        np.testing.assert_allclose(
            result.readout_traces.values,
            [
                [0.0, 0.0],
                [1.0, 0.5],
                [-0.2, 0.6],
                [-0.445, 0.4025],
            ],
        )
        self.assertEqual(result.readout_traces.captured_sample_count, 4)
        np.testing.assert_allclose(
            result.final_snapshot.dynamic_state,
            [0.0275, 0.50475],
        )
        np.testing.assert_allclose(
            result.final_snapshot.readout_values,
            [-0.47725, 0.266125],
        )
        summary_records = result.final_snapshot.state_summary_records()
        self.assertEqual(
            [
                (
                    row["state_id"],
                    row["scope"],
                    row["summary_stat"],
                    row["units"],
                )
                for row in summary_records
            ],
            [
                ("circuit_dynamic_state", "circuit_output", "mean", "activation_au"),
                ("root_101", "per_neuron", "final", "activation_au"),
                ("root_202", "per_neuron", "final", "activation_au"),
            ],
        )
        np.testing.assert_allclose(
            [row["value"] for row in summary_records],
            [0.266125, 0.50475, 0.0275],
        )
        self.assertEqual(
            event_log,
            [
                (INITIALIZED_EVENT, 0, 0.0, 7),
                (STEP_COMPLETED_EVENT, 1, 1.0, 7),
                (STEP_COMPLETED_EVENT, 2, 2.0, 7),
                (STEP_COMPLETED_EVENT, 3, 3.0, 7),
                (STEP_COMPLETED_EVENT, 4, 4.0, 7),
                (FINALIZED_EVENT, 4, 4.0, 7),
            ],
        )

    def test_run_to_completion_is_deterministic_for_fixture_circuit(self) -> None:
        blueprint = _build_fixture_run_blueprint()

        result_a = SimulatorRun(
            run_blueprint=blueprint,
            engine=_FixtureEngine(),
            drive_provider=_FixtureDriveProvider(),
            recurrent_input_provider=_FixtureRecurrentInputProvider(),
        ).run_to_completion()
        result_b = SimulatorRun(
            run_blueprint=blueprint,
            engine=_FixtureEngine(),
            drive_provider=_FixtureDriveProvider(),
            recurrent_input_provider=_FixtureRecurrentInputProvider(),
        ).run_to_completion()

        np.testing.assert_allclose(
            result_a.readout_traces.values,
            result_b.readout_traces.values,
        )
        np.testing.assert_allclose(
            result_a.final_snapshot.dynamic_state,
            result_b.final_snapshot.dynamic_state,
        )
        self.assertEqual(
            result_a.final_snapshot.state_summary_records(),
            result_b.final_snapshot.state_summary_records(),
        )


def _build_fixture_run_blueprint() -> SimulationRunBlueprint:
    arm_plan = {
        "manifest_reference": build_simulator_manifest_reference(
            experiment_id="simulator_fixture_experiment",
            manifest_id="simulator_fixture_experiment",
            manifest_path=ROOT / "manifests" / "examples" / "milestone_1_demo.yaml",
            milestone="milestone_9",
        ),
        "arm_reference": build_simulator_arm_reference(
            arm_id="baseline_fixture",
            model_mode="baseline",
            baseline_family=P0_BASELINE_FAMILY,
            comparison_tags=["fixture", "deterministic"],
        ),
        "selection": {"selected_root_ids": [202, 101]},
        "runtime": {
            "config_version": "simulation_runtime.v1",
            "time_unit": "ms",
            "timebase": {
                "dt_ms": 1.0,
                "duration_ms": 4.0,
                "sample_count": 4,
                "time_origin_ms": 0.0,
            },
            "readout_catalog": [
                build_simulator_readout_definition(
                    readout_id="shared_output_mean",
                    scope="circuit_output",
                    aggregation="mean_over_root_ids",
                    units="activation_au",
                    value_semantics="shared_downstream_activation",
                ),
                build_simulator_readout_definition(
                    readout_id="ordered_activity_gap",
                    scope="comparison_panel",
                    aggregation="identity",
                    units="activation_au",
                    value_semantics="ordered_root_activity_gap",
                ),
            ],
        },
        "determinism": build_simulator_determinism(seed=7),
    }
    return SimulationRunBlueprint.from_arm_plan(arm_plan)


@dataclass
class _FixtureEngineState:
    leak: np.ndarray


class _FixtureEngine:
    def initialize_state(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        neuron_state: PerNeuronRuntimeState,
        context: SimulationStepContext,
        rng: np.random.Generator,
    ) -> _FixtureEngineState:
        del run_blueprint, context, rng
        neuron_state.dynamic_state[:] = 0.0
        neuron_state.readout_state[:] = 0.0
        return _FixtureEngineState(
            leak=np.asarray([0.5, 0.25], dtype=np.float64),
        )

    def step(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[_FixtureEngineState],
        context: SimulationStepContext,
    ) -> None:
        del run_blueprint
        state = runtime_state.neuron_state
        state.dynamic_state[:] = state.dynamic_state + context.dt_ms * (
            state.exogenous_drive
            + state.recurrent_input
            - runtime_state.engine_state.leak * state.dynamic_state
        )
        state.readout_state[:] = state.dynamic_state

    def collect_readouts(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[_FixtureEngineState],
        context: SimulationStepContext,
    ) -> dict[str, float]:
        del run_blueprint, context
        state = runtime_state.neuron_state.readout_state
        return {
            "shared_output_mean": float(np.mean(state)),
            "ordered_activity_gap": float(state[0] - state[1]),
        }

    def summarize_state(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[_FixtureEngineState],
        context: SimulationStepContext,
    ) -> list[SimulationStateSummaryRow]:
        del run_blueprint, context
        state = runtime_state.neuron_state.dynamic_state
        return [
            SimulationStateSummaryRow(
                state_id="root_202",
                scope="per_neuron",
                summary_stat="final",
                value=float(state[0]),
                units="activation_au",
            ),
            SimulationStateSummaryRow(
                state_id="circuit_dynamic_state",
                scope="circuit_output",
                summary_stat="mean",
                value=float(np.mean(state)),
                units="activation_au",
            ),
            SimulationStateSummaryRow(
                state_id="root_101",
                scope="per_neuron",
                summary_stat="final",
                value=float(state[1]),
                units="activation_au",
            ),
        ]

    def finalize(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[_FixtureEngineState],
        context: SimulationStepContext,
    ) -> None:
        del run_blueprint, runtime_state, context


class _FixtureDriveProvider:
    _schedule = np.asarray(
        [
            [1.0, 0.0],
            [0.0, 0.5],
            [0.0, 0.0],
            [0.0, 0.0],
        ],
        dtype=np.float64,
    )

    def resolve_exogenous_drive(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[_FixtureEngineState],
        context: SimulationStepContext,
    ) -> np.ndarray:
        del run_blueprint, runtime_state
        return np.asarray(self._schedule[context.completed_steps], dtype=np.float64)


class _FixtureRecurrentInputProvider:
    _weight_matrix = np.asarray(
        [
            [0.0, -0.1],
            [0.2, 0.0],
        ],
        dtype=np.float64,
    )

    def resolve_recurrent_input(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[_FixtureEngineState],
        context: SimulationStepContext,
    ) -> np.ndarray:
        del run_blueprint, context
        return np.asarray(
            self._weight_matrix @ runtime_state.neuron_state.readout_state,
            dtype=np.float64,
        )


def _record_event(
    sink: list[tuple[str, int, float, int]],
) -> Callable[[SimulationLifecycleEvent], None]:
    def _hook(event: SimulationLifecycleEvent) -> None:
        sink.append(
            (
                event.event_type,
                event.context.completed_steps,
                event.context.current_time_ms,
                event.context.determinism.seed,
            )
        )

    return _hook


if __name__ == "__main__":
    unittest.main()
