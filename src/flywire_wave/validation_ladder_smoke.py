from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy.sparse as sp

from .coupling_assembly import (
    ANCHOR_COLUMN_TYPES,
    CLOUD_COLUMN_TYPES,
    COMPONENT_COLUMN_TYPES,
    COMPONENT_SYNAPSE_COLUMN_TYPES,
    EdgeCouplingBundle,
)
from .coupling_contract import (
    DEFAULT_AGGREGATION_RULE,
    DEFAULT_DELAY_REPRESENTATION,
    DEFAULT_SIGN_REPRESENTATION,
    DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
    SEPARABLE_RANK_ONE_CLOUD_KERNEL,
    SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
    SURFACE_PATCH_CLOUD_MODE,
)
from .experiment_comparison_analysis import EXPERIMENT_COMPARISON_SUMMARY_VERSION
from .geometry_contract import DEFAULT_BOUNDARY_CONDITION_MODE
from .simulator_result_contract import (
    build_selected_asset_reference,
    build_simulator_arm_reference,
    build_simulator_manifest_reference,
    build_simulator_readout_definition,
    build_simulator_result_bundle_metadata,
)
from .stimulus_contract import (
    build_stimulus_bundle_metadata,
    write_stimulus_bundle_metadata,
)
from .surface_wave_contract import build_surface_wave_model_metadata
from .surface_wave_solver import SurfaceWaveOperatorBundle
from .synapse_mapping import EDGE_BUNDLE_COLUMN_TYPES, _write_edge_coupling_bundle_npz
from .validation_circuit import (
    DelayValidationCase,
    MotionPathwayAsymmetryCase,
    run_circuit_validation_suite,
)
from .validation_contract import SUPPORTED_VALIDATION_LAYER_IDS, VALIDATION_STATUS_PASS
from .validation_morphology import (
    BOTTLENECK_EFFECT_COMPARISON_KIND,
    BRANCHING_EFFECT_COMPARISON_KIND,
    MorphologyProbeComparisonCase,
    MorphologyProbeVariant,
    run_morphology_validation_suite,
)
from .validation_numerics import (
    NumericalValidationCase,
    run_numerical_validation_suite,
)
from .validation_reporting import package_validation_ladder_outputs
from .validation_task import run_task_validation_suite


SMOKE_EXPERIMENT_ID = "fixture_validation_ladder_smoke"
SMOKE_LAYER_INPUT_DIRECTORY_NAME = "validation_ladder_inputs"

_FIXTURE_TIMEBASE = {
    "time_origin_ms": 0.0,
    "dt_ms": 10.0,
    "duration_ms": 70.0,
    "sample_count": 7,
}
_FIXTURE_TIME_MS = np.asarray(
    [0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
    dtype=np.float64,
)
_TASK_METRIC_IDS = (
    "motion_vector_heading_deg",
    "motion_vector_speed_deg_per_s",
    "optic_flow_heading_deg",
    "optic_flow_speed_deg_per_s",
)


def run_validation_ladder_smoke_workflow(
    *,
    processed_simulator_results_dir: str | Path = "data/processed/simulator_results",
    baseline_path: str | Path | None = None,
    enforce_baseline: bool = False,
) -> dict[str, Any]:
    processed_root = Path(processed_simulator_results_dir).resolve()
    layer_input_root = (
        processed_root / SMOKE_LAYER_INPUT_DIRECTORY_NAME / SMOKE_EXPERIMENT_ID
    ).resolve()

    numerical = _run_numerical_smoke_suite(layer_input_root)
    morphology = _run_morphology_smoke_suite(layer_input_root)
    circuit = _run_circuit_smoke_suite(layer_input_root)
    task = _run_task_smoke_suite(layer_input_root)

    packaged = package_validation_ladder_outputs(
        layer_bundle_metadata_paths=[
            numerical["metadata_path"],
            morphology["metadata_path"],
            circuit["metadata_path"],
            task["metadata_path"],
        ],
        processed_simulator_results_dir=processed_root,
        baseline_path=baseline_path,
        require_layer_ids=SUPPORTED_VALIDATION_LAYER_IDS,
    )
    if enforce_baseline and packaged["regression_status"] != VALIDATION_STATUS_PASS:
        raise ValueError(
            "Validation ladder smoke regression baseline mismatch. Inspect "
            f"{packaged['regression_summary_path']}."
        )
    return {
        **packaged,
        "smoke_layer_outputs": {
            "numerical_sanity": numerical,
            "morphology_sanity": morphology,
            "circuit_sanity": circuit,
            "task_sanity": task,
        },
    }


def _run_numerical_smoke_suite(layer_input_root: Path) -> dict[str, Any]:
    bundle = SurfaceWaveOperatorBundle.from_fixture(
        root_id=101,
        surface_operator=_fixture_surface_operator(),
        mass_diagonal=np.ones(5, dtype=np.float64),
    )
    case = NumericalValidationCase(
        case_id="stable_linear_case",
        arm_id="fixture_stable",
        root_id=101,
        surface_wave_model=_build_linear_fixture_model("stable_fixture"),
        reference_operator_bundle=bundle,
        integration_timestep_ms=0.2,
        shared_output_timestep_ms=0.2,
        shared_step_count=6,
        pulse_seed_vertex=1,
        timestep_sweep_factors=(0.5,),
        operator_qa_summary={
            "operator_readiness_gate": "go",
            "overall_status": "pass",
            "artifacts": {},
        },
    )
    return run_numerical_validation_suite(
        [case],
        processed_simulator_results_dir=layer_input_root,
        experiment_id=SMOKE_EXPERIMENT_ID,
    )


def _run_morphology_smoke_suite(layer_input_root: Path) -> dict[str, Any]:
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
    return run_morphology_validation_suite(
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
        ],
        processed_simulator_results_dir=layer_input_root,
        experiment_id=SMOKE_EXPERIMENT_ID,
    )


