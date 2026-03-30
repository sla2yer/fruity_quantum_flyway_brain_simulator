from __future__ import annotations

import copy
import csv
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .experiment_suite_contract import (
    ABLATION_VARIANT_LINEAGE_KIND,
    BASE_CONDITION_LINEAGE_KIND,
)
from .experiment_suite_packaging import (
    load_experiment_suite_package_metadata,
    load_experiment_suite_result_index,
    resolve_experiment_suite_package_metadata_path,
)
from .io_utils import ensure_dir, write_csv_rows, write_json
from .stimulus_contract import (
    _normalize_identifier,
    _normalize_nonempty_string,
)


EXPERIMENT_SUITE_AGGREGATION_FORMAT = "experiment_suite_aggregation.v1"

DEFAULT_AGGREGATION_DIRECTORY_NAME = "aggregation"
DEFAULT_EXPORT_DIRECTORY_NAME = "exports"

SUMMARY_ARTIFACT_ID = "summary_json"
SHARED_CELL_ROWS_ARTIFACT_ID = "shared_comparison_cell_rollups_csv"
SHARED_PAIR_ROWS_ARTIFACT_ID = "shared_comparison_paired_rows_csv"
SHARED_SUMMARY_TABLE_ARTIFACT_ID = "shared_comparison_summary_table_csv"
WAVE_CELL_ROWS_ARTIFACT_ID = "wave_diagnostic_cell_rollups_csv"
WAVE_PAIR_ROWS_ARTIFACT_ID = "wave_diagnostic_paired_rows_csv"
WAVE_SUMMARY_TABLE_ARTIFACT_ID = "wave_diagnostic_summary_table_csv"
VALIDATION_CELL_ROWS_ARTIFACT_ID = "validation_cell_summaries_csv"
VALIDATION_PAIR_ROWS_ARTIFACT_ID = "validation_paired_rows_csv"
VALIDATION_FINDING_ROWS_ARTIFACT_ID = "validation_finding_rows_csv"
VALIDATION_SUMMARY_TABLE_ARTIFACT_ID = "validation_summary_table_csv"

SHARED_COMPARISON_SECTION_ID = "shared_comparison_metrics"
WAVE_ONLY_DIAGNOSTICS_SECTION_ID = "wave_only_diagnostics"
VALIDATION_FINDINGS_SECTION_ID = "validation_findings"

CELL_ROLLUP_ROW_KIND = "cell_rollup"
CELL_SUMMARY_ROW_KIND = "cell_summary"
FINDING_ROW_KIND = "finding"
PAIRED_COMPARISON_ROW_KIND = "paired_comparison"
SUMMARY_TABLE_ROW_KIND = "summary_table"

INTACT_ABLATION_KEY = "intact"
CELL_ROLLUP_RULE_PASSTHROUGH = "single_source_row_passthrough"
CELL_ROLLUP_RULE_COLLAPSE = "deterministic_mean_of_source_rows"

_ROUND_DIGITS = 12
_VALIDATION_STATUS_RANK = {
    "pass": 0,
    "review": 1,
    "blocked": 2,
    "blocking": 3,
}


@dataclass(frozen=True)
class ExperimentSuiteAggregationPaths:
    suite_root: Path
    aggregation_directory: Path
    export_directory: Path
    summary_path: Path
    shared_cell_rows_path: Path
    shared_pair_rows_path: Path
    shared_summary_table_path: Path
    wave_cell_rows_path: Path
    wave_pair_rows_path: Path
    wave_summary_table_path: Path
    validation_cell_rows_path: Path
    validation_pair_rows_path: Path
    validation_finding_rows_path: Path
    validation_summary_table_path: Path

    def asset_paths(self) -> dict[str, Path]:
        return {
            SUMMARY_ARTIFACT_ID: self.summary_path,
            SHARED_CELL_ROWS_ARTIFACT_ID: self.shared_cell_rows_path,
            SHARED_PAIR_ROWS_ARTIFACT_ID: self.shared_pair_rows_path,
            SHARED_SUMMARY_TABLE_ARTIFACT_ID: self.shared_summary_table_path,
            WAVE_CELL_ROWS_ARTIFACT_ID: self.wave_cell_rows_path,
            WAVE_PAIR_ROWS_ARTIFACT_ID: self.wave_pair_rows_path,
            WAVE_SUMMARY_TABLE_ARTIFACT_ID: self.wave_summary_table_path,
            VALIDATION_CELL_ROWS_ARTIFACT_ID: self.validation_cell_rows_path,
            VALIDATION_PAIR_ROWS_ARTIFACT_ID: self.validation_pair_rows_path,
            VALIDATION_FINDING_ROWS_ARTIFACT_ID: self.validation_finding_rows_path,
            VALIDATION_SUMMARY_TABLE_ARTIFACT_ID: self.validation_summary_table_path,
        }


def build_experiment_suite_aggregation_paths(
    *,
    suite_root: str | Path,
    output_dir: str | Path | None = None,
) -> ExperimentSuiteAggregationPaths:
    resolved_suite_root = Path(suite_root).resolve()
    aggregation_directory = (
        Path(output_dir).resolve()
        if output_dir is not None
        else (
            resolved_suite_root
            / "package"
            / DEFAULT_AGGREGATION_DIRECTORY_NAME
        ).resolve()
    )
    export_directory = (aggregation_directory / DEFAULT_EXPORT_DIRECTORY_NAME).resolve()
    return ExperimentSuiteAggregationPaths(
        suite_root=resolved_suite_root,
        aggregation_directory=aggregation_directory,
        export_directory=export_directory,
        summary_path=aggregation_directory / "suite_aggregation_summary.json",
        shared_cell_rows_path=export_directory / "shared_comparison_cell_rollups.csv",
        shared_pair_rows_path=export_directory / "shared_comparison_paired_rows.csv",
        shared_summary_table_path=export_directory / "shared_comparison_summary_table.csv",
        wave_cell_rows_path=export_directory / "wave_diagnostic_cell_rollups.csv",
        wave_pair_rows_path=export_directory / "wave_diagnostic_paired_rows.csv",
        wave_summary_table_path=export_directory / "wave_diagnostic_summary_table.csv",
        validation_cell_rows_path=export_directory / "validation_cell_summaries.csv",
        validation_pair_rows_path=export_directory / "validation_paired_rows.csv",
        validation_finding_rows_path=export_directory / "validation_finding_rows.csv",
        validation_summary_table_path=export_directory / "validation_summary_table.csv",
    )


