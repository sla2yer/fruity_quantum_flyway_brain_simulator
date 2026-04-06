from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.io_utils import write_json
from flywire_wave.validation_contract import (
    METADATA_JSON_KEY,
    OFFLINE_REVIEW_REPORT_ARTIFACT_ID,
    REVIEW_HANDOFF_ARTIFACT_ID,
    SUPPORTED_VALIDATION_LAYER_IDS,
    VALIDATION_STATUS_PASS,
    VALIDATION_STATUS_REVIEW,
    VALIDATION_SUMMARY_ARTIFACT_ID,
    VALIDATOR_FINDINGS_ARTIFACT_ID,
    build_validation_bundle_metadata,
    build_validation_ladder_contract_metadata,
    build_validation_plan_reference,
    discover_validation_bundle_paths,
    discover_validation_validator_definitions,
    discover_validation_validator_families,
    write_validation_bundle_metadata,
)
from flywire_wave.validation_reporting import (
    build_validation_ladder_regression_baseline,
    load_validation_ladder_package_metadata,
    package_validation_ladder_outputs,
)


_FIXTURE_REPORT_VERSION = "fixture_validation_report.v1"
_FIXTURE_EXPERIMENT_ID = "fixture_validation_ladder_package"
_CONTRACT_METADATA = build_validation_ladder_contract_metadata()


def _status_counts(status: str) -> dict[str, int]:
    return {
        "pass": 1 if status == "pass" else 0,
        "review": 1 if status == "review" else 0,
        "blocked": 1 if status == "blocked" else 0,
        "blocking": 1 if status == "blocking" else 0,
    }


def _build_tiny_layer_bundle(
    fixture_root: Path,
    *,
    layer_id: str,
    overall_status: str = VALIDATION_STATUS_PASS,
    experiment_id: str = _FIXTURE_EXPERIMENT_ID,
    plan_version: str = "validation_plan.v1",
) -> Path:
    family = discover_validation_validator_families(
        _CONTRACT_METADATA,
        layer_id=layer_id,
    )[0]
    validator = discover_validation_validator_definitions(
        _CONTRACT_METADATA,
        layer_id=layer_id,
    )[0]
    family_id = str(family["validator_family_id"])
    validator_id = str(validator["validator_id"])
    criteria_profile_references = sorted(
        {
            str(family["default_criteria_profile_reference"]),
            str(validator["criteria_profile_reference"]),
        }
    )
    validation_plan = build_validation_plan_reference(
        experiment_id=experiment_id,
        active_layer_ids=[layer_id],
        active_validator_family_ids=[family_id],
        active_validator_ids=[validator_id],
        criteria_profile_references=criteria_profile_references,
        plan_version=plan_version,
    )
    bundle_metadata = build_validation_bundle_metadata(
        validation_plan_reference=validation_plan,
        processed_simulator_results_dir=fixture_root,
    )
    bundle_paths = discover_validation_bundle_paths(bundle_metadata)
    case_id = f"{layer_id}_case"
    finding_id = f"{validator_id}_{case_id}_finding"
    finding = {
        "finding_id": finding_id,
        "status": overall_status,
        "case_id": case_id,
        "validator_family_id": family_id,
        "summary": {
            "layer_id": layer_id,
            "validator_id": validator_id,
        },
    }
    summary_payload = {
        "format_version": "json_validation_summary.v1",
        "report_version": _FIXTURE_REPORT_VERSION,
        "bundle_id": str(bundle_metadata["bundle_id"]),
        "experiment_id": str(bundle_metadata["experiment_id"]),
        "validation_spec_hash": str(bundle_metadata["validation_spec_hash"]),
        "overall_status": overall_status,
        "active_layer_ids": [layer_id],
        "active_validator_family_ids": [family_id],
        "active_validator_ids": [validator_id],
        "status_counts": _status_counts(overall_status),
        "layers": [
            {
                "layer_id": layer_id,
                "status": overall_status,
                "validator_families": [
                    {
                        "validator_family_id": family_id,
                        "status": overall_status,
                        "validators": [
                            {
                                "validator_id": validator_id,
                                "status": overall_status,
                            }
                        ],
                    }
                ],
            }
        ],
        "case_summaries": [
            {
                "case_id": case_id,
                "overall_status": overall_status,
            }
        ],
        "artifact_paths": {
            artifact_id: str(record["path"])
            for artifact_id, record in bundle_metadata["artifacts"].items()
        },
    }
    findings_payload = {
        "format_version": "json_validation_findings.v1",
        "report_version": _FIXTURE_REPORT_VERSION,
        "bundle_id": str(bundle_metadata["bundle_id"]),
        "validator_findings": {
            validator_id: [finding],
        },
    }
    review_handoff_payload = {
        "format_version": "json_validation_review_handoff.v1",
        "report_version": _FIXTURE_REPORT_VERSION,
        "bundle_id": str(bundle_metadata["bundle_id"]),
        "review_owner": "grant",
        "review_status": VALIDATION_STATUS_REVIEW,
        "overall_status": overall_status,
        "open_finding_ids": [] if overall_status == VALIDATION_STATUS_PASS else [finding_id],
    }

    write_json(summary_payload, bundle_paths[VALIDATION_SUMMARY_ARTIFACT_ID])
    write_json(findings_payload, bundle_paths[VALIDATOR_FINDINGS_ARTIFACT_ID])
    write_json(review_handoff_payload, bundle_paths[REVIEW_HANDOFF_ARTIFACT_ID])
    bundle_paths[OFFLINE_REVIEW_REPORT_ARTIFACT_ID].parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    bundle_paths[OFFLINE_REVIEW_REPORT_ARTIFACT_ID].write_text(
        f"# {layer_id} fixture report\n",
        encoding="utf-8",
    )
    write_validation_bundle_metadata(bundle_metadata)
    return bundle_paths[METADATA_JSON_KEY]