def _run_circuit_smoke_suite(layer_input_root: Path) -> dict[str, Any]:
    fixture_root = (layer_input_root / "circuit_fixture").resolve()
    delay_edge_path = fixture_root / "edges" / "delay_edge.npz"
    delay_edge_path.parent.mkdir(parents=True, exist_ok=True)
    _write_fixture_edge_bundle(
        delay_edge_path,
        pre_root_id=101,
        post_root_id=202,
        signed_weight_total=1.0,
        delay_ms=2.0,
        sign_label="excitatory",
    )
    probe_plan = _build_probe_analysis_plan(["probe_pulse"])
    motion_plan = _build_motion_analysis_plan("preferred_pathway_output")
    delay_pass_record = _build_inline_bundle_record(
        fixture_root,
        asset_suffix="delay_pass",
        condition_ids=["probe_pulse"],
        readout_traces={
            "source_readout": [2.0, 2.0, 4.5, 3.0, 2.2, 2.0, 2.0],
            "target_readout": [2.0, 2.0, 2.1, 2.4, 5.0, 2.6, 2.0],
        },
        arm_id="delay_pass_arm",
        stimulus_family="translated_edge",
        stimulus_name="simple_translated_edge",
    )
    motion_records = [
        _build_inline_bundle_record(
            fixture_root,
            asset_suffix="motion_preferred",
            condition_ids=["preferred_direction"],
            readout_traces={
                "preferred_pathway_output": [2.0, 2.0, 6.0, 3.8, 2.4, 2.0, 2.0],
            },
            arm_id="motion_arm",
            stimulus_family="moving_edge",
            stimulus_name="simple_moving_edge",
        ),
        _build_inline_bundle_record(
            fixture_root,
            asset_suffix="motion_null",
            condition_ids=["null_direction"],
            readout_traces={
                "preferred_pathway_output": [2.0, 2.0, 2.8, 4.0, 2.6, 2.1, 2.0],
            },
            arm_id="motion_arm",
            stimulus_family="moving_edge",
            stimulus_name="simple_moving_edge",
        ),
    ]
    return run_circuit_validation_suite(
        delay_cases=[
            DelayValidationCase(
                case_id="delay_pass_case",
                motif_id="feedforward_delay_probe",
                analysis_plan=probe_plan,
                bundle_records=[delay_pass_record],
                source_readout_id="source_readout",
                target_readout_id="target_readout",
                edge_bundle_paths=[delay_edge_path],
            )
        ],
        motion_cases=[
            MotionPathwayAsymmetryCase(
                case_id="motion_pass_case",
                pathway_id="preferred_pathway",
                analysis_plan=motion_plan,
                bundle_records=motion_records,
                readout_id="preferred_pathway_output",
            )
        ],
        processed_simulator_results_dir=layer_input_root,
        experiment_id=SMOKE_EXPERIMENT_ID,
    )


