from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.io_utils import write_deterministic_npz, write_json
from flywire_wave.readout_analysis_contract import (
    SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
    SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
    SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
    get_readout_analysis_metric_definition,
)
from flywire_wave.simulator_result_contract import (
    build_selected_asset_reference,
    build_simulator_arm_reference,
    build_simulator_extension_artifact_record,
    build_simulator_manifest_reference,
    build_simulator_readout_definition,
    build_simulator_result_bundle_metadata,
    build_simulator_result_bundle_paths,
    build_simulator_run_spec_hash,
    load_simulator_result_bundle_metadata,
    write_simulator_result_bundle_metadata,
)
from flywire_wave.surface_operators import serialize_sparse_matrix
from flywire_wave.wave_structure_analysis import (
    WAVE_STRUCTURE_DIAGNOSTIC_INTERFACE_VERSION,
    compute_wave_structure_diagnostics,
)


FIXTURE_TIMEBASE = {
    "time_origin_ms": 0.0,
    "dt_ms": 1.0,
    "duration_ms": 4.0,
    "sample_count": 4,
}


class WaveStructureAnalysisTest(unittest.TestCase):
    def test_contract_exposes_wave_metric_dependencies(self) -> None:
        synchrony = get_readout_analysis_metric_definition("synchrony_coherence_index")
        phase_gradient = get_readout_analysis_metric_definition(
            "phase_gradient_mean_rad_per_patch"
        )
        curvature = get_readout_analysis_metric_definition("wavefront_curvature_inv_patch")

        self.assertEqual(
            synchrony["required_source_artifact_classes"],
            [
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
                SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
            ],
        )
        self.assertEqual(
            phase_gradient["required_source_artifact_classes"],
            [
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
                SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
            ],
        )
        self.assertEqual(
            curvature["required_source_artifact_classes"],
            [
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
                SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
            ],
        )

    def test_compute_wave_structure_diagnostics_from_deterministic_wave_bundle(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _write_wave_bundle_fixture(Path(tmp_dir_str))

            result = compute_wave_structure_diagnostics(
                bundle_records=[{"bundle_metadata": fixture["metadata"]}],
            )

            self.assertEqual(
                result["wave_diagnostic_interface_version"],
                WAVE_STRUCTURE_DIAGNOSTIC_INTERFACE_VERSION,
            )
            self.assertEqual(
                result["supported_metric_ids"],
                [
                    "patch_activation_entropy_bits",
                    "phase_gradient_dispersion_rad_per_patch",
                    "phase_gradient_mean_rad_per_patch",
                    "synchrony_coherence_index",
                    "wavefront_curvature_inv_patch",
                    "wavefront_speed_patch_per_ms",
                ],
            )
            self.assertEqual(len(result["metric_rows"]), 11)

            rows_by_key = {
                (row["metric_id"], row["root_id"]): row
                for row in result["metric_rows"]
            }
            self.assertEqual(
                rows_by_key[("synchrony_coherence_index", None)]["value"],
                1.0,
            )
            self.assertAlmostEqual(
                rows_by_key[("patch_activation_entropy_bits", 101)]["value"],
                1.584962500721,
                places=12,
            )
            self.assertAlmostEqual(
                rows_by_key[("patch_activation_entropy_bits", 202)]["value"],
                1.584962500721,
                places=12,
            )
            self.assertEqual(
                rows_by_key[("phase_gradient_mean_rad_per_patch", 101)]["value"],
                1.0,
            )
            self.assertEqual(
                rows_by_key[("phase_gradient_dispersion_rad_per_patch", 101)]["value"],
                0.0,
            )
            self.assertEqual(
                rows_by_key[("wavefront_speed_patch_per_ms", 101)]["value"],
                1.0,
            )
            self.assertEqual(
                rows_by_key[("wavefront_curvature_inv_patch", 101)]["value"],
                0.0,
            )

            summaries_by_key = {
                (item["metric_id"], item["root_id"]): item
                for item in result["diagnostic_summaries"]
            }
            self.assertEqual(
                summaries_by_key[("synchrony_coherence_index", None)]["status"],
                "ok",
            )
            self.assertEqual(
                summaries_by_key[("wavefront_speed_patch_per_ms", 101)]["diagnostics"][
                    "arrival_count"
                ],
                2,
            )
            self.assertEqual(
                summaries_by_key[("phase_gradient_mean_rad_per_patch", 101)][
                    "required_source_artifact_classes"
                ],
                [
                    SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                    SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
                    SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
                ],
            )

    def test_compute_wave_structure_diagnostics_handles_mixed_fidelity_partial_availability(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _write_wave_bundle_fixture(
                Path(tmp_dir_str),
                mixed_fidelity=True,
                include_phase_map=False,
            )

            result = compute_wave_structure_diagnostics(
                bundle_records=[{"bundle_metadata": fixture["metadata"]}],
                requested_metric_ids=[
                    "patch_activation_entropy_bits",
                    "synchrony_coherence_index",
                ],
            )

            rows_by_key = {
                (row["metric_id"], row["root_id"]): row
                for row in result["metric_rows"]
            }
            self.assertIn(("patch_activation_entropy_bits", 101), rows_by_key)
            self.assertNotIn(("patch_activation_entropy_bits", 303), rows_by_key)

            summaries_by_key = {
                (item["metric_id"], item["root_id"]): item
                for item in result["diagnostic_summaries"]
            }
            self.assertEqual(
                summaries_by_key[("synchrony_coherence_index", None)]["status"],
                "unavailable",
            )
            self.assertEqual(
                summaries_by_key[("synchrony_coherence_index", None)]["reason"],
                "insufficient_wave_roots",
            )
            self.assertEqual(
                summaries_by_key[("patch_activation_entropy_bits", 303)]["status"],
                "unavailable",
            )
            self.assertEqual(
                summaries_by_key[("patch_activation_entropy_bits", 303)]["reason"],
                "incompatible_projection_semantics",
            )

    def test_compute_wave_structure_diagnostics_fails_when_patch_traces_artifact_missing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _write_wave_bundle_fixture(
                Path(tmp_dir_str),
                include_patch_traces=False,
            )

            with self.assertRaises(ValueError) as ctx:
                compute_wave_structure_diagnostics(
                    bundle_records=[{"bundle_metadata": fixture["metadata"]}],
                    requested_metric_ids=["patch_activation_entropy_bits"],
                )

            self.assertIn("surface_wave_patch_traces", str(ctx.exception))


def _write_wave_bundle_fixture(
    tmp_dir: Path,
    *,
    include_patch_traces: bool = True,
    include_phase_map: bool = True,
    mixed_fidelity: bool = False,
) -> dict[str, object]:
    manifest_path = tmp_dir / "fixture_manifest.yaml"
    manifest_path.write_text("experiment_id: fixture_wave_structure\n", encoding="utf-8")

    manifest_reference = build_simulator_manifest_reference(
        experiment_id="fixture_wave_structure",
        manifest_path=manifest_path,
        milestone="milestone_12",
    )
    input_bundle_path = tmp_dir / "fixture_input_bundle.json"
    input_bundle_path.write_text("{}", encoding="utf-8")
    selected_assets = [
        build_selected_asset_reference(
            asset_role="input_bundle",
            artifact_type="stimulus_bundle",
            path=input_bundle_path,
        )
    ]
    arm_reference = build_simulator_arm_reference(
        arm_id="surface_wave_fixture",
        model_mode="surface_wave",
        baseline_family=None,
    )
    readout_catalog = [
        build_simulator_readout_definition(
            readout_id="shared_output_mean",
            scope="circuit_output",
            aggregation="mean_over_root_ids",
            units="activation_au",
            value_semantics="mean activation over the shared circuit readout surface",
            description="Fixture shared output.",
        )
    ]

    run_spec_hash = build_simulator_run_spec_hash(
        manifest_reference=manifest_reference,
        arm_reference=arm_reference,
        seed=7,
        timebase=FIXTURE_TIMEBASE,
        selected_assets=selected_assets,
        readout_catalog=readout_catalog,
    )
    bundle_paths = build_simulator_result_bundle_paths(
        experiment_id=manifest_reference["experiment_id"],
        arm_id=arm_reference["arm_id"],
        run_spec_hash=run_spec_hash,
        processed_simulator_results_dir=tmp_dir / "processed",
    )
    bundle_paths.bundle_directory.mkdir(parents=True, exist_ok=True)
    bundle_paths.extension_root_directory.mkdir(parents=True, exist_ok=True)

    coarse_operator_path = _write_chain_coarse_operator(
        bundle_paths.extension_root_directory / "root_101_coarse_operator.npz"
    )
    second_coarse_operator_path = _write_chain_coarse_operator(
        bundle_paths.extension_root_directory / "root_202_coarse_operator.npz"
    )

    model_artifacts = [
        build_simulator_extension_artifact_record(
            bundle_paths=bundle_paths,
            artifact_id="surface_wave_summary",
            file_name="surface_wave_summary.json",
            format="json_surface_wave_execution_summary.v1",
            status="ready",
            artifact_scope="wave_model_extension",
            description="Fixture surface-wave summary.",
        ),
    ]
    if include_patch_traces:
        model_artifacts.append(
            build_simulator_extension_artifact_record(
                bundle_paths=bundle_paths,
                artifact_id="surface_wave_patch_traces",
                file_name="surface_wave_patch_traces.npz",
                format="npz_surface_wave_patch_traces.v1",
                status="ready",
                artifact_scope="wave_model_extension",
                description="Fixture patch traces.",
            )
        )
    if include_phase_map:
        model_artifacts.append(
            build_simulator_extension_artifact_record(
                bundle_paths=bundle_paths,
                artifact_id="surface_wave_phase_map",
                file_name="surface_wave_phase_map.npz",
                format="npz_surface_wave_phase_map.v1",
                status="ready",
                artifact_scope="wave_model_extension",
                description="Fixture phase map.",
            )
        )
    mixed_morphology_index = None
    if mixed_fidelity:
        model_artifacts.append(
            build_simulator_extension_artifact_record(
                bundle_paths=bundle_paths,
                artifact_id="mixed_morphology_state_bundle",
                file_name="mixed_morphology_state_bundle.json",
                format="json_mixed_morphology_state_bundle.v1",
                status="ready",
                artifact_scope="wave_model_extension",
                description="Fixture mixed-morphology state bundle.",
            )
        )
        mixed_morphology_index = {
            "format_version": "json_mixed_morphology_index.v1",
            "state_bundle_artifact_id": "mixed_morphology_state_bundle",
            "projection_artifact_id": "surface_wave_patch_traces",
            "shared_state_summary_artifact_id": "state_summary",
            "shared_readout_traces_artifact_id": "readout_traces",
            "roots": [
                {
                    "root_id": 101,
                    "morphology_class": "surface_neuron",
                    "state_bundle_root_key": "101",
                    "runtime_metadata_root_key": "101",
                    "state_summary_ids": ["root_101_patch_activation_state"],
                    "projection_time_array": "substep_time_ms",
                    "projection_trace_array": "root_101_patch_activation",
                    "projection_semantics": "surface_patch_activation",
                    "shared_readout_ids": ["shared_output_mean"],
                },
                {
                    "root_id": 303,
                    "morphology_class": "point_neuron",
                    "state_bundle_root_key": "303",
                    "runtime_metadata_root_key": "303",
                    "state_summary_ids": ["root_303_point_activation_state"],
                    "projection_time_array": "substep_time_ms",
                    "projection_trace_array": "root_303_point_activation",
                    "projection_semantics": "point_projection_activation",
                    "shared_readout_ids": ["shared_output_mean"],
                },
            ],
        }

    metadata = build_simulator_result_bundle_metadata(
        manifest_reference=manifest_reference,
        arm_reference=arm_reference,
        seed=7,
        timebase=FIXTURE_TIMEBASE,
        selected_assets=selected_assets,
        readout_catalog=readout_catalog,
        processed_simulator_results_dir=tmp_dir / "processed",
        model_artifacts=model_artifacts,
        mixed_morphology_index=mixed_morphology_index,
    )
    write_simulator_result_bundle_metadata(metadata, bundle_paths.metadata_json_path)

    summary_roots = [
        {
            "root_id": 101,
            "morphology_class": "surface_neuron",
            "patch_count": 3,
            "source_reference": {
                "coarse_operator_path": str(coarse_operator_path),
            },
        }
    ]
    if mixed_fidelity:
        summary_roots.append(
            {
                "root_id": 303,
                "morphology_class": "point_neuron",
                "patch_count": 1,
                "source_reference": {},
            }
        )
    else:
        summary_roots.append(
            {
                "root_id": 202,
                "morphology_class": "surface_neuron",
                "patch_count": 3,
                "source_reference": {
                    "coarse_operator_path": str(second_coarse_operator_path),
                },
            }
        )
    summary_payload = {
        "format_version": "json_surface_wave_execution_summary.v1",
        "runtime_metadata_by_root": summary_roots,
        "wave_specific_artifacts": {
            "patch_traces_artifact_id": "surface_wave_patch_traces",
            **(
                {"phase_map_artifact_id": "surface_wave_phase_map"}
                if include_phase_map
                else {}
            ),
        },
    }
    write_json(
        summary_payload,
        bundle_paths.extension_root_directory / "surface_wave_summary.json",
    )

    if include_patch_traces:
        patch_payload = {
            "substep_time_ms": np.asarray([0.0, 1.0, 2.0, 3.0], dtype=np.float64),
            "root_ids": (
                np.asarray([101, 303], dtype=np.int64)
                if mixed_fidelity
                else np.asarray([101, 202], dtype=np.int64)
            ),
            "root_101_patch_activation": np.asarray(
                [
                    [1.0, 0.0, 0.0],
                    [0.5, 1.0, 0.0],
                    [0.0, 0.5, 1.0],
                    [0.0, 0.0, 0.5],
                ],
                dtype=np.float64,
            ),
        }
        if mixed_fidelity:
            patch_payload["root_303_point_activation"] = np.asarray(
                [[0.0], [0.2], [0.2], [0.0]],
                dtype=np.float64,
            )
        else:
            patch_payload["root_202_patch_activation"] = np.asarray(
                [
                    [2.0, 0.0, 0.0],
                    [1.0, 2.0, 0.0],
                    [0.0, 1.0, 2.0],
                    [0.0, 0.0, 1.0],
                ],
                dtype=np.float64,
            )
        write_deterministic_npz(
            patch_payload,
            bundle_paths.extension_root_directory / "surface_wave_patch_traces.npz",
        )

    if include_phase_map:
        phase_payload = {
            "substep_time_ms": np.asarray([0.0, 1.0, 2.0, 3.0], dtype=np.float64),
            "root_ids": np.asarray([101, 202], dtype=np.int64),
            "root_101_phase_rad": np.asarray(
                [[0.0, 1.0, 2.0]] * 4,
                dtype=np.float64,
            ),
            "root_202_phase_rad": np.asarray(
                [[0.5, 1.5, 2.5]] * 4,
                dtype=np.float64,
            ),
        }
        write_deterministic_npz(
            phase_payload,
            bundle_paths.extension_root_directory / "surface_wave_phase_map.npz",
        )

    if mixed_fidelity:
        write_json(
            {
                "format_version": "json_mixed_morphology_state_bundle.v1",
                "runtime_metadata_by_root": {
                    "101": {"root_id": 101, "morphology_class": "surface_neuron"},
                    "303": {"root_id": 303, "morphology_class": "point_neuron"},
                },
                "initial_state_exports_by_root": {
                    "101": {"activation": [0.0, 0.0, 0.0], "velocity": [0.0, 0.0, 0.0]},
                    "303": {"activation": [0.0], "velocity": [0.0]},
                },
                "final_state_exports_by_root": {
                    "101": {"activation": [0.0, 0.0, 0.5], "velocity": [0.0, 0.0, 0.0]},
                    "303": {"activation": [0.0], "velocity": [0.0]},
                },
            },
            bundle_paths.extension_root_directory / "mixed_morphology_state_bundle.json",
        )

    return {
        "metadata": load_simulator_result_bundle_metadata(bundle_paths.metadata_json_path),
        "metadata_path": bundle_paths.metadata_json_path,
    }


def _write_chain_coarse_operator(path: Path) -> Path:
    matrix = sp.csr_matrix(
        np.asarray(
            [
                [1.0, -1.0, 0.0],
                [-1.0, 2.0, -1.0],
                [0.0, -1.0, 1.0],
            ],
            dtype=np.float64,
        )
    )
    payload = {
        f"operator_{key}": value
        for key, value in serialize_sparse_matrix(matrix).items()
    }
    write_deterministic_npz(payload, path)
    return path.resolve()


if __name__ == "__main__":
    unittest.main()