def compute_experiment_suite_aggregation(
    record: Mapping[str, Any] | str | Path,
    *,
    table_dimension_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    package_metadata_path, package_metadata = _load_package_metadata_if_available(record)
    result_index = _load_result_index(record)
    suite_plan = _load_json_mapping(
        result_index["suite_plan_path"],
        field_name="suite_plan",
    )
    declared_dimension_ids = _declared_dimension_ids(suite_plan)
    resolved_table_dimension_ids = _resolve_table_dimension_ids(
        table_dimension_ids=table_dimension_ids,
        declared_dimension_ids=declared_dimension_ids,
    )
    review_cells = _review_cells(result_index)
    review_cells_by_id = {
        str(item["suite_cell_id"]): copy.deepcopy(dict(item)) for item in review_cells
    }
    has_validation_stage = _plan_has_stage(suite_plan, stage_id="validation")

    analysis_cache: dict[str, dict[str, Any]] = {}
    validation_cache: dict[str, dict[str, Any]] = {}
    shared_cell_rows: list[dict[str, Any]] = []
    wave_cell_rows: list[dict[str, Any]] = []
    validation_cell_rows: list[dict[str, Any]] = []
    validation_finding_rows: list[dict[str, Any]] = []

    for cell in review_cells:
        expected_seeds = _expected_seeds_for_review_cell(cell)
        analysis_artifact = _require_stage_artifact(
            cell,
            stage_id="analysis",
            artifact_ids=("experiment_comparison_summary",),
            artifact_label="experiment_comparison_summary",
        )
        analysis_payload = _load_json_mapping(
            analysis_artifact["path"],
            field_name=(
                f"analysis summary for suite_cell_id {cell['suite_cell_id']}"
            ),
        )
        analysis_bundle_id = (
            None
            if analysis_artifact.get("bundle_id") is None
            else str(analysis_artifact["bundle_id"])
        )
        shared_rows, wave_rows = _extract_analysis_rows(
            analysis_payload=analysis_payload,
            cell=cell,
            declared_dimension_ids=declared_dimension_ids,
            expected_seeds=expected_seeds,
            summary_path=str(analysis_artifact["path"]),
            bundle_id=analysis_bundle_id,
        )
        analysis_cache[str(cell["suite_cell_id"])] = {
            "summary_path": str(analysis_artifact["path"]),
            "bundle_id": analysis_bundle_id,
            "expected_seeds": expected_seeds,
            "shared_rows": shared_rows,
            "wave_rows": wave_rows,
        }
        shared_cell_rows.extend(shared_rows)
        wave_cell_rows.extend(wave_rows)

        if not has_validation_stage:
            continue
        validation_summary_artifact = _require_stage_artifact(
            cell,
            stage_id="validation",
            artifact_ids=("validation_ladder_summary",),
            artifact_label="validation_ladder_summary",
        )
        validation_findings_artifact = _require_optional_stage_artifact(
            cell,
            stage_id="validation",
            artifact_ids=("finding_rows_jsonl", "finding_rows_csv"),
        )
        if validation_findings_artifact is None:
            raise ValueError(
                "Suite aggregation requires validation finding rows for "
                f"suite_cell_id {cell['suite_cell_id']!r}."
            )
        validation_summary = _load_json_mapping(
            validation_summary_artifact["path"],
            field_name=(
                f"validation summary for suite_cell_id {cell['suite_cell_id']}"
            ),
        )
        validation_rows = _load_validation_finding_rows(
            validation_findings_artifact["path"]
        )
        validation_bundle_id = (
            None
            if validation_summary_artifact.get("bundle_id") is None
            else str(validation_summary_artifact["bundle_id"])
        )
        cell_summary_row = _build_validation_cell_summary_row(
            cell=cell,
            validation_summary=validation_summary,
            declared_dimension_ids=declared_dimension_ids,
            summary_path=str(validation_summary_artifact["path"]),
            findings_path=str(validation_findings_artifact["path"]),
            bundle_id=validation_bundle_id,
        )
        finding_rows = _build_validation_finding_rows(
            cell=cell,
            finding_rows=validation_rows,
            declared_dimension_ids=declared_dimension_ids,
            summary_row=cell_summary_row,
        )
        validation_cache[str(cell["suite_cell_id"])] = {
            "summary_row": cell_summary_row,
            "finding_rows": finding_rows,
        }
        validation_cell_rows.append(cell_summary_row)
        validation_finding_rows.extend(finding_rows)

    shared_cell_rows.sort(key=_shared_cell_row_sort_key)
    wave_cell_rows.sort(key=_wave_cell_row_sort_key)
    validation_cell_rows.sort(key=_validation_cell_row_sort_key)
    validation_finding_rows.sort(key=_validation_finding_row_sort_key)

    ablation_pairings = _ablation_pairings(suite_plan)
    shared_pair_rows: list[dict[str, Any]] = []
    wave_pair_rows: list[dict[str, Any]] = []
    validation_pair_rows: list[dict[str, Any]] = []
    for pairing in ablation_pairings:
        base_cell = _require_review_cell(
            review_cells_by_id,
            suite_cell_id=pairing["base_suite_cell_id"],
            pairing_id=pairing["pairing_id"],
        )
        ablation_cell = _require_review_cell(
            review_cells_by_id,
            suite_cell_id=pairing["ablation_suite_cell_id"],
            pairing_id=pairing["pairing_id"],
        )
        _validate_pairing_dimension_alignment(
            pairing=pairing,
            base_cell=base_cell,
            ablation_cell=ablation_cell,
            declared_dimension_ids=declared_dimension_ids,
        )
        base_analysis = _require_loaded_analysis(
            analysis_cache,
            suite_cell_id=str(base_cell["suite_cell_id"]),
            pairing_id=pairing["pairing_id"],
        )
        ablation_analysis = _require_loaded_analysis(
            analysis_cache,
            suite_cell_id=str(ablation_cell["suite_cell_id"]),
            pairing_id=pairing["pairing_id"],
        )
        if base_analysis["expected_seeds"] != ablation_analysis["expected_seeds"]:
            raise ValueError(
                "Suite aggregation requires matched seed coverage for pairing "
                f"{pairing['pairing_id']!r}; base seeds "
                f"{base_analysis['expected_seeds']!r} do not match ablation seeds "
                f"{ablation_analysis['expected_seeds']!r}."
            )
        shared_pair_rows.extend(
            _build_numeric_paired_rows(
                section_id=SHARED_COMPARISON_SECTION_ID,
                pair_label="shared comparison rollup",
                pairing=pairing,
                base_rows=base_analysis["shared_rows"],
                ablation_rows=ablation_analysis["shared_rows"],
                match_fields=(
                    "group_id",
                    "metric_id",
                    "readout_id",
                    "window_id",
                    "statistic",
                ),
                carried_fields=(
                    "group_id",
                    "group_kind",
                    "comparison_semantics",
                    "metric_id",
                    "readout_id",
                    "window_id",
                    "statistic",
                    "units",
                    "baseline_family",
                    "topology_condition",
                    "seed_aggregation_rule_id",
                    "seed_count",
                    "seeds",
                    "expected_seeds",
                ),
                base_path_field="analysis_summary_path",
                value_label="mean",
                declared_dimension_ids=declared_dimension_ids,
            )
        )
        wave_pair_rows.extend(
            _build_numeric_paired_rows(
                section_id=WAVE_ONLY_DIAGNOSTICS_SECTION_ID,
                pair_label="wave diagnostic rollup",
                pairing=pairing,
                base_rows=base_analysis["wave_rows"],
                ablation_rows=ablation_analysis["wave_rows"],
                match_fields=("arm_id", "metric_id"),
                carried_fields=(
                    "arm_id",
                    "metric_id",
                    "units",
                    "seed_count",
                    "seeds",
                    "expected_seeds",
                ),
                base_path_field="analysis_summary_path",
                value_label="mean",
                declared_dimension_ids=declared_dimension_ids,
            )
        )
        if has_validation_stage:
            base_validation = _require_loaded_validation(
                validation_cache,
                suite_cell_id=str(base_cell["suite_cell_id"]),
                pairing_id=pairing["pairing_id"],
            )
            ablation_validation = _require_loaded_validation(
                validation_cache,
                suite_cell_id=str(ablation_cell["suite_cell_id"]),
                pairing_id=pairing["pairing_id"],
            )
            validation_pair_rows.append(
                _build_validation_paired_row(
                    pairing=pairing,
                    base_row=base_validation["summary_row"],
                    ablation_row=ablation_validation["summary_row"],
                    declared_dimension_ids=declared_dimension_ids,
                )
            )

    shared_pair_rows.sort(key=_shared_pair_row_sort_key)
    wave_pair_rows.sort(key=_wave_pair_row_sort_key)
    validation_pair_rows.sort(key=_validation_pair_row_sort_key)

    shared_summary_table_rows = _build_numeric_summary_table_rows(
        section_id=SHARED_COMPARISON_SECTION_ID,
        source_rows=shared_pair_rows,
        table_dimension_ids=resolved_table_dimension_ids,
        grouping_fields=(
            "ablation_key",
            "ablation_identity_ids",
            "ablation_family_ids",
            "group_id",
            "group_kind",
            "comparison_semantics",
            "metric_id",
            "readout_id",
            "window_id",
            "statistic",
            "units",
            "baseline_family",
            "topology_condition",
            "seed_aggregation_rule_id",
        ),
    )
    wave_summary_table_rows = _build_numeric_summary_table_rows(
        section_id=WAVE_ONLY_DIAGNOSTICS_SECTION_ID,
        source_rows=wave_pair_rows,
        table_dimension_ids=resolved_table_dimension_ids,
        grouping_fields=(
            "ablation_key",
            "ablation_identity_ids",
            "ablation_family_ids",
            "arm_id",
            "metric_id",
            "units",
        ),
    )
    validation_summary_table_rows = _build_validation_summary_table_rows(
        source_rows=validation_pair_rows,
        table_dimension_ids=resolved_table_dimension_ids,
    )

    summary = {
        "format_version": EXPERIMENT_SUITE_AGGREGATION_FORMAT,
        "suite_reference": {
            "suite_id": str(result_index["suite_id"]),
            "suite_label": str(result_index["suite_label"]),
            "suite_spec_hash": str(result_index["suite_spec_hash"]),
            "suite_root": str(result_index["suite_root"]),
            "suite_plan_path": str(result_index["suite_plan_path"]),
            "suite_metadata_path": str(result_index["suite_metadata_path"]),
            "state_path": str(result_index["state_path"]),
            "package_metadata_path": (
                None
                if package_metadata_path is None
                else str(package_metadata_path)
            ),
            "package_bundle_id": (
                None
                if package_metadata is None
                else str(package_metadata["suite_reference"]["suite_id"])
                + ":"
                + str(package_metadata["suite_reference"]["suite_spec_hash"])
            ),
        },
        "table_dimensions": {
            "declared_dimension_ids": declared_dimension_ids,
            "table_dimension_ids": resolved_table_dimension_ids,
            "collapse_rule_id": CELL_ROLLUP_RULE_COLLAPSE,
            "collapse_description": (
                "Summary tables collapse repeated paired rows by the selected table "
                "dimension ids plus the row's metric identity and ablation identity."
            ),
        },
        "pairing_semantics": {
            "baseline_vs_wave": (
                "Suite aggregation carries forward experiment-level baseline-versus-wave "
                "pairing from group_id, group_kind, and comparison_semantics in the "
                "packaged experiment comparison summary."
            ),
            "intact_vs_ablated": (
                "Suite aggregation only compares base and ablation review cells "
                "declared by suite_plan.comparison_pairings.suite_cell_pairings "
                "with pairing_kind='ablation_vs_base'."
            ),
            "seed_rollup": (
                "Each consumed experiment-level rollup must declare the exact seed "
                "set realized by the suite cell's simulation-lineage children. "
                "The suite layer does not re-average per-seed simulator bundles."
            ),
        },
        "summary": {
            "review_cell_count": len(review_cells),
            "ablation_pairing_count": len(ablation_pairings),
            "has_validation_stage": has_validation_stage,
            "shared_comparison_cell_row_count": len(shared_cell_rows),
            "shared_comparison_paired_row_count": len(shared_pair_rows),
            "shared_comparison_summary_table_row_count": len(shared_summary_table_rows),
            "wave_diagnostic_cell_row_count": len(wave_cell_rows),
            "wave_diagnostic_paired_row_count": len(wave_pair_rows),
            "wave_diagnostic_summary_table_row_count": len(wave_summary_table_rows),
            "validation_cell_summary_row_count": len(validation_cell_rows),
            "validation_paired_row_count": len(validation_pair_rows),
            "validation_finding_row_count": len(validation_finding_rows),
            "validation_summary_table_row_count": len(validation_summary_table_rows),
        },
        SHARED_COMPARISON_SECTION_ID: {
            "cell_rollup_rows": shared_cell_rows,
            "paired_comparison_rows": shared_pair_rows,
            "summary_table_rows": shared_summary_table_rows,
        },
        WAVE_ONLY_DIAGNOSTICS_SECTION_ID: {
            "cell_rollup_rows": wave_cell_rows,
            "paired_comparison_rows": wave_pair_rows,
            "summary_table_rows": wave_summary_table_rows,
        },
        VALIDATION_FINDINGS_SECTION_ID: {
            "cell_summary_rows": validation_cell_rows,
            "paired_comparison_rows": validation_pair_rows,
            "finding_rows": validation_finding_rows,
            "summary_table_rows": validation_summary_table_rows,
        },
    }
    return summary


def execute_experiment_suite_aggregation_workflow(
    record: Mapping[str, Any] | str | Path,
    *,
    table_dimension_ids: Sequence[str] | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    summary = compute_experiment_suite_aggregation(
        record,
        table_dimension_ids=table_dimension_ids,
    )
    paths = build_experiment_suite_aggregation_paths(
        suite_root=summary["suite_reference"]["suite_root"],
        output_dir=output_dir,
    )
    ensure_dir(paths.aggregation_directory)
    ensure_dir(paths.export_directory)
    write_json(summary, paths.summary_path)
    write_csv_rows(
        fieldnames=_shared_row_fieldnames(),
        rows=(_flatten_shared_row(row) for row in summary[SHARED_COMPARISON_SECTION_ID]["cell_rollup_rows"]),
        out_path=paths.shared_cell_rows_path,
    )
    write_csv_rows(
        fieldnames=_shared_row_fieldnames(),
        rows=(
            _flatten_shared_row(row)
            for row in summary[SHARED_COMPARISON_SECTION_ID]["paired_comparison_rows"]
        ),
        out_path=paths.shared_pair_rows_path,
    )
    write_csv_rows(
        fieldnames=_shared_summary_table_fieldnames(),
        rows=(
            _flatten_numeric_summary_table_row(row)
            for row in summary[SHARED_COMPARISON_SECTION_ID]["summary_table_rows"]
        ),
        out_path=paths.shared_summary_table_path,
    )
    write_csv_rows(
        fieldnames=_wave_row_fieldnames(),
        rows=(
            _flatten_wave_row(row)
            for row in summary[WAVE_ONLY_DIAGNOSTICS_SECTION_ID]["cell_rollup_rows"]
        ),
        out_path=paths.wave_cell_rows_path,
    )
    write_csv_rows(
        fieldnames=_wave_row_fieldnames(),
        rows=(
            _flatten_wave_row(row)
            for row in summary[WAVE_ONLY_DIAGNOSTICS_SECTION_ID]["paired_comparison_rows"]
        ),
        out_path=paths.wave_pair_rows_path,
    )
    write_csv_rows(
        fieldnames=_wave_summary_table_fieldnames(),
        rows=(
            _flatten_numeric_summary_table_row(row)
            for row in summary[WAVE_ONLY_DIAGNOSTICS_SECTION_ID]["summary_table_rows"]
        ),
        out_path=paths.wave_summary_table_path,
    )
    write_csv_rows(
        fieldnames=_validation_cell_row_fieldnames(),
        rows=(
            _flatten_validation_cell_row(row)
            for row in summary[VALIDATION_FINDINGS_SECTION_ID]["cell_summary_rows"]
        ),
        out_path=paths.validation_cell_rows_path,
    )
    write_csv_rows(
        fieldnames=_validation_pair_row_fieldnames(),
        rows=(
            _flatten_validation_pair_row(row)
            for row in summary[VALIDATION_FINDINGS_SECTION_ID]["paired_comparison_rows"]
        ),
        out_path=paths.validation_pair_rows_path,
    )
    write_csv_rows(
        fieldnames=_validation_finding_row_fieldnames(),
        rows=(
            _flatten_validation_finding_row(row)
            for row in summary[VALIDATION_FINDINGS_SECTION_ID]["finding_rows"]
        ),
        out_path=paths.validation_finding_rows_path,
    )
    write_csv_rows(
        fieldnames=_validation_summary_table_fieldnames(),
        rows=(
            _flatten_validation_summary_table_row(row)
            for row in summary[VALIDATION_FINDINGS_SECTION_ID]["summary_table_rows"]
        ),
        out_path=paths.validation_summary_table_path,
    )
    return {
        "format_version": EXPERIMENT_SUITE_AGGREGATION_FORMAT,
        "suite_id": str(summary["suite_reference"]["suite_id"]),
        "suite_spec_hash": str(summary["suite_reference"]["suite_spec_hash"]),
        "table_dimension_ids": list(summary["table_dimensions"]["table_dimension_ids"]),
        "output_directory": str(paths.aggregation_directory),
        "summary_path": str(paths.summary_path),
        "shared_cell_rows_path": str(paths.shared_cell_rows_path),
        "shared_pair_rows_path": str(paths.shared_pair_rows_path),
        "shared_summary_table_path": str(paths.shared_summary_table_path),
        "wave_cell_rows_path": str(paths.wave_cell_rows_path),
        "wave_pair_rows_path": str(paths.wave_pair_rows_path),
        "wave_summary_table_path": str(paths.wave_summary_table_path),
        "validation_cell_rows_path": str(paths.validation_cell_rows_path),
        "validation_pair_rows_path": str(paths.validation_pair_rows_path),
        "validation_finding_rows_path": str(paths.validation_finding_rows_path),
        "validation_summary_table_path": str(paths.validation_summary_table_path),
        "row_counts": copy.deepcopy(dict(summary["summary"])),
    }


def _load_package_metadata_if_available(
    record: Mapping[str, Any] | str | Path,
) -> tuple[Path | None, dict[str, Any] | None]:
    if isinstance(record, (str, Path)):
        candidate = Path(record).resolve()
        if candidate.name == "experiment_suite_package.json":
            return candidate, load_experiment_suite_package_metadata(candidate)
    elif isinstance(record, Mapping):
        if "suite_reference" in record and "artifacts" in record:
            package_metadata = load_experiment_suite_package_metadata(
                Path(str(record["artifacts"]["metadata_json"]["path"])).resolve()
            )
            return (
                Path(str(package_metadata["artifacts"]["metadata_json"]["path"])).resolve(),
                package_metadata,
            )
    result_index = load_experiment_suite_result_index(record)
    candidate = resolve_experiment_suite_package_metadata_path(
        suite_root=result_index["suite_root"]
    )
    if candidate.exists():
        return candidate, load_experiment_suite_package_metadata(candidate)
    return None, None


def _load_result_index(
    record: Mapping[str, Any] | str | Path,
) -> dict[str, Any]:
    if isinstance(record, (str, Path)):
        candidate = Path(record).resolve()
        if candidate.name == "experiment_suite_package.json":
            return load_experiment_suite_result_index(
                load_experiment_suite_package_metadata(candidate)
            )
    return load_experiment_suite_result_index(record)


def _declared_dimension_ids(suite_plan: Mapping[str, Any]) -> list[str]:
    return [
        str(item["dimension_id"])
        for item in suite_plan["active_dimensions"]
        if bool(item["is_declared"])
    ]


def _resolve_table_dimension_ids(
    *,
    table_dimension_ids: Sequence[str] | None,
    declared_dimension_ids: Sequence[str],
) -> list[str]:
    declared_set = set(declared_dimension_ids)
    if table_dimension_ids is None:
        return list(declared_dimension_ids)
    resolved = [
        _normalize_identifier(item, field_name="table_dimension_ids")
        for item in table_dimension_ids
    ]
    if len(set(resolved)) != len(resolved):
        raise ValueError("table_dimension_ids must not contain duplicates.")
    invalid = [item for item in resolved if item not in declared_set]
    if invalid:
        raise ValueError(
            "table_dimension_ids must be drawn from declared suite dimensions; "
            f"got unsupported ids {invalid!r}."
        )
    return resolved


def _plan_has_stage(
    suite_plan: Mapping[str, Any],
    *,
    stage_id: str,
) -> bool:
    return any(str(item["stage_id"]) == stage_id for item in suite_plan["stage_targets"])


def _review_cells(result_index: Mapping[str, Any]) -> list[dict[str, Any]]:
    review_lineages = {
        BASE_CONDITION_LINEAGE_KIND,
        ABLATION_VARIANT_LINEAGE_KIND,
    }
    return [
        copy.deepcopy(dict(item))
        for item in result_index["cell_records"]
        if str(item["lineage_kind"]) in review_lineages
    ]


def _expected_seeds_for_review_cell(cell: Mapping[str, Any]) -> list[int]:
    seeds = sorted(
        int(item["simulation_seed"])
        for item in cell.get("simulation_lineage_cells", [])
        if item.get("simulation_seed") is not None
    )
    if not seeds:
        raise ValueError(
            "Suite aggregation requires simulation-lineage seed coverage for "
            f"suite_cell_id {cell['suite_cell_id']!r}."
        )
    return seeds


def _require_stage_artifact(
    cell: Mapping[str, Any],
    *,
    stage_id: str,
    artifact_ids: Sequence[str],
    artifact_label: str,
) -> dict[str, Any]:
    artifact = _require_optional_stage_artifact(
        cell,
        stage_id=stage_id,
        artifact_ids=artifact_ids,
    )
    if artifact is None:
        raise ValueError(
            "Suite aggregation requires "
            f"{artifact_label} for suite_cell_id {cell['suite_cell_id']!r} at "
            f"stage_id {stage_id!r}."
        )
    return artifact


def _require_optional_stage_artifact(
    cell: Mapping[str, Any],
    *,
    stage_id: str,
    artifact_ids: Sequence[str],
) -> dict[str, Any] | None:
    stage_record = _stage_record_for_cell(cell, stage_id=stage_id)
    if stage_record is None:
        return None
    artifacts = [
        copy.deepcopy(dict(item))
        for item in stage_record.get("artifacts", [])
        if str(item.get("artifact_id")) in set(artifact_ids)
    ]
    if not artifacts:
        return None
    artifacts.sort(
        key=lambda item: (
            "" if item.get("bundle_id") is None else str(item["bundle_id"]),
            str(item["path"]),
        )
    )
    chosen = artifacts[0]
    if not bool(chosen.get("exists", True)):
        raise ValueError(
            "Suite aggregation requires an existing artifact for "
            f"suite_cell_id {cell['suite_cell_id']!r}, stage_id {stage_id!r}, "
            f"artifact_id {chosen['artifact_id']!r}, but the indexed path "
            f"{chosen['path']!r} does not exist."
        )
    return chosen


def _stage_record_for_cell(
    cell: Mapping[str, Any],
    *,
    stage_id: str,
) -> dict[str, Any] | None:
    for stage_record in cell["stage_records"]:
        if str(stage_record["stage_id"]) == stage_id:
            return copy.deepcopy(dict(stage_record))
    return None


def _extract_analysis_rows(
    *,
    analysis_payload: Mapping[str, Any],
    cell: Mapping[str, Any],
    declared_dimension_ids: Sequence[str],
    expected_seeds: Sequence[int],
    summary_path: str,
    bundle_id: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    group_rollups = analysis_payload.get("group_metric_rollups", [])
    if not isinstance(group_rollups, Sequence) or isinstance(group_rollups, (str, bytes)):
        raise ValueError(
            "analysis_payload.group_metric_rollups must be a sequence for "
            f"suite_cell_id {cell['suite_cell_id']!r}."
        )
    wave_rollups = analysis_payload.get("wave_metric_rollups", [])
    if not isinstance(wave_rollups, Sequence) or isinstance(wave_rollups, (str, bytes)):
        raise ValueError(
            "analysis_payload.wave_metric_rollups must be a sequence for "
            f"suite_cell_id {cell['suite_cell_id']!r}."
        )
    shared_rows = [
        _build_shared_cell_rollup_row(
            cell=cell,
            declared_dimension_ids=declared_dimension_ids,
            expected_seeds=expected_seeds,
            rollup=item,
            summary_path=summary_path,
            bundle_id=bundle_id,
        )
        for item in group_rollups
    ]
    wave_rows = [
        _build_wave_cell_rollup_row(
            cell=cell,
            declared_dimension_ids=declared_dimension_ids,
            expected_seeds=expected_seeds,
            rollup=item,
            summary_path=summary_path,
            bundle_id=bundle_id,
        )
        for item in wave_rollups
    ]
    return shared_rows, wave_rows


def _build_shared_cell_rollup_row(
    *,
    cell: Mapping[str, Any],
    declared_dimension_ids: Sequence[str],
    expected_seeds: Sequence[int],
    rollup: Mapping[str, Any],
    summary_path: str,
    bundle_id: str | None,
) -> dict[str, Any]:
    normalized_rollup = _require_mapping(rollup, field_name="group_metric_rollup")
    seeds = _normalize_seed_list(
        normalized_rollup.get("seeds"),
        field_name=(
            f"group_metric_rollups[{normalized_rollup.get('group_id')}].seeds"
        ),
    )
    if list(seeds) != list(expected_seeds):
        raise ValueError(
            "Suite aggregation requires complete seed coverage for shared comparison "
            f"rollup suite_cell_id {cell['suite_cell_id']!r} "
            f"group_id {normalized_rollup.get('group_id')!r} "
            f"metric_id {normalized_rollup.get('metric_id')!r}; expected "
            f"{list(expected_seeds)!r}, got {list(seeds)!r}."
        )
    summary_statistics = _normalize_summary_statistics(
        normalized_rollup.get("summary_statistics"),
        field_name=(
            f"group_metric_rollups[{normalized_rollup.get('group_id')}].summary_statistics"
        ),
    )
    context = _cell_context(cell, declared_dimension_ids=declared_dimension_ids)
    return {
        **context,
        "section_id": SHARED_COMPARISON_SECTION_ID,
        "row_kind": CELL_ROLLUP_ROW_KIND,
        "suite_cell_id": str(cell["suite_cell_id"]),
        "lineage_kind": str(cell["lineage_kind"]),
        "parent_cell_id": (
            None if cell.get("parent_cell_id") is None else str(cell["parent_cell_id"])
        ),
        "root_cell_id": (
            None if cell.get("root_cell_id") is None else str(cell["root_cell_id"])
        ),
        "group_id": _normalize_nonempty_string(
            normalized_rollup.get("group_id"),
            field_name="group_metric_rollup.group_id",
        ),
        "group_kind": _normalize_nonempty_string(
            normalized_rollup.get("group_kind"),
            field_name="group_metric_rollup.group_kind",
        ),
        "comparison_semantics": _normalize_nonempty_string(
            normalized_rollup.get("comparison_semantics"),
            field_name="group_metric_rollup.comparison_semantics",
        ),
        "metric_id": _normalize_nonempty_string(
            normalized_rollup.get("metric_id"),
            field_name="group_metric_rollup.metric_id",
        ),
        "readout_id": _normalize_nonempty_string(
            normalized_rollup.get("readout_id"),
            field_name="group_metric_rollup.readout_id",
        ),
        "window_id": _normalize_nonempty_string(
            normalized_rollup.get("window_id"),
            field_name="group_metric_rollup.window_id",
        ),
        "statistic": _normalize_nonempty_string(
            normalized_rollup.get("statistic"),
            field_name="group_metric_rollup.statistic",
        ),
        "units": _normalize_nonempty_string(
            normalized_rollup.get("units"),
            field_name="group_metric_rollup.units",
        ),
        "baseline_family": (
            None
            if normalized_rollup.get("baseline_family") is None
            else str(normalized_rollup["baseline_family"])
        ),
        "topology_condition": (
            None
            if normalized_rollup.get("topology_condition") is None
            else str(normalized_rollup["topology_condition"])
        ),
        "seed_aggregation_rule_id": _normalize_nonempty_string(
            normalized_rollup.get("seed_aggregation_rule_id"),
            field_name="group_metric_rollup.seed_aggregation_rule_id",
        ),
        "seed_count": int(normalized_rollup.get("seed_count", len(seeds))),
        "seeds": list(seeds),
        "expected_seeds": list(expected_seeds),
        "summary_statistics": summary_statistics,
        "sign_consistency": bool(normalized_rollup.get("sign_consistency", False)),
        "effect_direction": _normalize_nonempty_string(
            normalized_rollup.get("effect_direction"),
            field_name="group_metric_rollup.effect_direction",
        ),
        "analysis_summary_path": str(Path(summary_path).resolve()),
        "analysis_bundle_id": bundle_id,
    }


def _build_wave_cell_rollup_row(
    *,
    cell: Mapping[str, Any],
    declared_dimension_ids: Sequence[str],
    expected_seeds: Sequence[int],
    rollup: Mapping[str, Any],
    summary_path: str,
    bundle_id: str | None,
) -> dict[str, Any]:
    normalized_rollup = _require_mapping(rollup, field_name="wave_metric_rollup")
    seeds = _normalize_seed_list(
        normalized_rollup.get("seeds"),
        field_name=(
            f"wave_metric_rollups[{normalized_rollup.get('arm_id')}].seeds"
        ),
    )
    if list(seeds) != list(expected_seeds):
        raise ValueError(
            "Suite aggregation requires complete seed coverage for wave diagnostic "
            f"rollup suite_cell_id {cell['suite_cell_id']!r} "
            f"arm_id {normalized_rollup.get('arm_id')!r} "
            f"metric_id {normalized_rollup.get('metric_id')!r}; expected "
            f"{list(expected_seeds)!r}, got {list(seeds)!r}."
        )
    summary_statistics = _normalize_summary_statistics(
        normalized_rollup.get("summary_statistics"),
        field_name=(
            f"wave_metric_rollups[{normalized_rollup.get('arm_id')}].summary_statistics"
        ),
    )
    context = _cell_context(cell, declared_dimension_ids=declared_dimension_ids)
    return {
        **context,
        "section_id": WAVE_ONLY_DIAGNOSTICS_SECTION_ID,
        "row_kind": CELL_ROLLUP_ROW_KIND,
        "suite_cell_id": str(cell["suite_cell_id"]),
        "lineage_kind": str(cell["lineage_kind"]),
        "parent_cell_id": (
            None if cell.get("parent_cell_id") is None else str(cell["parent_cell_id"])
        ),
        "root_cell_id": (
            None if cell.get("root_cell_id") is None else str(cell["root_cell_id"])
        ),
        "arm_id": _normalize_nonempty_string(
            normalized_rollup.get("arm_id"),
            field_name="wave_metric_rollup.arm_id",
        ),
        "metric_id": _normalize_nonempty_string(
            normalized_rollup.get("metric_id"),
            field_name="wave_metric_rollup.metric_id",
        ),
        "units": _normalize_nonempty_string(
            normalized_rollup.get("units"),
            field_name="wave_metric_rollup.units",
        ),
        "seed_count": int(normalized_rollup.get("seed_count", len(seeds))),
        "seeds": list(seeds),
        "expected_seeds": list(expected_seeds),
        "summary_statistics": summary_statistics,
        "analysis_summary_path": str(Path(summary_path).resolve()),
        "analysis_bundle_id": bundle_id,
    }


def _build_validation_cell_summary_row(
    *,
    cell: Mapping[str, Any],
    validation_summary: Mapping[str, Any],
    declared_dimension_ids: Sequence[str],
    summary_path: str,
    findings_path: str,
    bundle_id: str | None,
) -> dict[str, Any]:
    context = _cell_context(cell, declared_dimension_ids=declared_dimension_ids)
    layer_statuses = _normalize_string_mapping(
        validation_summary.get("layer_statuses", {}),
        field_name="validation_summary.layer_statuses",
    )
    validator_statuses = _normalize_string_mapping(
        validation_summary.get("validator_statuses", {}),
        field_name="validation_summary.validator_statuses",
    )
    return {
        **context,
        "section_id": VALIDATION_FINDINGS_SECTION_ID,
        "row_kind": CELL_SUMMARY_ROW_KIND,
        "suite_cell_id": str(cell["suite_cell_id"]),
        "lineage_kind": str(cell["lineage_kind"]),
        "parent_cell_id": (
            None if cell.get("parent_cell_id") is None else str(cell["parent_cell_id"])
        ),
        "root_cell_id": (
            None if cell.get("root_cell_id") is None else str(cell["root_cell_id"])
        ),
        "overall_status": _normalize_status(
            validation_summary.get("overall_status"),
            field_name="validation_summary.overall_status",
        ),
        "finding_count": int(validation_summary.get("finding_count", 0)),
        "case_count": int(validation_summary.get("case_count", 0)),
        "layer_statuses": layer_statuses,
        "validator_statuses": validator_statuses,
        "validation_summary_path": str(Path(summary_path).resolve()),
        "validation_finding_rows_path": str(Path(findings_path).resolve()),
        "validation_bundle_id": bundle_id,
    }


def _build_validation_finding_rows(
    *,
    cell: Mapping[str, Any],
    finding_rows: Sequence[Mapping[str, Any]],
    declared_dimension_ids: Sequence[str],
    summary_row: Mapping[str, Any],
) -> list[dict[str, Any]]:
    context = _cell_context(cell, declared_dimension_ids=declared_dimension_ids)
    rows: list[dict[str, Any]] = []
    for finding in finding_rows:
        row = {
            **context,
            "section_id": VALIDATION_FINDINGS_SECTION_ID,
            "row_kind": FINDING_ROW_KIND,
            "suite_cell_id": str(cell["suite_cell_id"]),
            "lineage_kind": str(cell["lineage_kind"]),
            "overall_status": str(summary_row["overall_status"]),
            "validation_summary_path": str(summary_row["validation_summary_path"]),
            "validation_finding_rows_path": str(summary_row["validation_finding_rows_path"]),
        }
        row.update(copy.deepcopy(dict(finding)))
        rows.append(row)
    return rows


def _ablation_pairings(suite_plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    pairings = suite_plan["comparison_pairings"]["suite_cell_pairings"]
    return [
        copy.deepcopy(dict(item))
        for item in sorted(pairings, key=lambda item: str(item["pairing_id"]))
        if str(item["pairing_kind"]) == "ablation_vs_base"
    ]


def _require_review_cell(
    review_cells_by_id: Mapping[str, Mapping[str, Any]],
    *,
    suite_cell_id: str,
    pairing_id: str,
) -> dict[str, Any]:
    cell = review_cells_by_id.get(str(suite_cell_id))
    if cell is None:
        raise ValueError(
            "Suite aggregation requires declared review cells for pairing "
            f"{pairing_id!r}; missing suite_cell_id {suite_cell_id!r}."
        )
    return copy.deepcopy(dict(cell))


def _require_loaded_analysis(
    analysis_cache: Mapping[str, Mapping[str, Any]],
    *,
    suite_cell_id: str,
    pairing_id: str,
) -> dict[str, Any]:
    loaded = analysis_cache.get(suite_cell_id)
    if loaded is None:
        raise ValueError(
            "Suite aggregation requires loaded analysis rollups for pairing "
            f"{pairing_id!r}; missing suite_cell_id {suite_cell_id!r}."
        )
    return copy.deepcopy(dict(loaded))


def _require_loaded_validation(
    validation_cache: Mapping[str, Mapping[str, Any]],
    *,
    suite_cell_id: str,
    pairing_id: str,
) -> dict[str, Any]:
    loaded = validation_cache.get(suite_cell_id)
    if loaded is None:
        raise ValueError(
            "Suite aggregation requires loaded validation summaries for pairing "
            f"{pairing_id!r}; missing suite_cell_id {suite_cell_id!r}."
        )
    return copy.deepcopy(dict(loaded))


def _validate_pairing_dimension_alignment(
    *,
    pairing: Mapping[str, Any],
    base_cell: Mapping[str, Any],
    ablation_cell: Mapping[str, Any],
    declared_dimension_ids: Sequence[str],
) -> None:
    base_dimensions = _dimension_value_ids(
        base_cell,
        declared_dimension_ids=declared_dimension_ids,
    )
    ablation_dimensions = _dimension_value_ids(
        ablation_cell,
        declared_dimension_ids=declared_dimension_ids,
    )
    if base_dimensions != ablation_dimensions:
        raise ValueError(
            "Suite aggregation requires base and ablation cells to share the same "
            f"declared dimension assignments for pairing {pairing['pairing_id']!r}; "
            f"base={base_dimensions!r}, ablation={ablation_dimensions!r}."
        )


def _build_numeric_paired_rows(
    *,
    section_id: str,
    pair_label: str,
    pairing: Mapping[str, Any],
    base_rows: Sequence[Mapping[str, Any]],
    ablation_rows: Sequence[Mapping[str, Any]],
    match_fields: Sequence[str],
    carried_fields: Sequence[str],
    base_path_field: str,
    value_label: str,
    declared_dimension_ids: Sequence[str],
) -> list[dict[str, Any]]:
    indexed_ablation = {
        _row_match_key(item, match_fields=match_fields): copy.deepcopy(dict(item))
        for item in ablation_rows
    }
    paired: list[dict[str, Any]] = []
    for base_row in sorted(base_rows, key=lambda item: _row_match_key(item, match_fields=match_fields)):
        key = _row_match_key(base_row, match_fields=match_fields)
        ablation_row = indexed_ablation.get(key)
        if ablation_row is None:
            raise ValueError(
                "Suite aggregation requires matching "
                f"{pair_label} for pairing {pairing['pairing_id']!r}; "
                f"missing key {key!r} in ablation suite_cell_id "
                f"{pairing['ablation_suite_cell_id']!r}."
            )
        if list(base_row["expected_seeds"]) != list(ablation_row["expected_seeds"]):
            raise ValueError(
                "Suite aggregation requires matched expected seeds for pairing "
                f"{pairing['pairing_id']!r} row {key!r}; base "
                f"{base_row['expected_seeds']!r} vs ablation "
                f"{ablation_row['expected_seeds']!r}."
            )
        base_mean = float(base_row["summary_statistics"][value_label])
        ablation_mean = float(ablation_row["summary_statistics"][value_label])
        context = {
            "section_id": section_id,
            "row_kind": PAIRED_COMPARISON_ROW_KIND,
            "pairing_id": str(pairing["pairing_id"]),
            "pairing_kind": str(pairing["pairing_kind"]),
            "base_suite_cell_id": str(pairing["base_suite_cell_id"]),
            "ablation_suite_cell_id": str(pairing["ablation_suite_cell_id"]),
            "dimension_value_ids": _ordered_mapping(
                base_row["dimension_value_ids"],
                keys=declared_dimension_ids,
            ),
            "dimension_value_labels": _ordered_mapping(
                base_row["dimension_value_labels"],
                keys=declared_dimension_ids,
            ),
            "dimension_key": str(base_row["dimension_key"]),
            "ablation_key": str(ablation_row["ablation_key"]),
            "ablation_identity_ids": list(ablation_row["ablation_identity_ids"]),
            "ablation_family_ids": list(ablation_row["ablation_family_ids"]),
        }
        for field_name in carried_fields:
            if field_name in {"dimension_value_ids", "dimension_value_labels"}:
                continue
            context[field_name] = copy.deepcopy(base_row.get(field_name))
        context.update(
            {
                "base_summary_statistics": copy.deepcopy(base_row["summary_statistics"]),
                "ablation_summary_statistics": copy.deepcopy(
                    ablation_row["summary_statistics"]
                ),
                "base_mean": _rounded_float(base_mean),
                "ablation_mean": _rounded_float(ablation_mean),
                "delta_mean": _rounded_float(ablation_mean - base_mean),
                "base_source_path": str(base_row[base_path_field]),
                "ablation_source_path": str(ablation_row[base_path_field]),
                "base_source_bundle_id": copy.deepcopy(base_row.get("analysis_bundle_id")),
                "ablation_source_bundle_id": copy.deepcopy(
                    ablation_row.get("analysis_bundle_id")
                ),
            }
        )
        paired.append(context)
    return paired


def _build_validation_paired_row(
    *,
    pairing: Mapping[str, Any],
    base_row: Mapping[str, Any],
    ablation_row: Mapping[str, Any],
    declared_dimension_ids: Sequence[str],
) -> dict[str, Any]:
    return {
        "section_id": VALIDATION_FINDINGS_SECTION_ID,
        "row_kind": PAIRED_COMPARISON_ROW_KIND,
        "pairing_id": str(pairing["pairing_id"]),
        "pairing_kind": str(pairing["pairing_kind"]),
        "base_suite_cell_id": str(pairing["base_suite_cell_id"]),
        "ablation_suite_cell_id": str(pairing["ablation_suite_cell_id"]),
        "dimension_value_ids": _ordered_mapping(
            base_row["dimension_value_ids"],
            keys=declared_dimension_ids,
        ),
        "dimension_value_labels": _ordered_mapping(
            base_row["dimension_value_labels"],
            keys=declared_dimension_ids,
        ),
        "dimension_key": str(base_row["dimension_key"]),
        "ablation_key": str(ablation_row["ablation_key"]),
        "ablation_identity_ids": list(ablation_row["ablation_identity_ids"]),
        "ablation_family_ids": list(ablation_row["ablation_family_ids"]),
        "base_overall_status": str(base_row["overall_status"]),
        "ablation_overall_status": str(ablation_row["overall_status"]),
        "status_transition": (
            f"{base_row['overall_status']}->{ablation_row['overall_status']}"
        ),
        "status_rank_delta": _validation_status_rank(
            ablation_row["overall_status"]
        )
        - _validation_status_rank(base_row["overall_status"]),
        "base_finding_count": int(base_row["finding_count"]),
        "ablation_finding_count": int(ablation_row["finding_count"]),
        "finding_count_delta": int(ablation_row["finding_count"])
        - int(base_row["finding_count"]),
        "base_case_count": int(base_row["case_count"]),
        "ablation_case_count": int(ablation_row["case_count"]),
        "base_layer_statuses": copy.deepcopy(dict(base_row["layer_statuses"])),
        "ablation_layer_statuses": copy.deepcopy(dict(ablation_row["layer_statuses"])),
        "base_validator_statuses": copy.deepcopy(
            dict(base_row["validator_statuses"])
        ),
        "ablation_validator_statuses": copy.deepcopy(
            dict(ablation_row["validator_statuses"])
        ),
        "base_source_path": str(base_row["validation_summary_path"]),
        "ablation_source_path": str(ablation_row["validation_summary_path"]),
        "base_findings_path": str(base_row["validation_finding_rows_path"]),
        "ablation_findings_path": str(ablation_row["validation_finding_rows_path"]),
        "base_source_bundle_id": copy.deepcopy(base_row.get("validation_bundle_id")),
        "ablation_source_bundle_id": copy.deepcopy(
            ablation_row.get("validation_bundle_id")
        ),
    }


def _build_numeric_summary_table_rows(
    *,
    section_id: str,
    source_rows: Sequence[Mapping[str, Any]],
    table_dimension_ids: Sequence[str],
    grouping_fields: Sequence[str],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        grouped[
            (
                _dimension_slice_key(
                    row["dimension_value_ids"],
                    table_dimension_ids=table_dimension_ids,
                ),
                *[_freeze_group_value(row.get(field_name)) for field_name in grouping_fields],
            )
        ].append(copy.deepcopy(dict(row)))
    summary_rows: list[dict[str, Any]] = []
    for key, items in grouped.items():
        items.sort(key=lambda item: str(item["pairing_id"]))
        template = items[0]
        base_values = np.asarray([float(item["base_mean"]) for item in items], dtype=np.float64)
        ablation_values = np.asarray(
            [float(item["ablation_mean"]) for item in items],
            dtype=np.float64,
        )
        delta_values = np.asarray([float(item["delta_mean"]) for item in items], dtype=np.float64)
        summary_row = {
            "section_id": section_id,
            "row_kind": SUMMARY_TABLE_ROW_KIND,
            "source_row_kind": PAIRED_COMPARISON_ROW_KIND,
            "table_dimension_ids": list(table_dimension_ids),
            "dimension_slice_value_ids": _dimension_slice(
                template["dimension_value_ids"],
                table_dimension_ids=table_dimension_ids,
            ),
            "dimension_slice_key": _dimension_slice_key(
                template["dimension_value_ids"],
                table_dimension_ids=table_dimension_ids,
            ),
            "source_row_count": len(items),
            "collapse_rule_id": (
                CELL_ROLLUP_RULE_PASSTHROUGH
                if len(items) == 1
                else CELL_ROLLUP_RULE_COLLAPSE
            ),
            "source_pairing_ids": [str(item["pairing_id"]) for item in items],
            "base_suite_cell_ids": [str(item["base_suite_cell_id"]) for item in items],
            "ablation_suite_cell_ids": [
                str(item["ablation_suite_cell_id"]) for item in items
            ],
            "base_mean_statistics": _summary_statistics(base_values),
            "ablation_mean_statistics": _summary_statistics(ablation_values),
            "delta_mean_statistics": _summary_statistics(delta_values),
        }
        for field_name in grouping_fields:
            summary_row[field_name] = copy.deepcopy(template.get(field_name))
        summary_rows.append(summary_row)
    summary_rows.sort(key=_numeric_summary_table_row_sort_key)
    return summary_rows


def _build_validation_summary_table_rows(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    table_dimension_ids: Sequence[str],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        grouped[
            (
                _dimension_slice_key(
                    row["dimension_value_ids"],
                    table_dimension_ids=table_dimension_ids,
                ),
                str(row["ablation_key"]),
            )
        ].append(copy.deepcopy(dict(row)))
    table_rows: list[dict[str, Any]] = []
    for (_, ablation_key), items in grouped.items():
        items.sort(key=lambda item: str(item["pairing_id"]))
        template = items[0]
        delta_values = np.asarray(
            [float(item["finding_count_delta"]) for item in items],
            dtype=np.float64,
        )
        base_status_counts = Counter(str(item["base_overall_status"]) for item in items)
        ablation_status_counts = Counter(
            str(item["ablation_overall_status"]) for item in items
        )
        transition_counts = Counter(str(item["status_transition"]) for item in items)
        table_rows.append(
            {
                "section_id": VALIDATION_FINDINGS_SECTION_ID,
                "row_kind": SUMMARY_TABLE_ROW_KIND,
                "source_row_kind": PAIRED_COMPARISON_ROW_KIND,
                "table_dimension_ids": list(table_dimension_ids),
                "dimension_slice_value_ids": _dimension_slice(
                    template["dimension_value_ids"],
                    table_dimension_ids=table_dimension_ids,
                ),
                "dimension_slice_key": _dimension_slice_key(
                    template["dimension_value_ids"],
                    table_dimension_ids=table_dimension_ids,
                ),
                "ablation_key": ablation_key,
                "ablation_identity_ids": list(template["ablation_identity_ids"]),
                "ablation_family_ids": list(template["ablation_family_ids"]),
                "source_row_count": len(items),
                "collapse_rule_id": (
                    CELL_ROLLUP_RULE_PASSTHROUGH
                    if len(items) == 1
                    else CELL_ROLLUP_RULE_COLLAPSE
                ),
                "source_pairing_ids": [str(item["pairing_id"]) for item in items],
                "base_status_counts": _ordered_counter(base_status_counts),
                "ablation_status_counts": _ordered_counter(ablation_status_counts),
                "status_transition_counts": _ordered_counter(transition_counts),
                "worst_base_status": _worst_status(base_status_counts),
                "worst_ablation_status": _worst_status(ablation_status_counts),
                "finding_count_delta_statistics": _summary_statistics(delta_values),
            }
        )
    table_rows.sort(key=_validation_summary_table_row_sort_key)
    return table_rows


def _cell_context(
    cell: Mapping[str, Any],
    *,
    declared_dimension_ids: Sequence[str],
) -> dict[str, Any]:
    value_ids = _dimension_value_ids(cell, declared_dimension_ids=declared_dimension_ids)
    value_labels = _dimension_value_labels(
        cell,
        declared_dimension_ids=declared_dimension_ids,
    )
    ablation_identity_ids = list(cell.get("ablation_identity_ids", []))
    ablation_family_ids = [
        str(item["ablation_family_id"]) for item in cell.get("ablations", [])
    ]
    return {
        "dimension_value_ids": value_ids,
        "dimension_value_labels": value_labels,
        "dimension_key": _dimension_key(value_ids),
        "ablation_identity_ids": ablation_identity_ids,
        "ablation_family_ids": ablation_family_ids,
        "ablation_key": (
            INTACT_ABLATION_KEY
            if not ablation_identity_ids
            else "|".join(ablation_identity_ids)
        ),
    }


def _dimension_value_ids(
    cell: Mapping[str, Any],
    *,
    declared_dimension_ids: Sequence[str],
) -> dict[str, str]:
    raw = _require_mapping(
        cell.get("dimension_value_ids", {}),
        field_name="cell.dimension_value_ids",
    )
    return {
        dimension_id: str(raw[dimension_id])
        for dimension_id in declared_dimension_ids
    }


def _dimension_value_labels(
    cell: Mapping[str, Any],
    *,
    declared_dimension_ids: Sequence[str],
) -> dict[str, str]:
    raw_dimensions = _require_mapping(
        cell.get("dimensions", {}),
        field_name="cell.dimensions",
    )
    labels: dict[str, str] = {}
    for dimension_id in declared_dimension_ids:
        value = _require_mapping(
            raw_dimensions.get(dimension_id),
            field_name=f"cell.dimensions.{dimension_id}",
        )
        label = value.get("value_label", value.get("value_id"))
        labels[dimension_id] = _normalize_nonempty_string(
            label,
            field_name=f"cell.dimensions.{dimension_id}.value_label",
        )
    return labels


def _dimension_key(value_ids: Mapping[str, str]) -> str:
    return "|".join(f"{dimension_id}={value_ids[dimension_id]}" for dimension_id in value_ids)


def _dimension_slice(
    value_ids: Mapping[str, str],
    *,
    table_dimension_ids: Sequence[str],
) -> dict[str, str]:
    return {
        dimension_id: str(value_ids[dimension_id]) for dimension_id in table_dimension_ids
    }


def _dimension_slice_key(
    value_ids: Mapping[str, str],
    *,
    table_dimension_ids: Sequence[str],
) -> str:
    slice_values = _dimension_slice(value_ids, table_dimension_ids=table_dimension_ids)
    if not slice_values:
        return "all_declared_dimensions"
    return _dimension_key(slice_values)


def _ordered_mapping(
    payload: Mapping[str, Any],
    *,
    keys: Sequence[str],
) -> dict[str, Any]:
    return {key: copy.deepcopy(payload[key]) for key in keys}


def _normalize_summary_statistics(
    payload: Any,
    *,
    field_name: str,
) -> dict[str, float]:
    mapping = _require_mapping(payload, field_name=field_name)
    required = ("mean", "median", "min", "max", "std")
    missing = [key for key in required if key not in mapping]
    if missing:
        raise ValueError(f"{field_name} is missing fields {missing!r}.")
    return {
        key: _rounded_float(float(mapping[key])) for key in required
    }


def _normalize_seed_list(
    payload: Any,
    *,
    field_name: str,
) -> list[int]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of integers.")
    return [int(item) for item in payload]


def _normalize_string_mapping(
    payload: Any,
    *,
    field_name: str,
) -> dict[str, str]:
    mapping = _require_mapping(payload, field_name=field_name)
    return {
        _normalize_identifier(key, field_name=f"{field_name}.key"): _normalize_status(
            value,
            field_name=f"{field_name}.{key}",
        )
        for key, value in sorted(mapping.items())
    }


def _normalize_status(payload: Any, *, field_name: str) -> str:
    value = _normalize_nonempty_string(payload, field_name=field_name)
    return value


def _validation_status_rank(status: str) -> int:
    return int(_VALIDATION_STATUS_RANK.get(str(status), 999))


def _worst_status(counts: Mapping[str, int]) -> str:
    if not counts:
        return "unknown"
    return sorted(
        counts,
        key=lambda item: (
            _validation_status_rank(str(item)),
            str(item),
        ),
        reverse=True,
    )[0]


def _ordered_counter(counter: Counter[str]) -> dict[str, int]:
    return {key: int(counter.get(key, 0)) for key in sorted(counter)}


def _summary_statistics(values: np.ndarray) -> dict[str, float]:
    if values.ndim != 1 or values.size < 1:
        raise ValueError("summary statistics require a non-empty 1D array.")
    return {
        "mean": _rounded_float(float(np.mean(values, dtype=np.float64))),
        "median": _rounded_float(float(np.median(values))),
        "min": _rounded_float(float(np.min(values))),
        "max": _rounded_float(float(np.max(values))),
        "std": _rounded_float(float(np.std(values, dtype=np.float64))),
    }


def _rounded_float(value: float) -> float:
    return round(float(value), _ROUND_DIGITS)


def _load_json_mapping(path: str | Path, *, field_name: str) -> dict[str, Any]:
    with Path(path).resolve().open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return _require_mapping(payload, field_name=field_name)


def _load_validation_finding_rows(path: str | Path) -> list[dict[str, Any]]:
    resolved = Path(path).resolve()
    suffix = resolved.suffix.lower()
    if suffix == ".jsonl":
        rows = []
        with resolved.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                rows.append(_require_mapping(payload, field_name="validation finding row"))
        return rows
    if suffix == ".csv":
        with resolved.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return [dict(row) for row in reader]
    raise ValueError(
        "Suite aggregation only supports validation finding rows in JSONL or CSV "
        f"form; got {resolved!r}."
    )


def _row_match_key(
    row: Mapping[str, Any],
    *,
    match_fields: Sequence[str],
) -> tuple[Any, ...]:
    return tuple(_freeze_group_value(row.get(field_name)) for field_name in match_fields)


def _freeze_group_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple((str(key), _freeze_group_value(subvalue)) for key, subvalue in sorted(value.items()))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_freeze_group_value(item) for item in value)
    return value


def _shared_cell_row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["dimension_key"]),
        str(row["ablation_key"]),
        str(row["suite_cell_id"]),
        str(row["group_id"]),
        str(row["metric_id"]),
        str(row["readout_id"]),
        str(row["window_id"]),
        str(row["statistic"]),
    )


def _wave_cell_row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["dimension_key"]),
        str(row["ablation_key"]),
        str(row["suite_cell_id"]),
        str(row["arm_id"]),
        str(row["metric_id"]),
    )


def _validation_cell_row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["dimension_key"]),
        str(row["ablation_key"]),
        str(row["suite_cell_id"]),
    )


