from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.experiment_suite_reporting import (
    EXPERIMENT_SUITE_REVIEW_REPORT_FORMAT,
    generate_experiment_suite_review_report,
)

try:
    from tests.test_experiment_suite_aggregation import (
        _materialize_packaged_suite_fixture,
    )
except ModuleNotFoundError:
    from test_experiment_suite_aggregation import (  # type: ignore[no-redef]
        _materialize_packaged_suite_fixture,
    )


class ExperimentSuiteReportingTest(unittest.TestCase):
    def test_fixture_workflow_writes_deterministic_report_catalog_tables_and_plots(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            package_metadata_path = _materialize_packaged_suite_fixture(tmp_dir)

            first = generate_experiment_suite_review_report(
                package_metadata_path,
                table_dimension_ids=["motion_direction"],
            )
            second = generate_experiment_suite_review_report(
                package_metadata_path,
                table_dimension_ids=["motion_direction"],
            )

            self.assertEqual(first, second)
            self.assertEqual(
                first["format_version"],
                EXPERIMENT_SUITE_REVIEW_REPORT_FORMAT,
            )
            self.assertEqual(
                [item["section_id"] for item in first["sections"]],
                [
                    "shared_comparison_metrics",
                    "wave_only_diagnostics",
                    "validation_findings",
                ],
            )
            self.assertEqual(
                first["aggregation_reference"]["table_dimension_ids"],
                ["motion_direction"],
            )

            summary_path = Path(first["report_layout"]["summary_path"]).resolve()
            index_path = Path(first["report_layout"]["index_path"]).resolve()
            catalog_path = Path(first["report_layout"]["artifact_catalog_path"]).resolve()
            self.assertTrue(summary_path.exists())
            self.assertTrue(index_path.exists())
            self.assertTrue(catalog_path.exists())

            persisted_summary = json.loads(summary_path.read_text(encoding="utf-8"))
            artifact_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            self.assertEqual(
                persisted_summary["report_layout"]["index_path"],
                first["report_layout"]["index_path"],
            )
            self.assertEqual(
                artifact_catalog["aggregation_reference"]["table_dimension_ids"],
                ["motion_direction"],
            )

            shared_table = next(
                item
                for item in artifact_catalog["table_artifacts"]
                if item["artifact_id"] == "shared_comparison_summary_table"
            )
            self.assertEqual(shared_table["section_id"], "shared_comparison_metrics")
            self.assertEqual(
                shared_table["row_count"],
                first["aggregation_reference"]["row_counts"][
                    "shared_comparison_summary_table_row_count"
                ],
            )
            self.assertTrue(
                shared_table["path"].endswith(
                    "/package/aggregation/exports/shared_comparison_summary_table.csv"
                )
            )
            self.assertGreater(
                len(shared_table["traceability"]["source_pairing_ids"]),
                0,
            )

            target_plot = next(
                item
                for item in artifact_catalog["plot_artifacts"]
                if item["display_name"]
                == (
                    "Shared Comparison: matched_surface_wave_vs_p0__intact / "
                    "null_direction_suppression_index"
                )
                and item["subtitle"]
                == "shared_output_mean / shared_response_window / normalized_peak_selectivity_index"
            )
            self.assertEqual(
                target_plot["section_id"],
                "shared_comparison_metrics",
            )
            self.assertTrue(target_plot["path"].endswith(".svg"))
            self.assertTrue(Path(target_plot["path"]).exists())
            self.assertEqual(
                target_plot["source_table_artifact_id"],
                "shared_comparison_summary_table",
            )

            plot_metadata = json.loads(
                Path(target_plot["metadata_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(
                plot_metadata["x_axis_labels"],
                ["motion_direction=null", "motion_direction=preferred"],
            )
            self.assertEqual(
                plot_metadata["series_labels"],
                ["no_waves:disabled", "shuffle_morphology:shuffled"],
            )
            self.assertEqual(
                plot_metadata["source_table_artifact_id"],
                "shared_comparison_summary_table",
            )
            self.assertGreater(
                len(plot_metadata["traceability"]["source_bundle_ids"]),
                0,
            )

            second_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            second_plot = next(
                item
                for item in second_catalog["plot_artifacts"]
                if item["artifact_id"] == target_plot["artifact_id"]
            )
            self.assertEqual(target_plot["relative_path"], second_plot["relative_path"])
            self.assertEqual(
                Path(target_plot["path"]).read_text(encoding="utf-8"),
                Path(second_plot["path"]).read_text(encoding="utf-8"),
            )

            html_report = index_path.read_text(encoding="utf-8")
            self.assertIn("Shared Comparison Metrics", html_report)
            self.assertIn("Wave-Only Diagnostics", html_report)
            self.assertIn("Validation Findings", html_report)
            self.assertIn("fairness_critical_shared_comparison", html_report)