def _build_layer_bundle_set(
    fixture_root: Path,
    *,
    layer_ids: list[str] | tuple[str, ...] = SUPPORTED_VALIDATION_LAYER_IDS,
    status_by_layer: dict[str, str] | None = None,
) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for layer_id in layer_ids:
        paths[layer_id] = _build_tiny_layer_bundle(
            fixture_root / "inputs" / layer_id,
            layer_id=layer_id,
            overall_status=(status_by_layer or {}).get(layer_id, VALIDATION_STATUS_PASS),
        )
    return paths


class ValidationLadderPackageTest(unittest.TestCase):
    def test_package_normalizes_input_order_and_summary_ordering(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            bundle_paths = _build_layer_bundle_set(tmp_dir)
            packaged_root = tmp_dir / "packaged"

            first = package_validation_ladder_outputs(
                layer_bundle_metadata_paths=[
                    bundle_paths["task_sanity"],
                    bundle_paths["numerical_sanity"],
                    bundle_paths["circuit_sanity"],
                    bundle_paths["morphology_sanity"],
                ],
                processed_simulator_results_dir=packaged_root,
            )
            first_metadata = load_validation_ladder_package_metadata(first["metadata_path"])
            first_summary_bytes = Path(first["summary_path"]).read_bytes()
            first_summary = json.loads(
                Path(first["summary_path"]).read_text(encoding="utf-8")
            )

            second = package_validation_ladder_outputs(
                layer_bundle_metadata_paths=[
                    bundle_paths["morphology_sanity"],
                    bundle_paths["task_sanity"],
                    bundle_paths["numerical_sanity"],
                    bundle_paths["circuit_sanity"],
                ],
                processed_simulator_results_dir=packaged_root,
            )
            second_metadata = load_validation_ladder_package_metadata(
                second["metadata_path"]
            )
            second_summary_bytes = Path(second["summary_path"]).read_bytes()
            second_summary = json.loads(
                Path(second["summary_path"]).read_text(encoding="utf-8")
            )

            self.assertEqual(first["bundle_id"], second["bundle_id"])
            self.assertEqual(first_summary_bytes, second_summary_bytes)
            self.assertEqual(
                [item["layer_id"] for item in first_metadata["layer_bundles"]],
                list(SUPPORTED_VALIDATION_LAYER_IDS),
            )
            self.assertEqual(
                [item["layer_id"] for item in second_metadata["layer_bundles"]],
                list(SUPPORTED_VALIDATION_LAYER_IDS),
            )
            self.assertEqual(
                first_summary["present_layer_ids"],
                list(SUPPORTED_VALIDATION_LAYER_IDS),
            )
            self.assertEqual(
                [item["layer_id"] for item in first_summary["layers"]],
                list(SUPPORTED_VALIDATION_LAYER_IDS),
            )
            self.assertEqual(
                second_summary["present_layer_ids"],
                list(SUPPORTED_VALIDATION_LAYER_IDS),
            )
            self.assertEqual(
                [item["layer_id"] for item in second_summary["layers"]],
                list(SUPPORTED_VALIDATION_LAYER_IDS),
            )

    def test_package_rejects_duplicate_layer_bundles_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            first_bundle = _build_tiny_layer_bundle(
                tmp_dir / "inputs" / "numerical_a",
                layer_id="numerical_sanity",
                plan_version="validation_plan.v1",
            )
            second_bundle = _build_tiny_layer_bundle(
                tmp_dir / "inputs" / "numerical_b",
                layer_id="numerical_sanity",
                plan_version="validation_plan.variant.v1",
            )

            with self.assertRaisesRegex(
                ValueError,
                r"Duplicate layer bundle supplied for layer_id 'numerical_sanity'\.",
            ):
                package_validation_ladder_outputs(
                    layer_bundle_metadata_paths=[first_bundle, second_bundle],
                    processed_simulator_results_dir=tmp_dir / "packaged",
                )

    def test_package_rejects_missing_required_layers_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            bundle_paths = _build_layer_bundle_set(
                tmp_dir,
                layer_ids=[
                    "numerical_sanity",
                    "morphology_sanity",
                    "circuit_sanity",
                ],
            )

            with self.assertRaisesRegex(
                ValueError,
                r"missing required layer bundles \['task_sanity'\]\.",
            ):
                package_validation_ladder_outputs(
                    layer_bundle_metadata_paths=list(bundle_paths.values()),
                    processed_simulator_results_dir=tmp_dir / "packaged",
                    require_layer_ids=SUPPORTED_VALIDATION_LAYER_IDS,
                )

    def test_package_cli_write_baseline_writes_normalized_summary_snapshot(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            bundle_paths = _build_layer_bundle_set(
                tmp_dir,
                status_by_layer={"task_sanity": VALIDATION_STATUS_REVIEW},
            )
            baseline_path = tmp_dir / "written_baseline.json"
            command = [
                sys.executable,
                str(ROOT / "scripts" / "27_validation_ladder.py"),
                "package",
                "--processed-simulator-results-dir",
                str(tmp_dir / "packaged"),
                "--write-baseline",
                str(baseline_path),
                "--layer-bundle-metadata",
                str(bundle_paths["task_sanity"]),
                "--layer-bundle-metadata",
                str(bundle_paths["numerical_sanity"]),
                "--layer-bundle-metadata",
                str(bundle_paths["circuit_sanity"]),
                "--layer-bundle-metadata",
                str(bundle_paths["morphology_sanity"]),
            ]

            completed = subprocess.run(
                command,
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            result = json.loads(completed.stdout)
            summary_payload = json.loads(
                Path(result["summary_path"]).read_text(encoding="utf-8")
            )
            baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))

            self.assertTrue(baseline_path.exists())
            self.assertEqual(
                baseline_payload,
                build_validation_ladder_regression_baseline(summary_payload),
            )
            self.assertEqual(
                baseline_payload["layer_ids"],
                list(SUPPORTED_VALIDATION_LAYER_IDS),
            )


if __name__ == "__main__":
    unittest.main()
