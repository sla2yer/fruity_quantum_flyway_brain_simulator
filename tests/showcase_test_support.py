from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.dashboard_session_contract import load_dashboard_session_metadata
from flywire_wave.dashboard_session_planning import (
    package_dashboard_session,
    resolve_dashboard_session_plan,
)
from flywire_wave.experiment_suite_packaging import (
    load_experiment_suite_package_metadata,
    load_experiment_suite_result_index,
)
from flywire_wave.experiment_suite_reporting import (
    generate_experiment_suite_review_report,
)
from flywire_wave.io_utils import write_json
from flywire_wave.validation_contract import (
    REVIEW_HANDOFF_ARTIFACT_ID,
    discover_validation_bundle_paths,
)

try:
    from tests.test_dashboard_session_planning import (
        DEFAULT_BASELINE_ARM_ID,
        DEFAULT_CONDITION_IDS,
        DEFAULT_SEED,
        DEFAULT_WAVE_ARM_ID,
        EXPERIMENT_ID,
        _materialize_dashboard_fixture,
    )
except ModuleNotFoundError:
    from test_dashboard_session_planning import (  # type: ignore[no-redef]
        DEFAULT_BASELINE_ARM_ID,
        DEFAULT_CONDITION_IDS,
        DEFAULT_SEED,
        DEFAULT_WAVE_ARM_ID,
        EXPERIMENT_ID,
        _materialize_dashboard_fixture,
    )

try:
    from tests.test_experiment_suite_aggregation import (
        _materialize_packaged_suite_fixture,
    )
except ModuleNotFoundError:
    from test_experiment_suite_aggregation import (  # type: ignore[no-redef]
        _materialize_packaged_suite_fixture,
    )


def _materialize_packaged_showcase_fixture(tmp_dir: Path) -> dict[str, Any]:
    dashboard_root = tmp_dir / "dashboard_fixture"
    dashboard_root.mkdir(parents=True, exist_ok=True)
    dashboard_fixture = _materialize_dashboard_fixture(dashboard_root)
    dashboard_plan = resolve_dashboard_session_plan(
        experiment_id=EXPERIMENT_ID,
        config_path=dashboard_fixture["config_path"],
        baseline_arm_id=DEFAULT_BASELINE_ARM_ID,
        wave_arm_id=DEFAULT_WAVE_ARM_ID,
        preferred_seed=DEFAULT_SEED,
        preferred_condition_ids=DEFAULT_CONDITION_IDS,
    )
    dashboard_package = package_dashboard_session(dashboard_plan)
    dashboard_metadata_path = Path(dashboard_package["metadata_path"]).resolve()

    suite_root = tmp_dir / "suite_fixture"
    suite_root.mkdir(parents=True, exist_ok=True)
    suite_package_metadata_path = _materialize_packaged_suite_fixture(suite_root)
    suite_review_summary = generate_experiment_suite_review_report(
        suite_package_metadata_path,
        table_dimension_ids=["motion_direction"],
    )
    suite_summary_table_path = Path(
        next(
            item["path"]
            for item in json.loads(
                Path(suite_review_summary["report_layout"]["artifact_catalog_path"]).read_text(
                    encoding="utf-8"
                )
            )["table_artifacts"]
            if item["artifact_id"] == "shared_comparison_summary_table"
        )
    ).resolve()

    return {
        **dashboard_fixture,
        "dashboard_plan": dashboard_plan,
        "dashboard_package": dashboard_package,
        "dashboard_metadata_path": dashboard_metadata_path,
        "suite_package_metadata_path": Path(suite_package_metadata_path).resolve(),
        "suite_review_summary_path": Path(
            suite_review_summary["report_layout"]["summary_path"]
        ).resolve(),
        "suite_summary_table_path": suite_summary_table_path,
    }


def _inject_dashboard_stage_artifact(
    *,
    suite_package_metadata_path: Path,
    dashboard_metadata_path: Path,
) -> None:
    package_metadata = load_experiment_suite_package_metadata(suite_package_metadata_path)
    result_index = load_experiment_suite_result_index(package_metadata)
    dashboard_metadata = load_dashboard_session_metadata(dashboard_metadata_path)
    result_index["stage_artifacts"] = [
        item
        for item in result_index["stage_artifacts"]
        if not (
            str(item.get("stage_id")) == "dashboard"
            and str(item.get("artifact_id")) == "metadata_json"
        )
    ]
    result_index["stage_artifacts"].append(
        {
            "suite_cell_id": str(result_index["cell_records"][0]["suite_cell_id"]),
            "stage_id": "dashboard",
            "work_item_id": "fixture_dashboard_stage",
            "stage_status": "succeeded",
            "artifact_role_id": "dashboard_session",
            "source_kind": "dashboard_session_package",
            "bundle_kind": "dashboard_session",
            "contract_version": "dashboard_session.v1",
            "bundle_id": str(dashboard_metadata["bundle_id"]),
            "artifact_id": "metadata_json",
            "artifact_kind": "metadata_json",
            "inventory_category": "bundle_metadata",
            "artifact_scope": "session_package",
            "status": "ready",
            "exists": True,
            "format": "json_dashboard_session_metadata.v1",
            "path": str(dashboard_metadata_path.resolve()),
        }
    )
    result_index_path = Path(package_metadata["artifacts"]["result_index"]["path"]).resolve()
    write_json(result_index, result_index_path)


def _approve_validation_highlight(fixture: dict[str, Any]) -> None:
    review_handoff_path = discover_validation_bundle_paths(
        fixture["validation_bundle_metadata"]
    )[REVIEW_HANDOFF_ARTIFACT_ID]
    payload = json.loads(review_handoff_path.read_text(encoding="utf-8"))
    payload["scientific_plausibility_decision"] = "approved_for_showcase"
    payload["review_status"] = "approved"
    payload["reviewer_rationale"] = "Fixture approves the wave-only beat for showcase coverage."
    write_json(payload, review_handoff_path)
