from __future__ import annotations

import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.geometry_contract import (
    CLAMPED_BOUNDARY_CONDITION_MODE,
    DEFAULT_BOUNDARY_CONDITION_MODE,
)
from flywire_wave.surface_wave_contract import build_surface_wave_model_metadata
from flywire_wave.surface_wave_solver import SurfaceWaveOperatorBundle
from flywire_wave.simulation_planning import resolve_manifest_simulation_plan
from flywire_wave.simulator_execution import execute_manifest_simulation
from flywire_wave.validation_numerics import (
    NumericalValidationCase,
    execute_numerical_validation_workflow,
    run_numerical_validation_suite,
)
from flywire_wave.validation_planning import resolve_validation_plan

try:
    from test_simulator_execution import _materialize_execution_fixture
except ModuleNotFoundError:
    from tests.test_simulator_execution import _materialize_execution_fixture


class NumericalValidationSuiteTest(unittest.TestCase):
    def test_fixture_suite_emits_stable_and_tripwire_findings_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            simulator_results_dir = tmp_dir / "simulator_results"

            stable_case = NumericalValidationCase(
                case_id="stable_linear_case",
                arm_id="fixture_stable",
                root_id=101,
                surface_wave_model=_build_linear_fixture_model("stable_fixture"),
                reference_operator_bundle=_build_reference_bundle(root_id=101),
                integration_timestep_ms=0.2,
                shared_output_timestep_ms=0.2,
                shared_step_count=6,
                pulse_seed_vertex=1,
                timestep_sweep_factors=(0.5, 0.9),
                boundary_variant_bundles={
                    "clamped": _build_boundary_bundle(
                        root_id=101,
                        boundary_condition_mode=CLAMPED_BOUNDARY_CONDITION_MODE,
                    ),
                    "zero_flux": _build_boundary_bundle(
                        root_id=101,
                        boundary_condition_mode=DEFAULT_BOUNDARY_CONDITION_MODE,
                    ),
                },
                coarse_operator_bundle=_build_coarse_bundle(root_id=101),
                operator_qa_summary={
                    "operator_readiness_gate": "go",
                    "overall_status": "pass",
                    "artifacts": {},
                },
            )
            unstable_case = NumericalValidationCase(
                case_id="unstable_tripwire_case",
                arm_id="fixture_unstable",
                root_id=202,
                surface_wave_model=_build_linear_fixture_model("unstable_fixture"),
                reference_operator_bundle=_build_reference_bundle(root_id=202),
                integration_timestep_ms=0.2,
                shared_output_timestep_ms=0.2,
                shared_step_count=6,
                timestep_sweep_factors=(1.05,),
                coarse_operator_bundle=_build_bad_coarse_bundle(root_id=202),
                operator_qa_summary={
                    "operator_readiness_gate": "hold",
                    "overall_status": "fail",
                    "artifacts": {},
                },
            )

            first = run_numerical_validation_suite(
                [stable_case, unstable_case],
                processed_simulator_results_dir=simulator_results_dir,
                experiment_id="fixture_numeric_suite",
            )
            second = run_numerical_validation_suite(
                [stable_case, unstable_case],
                processed_simulator_results_dir=simulator_results_dir,
                experiment_id="fixture_numeric_suite",
            )

            self.assertEqual(first["bundle_id"], second["bundle_id"])
            self.assertEqual(first["output_dir"], second["output_dir"])
            self.assertEqual(first["summary_path"], second["summary_path"])
            self.assertEqual(first["findings_path"], second["findings_path"])
            self.assertEqual(first["overall_status"], "blocking")
            self.assertEqual(
                first["validator_statuses"],
                {
                    "operator_bundle_gate_alignment": "blocking",
                    "surface_wave_stability_envelope": "blocking",
                },
            )

            summary_path = Path(first["summary_path"]).resolve()
            findings_path = Path(first["findings_path"]).resolve()
            report_path = Path(first["report_path"]).resolve()
            self.assertTrue(summary_path.exists())
            self.assertTrue(findings_path.exists())
            self.assertTrue(report_path.exists())
            self.assertEqual(summary_path.read_bytes(), Path(second["summary_path"]).read_bytes())
            self.assertEqual(findings_path.read_bytes(), Path(second["findings_path"]).read_bytes())

            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            findings_payload = json.loads(findings_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["overall_status"], "blocking")
            self.assertEqual(len(summary_payload["case_summaries"]), 2)

            findings = _flatten_validator_findings(findings_payload["validator_findings"])
            finding_by_id = {
                item["finding_id"]: item
                for item in findings
            }
            self.assertEqual(
                finding_by_id[
                    "operator_bundle_gate_alignment:stable_linear_case:operator_qa_gate"
                ]["status"],
                "pass",
            )
            self.assertEqual(
                finding_by_id[
                    "surface_wave_stability_envelope:stable_linear_case:clamped:boundary_vertex_activation_max_abs"
                ]["status"],
                "pass",
            )
            self.assertEqual(
                finding_by_id[
                    "operator_bundle_gate_alignment:unstable_tripwire_case:operator_qa_gate"
                ]["status"],
                "blocking",
            )
            self.assertEqual(
                finding_by_id[
                    "surface_wave_stability_envelope:unstable_tripwire_case:dt_ratio_105:timestep_sweep_execution"
                ]["status"],
                "blocking",
            )
            self.assertEqual(
                finding_by_id[
                    "surface_wave_stability_envelope:unstable_tripwire_case:coarse_vs_fine_final_patch_relative_l2"
                ]["status"],
                "blocking",
            )

    def test_workflow_runs_on_local_execution_fixture_and_writes_bundle_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_execution_fixture(tmp_dir)

            first = execute_numerical_validation_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                arm_ids=["surface_wave_intact"],
            )
            second = execute_numerical_validation_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                arm_ids=["surface_wave_intact"],
            )

            self.assertEqual(first["bundle_id"], second["bundle_id"])
            self.assertEqual(first["output_dir"], second["output_dir"])
            self.assertEqual(first["case_count"], 2)
            self.assertEqual(
                sorted(first["validator_statuses"]),
                [
                    "operator_bundle_gate_alignment",
                    "surface_wave_stability_envelope",
                ],
            )

            summary_path = Path(first["summary_path"]).resolve()
            findings_path = Path(first["findings_path"]).resolve()
            report_path = Path(first["report_path"]).resolve()
            self.assertTrue(summary_path.exists())
            self.assertTrue(findings_path.exists())
            self.assertTrue(report_path.exists())
            self.assertEqual(summary_path.read_bytes(), Path(second["summary_path"]).read_bytes())
            self.assertEqual(findings_path.read_bytes(), Path(second["findings_path"]).read_bytes())

            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["experiment_id"], "milestone_1_demo_motion_patch")
            self.assertEqual(summary_payload["active_layer_ids"], ["numerical_sanity"])
            self.assertEqual(len(summary_payload["case_summaries"]), 2)
            self.assertEqual(
                sorted(
                    item["case_id"]
                    for item in summary_payload["case_summaries"]
                ),
                [
                    "surface_wave_intact__root_101",
                    "surface_wave_intact__root_202",
                ],
            )

    def test_workflow_accepts_pre_resolved_validation_context_without_replanning(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_execution_fixture(tmp_dir)
            config_payload = yaml.safe_load(
                fixture["config_path"].read_text(encoding="utf-8")
            )
            config_payload["validation"] = {
                "active_layer_ids": ["numerical_sanity"],
            }
            fixture["config_path"].write_text(
                yaml.safe_dump(config_payload, sort_keys=False),
                encoding="utf-8",
            )

            simulation_plan = resolve_manifest_simulation_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            execution_summary = execute_manifest_simulation(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                model_mode="surface_wave",
                simulation_plan=simulation_plan,
            )
            surface_wave_arm_plans = {
                str(arm_plan["arm_reference"]["arm_id"]): arm_plan
                for arm_plan in simulation_plan["arm_plans"]
                if str(arm_plan["arm_reference"]["model_mode"]) == "surface_wave"
            }
            bundle_set = {
                "processed_simulator_results_dir": str(
                    Path(
                        next(iter(surface_wave_arm_plans.values()))["runtime"][
                            "processed_simulator_results_dir"
                        ]
                    ).resolve()
                ),
                "bundle_records": [],
                "bundle_inventory": [
                    {
                        "bundle_id": str(run["bundle_id"]),
                        "metadata_path": str(Path(run["metadata_path"]).resolve()),
                        "arm_id": str(run["arm_id"]),
                        "model_mode": "surface_wave",
                        "baseline_family": None,
                        "seed": int(
                            surface_wave_arm_plans[str(run["arm_id"])]["determinism"][
                                "seed"
                            ]
                        ),
                        "condition_ids": [],
                        "condition_signature": "",
                        "stimulus_family": "fixture",
                        "stimulus_name": "fixture",
                        "parameter_snapshot": {},
                        "available_readout_ids": [
                            str(item["readout_id"])
                            for item in surface_wave_arm_plans[str(run["arm_id"])][
                                "runtime"
                            ]["shared_readout_catalog"]
                        ],
                    }
                    for run in execution_summary["executed_runs"]
                ],
                "expected_arm_ids": sorted(surface_wave_arm_plans),
                "expected_seeds_by_arm_id": {
                    arm_id: [int(arm_plan["determinism"]["seed"])]
                    for arm_id, arm_plan in surface_wave_arm_plans.items()
                },
            }
            validation_plan = resolve_validation_plan(
                config_path=fixture["config_path"],
                simulation_plan=simulation_plan,
                bundle_set=bundle_set,
            )

            with mock.patch(
                "flywire_wave.validation_numerics.resolve_manifest_simulation_plan",
                side_effect=AssertionError("unexpected simulation plan re-resolution"),
            ):
                result = execute_numerical_validation_workflow(
                    manifest_path=fixture["manifest_path"],
                    config_path=fixture["config_path"],
                    schema_path=fixture["schema_path"],
                    design_lock_path=fixture["design_lock_path"],
                    arm_ids=["surface_wave_intact"],
                    simulation_plan=simulation_plan,
                    validation_plan=validation_plan,
                )

            self.assertEqual(result["case_count"], 2)


def _flatten_validator_findings(
    payload: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    flattened: list[dict[str, object]] = []
    for validator_id in sorted(payload):
        flattened.extend(payload[validator_id])
    return flattened


def _build_linear_fixture_model(parameter_preset: str) -> dict[str, object]:
    return build_surface_wave_model_metadata(
        parameter_bundle={
            "parameter_preset": parameter_preset,
            "propagation": {
                "wave_speed_sq_scale": 1.0,
                "restoring_strength_per_ms2": 0.07,
            },
            "damping": {
                "gamma_per_ms": 0.18,
            },
        }
    )


def _build_reference_bundle(*, root_id: int) -> SurfaceWaveOperatorBundle:
    return SurfaceWaveOperatorBundle.from_fixture(
        root_id=root_id,
        surface_operator=_fixture_surface_operator(),
        coarse_operator=_fixture_coarse_operator(),
        restriction=_fixture_restriction(),
        prolongation=_fixture_prolongation(),
        mass_diagonal=np.ones(5, dtype=np.float64),
        patch_mass_diagonal=np.ones(3, dtype=np.float64),
        surface_to_patch=np.asarray([0, 1, 1, 2, 2], dtype=np.int32),
        boundary_condition_mode=DEFAULT_BOUNDARY_CONDITION_MODE,
    )


def _build_coarse_bundle(*, root_id: int) -> SurfaceWaveOperatorBundle:
    return SurfaceWaveOperatorBundle.from_fixture(
        root_id=root_id,
        surface_operator=_fixture_coarse_operator(),
        mass_diagonal=np.ones(3, dtype=np.float64),
        boundary_condition_mode=DEFAULT_BOUNDARY_CONDITION_MODE,
    )


def _build_bad_coarse_bundle(*, root_id: int) -> SurfaceWaveOperatorBundle:
    return SurfaceWaveOperatorBundle.from_fixture(
        root_id=root_id,
        surface_operator=6.0 * _fixture_coarse_operator(),
        mass_diagonal=np.ones(3, dtype=np.float64),
        boundary_condition_mode=DEFAULT_BOUNDARY_CONDITION_MODE,
    )


def _build_boundary_bundle(
    *,
    root_id: int,
    boundary_condition_mode: str,
) -> SurfaceWaveOperatorBundle:
    return SurfaceWaveOperatorBundle.from_fixture(
        root_id=root_id,
        surface_operator=sp.csr_matrix(
            [
                [1.0, -1.0, 0.0, 0.0],
                [-1.0, 2.0, -1.0, 0.0],
                [0.0, -1.0, 2.0, -1.0],
                [0.0, 0.0, -1.0, 1.0],
            ],
            dtype=np.float64,
        ),
        boundary_vertex_mask=np.asarray([True, False, False, True], dtype=bool),
        boundary_condition_mode=boundary_condition_mode,
    )


def _fixture_surface_operator() -> sp.csr_matrix:
    return sp.csr_matrix(
        [
            [1.0, -1.0, 0.0, 0.0, 0.0],
            [-1.0, 2.0, -1.0, 0.0, 0.0],
            [0.0, -1.0, 2.0, -1.0, 0.0],
            [0.0, 0.0, -1.0, 2.0, -1.0],
            [0.0, 0.0, 0.0, -1.0, 1.0],
        ],
        dtype=np.float64,
    )


def _fixture_coarse_operator() -> sp.csr_matrix:
    return sp.csr_matrix(
        [
            [1.0, -1.0, 0.0],
            [-1.0, 2.0, -1.0],
            [0.0, -1.0, 1.0],
        ],
        dtype=np.float64,
    )


def _fixture_restriction() -> sp.csr_matrix:
    return sp.csr_matrix(
        [
            [1.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.5, 0.5, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.5, 0.5],
        ],
        dtype=np.float64,
    )


def _fixture_prolongation() -> sp.csr_matrix:
    return sp.csr_matrix(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


if __name__ == "__main__":
    unittest.main()