def _validation_finding_row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["dimension_key"]),
        str(row["ablation_key"]),
        str(row["suite_cell_id"]),
        str(row.get("layer_id", "")),
        str(row.get("validator_id", "")),
        str(row.get("finding_id", "")),
        str(row.get("case_id", "")),
    )


def _shared_pair_row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["dimension_key"]),
        str(row["ablation_key"]),
        str(row["pairing_id"]),
        str(row["group_id"]),
        str(row["metric_id"]),
        str(row["readout_id"]),
        str(row["window_id"]),
        str(row["statistic"]),
    )


def _wave_pair_row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["dimension_key"]),
        str(row["ablation_key"]),
        str(row["pairing_id"]),
        str(row["arm_id"]),
        str(row["metric_id"]),
    )


def _validation_pair_row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["dimension_key"]),
        str(row["ablation_key"]),
        str(row["pairing_id"]),
    )


def _numeric_summary_table_row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["dimension_slice_key"]),
        str(row.get("ablation_key", "")),
        str(row.get("group_id", "")),
        str(row.get("arm_id", "")),
        str(row.get("metric_id", "")),
        str(row.get("readout_id", "")),
        str(row.get("window_id", "")),
        str(row.get("statistic", "")),
    )


def _validation_summary_table_row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["dimension_slice_key"]),
        str(row["ablation_key"]),
    )