def _run_task_smoke_suite(layer_input_root: Path) -> dict[str, Any]:
    base_summary = _build_task_smoke_summary()
    neutral_noise_summary = copy.deepcopy(base_summary)
    mild_noise_summary = _build_task_noise_variant_summary(
        base_summary,
        shared_scale=0.9,
        speed_scale=0.9,
        heading_delta_deg=3.0,
    )
    return run_task_validation_suite(
        analysis_summary=base_summary,
        perturbation_analysis_bundle_specs=[
            {
                "suite_id": "noise_robustness",
                "variant_id": "seed_11__noise_0p0",
                "analysis_summary": neutral_noise_summary,
            },
            {
                "suite_id": "noise_robustness",
                "variant_id": "seed_11__noise_0p1",
                "analysis_summary": mild_noise_summary,
            },
        ],
        processed_simulator_results_dir=layer_input_root,
        experiment_id=SMOKE_EXPERIMENT_ID,
    )


def _build_task_smoke_summary() -> dict[str, Any]:
    summary = {
        "summary_version": EXPERIMENT_COMPARISON_SUMMARY_VERSION,
        "manifest_reference": {"experiment_id": SMOKE_EXPERIMENT_ID},
        "bundle_set": {
            "expected_arm_ids": ["baseline_arm", "surface_wave_arm"],
            "expected_seeds_by_arm_id": {
                "baseline_arm": [11, 17],
                "surface_wave_arm": [11, 17],
            },
        },
        "analysis_results": {
            "task_decoder_analysis": {
                "metric_rows": [],
                "decoder_summaries": [],
            },
        },
        "comparison_group_catalog": [
            {
                "group_id": "matched_surface_wave_vs_baseline",
                "group_kind": "matched_surface_wave_vs_baseline",
                "arm_ids": ["surface_wave_arm", "baseline_arm"],
                "component_group_ids": [],
            },
            {
                "group_id": "geometry_ablation_demo",
                "group_kind": "geometry_ablation",
                "arm_ids": ["surface_wave_arm", "baseline_arm"],
                "component_group_ids": [],
            },
        ],
        "group_metric_seed_rows": [],
        "group_metric_rollups": [
            {
                "group_id": "matched_surface_wave_vs_baseline",
                "group_kind": "matched_surface_wave_vs_baseline",
                "metric_id": "direction_selectivity_index",
                "summary_statistics": {"mean": 0.2},
                "seeds": [11, 17],
                "seed_count": 2,
                "sign_consistency": True,
                "effect_direction": "positive",
            },
            {
                "group_id": "geometry_ablation_demo",
                "group_kind": "geometry_ablation",
                "metric_id": "direction_selectivity_index",
                "summary_statistics": {"mean": 0.1},
                "seeds": [11, 17],
                "seed_count": 2,
                "sign_consistency": True,
                "effect_direction": "positive",
            },
        ],
        "null_test_results": [
            {
                "null_test_id": "geometry_shuffle_collapse",
                "status": "pass",
                "metric_outcomes": [],
            },
            {
                "null_test_id": "seed_stability",
                "status": "pass",
                "metric_outcomes": [],
            },
            {
                "null_test_id": "stronger_baseline_survival",
                "status": "pass",
                "metric_outcomes": [],
            },
        ],
        "task_scores": [],
        "wave_metric_rollups": [],
    }
    metric_values = {
        "motion_vector_heading_deg": {
            "baseline_arm": [1.0, 2.0],
            "surface_wave_arm": [3.0, 4.0],
        },
        "optic_flow_heading_deg": {
            "baseline_arm": [1.5, 2.5],
            "surface_wave_arm": [4.0, 5.0],
        },
        "motion_vector_speed_deg_per_s": {
            "baseline_arm": [1.0, 1.02],
            "surface_wave_arm": [1.4, 1.45],
        },
        "optic_flow_speed_deg_per_s": {
            "baseline_arm": [0.9, 0.93],
            "surface_wave_arm": [1.3, 1.34],
        },
    }
    for arm_id, decoder_id in (
        ("baseline_arm", "decoder_baseline"),
        ("surface_wave_arm", "decoder_wave"),
    ):
        for seed in (11, 17):
            summary["analysis_results"]["task_decoder_analysis"][
                "decoder_summaries"
            ].append(
                {
                    "arm_id": arm_id,
                    "decoder_id": decoder_id,
                    "status": "ok",
                    "seed": seed,
                    "readout_id": "shared_output_mean",
                }
            )
    for metric_id, per_arm_values in metric_values.items():
        for arm_id, values in per_arm_values.items():
            for seed, value in zip((11, 17), values):
                summary["analysis_results"]["task_decoder_analysis"][
                    "metric_rows"
                ].append(
                    {
                        "arm_id": arm_id,
                        "metric_id": metric_id,
                        "seed": seed,
                        "value": value,
                    }
                )
        summary["group_metric_rollups"].append(
            {
                "group_id": "matched_surface_wave_vs_baseline",
                "group_kind": "matched_surface_wave_vs_baseline",
                "metric_id": metric_id,
                "summary_statistics": {
                    "mean": 2.0 if "heading" in metric_id else 0.3
                },
                "seeds": [11, 17],
                "seed_count": 2,
                "sign_consistency": True,
                "effect_direction": "positive",
            }
        )
    return summary


