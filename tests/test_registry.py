from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.registry import (
    build_registry,
    load_connectivity_registry,
    load_neuron_registry,
    resolve_registry_source_paths,
    validate_selected_root_ids,
)
from flywire_wave.selection import extract_root_ids, select_visual_subset


class RegistryBuildTest(unittest.TestCase):
    def test_resolve_registry_source_paths_rejects_missing_optional_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            raw_dir = tmp_dir / "raw"
            raw_dir.mkdir()

            self._write_classification_csv(raw_dir / "classification.csv")
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

            missing_override = raw_dir / "missing_connections.csv"
            cfg = {
                "paths": {
                    "codex_raw_dir": str(raw_dir),
                    "classification_csv": str(raw_dir / "classification.csv"),
                    "connections_csv": str(missing_override),
                },
            }

            with self.assertRaisesRegex(
                FileNotFoundError,
                rf"paths\.connections_csv.*{re.escape(str(missing_override))}",
            ):
                resolve_registry_source_paths(cfg)

    def test_resolve_registry_source_paths_autodiscovers_optional_sources_without_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            raw_dir = tmp_dir / "raw"
            raw_dir.mkdir()

            classification_path = raw_dir / "classification.csv"
            connections_path = raw_dir / "connections_filtered.csv"
            self._write_classification_csv(classification_path)
            connections_path.write_text(
                "\n".join(
                    [
                        "pre_root_id,post_root_id,neuropil,syn_count,nt_type",
                        "101,102,LOP_R,12,ACH",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            cfg = {
                "paths": {
                    "codex_raw_dir": str(raw_dir),
                    "classification_csv": str(classification_path),
                },
            }

            source_paths = resolve_registry_source_paths(cfg)

            self.assertEqual(source_paths.connections, connections_path)

    def test_build_registry_joins_sources_and_writes_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            raw_dir = tmp_dir / "raw"
            out_dir = tmp_dir / "out"
            raw_dir.mkdir()
            out_dir.mkdir()

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
            (raw_dir / "connections_filtered.csv").write_text(
                "\n".join(
                    [
                        "pre_root_id,post_root_id,neuropil,syn_count,nt_type",
                        "101,102,LOP_R,12,ACH",
                        "102,103,ME_R,7,ACH",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (raw_dir / "visual_neuron_annotations.csv").write_text(
                "\n".join(
                    [
                        "root_id,type,family,subsystem,category,side",
                        "101,T5a,T5 Neuron,Motion,intrinsic,right",
                        "102,Tm1,Transmedullary,OFF,intrinsic,right",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (raw_dir / "visual_neuron_columns.csv").write_text(
                "\n".join(
                    [
                        "root_id,hemisphere,type,column_id,x,y,p,q",
                        "101,right,T5a,10,1,2,3,4",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            cfg = {
                "dataset": {
                    "materialization_version": 783,
                },
                "paths": {
                    "codex_raw_dir": str(raw_dir),
                    "classification_csv": str(raw_dir / "classification.csv"),
                    "neuron_registry_csv": str(out_dir / "neuron_registry.csv"),
                    "connectivity_registry_csv": str(out_dir / "connectivity_registry.csv"),
                    "registry_provenance_json": str(out_dir / "registry_provenance.json"),
                },
            }

            summary = build_registry(cfg)

            self.assertEqual(summary["neuron_count"], 3)
            self.assertEqual(summary["connection_count"], 2)

            neuron_registry = load_neuron_registry(out_dir / "neuron_registry.csv")
            connectivity_registry = load_connectivity_registry(out_dir / "connectivity_registry.csv")
            provenance = json.loads((out_dir / "registry_provenance.json").read_text(encoding="utf-8"))

            row_101 = neuron_registry.loc[neuron_registry["root_id"] == 101].iloc[0]
            row_102 = neuron_registry.loc[neuron_registry["root_id"] == 102].iloc[0]
            row_103 = neuron_registry.loc[neuron_registry["root_id"] == 103].iloc[0]

            self.assertEqual(row_101["cell_type"], "T5a")
            self.assertEqual(row_101["project_role"], "surface_simulated")
            self.assertEqual(row_101["proofread_status"], "proofread")
            self.assertEqual(row_101["snapshot_version"], 783)
            self.assertEqual(row_101["materialization_version"], 783)
            self.assertEqual(row_101["neuropils"], "LOP_R")
            self.assertIn("classification.csv", row_101["source_file"])
            self.assertIn("visual_neuron_columns.csv", row_101["source_file"])

            self.assertEqual(row_102["project_role"], "point_simulated")
            self.assertEqual(row_102["input_neuropils"], "LOP_R")
            self.assertEqual(row_102["output_neuropils"], "ME_R")
            self.assertEqual(row_102["neuropils"], "LOP_R;ME_R")

            self.assertTrue(row_103["cell_type"] != row_103["cell_type"])
            self.assertEqual(row_103["project_role"], "context_only")
            self.assertEqual(row_103["source_file"], "connections_filtered.csv")

            self.assertEqual(connectivity_registry.iloc[0]["snapshot_version"], 783)
            self.assertEqual(connectivity_registry.iloc[0]["materialization_version"], 783)
            self.assertEqual(connectivity_registry.iloc[0]["source_file"], "connections_filtered.csv")

            self.assertEqual(provenance["snapshot_version"], "783")
            self.assertEqual(provenance["materialization_version"], "783")
            self.assertIn("proofread_status_semantics", provenance)
            self.assertIn("classification", provenance["inputs"])
            self.assertTrue(provenance["inputs"]["classification"]["sha256"])

    def test_selection_can_filter_registry_by_super_class_and_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            registry_path = tmp_dir / "neuron_registry.csv"
            registry_path.write_text(
                "\n".join(
                    [
                        "root_id,super_class,project_role,cell_type,snapshot_version,materialization_version",
                        "101,optic,surface_simulated,T5a,783,783",
                        "102,optic,point_simulated,Tm1,783,783",
                        "201,central,context_only,FB5,783,783",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            registry = load_neuron_registry(registry_path)
            subset = select_visual_subset(
                registry,
                super_classes=["optic"],
                project_roles=["surface_simulated", "point_simulated"],
                limit=10,
            )

            self.assertEqual(extract_root_ids(subset), [101, 102])

    def _write_classification_csv(self, path: Path) -> None:
        path.write_text(
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


class RegistryMembershipValidationTest(unittest.TestCase):
    def test_validate_selected_root_ids_accepts_registered_roots(self) -> None:
        registry = pd.DataFrame({"root_id": [101, 102]})

        validate_selected_root_ids([101, 102], registry, "registry.csv")

    def test_validate_selected_root_ids_reports_missing_roots_with_sample(self) -> None:
        registry = pd.DataFrame({"root_id": [101, 102]})

        with self.assertRaisesRegex(
            RuntimeError,
            re.escape("2 selected root IDs were not found in the registry registry.csv. Sample missing IDs: [999, 1000]"),
        ):
            validate_selected_root_ids([101, 999, 1000], registry, "registry.csv")


if __name__ == "__main__":
    unittest.main()
