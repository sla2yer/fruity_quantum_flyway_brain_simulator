from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.config import get_config_path, get_project_root, load_config


class ConfigPathResolutionTest(unittest.TestCase):
    def test_load_config_resolves_paths_against_explicit_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = tmp_dir / "config.yaml"
            config_path.write_text(
                textwrap.dedent(
                    """
                    paths:
                      neuron_registry_csv: data/interim/registry/neuron_registry.csv
                      synapse_source_csv: data/raw/codex/synapses.csv
                      subset_output_dir: data/interim/subsets
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            cfg = load_config(config_path, project_root=tmp_dir)

            self.assertEqual(get_config_path(cfg), config_path.resolve())
            self.assertEqual(get_project_root(cfg), tmp_dir.resolve())
            self.assertEqual(
                cfg["paths"]["neuron_registry_csv"],
                str((tmp_dir / "data/interim/registry/neuron_registry.csv").resolve()),
            )
            self.assertEqual(
                cfg["paths"]["subset_output_dir"],
                str((tmp_dir / "data/interim/subsets").resolve()),
            )
            self.assertEqual(
                cfg["paths"]["classification_csv"],
                str((tmp_dir / "data/raw/codex/classification.csv").resolve()),
            )
            self.assertEqual(
                cfg["paths"]["processed_retinal_dir"],
                str((tmp_dir / "data/processed/retinal").resolve()),
            )
            self.assertEqual(
                cfg["paths"]["synapse_source_csv"],
                str((tmp_dir / "data/raw/codex/synapses.csv").resolve()),
            )


class PipelineConfigPathIntegrationTest(unittest.TestCase):
    def test_pipeline_scripts_work_from_non_repo_cwd_with_absolute_config_path(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as fixture_dir_str:
            fixture_dir = Path(fixture_dir_str)
            fixture_rel = fixture_dir.relative_to(ROOT)
            with tempfile.TemporaryDirectory() as outside_dir_str:
                outside_dir = Path(outside_dir_str)
                config_path = _write_pipeline_fixture(fixture_dir, fixture_rel)
                stub_dir = _write_stub_dependencies(fixture_dir)
                env = os.environ.copy()
                env["FLYWIRE_TOKEN"] = ""
                existing_pythonpath = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = (
                    str(stub_dir)
                    if not existing_pythonpath
                    else os.pathsep.join([str(stub_dir), existing_pythonpath])
                )

                self._run_script("build_registry.py", config_path, outside_dir, env)
                self._run_script("01_select_subset.py", config_path, outside_dir, env)
                self._run_script("02_fetch_meshes.py", config_path, outside_dir, env)
                self._run_script("03_build_wave_assets.py", config_path, outside_dir, env)

                root_ids_path = fixture_dir / "out" / "root_ids.txt"
                raw_mesh_path = fixture_dir / "out" / "meshes_raw" / "101.ply"
                processed_mesh_path = fixture_dir / "out" / "processed_meshes" / "101.ply"
                surface_graph_path = fixture_dir / "out" / "processed_graphs" / "101_graph.npz"
                fine_operator_path = fixture_dir / "out" / "processed_graphs" / "101_fine_operator.npz"
                patch_graph_path = fixture_dir / "out" / "processed_graphs" / "101_patch_graph.npz"
                coarse_operator_path = fixture_dir / "out" / "processed_graphs" / "101_coarse_operator.npz"
                processed_coupling_dir = fixture_dir / "out" / "processed_coupling"
                descriptor_path = fixture_dir / "out" / "processed_graphs" / "101_descriptors.json"
                qa_path = fixture_dir / "out" / "processed_graphs" / "101_qa.json"
                transfer_operator_path = fixture_dir / "out" / "processed_graphs" / "101_transfer_operators.npz"
                operator_metadata_path = fixture_dir / "out" / "processed_graphs" / "101_operator_metadata.json"
                legacy_meta_path = fixture_dir / "out" / "processed_graphs" / "101_meta.json"
                incoming_anchor_map_path = processed_coupling_dir / "roots" / "101_incoming_anchor_map.npz"
                outgoing_anchor_map_path = processed_coupling_dir / "roots" / "101_outgoing_anchor_map.npz"
                coupling_index_path = processed_coupling_dir / "roots" / "101_coupling_index.json"
                manifest_path = fixture_dir / "out" / "asset_manifest.json"

                self.assertEqual(root_ids_path.read_text(encoding="utf-8").strip(), "101")
                self.assertTrue(raw_mesh_path.exists())
                self.assertTrue(processed_mesh_path.exists())
                self.assertTrue(surface_graph_path.exists())
                self.assertTrue(fine_operator_path.exists())
                self.assertTrue(patch_graph_path.exists())
                self.assertTrue(coarse_operator_path.exists())
                self.assertTrue(descriptor_path.exists())
                self.assertTrue(qa_path.exists())
                self.assertTrue(transfer_operator_path.exists())
                self.assertTrue(operator_metadata_path.exists())
                self.assertTrue(legacy_meta_path.exists())
                self.assertTrue(incoming_anchor_map_path.exists())
                self.assertTrue(outgoing_anchor_map_path.exists())
                self.assertTrue(coupling_index_path.exists())

                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["_asset_contract_version"], "geometry_bundle.v1")
                self.assertEqual(manifest["_operator_contract_version"], "operator_bundle.v2")
                self.assertEqual(manifest["_coupling_contract_version"], "coupling_bundle.v1")
                self.assertEqual(manifest["_dataset"]["flywire_dataset"], "public")
                self.assertEqual(manifest["_dataset"]["materialization_version"], 783)
                self.assertEqual(manifest["_meshing_config_snapshot"]["patch_hops"], 2)
                self.assertEqual(
                    manifest["_meshing_config_snapshot"]["operator_assembly"]["boundary_condition"]["mode"],
                    "closed_surface_zero_flux",
                )
                self.assertEqual(
                    manifest["_meshing_config_snapshot"]["coupling_assembly"]["kernel_family"],
                    "separable_rank_one_cloud",
                )
                self.assertEqual(
                    manifest["_coupling_contract"]["local_synapse_registry"]["path"],
                    str((processed_coupling_dir / "synapse_registry.csv").resolve()),
                )
                self.assertIn("101", manifest)
                self.assertEqual(manifest["101"]["processed_mesh_path"], str(processed_mesh_path.resolve()))
                self.assertEqual(manifest["101"]["surface_graph_path"], str(surface_graph_path.resolve()))
                self.assertEqual(manifest["101"]["patch_graph_path"], str(patch_graph_path.resolve()))
                self.assertEqual(manifest["101"]["transfer_operator_path"], str(transfer_operator_path.resolve()))
                self.assertEqual(manifest["101"]["operator_metadata_path"], str(operator_metadata_path.resolve()))
                self.assertEqual(manifest["101"]["descriptor_sidecar_path"], str(descriptor_path.resolve()))
                self.assertEqual(manifest["101"]["qa_sidecar_path"], str(qa_path.resolve()))
                self.assertEqual(manifest["101"]["meta_json_path"], str(legacy_meta_path.resolve()))
                self.assertEqual(manifest["101"]["project_role"], "surface_simulated")
                self.assertEqual(manifest["101"]["bundle_version"], "geometry_bundle.v1")
                self.assertEqual(manifest["101"]["bundle_status"], "ready")
                self.assertEqual(manifest["101"]["assets"]["raw_mesh"]["status"], "ready")
                self.assertEqual(manifest["101"]["assets"]["raw_skeleton"]["status"], "skipped")
                self.assertEqual(manifest["101"]["assets"]["patch_graph"]["status"], "ready")
                self.assertEqual(manifest["101"]["assets"]["transfer_operators"]["status"], "ready")
                self.assertEqual(manifest["101"]["raw_asset_provenance"]["raw_mesh"]["fetch_status"], "fetched")
                self.assertEqual(manifest["101"]["raw_asset_provenance"]["raw_skeleton"]["fetch_status"], "skipped")
                self.assertEqual(
                    manifest["101"]["artifact_sources"]["patch_graph"]["raw_mesh_path"],
                    str(raw_mesh_path.resolve()),
                )
                self.assertEqual(
                    manifest["101"]["artifact_sources"]["patch_graph"]["raw_skeleton_status"],
                    "skipped",
                )
                self.assertEqual(manifest["101"]["build"]["materialization_version"], 783)
                self.assertEqual(manifest["101"]["build"]["meshing_config_snapshot"]["simplify_target_faces"], 8)
                self.assertEqual(manifest["101"]["operator_bundle"]["contract_version"], "operator_bundle.v2")
                self.assertEqual(manifest["101"]["operator_bundle"]["anisotropy_model"], "isotropic")
                self.assertEqual(manifest["101"]["coupling_bundle"]["contract_version"], "coupling_bundle.v1")
                self.assertEqual(manifest["101"]["coupling_bundle"]["status"], "ready")
                self.assertEqual(
                    manifest["101"]["coupling_bundle"]["kernel_family"],
                    "separable_rank_one_cloud",
                )
                self.assertEqual(
                    manifest["101"]["coupling_bundle"]["delay_model"],
                    "constant_zero_ms",
                )
                self.assertEqual(
                    manifest["101"]["coupling_bundle"]["assets"]["local_synapse_registry"]["path"],
                    str((processed_coupling_dir / "synapse_registry.csv").resolve()),
                )
                self.assertEqual(
                    manifest["101"]["coupling_bundle"]["assets"]["incoming_anchor_map"]["status"],
                    "ready",
                )
                self.assertEqual(
                    manifest["101"]["coupling_bundle"]["assets"]["incoming_anchor_map"]["path"],
                    str((processed_coupling_dir / "roots" / "101_incoming_anchor_map.npz").resolve()),
                )
                self.assertEqual(
                    manifest["101"]["coupling_bundle"]["assets"]["outgoing_anchor_map"]["status"],
                    "ready",
                )
                self.assertEqual(
                    manifest["101"]["coupling_bundle"]["assets"]["outgoing_anchor_map"]["path"],
                    str((processed_coupling_dir / "roots" / "101_outgoing_anchor_map.npz").resolve()),
                )
                self.assertEqual(
                    manifest["101"]["coupling_bundle"]["assets"]["coupling_index"]["status"],
                    "ready",
                )
                self.assertEqual(
                    manifest["101"]["coupling_bundle"]["assets"]["coupling_index"]["path"],
                    str((processed_coupling_dir / "roots" / "101_coupling_index.json").resolve()),
                )
                self.assertEqual(manifest["101"]["coupling_bundle"]["edge_bundles"], [])
                self.assertEqual(
                    manifest["101"]["operator_bundle"]["assets"]["fine_operator"]["path"],
                    str(fine_operator_path.resolve()),
                )
                self.assertEqual(
                    manifest["101"]["operator_bundle"]["assets"]["coarse_operator"]["path"],
                    str(coarse_operator_path.resolve()),
                )
                self.assertNotIn(
                    "legacy_alias",
                    manifest["101"]["operator_bundle"]["assets"]["coarse_operator"],
                )
                self.assertEqual(
                    manifest["101"]["operator_bundle"]["transfer_operators"]["coarse_to_fine_prolongation"]["path"],
                    str(transfer_operator_path.resolve()),
                )
                self.assertEqual(
                    manifest["101"]["operator_bundle"]["transfer_operators"]["fine_to_coarse_restriction"][
                        "normalization"
                    ],
                    "lumped_mass_patch_average",
                )

    def test_build_wave_assets_rejects_selected_root_ids_missing_from_registry(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as fixture_dir_str:
            fixture_dir = Path(fixture_dir_str)
            fixture_rel = fixture_dir.relative_to(ROOT)
            with tempfile.TemporaryDirectory() as outside_dir_str:
                outside_dir = Path(outside_dir_str)
                config_path = _write_pipeline_fixture(fixture_dir, fixture_rel)
                stub_dir = _write_stub_dependencies(fixture_dir)
                env = os.environ.copy()
                env["FLYWIRE_TOKEN"] = ""
                existing_pythonpath = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = (
                    str(stub_dir)
                    if not existing_pythonpath
                    else os.pathsep.join([str(stub_dir), existing_pythonpath])
                )

                self._run_script("build_registry.py", config_path, outside_dir, env)

                root_ids_path = fixture_dir / "out" / "root_ids.txt"
                root_ids_path.parent.mkdir(parents=True, exist_ok=True)
                root_ids_path.write_text("101\n999\n", encoding="utf-8")

                meshes_raw_dir = fixture_dir / "out" / "meshes_raw"
                _write_stub_mesh(meshes_raw_dir / "101.ply")
                _write_stub_mesh(meshes_raw_dir / "999.ply")

                result = self._run_script(
                    "03_build_wave_assets.py",
                    config_path,
                    outside_dir,
                    env,
                    expect_success=False,
                )

                self.assertNotEqual(result.returncode, 0)
                combined_output = result.stdout + result.stderr
                self.assertIn("1 selected root IDs were not found in the registry", combined_output)
                self.assertIn("[999]", combined_output)
                self.assertIn(str(fixture_dir / "out" / "registry" / "neuron_registry.csv"), combined_output)
                self.assertFalse((fixture_dir / "out" / "asset_manifest.json").exists())

    def test_build_wave_assets_surfaces_qa_warning_without_failing(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as fixture_dir_str:
            fixture_dir = Path(fixture_dir_str)
            fixture_rel = fixture_dir.relative_to(ROOT)
            with tempfile.TemporaryDirectory() as outside_dir_str:
                outside_dir = Path(outside_dir_str)
                config_path = _write_pipeline_fixture(
                    fixture_dir,
                    fixture_rel,
                    patch_hops=1,
                    patch_vertex_cap=2,
                    meshing_extra_yaml="""
                    qa_thresholds:
                      coarse_max_patch_vertex_fraction:
                        warn: 0.4
                        fail: 0.6
                        blocking: false
                    """,
                )
                stub_dir = _write_stub_dependencies(fixture_dir)
                env = os.environ.copy()
                env["FLYWIRE_TOKEN"] = ""
                existing_pythonpath = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = (
                    str(stub_dir)
                    if not existing_pythonpath
                    else os.pathsep.join([str(stub_dir), existing_pythonpath])
                )

                self._run_script("build_registry.py", config_path, outside_dir, env)
                self._run_script("01_select_subset.py", config_path, outside_dir, env)
                self._run_script("02_fetch_meshes.py", config_path, outside_dir, env)
                result = self._run_script("03_build_wave_assets.py", config_path, outside_dir, env)

                summary = json.loads(result.stdout)
                self.assertEqual(summary["qa"]["overall_status"], "warn")
                self.assertTrue(summary["qa"]["downstream_usable"])
                self.assertEqual(summary["qa"]["warning_root_ids"], [101])
                self.assertEqual(summary["qa"]["blocking_failure_root_ids"], [])
                self.assertIn("coarse_max_patch_vertex_fraction", summary["qa"]["warning_details"][0]["checks"])

    def test_build_wave_assets_fails_on_blocking_qa_violation(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as fixture_dir_str:
            fixture_dir = Path(fixture_dir_str)
            fixture_rel = fixture_dir.relative_to(ROOT)
            with tempfile.TemporaryDirectory() as outside_dir_str:
                outside_dir = Path(outside_dir_str)
                config_path = _write_pipeline_fixture(
                    fixture_dir,
                    fixture_rel,
                    patch_hops=1,
                    patch_vertex_cap=2,
                    meshing_extra_yaml="""
                    qa_thresholds:
                      coarse_max_patch_vertex_fraction:
                        warn: 0.3
                        fail: 0.4
                        blocking: true
                    """,
                )
                stub_dir = _write_stub_dependencies(fixture_dir)
                env = os.environ.copy()
                env["FLYWIRE_TOKEN"] = ""
                existing_pythonpath = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = (
                    str(stub_dir)
                    if not existing_pythonpath
                    else os.pathsep.join([str(stub_dir), existing_pythonpath])
                )

                self._run_script("build_registry.py", config_path, outside_dir, env)
                self._run_script("01_select_subset.py", config_path, outside_dir, env)
                self._run_script("02_fetch_meshes.py", config_path, outside_dir, env)
                result = self._run_script(
                    "03_build_wave_assets.py",
                    config_path,
                    outside_dir,
                    env,
                    expect_success=False,
                )

                self.assertNotEqual(result.returncode, 0)
                summary = json.loads(result.stdout)
                self.assertEqual(summary["qa"]["overall_status"], "fail")
                self.assertFalse(summary["qa"]["downstream_usable"])
                self.assertEqual(summary["qa"]["blocking_failure_root_ids"], [101])
                self.assertIn("coarse_max_patch_vertex_fraction", summary["qa"]["blocking_failure_details"][0]["checks"])

    def test_build_wave_assets_reports_missing_raw_meshes_after_processing_remaining_roots(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as fixture_dir_str:
            fixture_dir = Path(fixture_dir_str)
            fixture_rel = fixture_dir.relative_to(ROOT)
            with tempfile.TemporaryDirectory() as outside_dir_str:
                outside_dir = Path(outside_dir_str)
                config_path = _write_pipeline_fixture(fixture_dir, fixture_rel)
                stub_dir = _write_stub_dependencies(fixture_dir)
                env = os.environ.copy()
                env["FLYWIRE_TOKEN"] = ""
                existing_pythonpath = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = (
                    str(stub_dir)
                    if not existing_pythonpath
                    else os.pathsep.join([str(stub_dir), existing_pythonpath])
                )

                self._run_script("build_registry.py", config_path, outside_dir, env)

                root_ids_path = fixture_dir / "out" / "root_ids.txt"
                root_ids_path.parent.mkdir(parents=True, exist_ok=True)
                root_ids_path.write_text("101\n102\n", encoding="utf-8")

                meshes_raw_dir = fixture_dir / "out" / "meshes_raw"
                _write_stub_mesh(meshes_raw_dir / "101.ply")

                result = self._run_script(
                    "03_build_wave_assets.py",
                    config_path,
                    outside_dir,
                    env,
                    expect_success=False,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn("Missing raw meshes blocked root_ids=102", result.stderr)

                summary = json.loads(result.stdout)
                self.assertEqual(summary["build"]["built_root_ids"], [101])
                self.assertEqual(summary["build"]["skipped_root_ids"], [102])
                self.assertEqual(summary["build"]["failed_root_ids"], [])
                self.assertEqual(summary["build"]["missing_raw_mesh_count"], 1)
                self.assertEqual(summary["build"]["missing_raw_mesh_root_ids"], [102])
                self.assertEqual(summary["build"]["root_results"]["101"]["status"], "built")
                self.assertEqual(summary["build"]["root_results"]["102"]["status"], "skipped")
                self.assertEqual(summary["build"]["root_results"]["102"]["reason"], "missing_raw_mesh")
                self.assertTrue(summary["build"]["root_results"]["102"]["blocking"])
                self.assertEqual(summary["exit_code"], 1)
                self.assertEqual(summary["final_status"], "fail")

                manifest_path = fixture_dir / "out" / "asset_manifest.json"
                self.assertTrue(manifest_path.exists())
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertIn("101", manifest)
                self.assertIn("102", manifest)
                self.assertEqual(manifest["101"]["bundle_status"], "ready")
                self.assertEqual(manifest["102"]["assets"]["raw_mesh"]["status"], "missing")
                self.assertEqual(manifest["102"]["assets"]["patch_graph"]["status"], "missing")
                self.assertEqual(manifest["102"]["operator_bundle"]["status"], "missing")
                self.assertEqual(manifest["102"]["build_result"]["status"], "skipped")
                self.assertEqual(manifest["102"]["build_result"]["reason"], "missing_raw_mesh")

    def _run_script(
        self,
        script_name: str,
        config_path: Path,
        cwd: Path,
        env: dict[str, str],
        *,
        expect_success: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script_name), "--config", str(config_path)],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if expect_success and result.returncode != 0:
            self.fail(
                f"{script_name} failed with code {result.returncode}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return result


def _write_pipeline_fixture(
    fixture_dir: Path,
    fixture_rel: Path,
    *,
    patch_hops: int = 2,
    patch_vertex_cap: int = 8,
    meshing_extra_yaml: str = "",
) -> Path:
    raw_dir = fixture_dir / "raw" / "codex"
    raw_dir.mkdir(parents=True)

    (raw_dir / "classification.csv").write_text(
        "\n".join(
            [
                "root_id,flow,super_class,class,sub_class,hemilineage,side,nerve",
                "101,intrinsic,optic,optic_lobe_intrinsic,t5_neuron,,right,",
                "102,intrinsic,optic,optic_lobe_intrinsic,transmedullary,,right,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (raw_dir / "cell_types.csv").write_text(
        "\n".join(
            [
                "root_id,primary_type,additional_type(s)",
                "101,T5a,",
                "102,Tm1,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (raw_dir / "connections_filtered.csv").write_text(
        "\n".join(
            [
                "pre_root_id,post_root_id,neuropil,syn_count,nt_type",
                "101,102,LOP_R,12,ACH",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (raw_dir / "neurotransmitter_type_predictions.csv").write_text(
        "\n".join(
            [
                "root_id,group,nt_type,nt_type_score,da_avg,ser_avg,gaba_avg,glut_avg,ach_avg,oct_avg",
                "101,LO.LOP,ACH,0.71,0.0,0.0,0.0,0.0,0.71,0.0",
                "102,ME,ACH,0.61,0.0,0.0,0.0,0.0,0.61,0.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rel_prefix = fixture_rel.as_posix()
    config_path = fixture_dir / "config.yaml"
    meshing_extra_block = ""
    if meshing_extra_yaml.strip():
        meshing_extra_block = "\n" + textwrap.indent(textwrap.dedent(meshing_extra_yaml).strip(), "              ")
    config_path.write_text(
        textwrap.dedent(
            f"""
            dataset:
              materialization_version: 783
              flywire_dataset: public

            paths:
              codex_raw_dir: {rel_prefix}/raw/codex
              classification_csv: {rel_prefix}/raw/codex/classification.csv
              neuron_registry_csv: {rel_prefix}/out/registry/neuron_registry.csv
              connectivity_registry_csv: {rel_prefix}/out/registry/connectivity_registry.csv
              registry_provenance_json: {rel_prefix}/out/registry/registry_provenance.json
              selected_root_ids: {rel_prefix}/out/root_ids.txt
              subset_output_dir: {rel_prefix}/out/subsets
              meshes_raw_dir: {rel_prefix}/out/meshes_raw
              skeletons_raw_dir: {rel_prefix}/out/skeletons_raw
              processed_mesh_dir: {rel_prefix}/out/processed_meshes
              processed_graph_dir: {rel_prefix}/out/processed_graphs
              processed_coupling_dir: {rel_prefix}/out/processed_coupling
              manifest_json: {rel_prefix}/out/asset_manifest.json

            registry:
              snapshot_version: 783

            selection:
              active_preset: demo
              sort_by: root_id
              presets:
                demo:
                  description: Minimal integration selection.
                  include:
                    cell_types:
                      - T5a
                  max_neurons: 1

            meshing:
              fetch_skeletons: false
              refetch_meshes: false
              refetch_skeletons: false
              require_skeletons: false
              simplify_target_faces: 8
              patch_hops: {patch_hops}
              patch_vertex_cap: {patch_vertex_cap}
              operator_assembly:
                version: operator_assembly.v1
                boundary_condition:
                  mode: closed_surface_zero_flux
                anisotropy:
                  model: isotropic{meshing_extra_block}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path.resolve()


def _write_stub_dependencies(fixture_dir: Path) -> Path:
    stub_dir = fixture_dir / "stubs"
    fafbseg_dir = stub_dir / "fafbseg"
    fafbseg_dir.mkdir(parents=True)

    (fafbseg_dir / "__init__.py").write_text(
        "from . import flywire\n",
        encoding="utf-8",
    )
    (fafbseg_dir / "flywire.py").write_text(
        textwrap.dedent(
            """
            import numpy as np


            class _MeshNeuron:
                def __init__(self) -> None:
                    self.vertices = np.asarray(
                        [
                            [0.0, 0.0, 0.0],
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                        dtype=float,
                    )
                    self.faces = np.asarray(
                        [
                            [0, 1, 2],
                            [0, 1, 3],
                            [0, 2, 3],
                            [1, 2, 3],
                        ],
                        dtype=int,
                    )


            def set_default_dataset(_dataset: str) -> None:
                return None


            def get_mesh_neuron(_root_id: int) -> _MeshNeuron:
                return _MeshNeuron()


            def get_skeletons(_root_id: int) -> object:
                return object()
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (stub_dir / "navis.py").write_text(
        textwrap.dedent(
            """
            from pathlib import Path


            def write_swc(_skeleton: object, path: str | Path) -> None:
                Path(path).write_text("# stub skeleton\\n", encoding="utf-8")
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return stub_dir


def _write_stub_mesh(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """
            ply
            format ascii 1.0
            element vertex 4
            property float x
            property float y
            property float z
            element face 4
            property list uchar int vertex_indices
            end_header
            0 0 0
            1 0 0
            0 1 0
            0 0 1
            3 0 1 2
            3 0 1 3
            3 0 2 3
            3 1 2 3
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