def _json_string(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _shared_row_fieldnames() -> list[str]:
    return [
        "section_id",
        "row_kind",
        "suite_cell_id",
        "lineage_kind",
        "pairing_id",
        "base_suite_cell_id",
        "ablation_suite_cell_id",
        "dimension_key",
        "dimension_value_ids_json",
        "dimension_value_labels_json",
        "ablation_key",
        "ablation_identity_ids_json",
        "ablation_family_ids_json",
        "group_id",
        "group_kind",
        "comparison_semantics",
        "metric_id",
        "readout_id",
        "window_id",
        "statistic",
        "units",
        "baseline_family",
        "topology_condition",
        "seed_aggregation_rule_id",
        "seed_count",
        "seeds_json",
        "expected_seeds_json",
        "summary_mean",
        "summary_median",
        "summary_min",
        "summary_max",
        "summary_std",
        "sign_consistency",
        "effect_direction",
        "base_mean",
        "ablation_mean",
        "delta_mean",
        "analysis_summary_path",
        "base_source_path",
        "ablation_source_path",
        "analysis_bundle_id",
        "base_source_bundle_id",
        "ablation_source_bundle_id",
    ]


def _wave_row_fieldnames() -> list[str]:
    return [
        "section_id",
        "row_kind",
        "suite_cell_id",
        "lineage_kind",
        "pairing_id",
        "base_suite_cell_id",
        "ablation_suite_cell_id",
        "dimension_key",
        "dimension_value_ids_json",
        "dimension_value_labels_json",
        "ablation_key",
        "ablation_identity_ids_json",
        "ablation_family_ids_json",
        "arm_id",
        "metric_id",
        "units",
        "seed_count",
        "seeds_json",
        "expected_seeds_json",
        "summary_mean",
        "summary_median",
        "summary_min",
        "summary_max",
        "summary_std",
        "base_mean",
        "ablation_mean",
        "delta_mean",
        "analysis_summary_path",
        "base_source_path",
        "ablation_source_path",
        "analysis_bundle_id",
        "base_source_bundle_id",
        "ablation_source_bundle_id",
    ]


def _validation_cell_row_fieldnames() -> list[str]:
    return [
        "section_id",
        "row_kind",
        "suite_cell_id",
        "lineage_kind",
        "dimension_key",
        "dimension_value_ids_json",
        "dimension_value_labels_json",
        "ablation_key",
        "ablation_identity_ids_json",
        "ablation_family_ids_json",
        "overall_status",
        "finding_count",
        "case_count",
        "layer_statuses_json",
        "validator_statuses_json",
        "validation_summary_path",
        "validation_finding_rows_path",
        "validation_bundle_id",
    ]


def _validation_pair_row_fieldnames() -> list[str]:
    return [
        "section_id",
        "row_kind",
        "pairing_id",
        "base_suite_cell_id",
        "ablation_suite_cell_id",
        "dimension_key",
        "dimension_value_ids_json",
        "dimension_value_labels_json",
        "ablation_key",
        "ablation_identity_ids_json",
        "ablation_family_ids_json",
        "base_overall_status",
        "ablation_overall_status",
        "status_transition",
        "status_rank_delta",
        "base_finding_count",
        "ablation_finding_count",
        "finding_count_delta",
        "base_case_count",
        "ablation_case_count",
        "base_layer_statuses_json",
        "ablation_layer_statuses_json",
        "base_validator_statuses_json",
        "ablation_validator_statuses_json",
        "base_source_path",
        "ablation_source_path",
        "base_findings_path",
        "ablation_findings_path",
        "base_source_bundle_id",
        "ablation_source_bundle_id",
    ]


def _validation_finding_row_fieldnames() -> list[str]:
    return [
        "section_id",
        "row_kind",
        "suite_cell_id",
        "lineage_kind",
        "overall_status",
        "dimension_key",
        "dimension_value_ids_json",
        "dimension_value_labels_json",
        "ablation_key",
        "ablation_identity_ids_json",
        "ablation_family_ids_json",
        "layer_id",
        "layer_sequence_index",
        "layer_bundle_id",
        "validator_id",
        "finding_id",
        "status",
        "case_id",
        "validator_family_id",
        "arm_id",
        "root_id",
        "variant_id",
        "measured_quantity",
        "measured_value",
        "summary_json",
        "comparison_basis_json",
        "diagnostic_metadata_json",
        "validation_summary_path",
        "validation_finding_rows_path",
    ]


def _shared_summary_table_fieldnames() -> list[str]:
    return [
        "section_id",
        "row_kind",
        "source_row_kind",
        "table_dimension_ids_json",
        "dimension_slice_key",
        "dimension_slice_value_ids_json",
        "ablation_key",
        "ablation_identity_ids_json",
        "ablation_family_ids_json",
        "group_id",
        "group_kind",
        "comparison_semantics",
        "metric_id",
        "readout_id",
        "window_id",
        "statistic",
        "units",
        "baseline_family",
        "topology_condition",
        "seed_aggregation_rule_id",
        "source_row_count",
        "collapse_rule_id",
        "source_pairing_ids_json",
        "base_suite_cell_ids_json",
        "ablation_suite_cell_ids_json",
        "base_mean_mean",
        "base_mean_median",
        "base_mean_min",
        "base_mean_max",
        "base_mean_std",
        "ablation_mean_mean",
        "ablation_mean_median",
        "ablation_mean_min",
        "ablation_mean_max",
        "ablation_mean_std",
        "delta_mean_mean",
        "delta_mean_median",
        "delta_mean_min",
        "delta_mean_max",
        "delta_mean_std",
    ]


def _wave_summary_table_fieldnames() -> list[str]:
    return [
        "section_id",
        "row_kind",
        "source_row_kind",
        "table_dimension_ids_json",
        "dimension_slice_key",
        "dimension_slice_value_ids_json",
        "ablation_key",
        "ablation_identity_ids_json",
        "ablation_family_ids_json",
        "arm_id",
        "metric_id",
        "units",
        "source_row_count",
        "collapse_rule_id",
        "source_pairing_ids_json",
        "base_suite_cell_ids_json",
        "ablation_suite_cell_ids_json",
        "base_mean_mean",
        "base_mean_median",
        "base_mean_min",
        "base_mean_max",
        "base_mean_std",
        "ablation_mean_mean",
        "ablation_mean_median",
        "ablation_mean_min",
        "ablation_mean_max",
        "ablation_mean_std",
        "delta_mean_mean",
        "delta_mean_median",
        "delta_mean_min",
        "delta_mean_max",
        "delta_mean_std",
    ]


def _validation_summary_table_fieldnames() -> list[str]:
    return [
        "section_id",
        "row_kind",
        "source_row_kind",
        "table_dimension_ids_json",
        "dimension_slice_key",
        "dimension_slice_value_ids_json",
        "ablation_key",
        "ablation_identity_ids_json",
        "ablation_family_ids_json",
        "source_row_count",
        "collapse_rule_id",
        "source_pairing_ids_json",
        "base_status_counts_json",
        "ablation_status_counts_json",
        "status_transition_counts_json",
        "worst_base_status",
        "worst_ablation_status",
        "finding_count_delta_mean",
        "finding_count_delta_median",
        "finding_count_delta_min",
        "finding_count_delta_max",
        "finding_count_delta_std",
    ]


def _flatten_shared_row(row: Mapping[str, Any]) -> dict[str, Any]:
    summary_statistics = dict(row.get("summary_statistics", {}))
    base_summary = dict(row.get("base_summary_statistics", {}))
    ablation_summary = dict(row.get("ablation_summary_statistics", {}))
    return {
        "section_id": str(row["section_id"]),
        "row_kind": str(row["row_kind"]),
        "suite_cell_id": row.get("suite_cell_id"),
        "lineage_kind": row.get("lineage_kind"),
        "pairing_id": row.get("pairing_id"),
        "base_suite_cell_id": row.get("base_suite_cell_id"),
        "ablation_suite_cell_id": row.get("ablation_suite_cell_id"),
        "dimension_key": str(row["dimension_key"]),
        "dimension_value_ids_json": _json_string(row["dimension_value_ids"]),
        "dimension_value_labels_json": _json_string(row["dimension_value_labels"]),
        "ablation_key": str(row["ablation_key"]),
        "ablation_identity_ids_json": _json_string(row["ablation_identity_ids"]),
        "ablation_family_ids_json": _json_string(row["ablation_family_ids"]),
        "group_id": row.get("group_id"),
        "group_kind": row.get("group_kind"),
        "comparison_semantics": row.get("comparison_semantics"),
        "metric_id": row.get("metric_id"),
        "readout_id": row.get("readout_id"),
        "window_id": row.get("window_id"),
        "statistic": row.get("statistic"),
        "units": row.get("units"),
        "baseline_family": row.get("baseline_family"),
        "topology_condition": row.get("topology_condition"),
        "seed_aggregation_rule_id": row.get("seed_aggregation_rule_id"),
        "seed_count": row.get("seed_count"),
        "seeds_json": _json_string(row.get("seeds", [])),
        "expected_seeds_json": _json_string(row.get("expected_seeds", [])),
        "summary_mean": summary_statistics.get("mean"),
        "summary_median": summary_statistics.get("median"),
        "summary_min": summary_statistics.get("min"),
        "summary_max": summary_statistics.get("max"),
        "summary_std": summary_statistics.get("std"),
        "sign_consistency": row.get("sign_consistency"),
        "effect_direction": row.get("effect_direction"),
        "base_mean": row.get("base_mean", base_summary.get("mean")),
        "ablation_mean": row.get("ablation_mean", ablation_summary.get("mean")),
        "delta_mean": row.get("delta_mean"),
        "analysis_summary_path": row.get("analysis_summary_path"),
        "base_source_path": row.get("base_source_path"),
        "ablation_source_path": row.get("ablation_source_path"),
        "analysis_bundle_id": row.get("analysis_bundle_id"),
        "base_source_bundle_id": row.get("base_source_bundle_id"),
        "ablation_source_bundle_id": row.get("ablation_source_bundle_id"),
    }


def _flatten_wave_row(row: Mapping[str, Any]) -> dict[str, Any]:
    summary_statistics = dict(row.get("summary_statistics", {}))
    base_summary = dict(row.get("base_summary_statistics", {}))
    ablation_summary = dict(row.get("ablation_summary_statistics", {}))
    return {
        "section_id": str(row["section_id"]),
        "row_kind": str(row["row_kind"]),
        "suite_cell_id": row.get("suite_cell_id"),
        "lineage_kind": row.get("lineage_kind"),
        "pairing_id": row.get("pairing_id"),
        "base_suite_cell_id": row.get("base_suite_cell_id"),
        "ablation_suite_cell_id": row.get("ablation_suite_cell_id"),
        "dimension_key": str(row["dimension_key"]),
        "dimension_value_ids_json": _json_string(row["dimension_value_ids"]),
        "dimension_value_labels_json": _json_string(row["dimension_value_labels"]),
        "ablation_key": str(row["ablation_key"]),
        "ablation_identity_ids_json": _json_string(row["ablation_identity_ids"]),
        "ablation_family_ids_json": _json_string(row["ablation_family_ids"]),
        "arm_id": row.get("arm_id"),
        "metric_id": row.get("metric_id"),
        "units": row.get("units"),
        "seed_count": row.get("seed_count"),
        "seeds_json": _json_string(row.get("seeds", [])),
        "expected_seeds_json": _json_string(row.get("expected_seeds", [])),
        "summary_mean": summary_statistics.get("mean"),
        "summary_median": summary_statistics.get("median"),
        "summary_min": summary_statistics.get("min"),
        "summary_max": summary_statistics.get("max"),
        "summary_std": summary_statistics.get("std"),
        "base_mean": row.get("base_mean", base_summary.get("mean")),
        "ablation_mean": row.get("ablation_mean", ablation_summary.get("mean")),
        "delta_mean": row.get("delta_mean"),
        "analysis_summary_path": row.get("analysis_summary_path"),
        "base_source_path": row.get("base_source_path"),
        "ablation_source_path": row.get("ablation_source_path"),
        "analysis_bundle_id": row.get("analysis_bundle_id"),
        "base_source_bundle_id": row.get("base_source_bundle_id"),
        "ablation_source_bundle_id": row.get("ablation_source_bundle_id"),
    }


def _flatten_validation_cell_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "section_id": str(row["section_id"]),
        "row_kind": str(row["row_kind"]),
        "suite_cell_id": str(row["suite_cell_id"]),
        "lineage_kind": str(row["lineage_kind"]),
        "dimension_key": str(row["dimension_key"]),
        "dimension_value_ids_json": _json_string(row["dimension_value_ids"]),
        "dimension_value_labels_json": _json_string(row["dimension_value_labels"]),
        "ablation_key": str(row["ablation_key"]),
        "ablation_identity_ids_json": _json_string(row["ablation_identity_ids"]),
        "ablation_family_ids_json": _json_string(row["ablation_family_ids"]),
        "overall_status": str(row["overall_status"]),
        "finding_count": int(row["finding_count"]),
        "case_count": int(row["case_count"]),
        "layer_statuses_json": _json_string(row["layer_statuses"]),
        "validator_statuses_json": _json_string(row["validator_statuses"]),
        "validation_summary_path": str(row["validation_summary_path"]),
        "validation_finding_rows_path": str(row["validation_finding_rows_path"]),
        "validation_bundle_id": row.get("validation_bundle_id"),
    }


