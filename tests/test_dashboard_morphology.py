from __future__ import annotations

import html
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.dashboard_morphology import (
    build_dashboard_morphology_context,
    resolve_dashboard_morphology_view_model,
)
from flywire_wave.dashboard_session_planning import (
    package_dashboard_session,
    resolve_dashboard_session_plan,
)
from flywire_wave.io_utils import write_deterministic_npz, write_json
from flywire_wave.simulator_result_contract import (
    METRICS_TABLE_KEY,
    READOUT_TRACES_KEY,
    STATE_SUMMARY_KEY,
    build_selected_asset_reference,
    build_simulator_arm_reference,
    build_simulator_extension_artifact_record,
    build_simulator_manifest_reference,
    build_simulator_readout_definition,
    build_simulator_result_bundle_metadata,
    build_simulator_result_bundle_paths,
    discover_simulator_result_bundle_paths,
    write_simulator_result_bundle_metadata,
)

try:
    from test_dashboard_session_planning import _materialize_dashboard_fixture
except ModuleNotFoundError:
    from tests.test_dashboard_session_planning import _materialize_dashboard_fixture


class DashboardMorphologyTest(unittest.TestCase):
    def test_fixture_session_packages_surface_and_skeleton_render_models(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            plan = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )

            morphology = plan["pane_inputs"]["morphology"]
            root_by_id = {
                int(item["root_id"]): dict(item)
                for item in morphology["root_catalog"]
            }

            self.assertEqual(
                morphology["context_version"],
                "dashboard_morphology_context.v1",
            )
            self.assertEqual(
                root_by_id[101]["preferred_representation"],
                "surface_mesh",
            )
            self.assertGreater(
                len(root_by_id[101]["render_geometry"]["mesh_polygons"]),
                0,
            )
            self.assertEqual(
                root_by_id[202]["morphology_class"],
                "skeleton_neuron",
            )
            self.assertEqual(
                root_by_id[202]["preferred_representation"],
                "skeleton",
            )
            self.assertGreater(
                len(root_by_id[202]["render_geometry"]["segments"]),
                0,
            )
            self.assertEqual(
                morphology["overlay_support"]["shared_readout_activity"]["availability"],
                "available",
            )
            self.assertEqual(
                morphology["overlay_support"]["wave_patch_activity"]["availability"],
                "available",
            )

            packaged = package_dashboard_session(plan)
            html_text = Path(packaged["app_shell_path"]).read_text(encoding="utf-8")
            bootstrap = _extract_embedded_json(
                html_text,
                script_id="dashboard-app-bootstrap",
            )
            packaged_root_by_id = {
                int(item["root_id"]): dict(item)
                for item in bootstrap["morphology_context"]["root_catalog"]
            }
            self.assertEqual(
                packaged_root_by_id[101]["render_geometry"]["representation_id"],
                "surface_mesh",
            )
            self.assertEqual(
                packaged_root_by_id[202]["render_geometry"]["representation_id"],
                "skeleton",
            )
            self.assertIn('data-pane-id="morphology"', html_text)

    def test_view_model_normalizes_shared_and_wave_overlay_states(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            plan = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            morphology = plan["pane_inputs"]["morphology"]

            shared_view = resolve_dashboard_morphology_view_model(
                morphology,
                selected_neuron_id=101,
                active_overlay_id="shared_readout_activity",
                selected_readout_id="shared_output_mean",
                comparison_mode="paired_baseline_vs_wave",
                active_arm_id="surface_wave_intact",
                sample_index=2,
            )
            self.assertEqual(
                shared_view["overlay_state"]["availability"],
                "available",
            )
            self.assertEqual(
                shared_view["overlay_state"]["scope_label"],
                "shared_comparison",
            )
            self.assertGreater(
                shared_view["overlay_state"]["wave_value"],
                shared_view["overlay_state"]["baseline_value"],
            )
            self.assertEqual(
                len(shared_view["camera_focus"]["view_box"]),
                4,
            )

            wave_view = resolve_dashboard_morphology_view_model(
                morphology,
                selected_neuron_id=202,
                active_overlay_id="wave_patch_activity",
                selected_readout_id="shared_output_mean",
                comparison_mode="paired_baseline_vs_wave",
                active_arm_id="surface_wave_intact",
                sample_index=3,
            )
            self.assertEqual(
                wave_view["overlay_state"]["availability"],
                "available",
            )
            self.assertEqual(
                len(wave_view["overlay_state"]["element_values"]),
                3,
            )
            self.assertEqual(
                wave_view["overlay_state"]["scope_label"],
                "wave_only_diagnostic",
            )

            inapplicable_view = resolve_dashboard_morphology_view_model(
                morphology,
                selected_neuron_id=101,
                active_overlay_id="reviewer_findings",
                selected_readout_id="shared_output_mean",
                comparison_mode="paired_baseline_vs_wave",
                active_arm_id="surface_wave_intact",
                sample_index=1,
            )
            self.assertEqual(
                inapplicable_view["overlay_state"]["availability"],
                "inapplicable",
            )
            self.assertIn(
                "another pane",
                str(inapplicable_view["overlay_state"]["reason"]).lower(),
            )

    def test_point_fallback_context_remains_displayable_without_geometry_assets(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _build_point_fallback_fixture(tmp_dir)
            context = build_dashboard_morphology_context(
                circuit_context=fixture["circuit_context"],
                baseline_metadata=fixture["baseline_metadata"],
                wave_metadata=fixture["wave_metadata"],
                analysis_ui_payload=fixture["analysis_ui_payload"],
                selected_neuron_id=303,
            )

            root = context["root_catalog"][0]
            self.assertEqual(root["morphology_class"], "point_neuron")
            self.assertEqual(root["preferred_representation"], "point_fallback")
            self.assertTrue(root["displayable"])
            self.assertEqual(
                root["overlay_samples"]["wave_patch_activity"]["availability"],
                "available",
            )
            self.assertEqual(
                len(root["overlay_samples"]["wave_patch_activity"]["element_series"]),
                1,
            )


def _build_point_fallback_fixture(tmp_dir: Path) -> dict[str, object]:
    processed_dir = tmp_dir / "simulator_results"
    geometry_manifest_path = tmp_dir / "geometry_manifest.json"
    write_json({"_asset_contract_version": "geometry_bundle.v1"}, geometry_manifest_path)

    selected_assets = [
        build_selected_asset_reference(
            asset_role="geometry_manifest",
            artifact_type="geometry_bundle",
            path=geometry_manifest_path,
            contract_version="geometry_bundle.v1",
            artifact_id="fixture_geometry_manifest",
            bundle_id=None,
        )
    ]
    readout_catalog = [
        build_simulator_readout_definition(
            readout_id="shared_output_mean",
            scope="circuit_output",
            aggregation="mean_over_root_ids",
            units="activation_au",
            value_semantics="shared_downstream_activation",
            description="Fixture shared readout.",
        )
    ]
    timebase = {
        "dt_ms": 1.0,
        "duration_ms": 3.0,
        "sample_count": 3,
        "time_origin_ms": 0.0,
        "sampling_mode": "fixed_step_uniform",
    }
    manifest_reference = build_simulator_manifest_reference(
        experiment_id="dashboard_point_fixture",
        manifest_path=tmp_dir / "fixture_manifest.yaml",
        milestone="14",
    )
    baseline_metadata = build_simulator_result_bundle_metadata(
        manifest_reference=manifest_reference,
        arm_reference=build_simulator_arm_reference(
            arm_id="baseline_fixture",
            model_mode="baseline",
            baseline_family="P0",
            comparison_tags=[],
        ),
        timebase=timebase,
        seed=7,
        selected_assets=selected_assets,
        readout_catalog=readout_catalog,
        processed_simulator_results_dir=processed_dir,
        state_summary_status="ready",
        readout_traces_status="ready",
        metrics_table_status="ready",
    )
    write_simulator_result_bundle_metadata(baseline_metadata)
    _write_shared_bundle_artifacts(
        baseline_metadata,
        trace_values=np.asarray([[0.0], [0.2], [0.3]], dtype=np.float64),
        state_summary_rows=[],
    )

    wave_bundle_paths = build_simulator_result_bundle_paths(
        experiment_id="dashboard_point_fixture",
        arm_id="surface_wave_fixture",
        run_spec_hash=build_simulator_result_bundle_metadata(
            manifest_reference=manifest_reference,
            arm_reference=build_simulator_arm_reference(
                arm_id="surface_wave_fixture",
                model_mode="surface_wave",
                baseline_family=None,
                comparison_tags=["mixed_fidelity"],
            ),
            timebase=timebase,
            seed=7,
            selected_assets=selected_assets,
            readout_catalog=readout_catalog,
            processed_simulator_results_dir=processed_dir,
            state_summary_status="ready",
            readout_traces_status="ready",
            metrics_table_status="ready",
        )["run_spec_hash"],
        processed_simulator_results_dir=processed_dir,
    )
    patch_artifact = build_simulator_extension_artifact_record(
        bundle_paths=wave_bundle_paths,
        artifact_id="surface_wave_patch_traces",
        file_name="surface_wave_patch_traces.npz",
        format="npz_surface_wave_patch_traces.v1",
        status="ready",
        artifact_scope="shared_comparison",
        description="Point projection traces.",
    )
    state_bundle_artifact = build_simulator_extension_artifact_record(
        bundle_paths=wave_bundle_paths,
        artifact_id="mixed_morphology_state_bundle",
        file_name="mixed_morphology_state_bundle.json",
        format="json_mixed_morphology_state_bundle.v1",
        status="ready",
        artifact_scope="model_diagnostic",
        description="Point state exports.",
    )
    wave_metadata = build_simulator_result_bundle_metadata(
        manifest_reference=manifest_reference,
        arm_reference=build_simulator_arm_reference(
            arm_id="surface_wave_fixture",
            model_mode="surface_wave",
            baseline_family=None,
            comparison_tags=["mixed_fidelity"],
        ),
        timebase=timebase,
        seed=7,
        selected_assets=selected_assets,
        readout_catalog=readout_catalog,
        processed_simulator_results_dir=processed_dir,
        state_summary_status="ready",
        readout_traces_status="ready",
        metrics_table_status="ready",
        model_artifacts=[patch_artifact, state_bundle_artifact],
        mixed_morphology_index={
            "format_version": "json_mixed_morphology_index.v1",
            "state_bundle_artifact_id": "mixed_morphology_state_bundle",
            "projection_artifact_id": "surface_wave_patch_traces",
            "shared_state_summary_artifact_id": "state_summary",
            "shared_readout_traces_artifact_id": "readout_traces",
            "roots": [
                {
                    "root_id": 303,
                    "morphology_class": "point_neuron",
                    "state_bundle_root_key": "303",
                    "runtime_metadata_root_key": "303",
                    "state_summary_ids": ["root_303_point_activation_state"],
                    "projection_time_array": "shared_time_ms",
                    "projection_trace_array": "root_303_point_activation",
                    "projection_semantics": "point_projection_activation",
                    "shared_readout_ids": ["shared_output_mean"],
                }
            ],
        },
    )
    write_simulator_result_bundle_metadata(wave_metadata)
    _write_shared_bundle_artifacts(
        wave_metadata,
        trace_values=np.asarray([[0.1], [0.3], [0.45]], dtype=np.float64),
        state_summary_rows=[
            {
                "state_id": "root_303_point_activation_state",
                "scope": "root_state",
                "summary_stat": "mean",
                "value": 0.45,
                "units": "activation_au",
            }
        ],
    )
    wave_paths = discover_simulator_result_bundle_paths(wave_metadata)
    write_deterministic_npz(
        {
            "shared_time_ms": np.asarray([0.0, 1.0, 2.0], dtype=np.float64),
            "root_ids": np.asarray([303], dtype=np.int64),
            "root_303_point_activation": np.asarray([[0.0], [0.25], [0.45]], dtype=np.float64),
        },
        wave_bundle_paths.extension_root_directory / "surface_wave_patch_traces.npz",
    )
    write_json(
        {
            "format_version": "json_mixed_morphology_state_bundle.v1",
            "runtime_metadata_by_root": {
                "303": {
                    "root_id": 303,
                    "morphology_class": "point_neuron",
                    "baseline_family": "P0",
                }
            },
            "initial_state_exports_by_root": {
                "303": {"activation": [0.0], "velocity": [0.0]},
            },
            "final_state_exports_by_root": {
                "303": {"activation": [0.45], "velocity": [0.0]},
            },
        },
        wave_bundle_paths.extension_root_directory / "mixed_morphology_state_bundle.json",
    )

    missing_asset = {
        "path": str(tmp_dir / "missing_asset.bin"),
        "status": "missing",
        "exists": False,
    }
    circuit_context = {
        "root_catalog": [
            {
                "root_id": 303,
                "cell_type": "fixture_303",
                "project_role": "point_proxy",
                "morphology_class": "point_neuron",
                "geometry_assets": {
                    "simplified_mesh": dict(missing_asset),
                    "raw_skeleton": dict(missing_asset),
                    "surface_graph": dict(missing_asset),
                    "patch_graph": dict(missing_asset),
                },
            }
        ]
    }
    return {
        "baseline_metadata": baseline_metadata,
        "wave_metadata": wave_metadata,
        "circuit_context": circuit_context,
        "analysis_ui_payload": {
            "wave_only_diagnostics": {
                "phase_map_references": [],
            }
        },
        "wave_readout_traces_path": wave_paths[READOUT_TRACES_KEY],
    }


def _write_shared_bundle_artifacts(
    bundle_metadata: dict[str, object],
    *,
    trace_values: np.ndarray,
    state_summary_rows: list[dict[str, object]],
) -> None:
    bundle_paths = discover_simulator_result_bundle_paths(bundle_metadata)
    write_json(state_summary_rows, bundle_paths[STATE_SUMMARY_KEY])
    bundle_paths[METRICS_TABLE_KEY].parent.mkdir(parents=True, exist_ok=True)
    bundle_paths[METRICS_TABLE_KEY].write_text(
        "metric_id,readout_id,scope,window_id,statistic,value,units\n",
        encoding="utf-8",
    )
    write_deterministic_npz(
        {
            "time_ms": np.asarray([0.0, 1.0, 2.0], dtype=np.float64),
            "readout_ids": np.asarray(["shared_output_mean"]),
            "values": np.asarray(trace_values, dtype=np.float64),
        },
        bundle_paths[READOUT_TRACES_KEY],
    )


def _extract_embedded_json(html_text: str, *, script_id: str) -> dict[str, object]:
    marker = f'<script id="{script_id}" type="application/json">'
    start = html_text.find(marker)
    if start == -1:
        raise AssertionError(f"Could not find JSON script tag {script_id!r}.")
    content_start = start + len(marker)
    content_end = html_text.find("</script>", content_start)
    if content_end == -1:
        raise AssertionError(f"Could not find closing script tag for {script_id!r}.")
    return json.loads(html.unescape(html_text[content_start:content_end]))


if __name__ == "__main__":
    unittest.main()