def _build_task_noise_variant_summary(
    base_summary: dict[str, Any],
    *,
    shared_scale: float,
    speed_scale: float,
    heading_delta_deg: float,
) -> dict[str, Any]:
    summary = copy.deepcopy(base_summary)
    for row in summary["analysis_results"]["task_decoder_analysis"]["metric_rows"]:
        metric_id = str(row["metric_id"])
        if "heading" in metric_id:
            row["value"] = round(float(row["value"]) + heading_delta_deg, 12)
        else:
            row["value"] = round(float(row["value"]) * speed_scale, 12)
    for rollup in summary["group_metric_rollups"]:
        metric_id = str(rollup["metric_id"])
        mean_value = float(rollup["summary_statistics"]["mean"])
        if "heading" in metric_id:
            rollup["summary_statistics"]["mean"] = round(
                mean_value + heading_delta_deg,
                12,
            )
        else:
            scale = shared_scale if metric_id == "direction_selectivity_index" else speed_scale
            rollup["summary_statistics"]["mean"] = round(mean_value * scale, 12)
    return summary


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


def _build_probe_analysis_plan(condition_ids: list[str]) -> dict[str, object]:
    return {
        "plan_version": "readout_analysis_plan.v1",
        "condition_catalog": [
            {
                "condition_id": condition_id,
                "display_name": condition_id.replace("_", " ").title(),
                "parameter_name": "fixture_condition",
                "value": condition_id,
            }
            for condition_id in condition_ids
        ],
        "condition_pair_catalog": [],
        "analysis_window_catalog": [
            {
                "window_id": "shared_response_window",
                "start_ms": 10.0,
                "end_ms": 60.0,
                "description": "Fixture shared-response window.",
            }
        ],
        "metric_recipe_catalog": [],
    }


def _build_motion_analysis_plan(readout_id: str) -> dict[str, object]:
    return {
        "plan_version": "readout_analysis_plan.v1",
        "condition_catalog": [
            {
                "condition_id": "preferred_direction",
                "display_name": "Preferred Direction",
                "parameter_name": "direction_deg",
                "value": 0.0,
            },
            {
                "condition_id": "null_direction",
                "display_name": "Null Direction",
                "parameter_name": "direction_deg",
                "value": 180.0,
            },
        ],
        "condition_pair_catalog": [
            {
                "pair_id": "preferred_vs_null",
                "left_condition_id": "preferred_direction",
                "right_condition_id": "null_direction",
            }
        ],
        "analysis_window_catalog": [
            {
                "window_id": "shared_response_window",
                "start_ms": 10.0,
                "end_ms": 60.0,
                "description": "Fixture shared-response window.",
            }
        ],
        "metric_recipe_catalog": [
            {
                "recipe_id": f"response_latency_to_peak_ms__{readout_id}",
                "metric_id": "response_latency_to_peak_ms",
                "window_id": "shared_response_window",
                "active_readout_ids": [readout_id],
                "condition_ids": ["preferred_direction", "null_direction"],
                "condition_pair_id": None,
            },
            {
                "recipe_id": f"direction_selectivity_index__{readout_id}",
                "metric_id": "direction_selectivity_index",
                "window_id": "shared_response_window",
                "active_readout_ids": [readout_id],
                "condition_ids": [],
                "condition_pair_id": "preferred_vs_null",
            },
        ],
    }