def _flatten_validation_pair_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "section_id": str(row["section_id"]),
        "row_kind": str(row["row_kind"]),
        "pairing_id": str(row["pairing_id"]),
        "base_suite_cell_id": str(row["base_suite_cell_id"]),
        "ablation_suite_cell_id": str(row["ablation_suite_cell_id"]),
        "dimension_key": str(row["dimension_key"]),
        "dimension_value_ids_json": _json_string(row["dimension_value_ids"]),
        "dimension_value_labels_json": _json_string(row["dimension_value_labels"]),
        "ablation_key": str(row["ablation_key"]),
        "ablation_identity_ids_json": _json_string(row["ablation_identity_ids"]),
        "ablation_family_ids_json": _json_string(row["ablation_family_ids"]),
        "base_overall_status": str(row["base_overall_status"]),
        "ablation_overall_status": str(row["ablation_overall_status"]),
        "status_transition": str(row["status_transition"]),
        "status_rank_delta": int(row["status_rank_delta"]),
        "base_finding_count": int(row["base_finding_count"]),
        "ablation_finding_count": int(row["ablation_finding_count"]),
        "finding_count_delta": int(row["finding_count_delta"]),
        "base_case_count": int(row["base_case_count"]),
        "ablation_case_count": int(row["ablation_case_count"]),
        "base_layer_statuses_json": _json_string(row["base_layer_statuses"]),
        "ablation_layer_statuses_json": _json_string(row["ablation_layer_statuses"]),
        "base_validator_statuses_json": _json_string(row["base_validator_statuses"]),
        "ablation_validator_statuses_json": _json_string(
            row["ablation_validator_statuses"]
        ),
        "base_source_path": str(row["base_source_path"]),
        "ablation_source_path": str(row["ablation_source_path"]),
        "base_findings_path": str(row["base_findings_path"]),
        "ablation_findings_path": str(row["ablation_findings_path"]),
        "base_source_bundle_id": row.get("base_source_bundle_id"),
        "ablation_source_bundle_id": row.get("ablation_source_bundle_id"),
    }


