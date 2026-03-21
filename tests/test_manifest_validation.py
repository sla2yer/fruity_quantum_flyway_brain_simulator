from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.manifests import load_yaml, validate_manifest


class ManifestValidationTest(unittest.TestCase):
    def test_example_manifest_validates_against_schema_and_design_lock(self) -> None:
        summary = validate_manifest(
            manifest_path=ROOT / "manifests/examples/milestone_1_demo.yaml",
            schema_path=ROOT / "schemas/milestone_1_experiment_manifest.schema.json",
            design_lock_path=ROOT / "config/milestone_1_design_lock.yaml",
        )

        self.assertEqual(summary["milestone"], "milestone_1")
        self.assertEqual(summary["comparison_arm_count"], 6)
        self.assertEqual(summary["success_criteria_count"], 5)

    def test_thresholds_remain_intentionally_unspecified(self) -> None:
        design_lock = load_yaml(ROOT / "config/milestone_1_design_lock.yaml")
        for criterion in design_lock["success_criteria"]:
            self.assertIsNone(criterion["metric"]["threshold"])
            self.assertEqual(criterion["metric"]["threshold_status"], "intentionally_unspecified")


if __name__ == "__main__":
    unittest.main()