def _build_inline_bundle_record(
    tmp_dir: Path,
    *,
    asset_suffix: str,
    condition_ids: list[str],
    readout_traces: dict[str, list[float]],
    arm_id: str,
    stimulus_family: str,
    stimulus_name: str,
    model_mode: str = "baseline",
    baseline_family: str | None = "P0",
    seed: int = 11,
) -> dict[str, object]:
    stimulus_metadata = _write_fixture_stimulus_metadata(
        tmp_dir,
        asset_suffix=asset_suffix,
        stimulus_family=stimulus_family,
        stimulus_name=stimulus_name,
    )
    readout_ids = list(readout_traces)
    values = np.column_stack(
        [
            np.asarray(readout_traces[readout_id], dtype=np.float64)
            for readout_id in readout_ids
        ]
    )
    metadata = build_simulator_result_bundle_metadata(
        manifest_reference=build_simulator_manifest_reference(
            experiment_id="fixture_circuit",
            manifest_path=tmp_dir / "fixture_manifest.yaml",
            milestone="milestone_13",
        ),
        arm_reference=build_simulator_arm_reference(
            arm_id=arm_id,
            model_mode=model_mode,
            baseline_family=baseline_family,
        ),
        timebase=_FIXTURE_TIMEBASE,
        selected_assets=[
            build_selected_asset_reference(
                asset_role="input_bundle",
                artifact_type="stimulus_bundle",
                path=Path(stimulus_metadata["assets"]["metadata_json"]["path"]),
                contract_version=str(stimulus_metadata["contract_version"]),
                artifact_id="stimulus_bundle",
                bundle_id=str(stimulus_metadata["bundle_id"]),
            )
        ],
        readout_catalog=[
            build_simulator_readout_definition(
                readout_id=readout_id,
                scope="circuit_output",
                aggregation="mean_over_root_ids",
                units="activation_au",
                value_semantics=f"{readout_id}_semantics",
                description=f"Fixture readout {readout_id}.",
            )
            for readout_id in readout_ids
        ],
        processed_simulator_results_dir=tmp_dir / "simulator_results",
        seed=seed,
    )
    return {
        "bundle_metadata": metadata,
        "condition_ids": list(condition_ids),
        "shared_readout_payload": {
            "time_ms": _FIXTURE_TIME_MS,
            "readout_ids": tuple(readout_ids),
            "values": values,
        },
    }