def _flatten_validation_finding_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "section_id": str(row["section_id"]),
        "row_kind": str(row["row_kind"]),
        "suite_cell_id": str(row["suite_cell_id"]),
        "lineage_kind": str(row["lineage_kind"]),
        "overall_status": str(row["overall_status"]),
        "dimension_key": str(row["dimension_key"]),
        "dimension_value_ids_json": _json_string(row["dimension_value_ids"]),
        "dimension_value_labels_json": _json_string(row["dimension_value_labels"]),
        "ablation_key": str(row["ablation_key"]),
        "ablation_identity_ids_json": _json_string(row["ablation_identity_ids"]),
        "ablation_family_ids_json": _json_string(row["ablation_family_ids"]),
        "layer_id": row.get("layer_id"),
        "layer_sequence_index": row.get("layer_sequence_index"),
        "layer_bundle_id": row.get("layer_bundle_id"),
        "validator_id": row.get("validator_id"),
        "finding_id": row.get("finding_id"),
        "status": row.get("status"),
        "case_id": row.get("case_id"),
        "validator_family_id": row.get("validator_family_id"),
        "arm_id": row.get("arm_id"),
        "root_id": row.get("root_id"),
        "variant_id": row.get("variant_id"),
        "measured_quantity": row.get("measured_quantity"),
        "measured_value": row.get("measured_value"),
        "summary_json": _stringify_if_needed(row.get("summary_json")),
        "comparison_basis_json": _stringify_if_needed(
            row.get("comparison_basis_json")
        ),
        "diagnostic_metadata_json": _stringify_if_needed(
            row.get("diagnostic_metadata_json")
        ),
        "validation_summary_path": str(row["validation_summary_path"]),
        "validation_finding_rows_path": str(row["validation_finding_rows_path"]),
    }


