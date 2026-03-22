from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.baseline_families import (
    DELAY_FROM_COUPLING_BUNDLE_MODE,
    MEMBRANE_READOUT_STATE,
    SYNAPTIC_CURRENT_STATE,
    resolve_baseline_neuron_family,
    resolve_baseline_neuron_family_from_arm_plan,
)
from flywire_wave.simulation_planning import default_baseline_family_configs
from flywire_wave.simulator_result_contract import (
    P0_BASELINE_FAMILY,
    P1_BASELINE_FAMILY,
    build_simulator_arm_reference,
    build_simulator_determinism,
    build_simulator_manifest_reference,
    build_simulator_readout_definition,
)
from flywire_wave.simulator_runtime import (
    SimulationRunBlueprint,
    SimulationRuntimeState,
    SimulationStepContext,
    SimulatorRun,
)


class BaselineFamiliesTest(unittest.TestCase):
    def test_p0_family_uses_passive_membrane_dynamics_with_shared_readout_aggregations(self) -> None:
        family_spec = copy.deepcopy(default_baseline_family_configs()[P0_BASELINE_FAMILY])
        family_spec["parameters"]["membrane_time_constant_ms"] = 4.0
        family_spec["parameters"]["input_gain"] = 2.0
        family_spec["parameters"]["recurrent_gain"] = 0.0
        arm_plan = _build_arm_plan(
            family_spec=family_spec,
            readout_catalog=[
                build_simulator_readout_definition(
                    readout_id="shared_output_mean",
                    scope="circuit_output",
                    aggregation="mean_over_root_ids",
                    units="activation_au",
                    value_semantics="shared_downstream_activation",
                    description="Shared downstream mean output.",
                ),
                build_simulator_readout_definition(
                    readout_id="shared_output_sum",
                    scope="circuit_output",
                    aggregation="sum_over_root_ids",
                    units="activation_au",
                    value_semantics="shared_downstream_activation",
                    description="Shared downstream summed output.",
                ),
            ],
            root_ids=[101, 202],
            sample_count=4,
            dt_ms=1.0,
        )

        family = resolve_baseline_neuron_family_from_arm_plan(arm_plan)
        self.assertEqual(family.spec.family, P0_BASELINE_FAMILY)
        self.assertEqual(
            tuple(variable.state_id for variable in family.state_variables),
            (MEMBRANE_READOUT_STATE,),
        )
        self.assertEqual(
            {
                mapping.readout_id: mapping.aggregation
                for mapping in family.shared_readout_mappings
            },
            {
                "shared_output_mean": "mean_over_root_ids",
                "shared_output_sum": "sum_over_root_ids",
            },
        )

        run = SimulatorRun(
            run_blueprint=SimulationRunBlueprint.from_arm_plan(arm_plan),
            engine=family.build_engine(),
            drive_provider=_SequenceDriveProvider(
                [
                    [1.0, 0.0],
                    [1.0, 0.0],
                    [1.0, 0.0],
                    [1.0, 0.0],
                ]
            ),
        )
        result = run.run_to_completion()

        np.testing.assert_allclose(
            result.readout_traces.values,
            [
                [0.0, 0.0],
                [0.25, 0.5],
                [0.4375, 0.875],
                [0.578125, 1.15625],
            ],
        )
        np.testing.assert_allclose(
            result.final_snapshot.dynamic_state,
            [1.3671875, 0.0],
        )
        np.testing.assert_allclose(
            result.final_snapshot.readout_values,
            [0.68359375, 1.3671875],
        )
        summary_by_state = {
            row["state_id"]: row["value"] for row in result.final_snapshot.state_summary_records()
        }
        self.assertEqual(
            sorted(summary_by_state),
            [
                "circuit_membrane_state",
                "root_101_membrane_state",
                "root_202_membrane_state",
            ],
        )
        self.assertAlmostEqual(summary_by_state["circuit_membrane_state"], 0.68359375)
        self.assertAlmostEqual(summary_by_state["root_101_membrane_state"], 1.3671875)
        self.assertAlmostEqual(summary_by_state["root_202_membrane_state"], 0.0)

    def test_p1_family_adds_synaptic_current_and_identity_shared_readout(self) -> None:
        family_spec = copy.deepcopy(default_baseline_family_configs()[P1_BASELINE_FAMILY])
        family_spec["parameters"]["membrane_time_constant_ms"] = 4.0
        family_spec["parameters"]["synaptic_current_time_constant_ms"] = 2.0
        family_spec["parameters"]["input_gain"] = 1.0
        family_spec["parameters"]["recurrent_gain"] = 0.0
        arm_plan = _build_arm_plan(
            family_spec=family_spec,
            readout_catalog=[
                build_simulator_readout_definition(
                    readout_id="shared_output_identity",
                    scope="circuit_output",
                    aggregation="identity",
                    units="activation_au",
                    value_semantics="shared_downstream_activation",
                    description="Shared downstream output for a one-root fixture.",
                )
            ],
            root_ids=[101],
            sample_count=4,
            dt_ms=1.0,
        )

        family = resolve_baseline_neuron_family_from_arm_plan(arm_plan)
        self.assertEqual(family.spec.family, P1_BASELINE_FAMILY)
        self.assertEqual(
            tuple(variable.state_id for variable in family.state_variables),
            (MEMBRANE_READOUT_STATE, SYNAPTIC_CURRENT_STATE),
        )
        self.assertEqual(
            family.spec.parameters.delay_handling.mode,
            DELAY_FROM_COUPLING_BUNDLE_MODE,
        )

        run = SimulatorRun(
            run_blueprint=SimulationRunBlueprint.from_arm_plan(arm_plan),
            engine=family.build_engine(),
            drive_provider=_SequenceDriveProvider(
                [
                    [1.0],
                    [0.0],
                    [0.0],
                    [0.0],
                ]
            ),
        )
        result = run.run_to_completion()

        np.testing.assert_allclose(
            result.readout_traces.values[:, 0],
            [0.0, 0.125, 0.15625, 0.1484375],
        )
        np.testing.assert_allclose(
            result.final_snapshot.dynamic_state,
            [0.126953125],
        )
        np.testing.assert_allclose(
            result.final_snapshot.readout_values,
            [0.126953125],
        )
        summary_by_state = {
            row["state_id"]: row["value"] for row in result.final_snapshot.state_summary_records()
        }
        self.assertAlmostEqual(summary_by_state["circuit_membrane_state"], 0.126953125)
        self.assertAlmostEqual(summary_by_state["root_101_membrane_state"], 0.126953125)
        self.assertAlmostEqual(summary_by_state["circuit_synaptic_current_state"], 0.0625)
        self.assertAlmostEqual(summary_by_state["root_101_synaptic_current_state"], 0.0625)

    def test_invalid_or_non_shared_specs_fail_clearly(self) -> None:
        p0_spec = copy.deepcopy(default_baseline_family_configs()[P0_BASELINE_FAMILY])
        p0_spec["parameters"]["resting_potential"] = 1.0
        with self.assertRaises(ValueError) as resting_ctx:
            resolve_baseline_neuron_family(
                p0_spec,
                readout_catalog=[_shared_mean_readout()],
            )
        self.assertIn("resting_potential == 0.0", str(resting_ctx.exception))

        p1_spec = copy.deepcopy(default_baseline_family_configs()[P1_BASELINE_FAMILY])
        p1_spec["parameters"]["delay_handling"]["mode"] = "mystery_delay"
        with self.assertRaises(ValueError) as delay_ctx:
            resolve_baseline_neuron_family(
                p1_spec,
                readout_catalog=[_shared_mean_readout()],
            )
        self.assertIn("Unsupported P1.delay_handling.mode", str(delay_ctx.exception))

        with self.assertRaises(ValueError) as readout_ctx:
            resolve_baseline_neuron_family(
                default_baseline_family_configs()[P0_BASELINE_FAMILY],
                readout_catalog=[
                    build_simulator_readout_definition(
                        readout_id="direction_selectivity_index",
                        scope="comparison_panel",
                        aggregation="identity",
                        units="unitless",
                        value_semantics="direction_selectivity_index",
                        description="Derived metric, not a shared per-step readout.",
                    )
                ],
            )
        self.assertIn("support only shared readout semantics", str(readout_ctx.exception))