def _write_fixture_edge_bundle(
    path: Path,
    *,
    pre_root_id: int,
    post_root_id: int,
    signed_weight_total: float,
    delay_ms: float,
    sign_label: str,
) -> None:
    source_anchor_table = pd.DataFrame.from_records(
        [
            {
                "anchor_table_index": 0,
                "root_id": pre_root_id,
                "anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "anchor_type": "surface_patch",
                "anchor_resolution": "coarse_patch",
                "anchor_index": 0,
                "anchor_x": 0.0,
                "anchor_y": 0.0,
                "anchor_z": 0.0,
            }
        ],
        columns=list(ANCHOR_COLUMN_TYPES),
    )
    target_anchor_table = pd.DataFrame.from_records(
        [
            {
                "anchor_table_index": 0,
                "root_id": post_root_id,
                "anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "anchor_type": "surface_patch",
                "anchor_resolution": "coarse_patch",
                "anchor_index": 0,
                "anchor_x": 1.0,
                "anchor_y": 0.0,
                "anchor_z": 0.0,
            }
        ],
        columns=list(ANCHOR_COLUMN_TYPES),
    )
    component_id = f"{pre_root_id}__to__{post_root_id}__component_0000"
    component_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "component_id": component_id,
                "pre_root_id": pre_root_id,
                "post_root_id": post_root_id,
                "topology_family": DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
                "kernel_family": SEPARABLE_RANK_ONE_CLOUD_KERNEL,
                "pre_anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "post_anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "sign_label": sign_label,
                "sign_polarity": 1 if signed_weight_total > 0.0 else -1,
                "sign_representation": DEFAULT_SIGN_REPRESENTATION,
                "delay_representation": DEFAULT_DELAY_REPRESENTATION,
                "delay_model": "fixture_delay_model",
                "delay_ms": delay_ms,
                "delay_bin_index": 0,
                "delay_bin_label": f"{delay_ms:.6f}",
                "delay_bin_start_ms": delay_ms,
                "delay_bin_end_ms": delay_ms,
                "aggregation_rule": DEFAULT_AGGREGATION_RULE,
                "source_anchor_count": 1,
                "target_anchor_count": 1,
                "synapse_count": 1,
                "signed_weight_total": signed_weight_total,
                "absolute_weight_total": abs(signed_weight_total),
                "confidence_sum": 1.0,
                "confidence_mean": 1.0,
                "source_cloud_normalization": SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
                "target_cloud_normalization": SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
                "source_normalization_total": 1.0,
                "target_normalization_total": 1.0,
            }
        ],
        columns=list(COMPONENT_COLUMN_TYPES),
    )
    source_cloud_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "anchor_table_index": 0,
                "cloud_weight": 1.0,
                "anchor_weight_total": 1.0,
                "supporting_synapse_count": 1,
            }
        ],
        columns=list(CLOUD_COLUMN_TYPES),
    )
    target_cloud_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "anchor_table_index": 0,
                "cloud_weight": 1.0,
                "anchor_weight_total": 1.0,
                "supporting_synapse_count": 1,
            }
        ],
        columns=list(CLOUD_COLUMN_TYPES),
    )
    component_synapse_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "synapse_row_id": f"{component_id}#0",
                "source_row_number": 1,
                "synapse_id": f"{component_id}#synapse",
                "sign_label": sign_label,
                "signed_weight": signed_weight_total,
                "absolute_weight": abs(signed_weight_total),
                "delay_ms": delay_ms,
                "delay_bin_index": 0,
                "delay_bin_label": f"{delay_ms:.6f}",
            }
        ],
        columns=list(COMPONENT_SYNAPSE_COLUMN_TYPES),
    )
    empty_synapse_table = pd.DataFrame(columns=list(EDGE_BUNDLE_COLUMN_TYPES))
    bundle = EdgeCouplingBundle(
        pre_root_id=pre_root_id,
        post_root_id=post_root_id,
        status="ready",
        topology_family=DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
        kernel_family=SEPARABLE_RANK_ONE_CLOUD_KERNEL,
        sign_representation=DEFAULT_SIGN_REPRESENTATION,
        delay_representation=DEFAULT_DELAY_REPRESENTATION,
        delay_model="fixture_delay_model",
        delay_model_parameters={
            "base_delay_ms": 0.0,
            "velocity_distance_units_per_ms": 1.0,
            "delay_bin_size_ms": 0.0,
        },
        aggregation_rule=DEFAULT_AGGREGATION_RULE,
        missing_geometry_policy="fixture_only",
        source_cloud_normalization=SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
        target_cloud_normalization=SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
        synapse_table=empty_synapse_table.copy(),
        component_table=component_table,
        blocked_synapse_table=empty_synapse_table.copy(),
        source_anchor_table=source_anchor_table,
        target_anchor_table=target_anchor_table,
        source_cloud_table=source_cloud_table,
        target_cloud_table=target_cloud_table,
        component_synapse_table=component_synapse_table,
    )
    _write_edge_coupling_bundle_npz(path=path, bundle=bundle)


def _write_fixture_stimulus_metadata(
    tmp_dir: Path,
    *,
    asset_suffix: str,
    stimulus_family: str,
    stimulus_name: str,
    parameter_snapshot: dict[str, object] | None = None,
) -> dict[str, object]:
    stimulus_metadata = build_stimulus_bundle_metadata(
        stimulus_family=stimulus_family,
        stimulus_name=stimulus_name,
        parameter_snapshot={
            "fixture_id": asset_suffix,
            **(parameter_snapshot or {}),
        },
        seed=11,
        temporal_sampling={
            "dt_ms": 10.0,
            "fps": 100.0,
            "frame_count": 7,
            "duration_ms": 70.0,
        },
        spatial_frame={
            "width_px": 8,
            "height_px": 4,
            "width_deg": 80.0,
            "height_deg": 40.0,
        },
        processed_stimulus_dir=tmp_dir / "stimuli",
    )
    write_stimulus_bundle_metadata(stimulus_metadata)
    return stimulus_metadata


__all__ = [
    "SMOKE_EXPERIMENT_ID",
    "run_validation_ladder_smoke_workflow",
]