def _flatten_numeric_summary_table_row(row: Mapping[str, Any]) -> dict[str, Any]:
    base_stats = dict(row["base_mean_statistics"])
    ablation_stats = dict(row["ablation_mean_statistics"])
    delta_stats = dict(row["delta_mean_statistics"])
    payload = {
        "section_id": str(row["section_id"]),
        "row_kind": str(row["row_kind"]),
        "source_row_kind": str(row["source_row_kind"]),
        "table_dimension_ids_json": _json_string(row["table_dimension_ids"]),
        "dimension_slice_key": str(row["dimension_slice_key"]),
        "dimension_slice_value_ids_json": _json_string(
            row["dimension_slice_value_ids"]
        ),
        "ablation_key": str(row.get("ablation_key", "")),
        "ablation_identity_ids_json": _json_string(row.get("ablation_identity_ids", [])),
        "ablation_family_ids_json": _json_string(row.get("ablation_family_ids", [])),
        "source_row_count": int(row["source_row_count"]),
        "collapse_rule_id": str(row["collapse_rule_id"]),
        "source_pairing_ids_json": _json_string(row["source_pairing_ids"]),
        "base_suite_cell_ids_json": _json_string(row["base_suite_cell_ids"]),
        "ablation_suite_cell_ids_json": _json_string(row["ablation_suite_cell_ids"]),
        "base_mean_mean": base_stats["mean"],
        "base_mean_median": base_stats["median"],
        "base_mean_min": base_stats["min"],
        "base_mean_max": base_stats["max"],
        "base_mean_std": base_stats["std"],
        "ablation_mean_mean": ablation_stats["mean"],
        "ablation_mean_median": ablation_stats["median"],
        "ablation_mean_min": ablation_stats["min"],
        "ablation_mean_max": ablation_stats["max"],
        "ablation_mean_std": ablation_stats["std"],
        "delta_mean_mean": delta_stats["mean"],
        "delta_mean_median": delta_stats["median"],
        "delta_mean_min": delta_stats["min"],
        "delta_mean_max": delta_stats["max"],
        "delta_mean_std": delta_stats["std"],
    }
    for field_name in (
        "group_id",
        "group_kind",
        "comparison_semantics",
        "metric_id",
        "readout_id",
        "window_id",
        "statistic",
        "units",
        "baseline_family",
        "topology_condition",
        "seed_aggregation_rule_id",
        "arm_id",
    ):
        if field_name in row:
            payload[field_name] = row.get(field_name)
    return payload


