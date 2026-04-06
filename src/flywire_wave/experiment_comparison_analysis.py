from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .experiment_comparison_common import (
    EXPERIMENT_COMPARISON_SUMMARY_VERSION,
    _require_mapping,
)
from .experiment_comparison_core import compute_experiment_comparison_summary
from .experiment_comparison_discovery import discover_experiment_bundle_set
from .experiment_comparison_packaging import (
    package_experiment_analysis_bundle,
    write_experiment_comparison_summary,
)
from .simulation_planning import (
    discover_simulation_run_plans,
    resolve_manifest_readout_analysis_plan,
    resolve_manifest_simulation_plan,
)


def execute_experiment_comparison_workflow(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    output_path: str | Path | None = None,
    simulation_plan: Mapping[str, Any] | None = None,
    analysis_plan: Mapping[str, Any] | None = None,
    bundle_set: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_simulation_plan = (
        _require_mapping(simulation_plan, field_name="simulation_plan")
        if simulation_plan is not None
        else resolve_manifest_simulation_plan(
            manifest_path=manifest_path,
            config_path=config_path,
            schema_path=schema_path,
            design_lock_path=design_lock_path,
        )
    )
    resolved_analysis_plan = (
        _require_mapping(analysis_plan, field_name="analysis_plan")
        if analysis_plan is not None
        else _require_mapping(
            resolved_simulation_plan.get("readout_analysis_plan"),
            field_name="simulation_plan.readout_analysis_plan",
        )
    )
    resolved_bundle_set = (
        _require_mapping(bundle_set, field_name="bundle_set")
        if bundle_set is not None
        else discover_experiment_bundle_set(
            simulation_plan=resolved_simulation_plan,
            analysis_plan=resolved_analysis_plan,
        )
    )
    summary = compute_experiment_comparison_summary(
        analysis_plan=resolved_analysis_plan,
        bundle_set=resolved_bundle_set,
    )
    packaged_bundle = package_experiment_analysis_bundle(
        summary=summary,
        analysis_plan=resolved_analysis_plan,
        bundle_set=resolved_bundle_set,
    )
    written_path = (
        write_experiment_comparison_summary(summary, output_path)
        if output_path is not None
        else None
    )
    result = copy.deepcopy(dict(summary))
    result["summary_path"] = None if written_path is None else str(written_path)
    result["packaged_analysis_bundle"] = packaged_bundle
    return result


__all__ = [
    "EXPERIMENT_COMPARISON_SUMMARY_VERSION",
    "compute_experiment_comparison_summary",
    "discover_experiment_bundle_set",
    "discover_simulation_run_plans",
    "execute_experiment_comparison_workflow",
    "package_experiment_analysis_bundle",
    "resolve_manifest_readout_analysis_plan",
    "resolve_manifest_simulation_plan",
    "write_experiment_comparison_summary",
]
