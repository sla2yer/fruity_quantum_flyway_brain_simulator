from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.io_utils import read_root_ids
from flywire_wave.registry import load_synapse_registry
from flywire_wave.selection import generate_subsets_from_config


class SelectionPresetToolTest(unittest.TestCase):
    def test_active_preset_writes_manifest_stats_preview_and_root_id_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            registry_path, connectivity_path = _write_fixture_registry(tmp_dir)
            selected_root_ids_path = tmp_dir / "active_root_ids.txt"
            subset_output_dir = tmp_dir / "subsets"

            cfg = _fixture_config(
                registry_path=registry_path,
                connectivity_path=connectivity_path,
                selected_root_ids_path=selected_root_ids_path,
                subset_output_dir=subset_output_dir,
            )

            summary = generate_subsets_from_config(cfg, config_path=tmp_dir / "config.yaml")

            self.assertEqual(summary["active_preset"], "motion_medium")
            self.assertEqual(len(summary["generated_presets"]), 1)

            generated = summary["generated_presets"][0]
            self.assertEqual(generated["preset_name"], "motion_medium")
            self.assertEqual(generated["root_id_count"], 13)

            manifest = json.loads(Path(generated["paths"]["manifest_json"]).read_text(encoding="utf-8"))
            stats = json.loads(Path(generated["paths"]["stats_json"]).read_text(encoding="utf-8"))
            preview = Path(generated["paths"]["preview_markdown"]).read_text(encoding="utf-8")

            self.assertEqual(manifest["preset_name"], "motion_medium")
            self.assertEqual(len(manifest["root_ids"]), 13)
            self.assertIn(11, manifest["root_ids"])
            self.assertIn(12, manifest["root_ids"])
            self.assertIn(13, manifest["root_ids"])
            self.assertEqual(stats["selection"]["final_neuron_count"], 13)
            self.assertEqual(len(stats["relation_steps"]), 2)
            self.assertIn("```mermaid", preview)

            self.assertEqual(
                read_root_ids(selected_root_ids_path),
                [int(root_id) for root_id in manifest["root_ids"]],
            )

    def test_generate_all_presets_respects_inheritance_and_relation_append(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            registry_path, connectivity_path = _write_fixture_registry(tmp_dir)
            selected_root_ids_path = tmp_dir / "active_root_ids.txt"
            subset_output_dir = tmp_dir / "subsets"

            cfg = _fixture_config(
                registry_path=registry_path,
                connectivity_path=connectivity_path,
                selected_root_ids_path=selected_root_ids_path,
                subset_output_dir=subset_output_dir,
            )

            summary = generate_subsets_from_config(
                cfg,
                config_path=tmp_dir / "config.yaml",
                generate_all=True,
            )

            preset_counts = {
                item["preset_name"]: item["root_id_count"]
                for item in summary["generated_presets"]
            }
            self.assertEqual(
                preset_counts,
                {
                    "motion_minimal": 10,
                    "motion_medium": 13,
                    "motion_dense": 14,
                },
            )

            dense_manifest_path = next(
                item["paths"]["manifest_json"]
                for item in summary["generated_presets"]
                if item["preset_name"] == "motion_dense"
            )
            dense_stats_path = next(
                item["paths"]["stats_json"]
                for item in summary["generated_presets"]
                if item["preset_name"] == "motion_dense"
            )

            dense_manifest = json.loads(Path(dense_manifest_path).read_text(encoding="utf-8"))
            dense_stats = json.loads(Path(dense_stats_path).read_text(encoding="utf-8"))

            self.assertIn(14, dense_manifest["root_ids"])
            self.assertEqual(len(dense_stats["relation_steps"]), 3)
            self.assertEqual(
                [step["name"] for step in dense_stats["relation_steps"]],
                ["add_direct_context", "add_downstream_readout", "add_halo_context"],
            )

    def test_active_preset_refreshes_subset_scoped_synapse_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            registry_path, connectivity_path = _write_fixture_registry(tmp_dir)
            synapse_source_path = _write_fixture_synapses(tmp_dir / "synapses.csv")
            selected_root_ids_path = tmp_dir / "active_root_ids.txt"
            subset_output_dir = tmp_dir / "subsets"
            processed_coupling_dir = tmp_dir / "processed_coupling"

            cfg = _fixture_config(
                registry_path=registry_path,
                connectivity_path=connectivity_path,
                selected_root_ids_path=selected_root_ids_path,
                subset_output_dir=subset_output_dir,
                processed_coupling_dir=processed_coupling_dir,
                synapse_source_csv=synapse_source_path,
            )

            generate_subsets_from_config(cfg, config_path=tmp_dir / "config.yaml")

            selected_root_ids = set(read_root_ids(selected_root_ids_path))
            synapse_registry = load_synapse_registry(processed_coupling_dir / "synapse_registry.csv")

            self.assertEqual(synapse_registry["synapse_id"].tolist(), ["syn-1", "syn-4"])
            self.assertTrue(synapse_registry["pre_root_id"].isin(selected_root_ids).all())
            self.assertTrue(synapse_registry["post_root_id"].isin(selected_root_ids).all())


def _fixture_config(
    *,
    registry_path: Path,
    connectivity_path: Path,
    selected_root_ids_path: Path,
    subset_output_dir: Path,
    processed_coupling_dir: Path | None = None,
    synapse_source_csv: Path | None = None,
) -> dict:
    paths = {
        "neuron_registry_csv": str(registry_path),
        "connectivity_registry_csv": str(connectivity_path),
        "selected_root_ids": str(selected_root_ids_path),
        "subset_output_dir": str(subset_output_dir),
    }
    if processed_coupling_dir is not None:
        paths["processed_coupling_dir"] = str(processed_coupling_dir)
    if synapse_source_csv is not None:
        paths["synapse_source_csv"] = str(synapse_source_csv)

    return {
        "paths": {
            **paths,
        },
        "selection": {
            "active_preset": "motion_medium",
            "sort_by": "root_id",
            "preview_edge_limit": 12,
            "presets": {
                "motion_minimal": {
                    "description": "Milestone 2 locked core T4a/T5a motion channel.",
                    "include": {
                        "super_classes": ["optic"],
                        "cell_types": [
                            "T4a",
                            "T5a",
                            "Mi1",
                            "Tm3",
                            "Mi4",
                            "Mi9",
                            "Tm1",
                            "Tm2",
                            "Tm4",
                            "Tm9",
                        ],
                    },
                    "exclude": {
                        "cell_types": ["R7"],
                    },
                    "max_neurons": 10,
                },
                "motion_medium": {
                    "extends": "motion_minimal",
                    "description": "Add direct context and downstream readout candidates.",
                    "max_neurons": 13,
                    "relations": [
                        {
                            "name": "add_direct_context",
                            "direction": "upstream",
                            "seed": {"cell_types": ["T4a", "T5a"]},
                            "include": {"cell_types": ["CT1", "TmY15"]},
                            "hops": 1,
                            "min_syn_count": 5,
                        },
                        {
                            "name": "add_downstream_readout",
                            "direction": "downstream",
                            "seed": {"cell_types": ["T4a", "T5a"]},
                            "include": {"cell_types": ["LPi"]},
                            "hops": 1,
                            "min_syn_count": 5,
                        },
                    ],
                },
                "motion_dense": {
                    "extends": "motion_medium",
                    "description": "Add one extra halo partner in the neighboring column.",
                    "max_neurons": 14,
                    "relations": [
                        {
                            "name": "add_halo_context",
                            "direction": "upstream",
                            "seed_from": "current",
                            "include": {
                                "cell_types": ["C3"],
                                "column_id_range": [10, 11],
                                "neuropils": ["ME_R"],
                            },
                            "hops": 1,
                            "min_syn_count": 5,
                            "max_added": 1,
                        }
                    ],
                },
            },
        },
    }


def _write_fixture_registry(tmp_dir: Path) -> tuple[Path, Path]:
    registry_path = tmp_dir / "neuron_registry.csv"
    connectivity_path = tmp_dir / "connectivity_registry.csv"

    registry_path.write_text(
        "\n".join(
            [
                "root_id,cell_type,resolved_type,primary_type,project_role,super_class,side,hemisphere,column_id,neuropils,input_neuropils,output_neuropils,snapshot_version,materialization_version",
                "1,T4a,T4a,T4a,surface_simulated,optic,right,right,10,ME_R;LOP_R,ME_R,LOP_R,783,783",
                "2,T5a,T5a,T5a,surface_simulated,optic,right,right,10,LO_R;LOP_R,LO_R,LOP_R,783,783",
                "3,Mi1,Mi1,Mi1,point_simulated,optic,right,right,10,ME_R,,ME_R,783,783",
                "4,Tm3,Tm3,Tm3,point_simulated,optic,right,right,10,ME_R,,ME_R,783,783",
                "5,Mi4,Mi4,Mi4,point_simulated,optic,right,right,11,ME_R,,ME_R,783,783",
                "6,Mi9,Mi9,Mi9,point_simulated,optic,right,right,11,ME_R,,ME_R,783,783",
                "7,Tm1,Tm1,Tm1,point_simulated,optic,right,right,10,LO_R,,LO_R,783,783",
                "8,Tm2,Tm2,Tm2,point_simulated,optic,right,right,10,LO_R,,LO_R,783,783",
                "9,Tm4,Tm4,Tm4,point_simulated,optic,right,right,10,LO_R,,LO_R,783,783",
                "10,Tm9,Tm9,Tm9,point_simulated,optic,right,right,10,LO_R,,LO_R,783,783",
                "11,CT1,CT1,CT1,context_only,optic,right,right,10,ME_R;LO_R,,ME_R;LO_R,783,783",
                "12,TmY15,TmY15,TmY15,context_only,optic,right,right,10,ME_R;LO_R,,ME_R;LO_R,783,783",
                "13,LPi,LPi,LPi,context_only,optic,right,right,10,LOP_R,LOP_R,,783,783",
                "14,C3,C3,C3,context_only,optic,right,right,11,ME_R,,ME_R,783,783",
                "15,R7,R7,R7,context_only,sensory,right,right,10,AME_R,,AME_R,783,783",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    connectivity_path.write_text(
        "\n".join(
            [
                "pre_root_id,post_root_id,neuropil,syn_count,snapshot_version,materialization_version,source_file",
                "3,1,ME_R,20,783,783,connections_filtered.csv",
                "4,1,ME_R,18,783,783,connections_filtered.csv",
                "5,1,ME_R,8,783,783,connections_filtered.csv",
                "6,1,ME_R,7,783,783,connections_filtered.csv",
                "7,2,LO_R,15,783,783,connections_filtered.csv",
                "8,2,LO_R,14,783,783,connections_filtered.csv",
                "9,2,LO_R,10,783,783,connections_filtered.csv",
                "10,2,LO_R,9,783,783,connections_filtered.csv",
                "11,1,ME_R,6,783,783,connections_filtered.csv",
                "12,2,LO_R,6,783,783,connections_filtered.csv",
                "14,1,ME_R,5,783,783,connections_filtered.csv",
                "1,13,LOP_R,11,783,783,connections_filtered.csv",
                "2,13,LOP_R,13,783,783,connections_filtered.csv",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return registry_path, connectivity_path


def _write_fixture_synapses(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "synapse_id,pre_root_id,post_root_id,x,y,z,neuropil",
                "syn-1,1,2,1.0,2.0,3.0,LOP_R",
                "syn-2,1,99,4.0,5.0,6.0,LOP_R",
                "syn-3,99,2,7.0,8.0,9.0,LOP_R",
                "syn-4,12,13,10.0,11.0,12.0,ME_R",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