def _flatten_validation_summary_table_row(row: Mapping[str, Any]) -> dict[str, Any]:
    delta_stats = dict(row["finding_count_delta_statistics"])
    return {
        "section_id": str(row["section_id"]),
        "row_kind": str(row["row_kind"]),
        "source_row_kind": str(row["source_row_kind"]),
        "table_dimension_ids_json": _json_string(row["table_dimension_ids"]),
        "dimension_slice_key": str(row["dimension_slice_key"]),
        "dimension_slice_value_ids_json": _json_string(
            row["dimension_slice_value_ids"]
        ),
        "ablation_key": str(row["ablation_key"]),
        "ablation_identity_ids_json": _json_string(row["ablation_identity_ids"]),
        "ablation_family_ids_json": _json_string(row["ablation_family_ids"]),
        "source_row_count": int(row["source_row_count"]),
        "collapse_rule_id": str(row["collapse_rule_id"]),
        "source_pairing_ids_json": _json_string(row["source_pairing_ids"]),
        "base_status_counts_json": _json_string(row["base_status_counts"]),
        "ablation_status_counts_json": _json_string(row["ablation_status_counts"]),
        "status_transition_counts_json": _json_string(
            row["status_transition_counts"]
        ),
        "worst_base_status": str(row["worst_base_status"]),
        "worst_ablation_status": str(row["worst_ablation_status"]),
        "finding_count_delta_mean": delta_stats["mean"],
        "finding_count_delta_median": delta_stats["median"],
        "finding_count_delta_min": delta_stats["min"],
        "finding_count_delta_max": delta_stats["max"],
        "finding_count_delta_std": delta_stats["std"],
    }


def _stringify_if_needed(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return _json_string(value)


def _require_mapping(payload: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return copy.deepcopy(dict(payload))


__all__ = [
    "EXPERIMENT_SUITE_AGGREGATION_FORMAT",
    "ExperimentSuiteAggregationPaths",
    "build_experiment_suite_aggregation_paths",
    "compute_experiment_suite_aggregation",
    "execute_experiment_suite_aggregation_workflow",
]