class _SequenceDriveProvider:
    def __init__(self, samples: list[list[float]]) -> None:
        self._samples = [np.asarray(sample, dtype=np.float64) for sample in samples]

    def resolve_exogenous_drive(
        self,
        *,
        run_blueprint: SimulationRunBlueprint,
        runtime_state: SimulationRuntimeState[object],
        context: SimulationStepContext,
    ) -> np.ndarray:
        del run_blueprint, context
        step_index = runtime_state.completed_steps
        if step_index >= len(self._samples):
            return np.zeros(runtime_state.neuron_state.neuron_count, dtype=np.float64)
        return np.asarray(self._samples[step_index], dtype=np.float64)


def _build_arm_plan(
    *,
    family_spec: dict[str, object],
    readout_catalog: list[dict[str, object]],
    root_ids: list[int],
    sample_count: int,
    dt_ms: float,
) -> dict[str, object]:
    return {
        "manifest_reference": build_simulator_manifest_reference(
            experiment_id="baseline_family_fixture",
            manifest_id="baseline_family_fixture",
            manifest_path=ROOT / "manifests" / "examples" / "milestone_1_demo.yaml",
            milestone="milestone_9",
        ),
        "arm_reference": build_simulator_arm_reference(
            arm_id=f"baseline_{family_spec['family'].lower()}_fixture",
            model_mode="baseline",
            baseline_family=str(family_spec["family"]),
            comparison_tags=["fixture"],
        ),
        "selection": {"selected_root_ids": list(root_ids)},
        "runtime": {
            "config_version": "simulation_runtime.v1",
            "time_unit": "ms",
            "timebase": {
                "time_origin_ms": 0.0,
                "dt_ms": float(dt_ms),
                "duration_ms": float(sample_count) * float(dt_ms),
                "sample_count": int(sample_count),
            },
            "readout_catalog": copy.deepcopy(readout_catalog),
        },
        "determinism": build_simulator_determinism(seed=13),
        "model_configuration": {
            "model_mode": "baseline",
            "baseline_family": str(family_spec["family"]),
            "baseline_parameters": copy.deepcopy(family_spec),
        },
    }


def _shared_mean_readout() -> dict[str, object]:
    return build_simulator_readout_definition(
        readout_id="shared_output_mean",
        scope="circuit_output",
        aggregation="mean_over_root_ids",
        units="activation_au",
        value_semantics="shared_downstream_activation",
        description="Shared downstream mean output.",
    )


if __name__ == "__main__":
    unittest.main()
