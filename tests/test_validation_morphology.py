from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.geometry_contract import DEFAULT_BOUNDARY_CONDITION_MODE
from flywire_wave.surface_wave_contract import build_surface_wave_model_metadata
from flywire_wave.surface_wave_solver import SurfaceWaveOperatorBundle
from flywire_wave.validation_morphology import (
    BOTTLENECK_EFFECT_COMPARISON_KIND,
    BRANCHING_EFFECT_COMPARISON_KIND,
    PATCHIFICATION_SENSITIVITY_COMPARISON_KIND,
    SIMPLIFICATION_SENSITIVITY_COMPARISON_KIND,
    MorphologyProbeComparisonCase,
    MorphologyProbeVariant,
    execute_morphology_validation_workflow,
    run_morphology_validation_suite,
)

try:
    from test_mixed_fidelity_inspection import _materialize_policy_fixture
except ModuleNotFoundError:
    from tests.test_mixed_fidelity_inspection import _materialize_policy_fixture


class MorphologyValidationSuiteTest(unittest.TestCase):
    def test_local_probe_suite_emits_deterministic_bottleneck_branching_and_sensitivity_findings(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            simulator_results_dir = tmp_dir / "simulator_results"

            open_variant = MorphologyProbeVariant(
                variant_id="open_corridor",
                display_name="Open Corridor",
                root_id=101,
                operator_bundle=_build_patch_bundle(
                    root_id=101,
                    weights=[1.0, 1.0, 1.0, 1.0],
                    surface_to_patch=[0, 1, 1, 2, 2],
                ),
                surface_wave_model=_build_linear_fixture_model("open_corridor"),
                shared_step_count=10,
                patch_sets={"distal": [2], "seed": [0]},
                provenance={"morphology_variant": "open_corridor"},
            )
            bottleneck_variant = MorphologyProbeVariant(
                variant_id="narrow_bottleneck",
                display_name="Narrow Bottleneck",
                root_id=101,
                operator_bundle=_build_patch_bundle(
                    root_id=101,
                    weights=[1.0, 0.15, 0.15, 1.0],
                    surface_to_patch=[0, 1, 1, 2, 2],
                ),
                surface_wave_model=_build_linear_fixture_model("narrow_bottleneck"),
                shared_step_count=10,
                patch_sets={"distal": [2], "seed": [0]},
                provenance={"morphology_variant": "narrow_bottleneck"},
            )
            branching_reference = MorphologyProbeVariant(
                variant_id="branching_disabled",
                display_name="Branching Disabled",
                root_id=202,
                operator_bundle=_build_patch_bundle(
                    root_id=202,
                    weights=[1.0, 1.0, 1.0],
                    surface_to_patch=[0, 0, 1, 2],
                    branch_point_count=3,
                ),
                surface_wave_model=_build_linear_fixture_model("branching_disabled"),
                shared_step_count=8,
                provenance={"branching_variant": "disabled"},
            )
            branching_candidate = MorphologyProbeVariant(
                variant_id="branching_enabled",
                display_name="Branching Enabled",
                root_id=202,
                operator_bundle=_build_patch_bundle(
                    root_id=202,
                    weights=[1.0, 1.0, 1.0],
                    surface_to_patch=[0, 0, 1, 2],
                    branch_point_count=3,
                ),
                surface_wave_model=_build_branching_fixture_model(),
                shared_step_count=8,
                provenance={"branching_variant": "descriptor_scaled_damping"},
            )
            simplification_reference = MorphologyProbeVariant(
                variant_id="full_resolution_reference",
                display_name="Full Resolution Reference",
                root_id=303,
                operator_bundle=_build_patch_bundle(
                    root_id=303,
                    weights=[1.0, 1.0, 1.0, 1.0],
                    surface_to_patch=[0, 1, 1, 2, 2],
                ),
                surface_wave_model=_build_linear_fixture_model("simplification_reference"),
                shared_step_count=9,
                patch_sets={"distal": [2]},
                provenance={"simplification_variant_id": "full_resolution_reference"},
            )
            simplification_candidate = MorphologyProbeVariant(
                variant_id="simplified_surface_variant",
                display_name="Simplified Surface Variant",
                root_id=303,
                operator_bundle=_build_patch_bundle(
                    root_id=303,
                    weights=[1.0, 0.95, 0.9, 1.05],
                    surface_to_patch=[0, 1, 1, 2, 2],
                ),
                surface_wave_model=_build_linear_fixture_model("simplified_surface_variant"),
                shared_step_count=9,
                patch_sets={"distal": [2]},
                provenance={"simplification_variant_id": "simplified_surface_variant"},
            )
            patch_reference = MorphologyProbeVariant(
                variant_id="canonical_patch_set",
                display_name="Canonical Patch Set",
                root_id=404,
                operator_bundle=_build_patch_bundle(
                    root_id=404,
                    weights=[1.0, 1.0, 1.0, 1.0],
                    surface_to_patch=[0, 1, 1, 2, 2],
                ),
                surface_wave_model=_build_linear_fixture_model("canonical_patch_set"),
                shared_step_count=9,
                patch_sets={"distal": [2]},
                provenance={"patchification_variant_id": "canonical_patch_set"},
            )
            patch_candidate = MorphologyProbeVariant(
                variant_id="wide_distal_patch_window",
                display_name="Wide Distal Patch Window",
                root_id=404,
                operator_bundle=_build_patch_bundle(
                    root_id=404,
                    weights=[1.0, 1.0, 1.0, 1.0],
                    surface_to_patch=[0, 1, 1, 2, 2],
                ),
                surface_wave_model=_build_linear_fixture_model("wide_distal_patch_window"),
                shared_step_count=9,
                patch_sets={"distal": [1, 2]},
                provenance={"patchification_variant_id": "wide_distal_patch_window"},
            )

            first = run_morphology_validation_suite(
                probe_cases=[
                    MorphologyProbeComparisonCase(
                        case_id="bottleneck_distal_case",
                        comparison_kind=BOTTLENECK_EFFECT_COMPARISON_KIND,
                        reference_variant=open_variant,
                        candidate_variant=bottleneck_variant,
                        focus_patch_set_label="distal",
                        localized_scope_label="root_101_distal_branch",
                    ),
                    MorphologyProbeComparisonCase(
                        case_id="branching_energy_case",
                        comparison_kind=BRANCHING_EFFECT_COMPARISON_KIND,
                        reference_variant=branching_reference,
                        candidate_variant=branching_candidate,
                        localized_scope_label="root_202_branch_points",
                    ),
                    MorphologyProbeComparisonCase(
                        case_id="simplification_review_case",
                        comparison_kind=SIMPLIFICATION_SENSITIVITY_COMPARISON_KIND,
                        reference_variant=simplification_reference,
                        candidate_variant=simplification_candidate,
                        focus_patch_set_label="distal",
                        localized_scope_label="root_303_distal_patch_set",
                        threshold_overrides={
                            "focus_patch_trace_mae": {
                                "warn": 1.0e-12,
                                "fail": 1.0e6,
                                "comparison": "max",
                            },
                            "focus_patch_peak_abs_error": {
                                "warn": 1.0e6,
                                "fail": 1.0e9,
                                "comparison": "max",
                            },
                        },
                    ),
                    MorphologyProbeComparisonCase(
                        case_id="patchification_blocking_case",
                        comparison_kind=PATCHIFICATION_SENSITIVITY_COMPARISON_KIND,
                        reference_variant=patch_reference,
                        candidate_variant=patch_candidate,
                        focus_patch_set_label="distal",
                        localized_scope_label="root_404_patch_window",
                        threshold_overrides={
                            "focus_patch_trace_mae": {
                                "warn": 1.0e-13,
                                "fail": 1.0e-12,
                                "comparison": "max",
                            },
                            "focus_patch_peak_abs_error": {
                                "warn": 1.0e9,
                                "fail": 1.0e12,
                                "comparison": "max",
                            },
                        },
                    ),
                ],
                processed_simulator_results_dir=simulator_results_dir,
                experiment_id="fixture_morphology_suite",
            )
            second = run_morphology_validation_suite(
                probe_cases=[
                    MorphologyProbeComparisonCase(
                        case_id="bottleneck_distal_case",
                        comparison_kind=BOTTLENECK_EFFECT_COMPARISON_KIND,
                        reference_variant=open_variant,
                        candidate_variant=bottleneck_variant,
                        focus_patch_set_label="distal",
                        localized_scope_label="root_101_distal_branch",
                    ),
                    MorphologyProbeComparisonCase(
                        case_id="branching_energy_case",
                        comparison_kind=BRANCHING_EFFECT_COMPARISON_KIND,
                        reference_variant=branching_reference,
                        candidate_variant=branching_candidate,
                        localized_scope_label="root_202_branch_points",
                    ),
                    MorphologyProbeComparisonCase(
                        case_id="simplification_review_case",
                        comparison_kind=SIMPLIFICATION_SENSITIVITY_COMPARISON_KIND,
                        reference_variant=simplification_reference,
                        candidate_variant=simplification_candidate,
                        focus_patch_set_label="distal",
                        localized_scope_label="root_303_distal_patch_set",
                        threshold_overrides={
                            "focus_patch_trace_mae": {
                                "warn": 1.0e-12,
                                "fail": 1.0e6,
                                "comparison": "max",
                            },
                            "focus_patch_peak_abs_error": {
                                "warn": 1.0e6,
                                "fail": 1.0e9,
                                "comparison": "max",
                            },
                        },
                    ),
                    MorphologyProbeComparisonCase(
                        case_id="patchification_blocking_case",
                        comparison_kind=PATCHIFICATION_SENSITIVITY_COMPARISON_KIND,
                        reference_variant=patch_reference,
                        candidate_variant=patch_candidate,
                        focus_patch_set_label="distal",
                        localized_scope_label="root_404_patch_window",
                        threshold_overrides={
                            "focus_patch_trace_mae": {
                                "warn": 1.0e-13,
                                "fail": 1.0e-12,
                                "comparison": "max",
                            },
                            "focus_patch_peak_abs_error": {
                                "warn": 1.0e9,
                                "fail": 1.0e12,
                                "comparison": "max",
                            },
                        },
                    ),
                ],
                processed_simulator_results_dir=simulator_results_dir,
                experiment_id="fixture_morphology_suite",
            )

            self.assertEqual(first["bundle_id"], second["bundle_id"])
            self.assertEqual(first["output_dir"], second["output_dir"])
            self.assertEqual(first["summary_path"], second["summary_path"])
            self.assertEqual(first["findings_path"], second["findings_path"])
            self.assertEqual(first["overall_status"], "blocking")
            self.assertEqual(
                first["validator_statuses"],
                {
                    "geometry_dependence_collapse": "blocking",
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
            self.assertEqual(len(summary_payload["case_summaries"]), 4)

            case_status_by_id = {
                item["case_id"]: item["overall_status"]
                for item in summary_payload["case_summaries"]
            }
            self.assertEqual(case_status_by_id["bottleneck_distal_case"], "pass")
            self.assertEqual(case_status_by_id["branching_energy_case"], "pass")
            self.assertEqual(case_status_by_id["simplification_review_case"], "review")
            self.assertEqual(case_status_by_id["patchification_blocking_case"], "blocking")

            findings = _flatten_validator_findings(findings_payload["validator_findings"])
            finding_by_id = {item["finding_id"]: item for item in findings}
            self.assertEqual(
                finding_by_id[
                    "geometry_dependence_collapse:bottleneck_distal_case:distal_arrival_delay_delta_ms"
                ]["status"],
                "pass",
            )
            self.assertEqual(
                finding_by_id[
                    "geometry_dependence_collapse:branching_energy_case:final_energy_drop_fraction"
                ]["status"],
                "pass",
            )
            self.assertEqual(
                finding_by_id[
                    "geometry_dependence_collapse:simplification_review_case:focus_patch_trace_mae"
                ]["status"],
                "review",
            )
            self.assertEqual(
                finding_by_id[
                    "geometry_dependence_collapse:patchification_blocking_case:focus_patch_trace_mae"
                ]["status"],
                "blocking",
            )
            self.assertEqual(
                finding_by_id[
                    "geometry_dependence_collapse:patchification_blocking_case:focus_patch_trace_mae"
                ]["diagnostic_metadata"]["candidate_variant"]["provenance"]["patchification_variant_id"],
                "wide_distal_patch_window",
            )

    def test_manifest_workflow_reuses_local_mixed_fidelity_assets(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_policy_fixture(Path(tmp_dir_str))
            thresholds = {
                "root_mean_trace_mae": {
                    "warn": 1.0e-12,
                    "fail": 1.0e6,
                    "comparison": "max",
                    "blocking": False,
                },
                "root_peak_abs_error": {
                    "warn": 1.0e6,
                    "fail": 1.0e9,
                    "comparison": "max",
                    "blocking": False,
                },
                "root_final_abs_error": {
                    "warn": 1.0e6,
                    "fail": 1.0e9,
                    "comparison": "max",
                    "blocking": False,
                },
                "root_peak_time_delta_ms": {
                    "warn": 1.0e6,
                    "fail": 1.0e9,
                    "comparison": "max",
                    "blocking": False,
                },
                "shared_output_trace_mae": {
                    "warn": 1.0e6,
                    "fail": 1.0e9,
                    "comparison": "max",
                    "blocking": True,
                },
                "shared_output_peak_abs_error": {
                    "warn": 1.0e6,
                    "fail": 1.0e9,
                    "comparison": "max",
                    "blocking": True,
                },
            }

            first = execute_morphology_validation_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                arm_ids=["surface_wave_intact"],
                mixed_fidelity_thresholds=thresholds,
            )
            second = execute_morphology_validation_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                arm_ids=["surface_wave_intact"],
                mixed_fidelity_thresholds=thresholds,
            )

            self.assertEqual(first["bundle_id"], second["bundle_id"])
            self.assertEqual(first["output_dir"], second["output_dir"])
            self.assertEqual(first["overall_status"], "review")
            self.assertEqual(
                first["validator_statuses"],
                {
                    "mixed_fidelity_surrogate_preservation": "review",
                },
            )

            summary_path = Path(first["summary_path"]).resolve()
            findings_path = Path(first["findings_path"]).resolve()
            self.assertTrue(summary_path.exists())
            self.assertTrue(findings_path.exists())
            self.assertEqual(summary_path.read_bytes(), Path(second["summary_path"]).read_bytes())
            self.assertEqual(findings_path.read_bytes(), Path(second["findings_path"]).read_bytes())

            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            findings_payload = json.loads(findings_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["experiment_id"], "milestone_1_demo_motion_patch")
            self.assertEqual(summary_payload["active_layer_ids"], ["morphology_sanity"])
            self.assertEqual(len(summary_payload["case_summaries"]), 1)

            case_ids = {item["case_id"] for item in summary_payload["case_summaries"]}
            self.assertIn("surface_wave_intact__root_303", case_ids)

            findings = _flatten_validator_findings(findings_payload["validator_findings"])
            finding_by_id = {item["finding_id"]: item for item in findings}
            mixed_fidelity_finding = finding_by_id[
                "mixed_fidelity_surrogate_preservation:surface_wave_intact__root_303:surface_neuron:root_mean_trace_mae"
            ]
            self.assertEqual(mixed_fidelity_finding["status"], "review")
            self.assertEqual(
                mixed_fidelity_finding["diagnostic_metadata"]["policy_evaluation"]["matched_rule_ids"],
                ["promote_patch_dense_surrogate"],
            )


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


def _build_branching_fixture_model() -> dict[str, object]:
    return build_surface_wave_model_metadata(
        parameter_bundle={
            "parameter_preset": "branching_enabled",
            "propagation": {
                "wave_speed_sq_scale": 1.0,
                "restoring_strength_per_ms2": 0.07,
            },
            "damping": {
                "gamma_per_ms": 0.18,
            },
            "branching": {
                "mode": "descriptor_scaled_damping",
                "gain": 0.5,
            },
        }
    )


def _build_patch_bundle(
    *,
    root_id: int,
    weights: list[float],
    surface_to_patch: list[int],
    branch_point_count: int | None = None,
) -> SurfaceWaveOperatorBundle:
    patch_map = np.asarray(surface_to_patch, dtype=np.int32)
    return SurfaceWaveOperatorBundle.from_fixture(
        root_id=root_id,
        surface_operator=_path_surface_operator(weights),
        restriction=_restriction_from_surface_to_patch(patch_map),
        prolongation=_prolongation_from_surface_to_patch(patch_map),
        mass_diagonal=np.ones(len(weights) + 1, dtype=np.float64),
        patch_mass_diagonal=np.ones(int(np.max(patch_map)) + 1, dtype=np.float64),
        surface_to_patch=patch_map,
        geometry_descriptors=(
            {}
            if branch_point_count is None
            else {
                "descriptor_version": "geometry_descriptors.v1",
                "representations": {
                    "skeleton": {
                        "available": True,
                        "branch_point_count": int(branch_point_count),
                        "leaf_count": 4,
                        "root_count": 1,
                        "total_cable_length": 10.0,
                    }
                },
            }
        ),
        boundary_condition_mode=DEFAULT_BOUNDARY_CONDITION_MODE,
        fixture_name=f"validation_morphology_root_{root_id}",
    )


def _path_surface_operator(weights: list[float]) -> sp.csr_matrix:
    diagonal = np.zeros(len(weights) + 1, dtype=np.float64)
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    for edge_index, weight in enumerate(weights):
        i = edge_index
        j = edge_index + 1
        diagonal[i] += float(weight)
        diagonal[j] += float(weight)
        rows.extend([i, j])
        cols.extend([j, i])
        data.extend([-float(weight), -float(weight)])
    for vertex_index, value in enumerate(diagonal):
        rows.append(vertex_index)
        cols.append(vertex_index)
        data.append(float(value))
    return sp.csr_matrix(
        (
            np.asarray(data, dtype=np.float64),
            (np.asarray(rows, dtype=np.int32), np.asarray(cols, dtype=np.int32)),
        ),
        shape=(len(weights) + 1, len(weights) + 1),
        dtype=np.float64,
    )


def _restriction_from_surface_to_patch(surface_to_patch: np.ndarray) -> sp.csr_matrix:
    patch_count = int(np.max(surface_to_patch)) + 1
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    for patch_index in range(patch_count):
        vertex_indices = np.flatnonzero(surface_to_patch == patch_index)
        weight = 1.0 / float(vertex_indices.size)
        for vertex_index in vertex_indices:
            rows.append(patch_index)
            cols.append(int(vertex_index))
            data.append(weight)
    return sp.csr_matrix(
        (
            np.asarray(data, dtype=np.float64),
            (np.asarray(rows, dtype=np.int32), np.asarray(cols, dtype=np.int32)),
        ),
        shape=(patch_count, int(surface_to_patch.size)),
        dtype=np.float64,
    )


def _prolongation_from_surface_to_patch(surface_to_patch: np.ndarray) -> sp.csr_matrix:
    patch_count = int(np.max(surface_to_patch)) + 1
    rows = np.arange(surface_to_patch.size, dtype=np.int32)
    cols = np.asarray(surface_to_patch, dtype=np.int32)
    data = np.ones(surface_to_patch.size, dtype=np.float64)
    return sp.csr_matrix(
        (data, (rows, cols)),
        shape=(int(surface_to_patch.size), patch_count),
        dtype=np.float64,
    )


if __name__ == "__main__":
    unittest.main()
