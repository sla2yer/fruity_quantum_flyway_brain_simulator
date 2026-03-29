from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.validation_ladder_smoke import run_validation_ladder_smoke_workflow
from flywire_wave.validation_reporting import (
    FINDING_ROWS_CSV_ARTIFACT_ID,
    REGRESSION_SUMMARY_ARTIFACT_ID,
    VALIDATION_LADDER_SUMMARY_ARTIFACT_ID,
    discover_validation_ladder_layer_artifacts,
    discover_validation_ladder_package_paths,
    load_validation_ladder_package_metadata,
)


class ValidationReportingSmokeTest(unittest.TestCase):
    def test_smoke_workflow_packages_deterministic_outputs_and_matches_baseline(self) -> None:
        baseline_path = ROOT / "tests" / "fixtures" / "validation_ladder_smoke_baseline.json"
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            processed_root = tmp_dir / "processed"

            first = run_validation_ladder_smoke_workflow(
                processed_simulator_results_dir=processed_root,
                baseline_path=baseline_path,
                enforce_baseline=True,
            )
            second = run_validation_ladder_smoke_workflow(
                processed_simulator_results_dir=processed_root,
                baseline_path=baseline_path,
                enforce_baseline=True,
            )

            self.assertEqual(first["bundle_id"], second["bundle_id"])
            self.assertEqual(first["metadata_path"], second["metadata_path"])
            self.assertEqual(first["summary_path"], second["summary_path"])
            self.assertEqual(
                first["finding_rows_csv_path"],
                second["finding_rows_csv_path"],
            )
            self.assertEqual(
                Path(first["summary_path"]).read_bytes(),
                Path(second["summary_path"]).read_bytes(),
            )
            self.assertEqual(
                Path(first["finding_rows_csv_path"]).read_bytes(),
                Path(second["finding_rows_csv_path"]).read_bytes(),
            )

            metadata = load_validation_ladder_package_metadata(first["metadata_path"])
            discovered_paths = discover_validation_ladder_package_paths(metadata)
            discovered_layer_paths = discover_validation_ladder_layer_artifacts(metadata)
            numerical_paths = discover_validation_ladder_layer_artifacts(
                metadata,
                layer_id="numerical_sanity",
            )

            self.assertEqual(
                discovered_paths[VALIDATION_LADDER_SUMMARY_ARTIFACT_ID],
                Path(first["summary_path"]).resolve(),
            )
            self.assertEqual(
                discovered_paths[FINDING_ROWS_CSV_ARTIFACT_ID],
                Path(first["finding_rows_csv_path"]).resolve(),
            )
            self.assertEqual(
                discovered_paths[REGRESSION_SUMMARY_ARTIFACT_ID],
                Path(first["regression_summary_path"]).resolve(),
            )
            self.assertEqual(
                sorted(discovered_layer_paths),
                [
                    "circuit_sanity",
                    "morphology_sanity",
                    "numerical_sanity",
                    "task_sanity",
                ],
            )
            self.assertEqual(
                numerical_paths["validation_summary"].name,
                "validation_summary.json",
            )
            self.assertEqual(
                numerical_paths["validator_findings"].name,
                "validator_findings.json",
            )

            summary_payload = json.loads(
                Path(first["summary_path"]).read_text(encoding="utf-8")
            )
            regression_payload = json.loads(
                Path(first["regression_summary_path"]).read_text(encoding="utf-8")
            )
            csv_lines = Path(first["finding_rows_csv_path"]).read_text(
                encoding="utf-8"
            ).splitlines()

            self.assertEqual(summary_payload["overall_status"], "review")
            self.assertEqual(summary_payload["finding_count"], 63)
            self.assertEqual(summary_payload["case_count"], 7)
            self.assertEqual(summary_payload["missing_layer_ids"], [])
            self.assertEqual(
                summary_payload["layer_statuses"],
                {
                    "circuit_sanity": "pass",
                    "morphology_sanity": "pass",
                    "numerical_sanity": "pass",
                    "task_sanity": "review",
                },
            )
            self.assertEqual(
                summary_payload["validator_statuses"]["shared_effect_reproducibility"],
                "review",
            )
            self.assertEqual(
                summary_payload["status_counts"],
                {
                    "blocked": 0,
                    "blocking": 0,
                    "pass": 62,
                    "review": 1,
                },
            )
            self.assertEqual(regression_payload["status"], "pass")
            self.assertEqual(
                csv_lines[0],
                "layer_id,layer_sequence_index,layer_bundle_id,validator_id,finding_id,status,case_id,validator_family_id,arm_id,root_id,variant_id,measured_quantity,measured_value,summary_json,comparison_basis_json,diagnostic_metadata_json",
            )


if __name__ == "__main__":
    unittest.main()
