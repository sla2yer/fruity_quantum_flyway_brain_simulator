from __future__ import annotations

import copy
import html
import importlib
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import REPO_ROOT, load_config
from .dashboard_scene_circuit import load_dashboard_whole_brain_context
from .dashboard_session_contract import (
    APP_SHELL_INDEX_ARTIFACT_ID,
    METADATA_JSON_KEY as DASHBOARD_METADATA_JSON_KEY,
    SESSION_PAYLOAD_ARTIFACT_ID,
    discover_dashboard_session_bundle_paths,
    load_dashboard_session_metadata,
)
from .io_utils import ensure_dir, write_json
from .readiness_contract import (
    FOLLOW_ON_READINESS_KEY,
    READINESS_GATE_HOLD,
    READY_FOR_FOLLOW_ON_WORK_KEY,
)
from .showcase_session_contract import (
    METADATA_JSON_KEY as SHOWCASE_METADATA_JSON_KEY,
    NARRATIVE_PRESET_CATALOG_ARTIFACT_ID,
    discover_showcase_session_bundle_paths,
    load_showcase_session_metadata,
)
from .showcase_session_planning import package_showcase_session, resolve_showcase_session_plan
from .whole_brain_context_contract import (
    CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
    CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
    CONTEXT_VIEW_STATE_ARTIFACT_ID,
    discover_whole_brain_context_session_bundle_paths,
    load_whole_brain_context_session_metadata,
)


MILESTONE17_READINESS_REPORT_VERSION = "milestone17_readiness.v1"

DEFAULT_FIXTURE_TEST_TARGETS = (
    "tests.test_whole_brain_context_contract",
    "tests.test_whole_brain_context_planning",
    "tests.test_whole_brain_context_query",
    "tests.test_dashboard_scene_circuit",
    "tests.test_showcase_session_planning",
)

DEFAULT_DOCUMENTATION_SNIPPETS: dict[str, tuple[str, ...]] = {
    "README.md": (
        "make milestone17-readiness",
        "scripts/37_milestone17_readiness.py",
        "scripts/36_whole_brain_context_session.py",
        "make whole-brain-context",
        "milestone_17_readiness.md",
        "milestone_17_readiness.json",
    ),
    "docs/pipeline_notes.md": (
        "make milestone17-readiness",
        "scripts/37_milestone17_readiness.py",
        "scripts/36_whole_brain_context_session.py",
        "whole_brain_context_session.v1",
        "milestone_17_readiness.md",
        "milestone_17_readiness.json",
    ),
    "Makefile": (
        "whole-brain-context",
        "milestone17-readiness",
        "scripts/36_whole_brain_context_session.py",
        "scripts/37_milestone17_readiness.py",
    ),
}

FOLLOW_ON_TICKETS = (
    {
        "ticket_id": "FW-M17-FOLLOW-001",
        "severity": "non_blocking",
        "title": "Add a browser-level smoke for packaged whole-brain context controls and showcase handoff",
        "summary": (
            "FW-M17-008 proves deterministic planning, packaging, dashboard bridge "
            "metadata, overlay semantics, and showcase handoff records from shipped "
            "local commands, but it still validates the packaged HTML and JSON "
            "surface rather than clicking the browser-rendered controls."
        ),
        "reproduction_notes": (
            "Run `make milestone17-readiness`, then inspect the packaged dashboard "
            "session and whole-brain context bundle under "
            "`data/processed/milestone_17_verification/simulator_results/readiness/milestone_17/generated_fixture/`. "
            "The current report proves contract coherence, but it does not yet drive "
            "representation switches, facet filters, or showcase handoff in a real browser engine."
        ),
    },
    {
        "ticket_id": "FW-M17-FOLLOW-002",
        "severity": "non_blocking",
        "title": "Promote the review fixture into a denser scientifically curated whole-brain context pack",
        "summary": (
            "FW-M17-008 packages a deterministic local whole-brain review fixture with "
            "truthful context-only labeling, pathway explanations, and optional "
            "downstream modules, but it remains an engineering review fixture rather "
            "than the final scientifically curated broader-brain package."
        ),
        "reproduction_notes": (
            "Run `make milestone17-readiness`, then inspect "
            "`data/processed/milestone_17_verification/simulator_results/readiness/milestone_17/generated_fixture/`. "
            "The current fixture is reviewable and deterministic, but it still uses a "
            "compact local metadata graph rather than a denser curated whole-brain pack."
        ),
    },
)


def build_milestone17_readiness_paths(
    processed_simulator_results_dir: str | Path,
) -> dict[str, Path]:
    root = Path(processed_simulator_results_dir).resolve()
    report_dir = root / "readiness" / "milestone_17"
    return {
        "report_dir": report_dir,
        "markdown_path": report_dir / "milestone_17_readiness.md",
        "json_path": report_dir / "milestone_17_readiness.json",
        "commands_dir": report_dir / "commands",
        "generated_fixture_dir": report_dir / "generated_fixture",
    }


def execute_milestone17_readiness_pass(
    *,
    config_path: str | Path,
    fixture_verification: Mapping[str, Any],
    python_executable: str,
    root_dir: str | Path = REPO_ROOT,
) -> dict[str, Any]:
    repo_root = Path(root_dir).resolve()
    cfg = load_config(config_path, project_root=repo_root)
    processed_simulator_results_dir = Path(
        cfg["paths"]["processed_simulator_results_dir"]
    ).resolve()
    readiness_paths = build_milestone17_readiness_paths(processed_simulator_results_dir)
    report_dir = ensure_dir(readiness_paths["report_dir"])
    commands_dir = ensure_dir(readiness_paths["commands_dir"])
    generated_fixture_dir = readiness_paths["generated_fixture_dir"]
    shutil.rmtree(generated_fixture_dir, ignore_errors=True)
    ensure_dir(generated_fixture_dir)

    fixture = _materialize_milestone17_fixture(
        repo_root=repo_root,
        generated_fixture_dir=generated_fixture_dir,
    )
    showcase_audit = _audit_showcase_handoff(
        repo_root=repo_root,
        python_executable=python_executable,
        commands_dir=commands_dir,
        fixture=fixture,
    )
    context_review_audit = _audit_context_review_workflow(
        repo_root=repo_root,
        python_executable=python_executable,
        commands_dir=commands_dir,
        fixture=fixture,
        showcase_metadata_path=Path(showcase_audit["metadata_path"]).resolve(),
    )
    dashboard_audit = _audit_dashboard_bridge(
        repo_root=repo_root,
        python_executable=python_executable,
        commands_dir=commands_dir,
        fixture=fixture,
        context_metadata_path=Path(context_review_audit["metadata_path"]).resolve(),
    )
    downstream_module_audit = _audit_downstream_module_packaging(
        repo_root=repo_root,
        python_executable=python_executable,
        commands_dir=commands_dir,
        fixture=fixture,
        showcase_metadata_path=Path(showcase_audit["metadata_path"]).resolve(),
    )
    documentation_audit = _audit_documentation(repo_root=repo_root)

    workflow_coverage = {
        "fixture_context_suite": str(fixture_verification.get("status", "")) == "pass",
        "showcase_handoff_behavior": showcase_audit["overall_status"] == "pass",
        "context_session_planning_and_packaging": context_review_audit["overall_status"]
        == "pass",
        "reduction_profile_behavior": context_review_audit["reduction_profiles_verified"],
        "dashboard_render_bridge": dashboard_audit["overall_status"] == "pass",
        "overlay_and_pathway_explanations": context_review_audit["overlay_semantics_verified"]
        and dashboard_audit["overlay_semantics_verified"],
        "optional_downstream_module_packaging": downstream_module_audit["overall_status"]
        == "pass",
        "documentation": documentation_audit["overall_status"] == "pass",
    }

    all_issues = (
        list(showcase_audit["issues"])
        + list(context_review_audit["issues"])
        + list(dashboard_audit["issues"])
        + list(downstream_module_audit["issues"])
        + list(documentation_audit["issues"])
    )
    blocking_issues = [
        issue for issue in all_issues if str(issue.get("severity")) == "blocking"
    ]
    review_issues = [
        issue for issue in all_issues if str(issue.get("severity")) == "review"
    ]
    fixture_status = str(fixture_verification.get("status", "skipped"))
    if fixture_status != "pass" or blocking_issues or not all(workflow_coverage.values()):
        readiness_status = READINESS_GATE_HOLD
    elif review_issues:
        readiness_status = "review"
    else:
        readiness_status = "ready"

    verification_command_sequence = _verification_command_sequence(
        fixture=fixture,
        showcase_audit=showcase_audit,
        context_review_audit=context_review_audit,
        downstream_module_audit=downstream_module_audit,
        dashboard_audit=dashboard_audit,
    )
    summary = {
        "report_version": MILESTONE17_READINESS_REPORT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "report_dir": str(report_dir.resolve()),
        "markdown_path": str(readiness_paths["markdown_path"].resolve()),
        "json_path": str(readiness_paths["json_path"].resolve()),
        "generated_fixture_dir": str(generated_fixture_dir.resolve()),
        "generated_fixture_manifest_path": str(Path(fixture["manifest_path"]).resolve()),
        "generated_fixture_config_path": str(Path(fixture["config_path"]).resolve()),
        "documented_verification_command": "make milestone17-readiness",
        "explicit_verification_command": (
            "python scripts/37_milestone17_readiness.py "
            "--config config/milestone_17_verification.yaml"
        ),
        "verification_command_sequence": verification_command_sequence,
        "fixture_verification": dict(fixture_verification),
        "fixture_inputs": {
            "dashboard_metadata_path": str(Path(fixture["dashboard_metadata_path"]).resolve()),
            "suite_package_metadata_path": str(
                Path(fixture["suite_package_metadata_path"]).resolve()
            ),
            "suite_review_summary_path": str(
                Path(fixture["suite_review_summary_path"]).resolve()
            ),
            "synapse_registry_path": str(Path(fixture["synapse_registry_path"]).resolve()),
            "node_metadata_registry_path": str(
                Path(fixture["node_metadata_registry_path"]).resolve()
            ),
        },
        "showcase_audit": showcase_audit,
        "context_review_audit": context_review_audit,
        "dashboard_audit": dashboard_audit,
        "downstream_module_audit": downstream_module_audit,
        "documentation_audit": documentation_audit,
        "workflow_coverage": workflow_coverage,
        "remaining_risks": [
            "The Milestone 17 readiness pass proves deterministic local whole-brain-context packaging, dashboard bridge semantics, and showcase handoff on a shipped fixture. It is an engineering integration gate, not a scientific claim that the packaged broader-brain relationships are exhaustive or final.",
            "The current verification checks packaged HTML and JSON contract behavior plus summary-only fallback logic, but it does not yet click browser-rendered context controls or showcase handoff affordances in a real DOM runtime.",
            "Optional downstream modules remain explicitly simplified context summaries. Later work must preserve those truthfulness labels and keep any richer broader-brain curation visibly separate from the active simulator subset.",
        ],
        "follow_on_tickets": [dict(item) for item in FOLLOW_ON_TICKETS],
        "readiness_scope_note": (
            "The shipped readiness pass exercises showcase-driven whole-brain-context "
            "planning, deterministic packaged query execution, richer preset packaging, "
            "scalable dashboard bridge rendering, overlay and pathway explanation "
            "metadata, optional downstream-module packaging, and showcase-aware handoff "
            "semantics from one coherent local fixture."
        ),
        FOLLOW_ON_READINESS_KEY: {
            "status": readiness_status,
            READY_FOR_FOLLOW_ON_WORK_KEY: bool(readiness_status != READINESS_GATE_HOLD),
            "ready_for_milestones": (
                ["broader_scientific_review", "later_context_follow_on_work"]
                if readiness_status != READINESS_GATE_HOLD
                else []
            ),
            "local_context_gate": readiness_status,
            "scientific_review_boundary": (
                "Milestone 17 is engineering-ready when the packaged context session "
                "keeps active-versus-context labels explicit, preserves deterministic "
                "preset and handoff semantics, and degrades honestly when broader graph "
                "payloads exceed render budgets. Scientific interpretation still depends "
                "on later curation of which broader pathways or modules are worth showing."
            ),
        },
    }

    readiness_paths["markdown_path"].write_text(
        _render_milestone17_readiness_markdown(summary=summary),
        encoding="utf-8",
    )
    write_json(summary, readiness_paths["json_path"])
    return summary


def _materialize_milestone17_fixture(
    *,
    repo_root: Path,
    generated_fixture_dir: Path,
) -> dict[str, Any]:
    showcase_fixture_builder = _load_fixture_builder(
        repo_root=repo_root,
        module_names=(
            "tests.test_showcase_session_planning",
            "test_showcase_session_planning",
        ),
        builder_name="_materialize_packaged_showcase_fixture",
    )
    node_metadata_builder = _load_fixture_builder(
        repo_root=repo_root,
        module_names=(
            "tests.test_whole_brain_context_planning",
            "test_whole_brain_context_planning",
        ),
        builder_name="_write_context_review_metadata_fixture",
    )
    synapse_registry_builder = _load_fixture_builder(
        repo_root=repo_root,
        module_names=(
            "tests.test_whole_brain_context_planning",
            "test_whole_brain_context_planning",
        ),
        builder_name="_write_context_review_synapse_registry",
    )

    fixture_root = generated_fixture_dir / "showcase_fixture"
    fixture_root.mkdir(parents=True, exist_ok=True)
    fixture = showcase_fixture_builder(fixture_root)
    node_metadata_registry_path = node_metadata_builder(fixture["config_path"])
    synapse_registry_path = generated_fixture_dir / "context_review_fixture" / "local_synapse_registry.csv"
    synapse_registry_builder(synapse_registry_path)
    return {
        **fixture,
        "node_metadata_registry_path": str(Path(node_metadata_registry_path).resolve()),
        "synapse_registry_path": str(synapse_registry_path.resolve()),
    }


def _load_fixture_builder(
    *,
    repo_root: Path,
    module_names: Sequence[str],
    builder_name: str,
):
    tests_dir = repo_root / "tests"
    src_dir = repo_root / "src"
    for path in (tests_dir, src_dir):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        builder = getattr(module, builder_name, None)
        if callable(builder):
            return builder
    raise ModuleNotFoundError(
        f"Could not import the repo-owned fixture helper {builder_name!r}."
    )


def _audit_showcase_handoff(
    *,
    repo_root: Path,
    python_executable: str,
    commands_dir: Path,
    fixture: Mapping[str, Any],
) -> dict[str, Any]:
    issues = []
    command = [
        python_executable,
        "scripts/35_showcase_session.py",
        "build",
        "--config",
        str(Path(fixture["config_path"]).resolve()),
        "--dashboard-session-metadata",
        str(Path(fixture["dashboard_metadata_path"]).resolve()),
        "--suite-package-metadata",
        str(Path(fixture["suite_package_metadata_path"]).resolve()),
        "--suite-review-summary",
        str(Path(fixture["suite_review_summary_path"]).resolve()),
        "--table-dimension-id",
        "motion_direction",
    ]
    build_command = _run_json_command(
        command=command,
        cwd=repo_root,
        command_path=commands_dir / "showcase_session_build.json",
    )
    if build_command["returncode"] != 0:
        issues.append(
            _issue(
                severity="blocking",
                title="Showcase session build command failed",
                summary="Milestone 17 readiness requires one packaged showcase session to verify the handoff path.",
            )
        )
        return {
            "overall_status": "fail",
            "build_command": build_command,
            "metadata_path": "",
            "issues": issues,
        }

    metadata_path = Path(build_command["parsed_summary"]["metadata_path"]).resolve()
    metadata = load_showcase_session_metadata(metadata_path)
    bundle_paths = discover_showcase_session_bundle_paths(metadata)
    catalog = json.loads(
        bundle_paths[NARRATIVE_PRESET_CATALOG_ARTIFACT_ID].read_text(encoding="utf-8")
    )
    analysis_summary = next(
        item
        for item in catalog["saved_presets"]
        if str(item["preset_id"]) == "analysis_summary"
    )
    handoff_links = [
        item
        for item in analysis_summary["presentation_state_patch"]["rehearsal_metadata"][
            "presentation_links"
        ]
        if str(item["link_kind"]) == "whole_brain_context_handoff"
    ]
    if len(handoff_links) != 1:
        issues.append(
            _issue(
                severity="blocking",
                title="Showcase analysis summary preset lost its whole-brain context handoff link",
                summary="The packaged showcase summary landing must advertise one stable Milestone 17 handoff link.",
            )
        )
    elif (
        str(handoff_links[0]["shared_context"]["target_context_preset_id"])
        != "showcase_handoff"
    ):
        issues.append(
            _issue(
                severity="blocking",
                title="Showcase handoff points at the wrong Milestone 17 preset",
                summary="The packaged showcase handoff must target the reserved `showcase_handoff` preset.",
            )
        )

    return {
        "overall_status": "pass" if not issues else "fail",
        "build_command": build_command,
        "metadata_path": str(metadata_path),
        "narrative_preset_catalog_path": str(
            bundle_paths[NARRATIVE_PRESET_CATALOG_ARTIFACT_ID].resolve()
        ),
        "analysis_summary_handoff_link_count": len(handoff_links),
        "handoff_target_preset_id": (
            None if not handoff_links else handoff_links[0]["shared_context"]["target_context_preset_id"]
        ),
        "issues": issues,
    }


def _audit_context_review_workflow(
    *,
    repo_root: Path,
    python_executable: str,
    commands_dir: Path,
    fixture: Mapping[str, Any],
    showcase_metadata_path: Path,
) -> dict[str, Any]:
    issues = []
    first_command = _run_json_command(
        command=_context_build_command(
            python_executable=python_executable,
            fixture=fixture,
            showcase_metadata_path=showcase_metadata_path,
        ),
        cwd=repo_root,
        command_path=commands_dir / "whole_brain_context_build_first.json",
    )
    if first_command["returncode"] != 0:
        issues.append(
            _issue(
                severity="blocking",
                title="Whole-brain context build command failed",
                summary="Milestone 17 readiness requires one shipped whole-brain context CLI path to package the richer local review surface.",
            )
        )
        return {
            "overall_status": "fail",
            "first_command": first_command,
            "issues": issues,
            "reduction_profiles_verified": False,
            "overlay_semantics_verified": False,
            "metadata_path": "",
        }

    metadata_path = Path(first_command["parsed_summary"]["metadata_path"]).resolve()
    bundle_paths = discover_whole_brain_context_session_bundle_paths(
        load_whole_brain_context_session_metadata(metadata_path)
    )
    first_snapshot = {
        artifact_id: bundle_paths[artifact_id].read_text(encoding="utf-8")
        for artifact_id in (
            DASHBOARD_METADATA_JSON_KEY,
            CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
            CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
            CONTEXT_VIEW_STATE_ARTIFACT_ID,
        )
    }
    second_command = _run_json_command(
        command=_context_build_command(
            python_executable=python_executable,
            fixture=fixture,
            showcase_metadata_path=showcase_metadata_path,
        ),
        cwd=repo_root,
        command_path=commands_dir / "whole_brain_context_build_second.json",
    )
    if second_command["returncode"] != 0:
        issues.append(
            _issue(
                severity="blocking",
                title="Repeated whole-brain context build command failed",
                summary="Milestone 17 readiness requires the public context-packaging command to rerun deterministically.",
            )
        )

    second_snapshot = {
        artifact_id: bundle_paths[artifact_id].read_text(encoding="utf-8")
        for artifact_id in (
            DASHBOARD_METADATA_JSON_KEY,
            CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
            CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
            CONTEXT_VIEW_STATE_ARTIFACT_ID,
        )
    }
    deterministic = first_snapshot == second_snapshot
    if not deterministic:
        issues.append(
            _issue(
                severity="blocking",
                title="Whole-brain context package changed across reruns",
                summary="The public Milestone 17 context workflow no longer writes deterministic package artifacts across repeated CLI builds.",
            )
        )

    inspect_command = _run_json_command(
        command=[
            python_executable,
            "scripts/36_whole_brain_context_session.py",
            "inspect",
            "--whole-brain-context-metadata",
            str(metadata_path),
        ],
        cwd=repo_root,
        command_path=commands_dir / "whole_brain_context_inspect.json",
    )
    if inspect_command["returncode"] != 0:
        issues.append(
            _issue(
                severity="blocking",
                title="Whole-brain context inspect command failed",
                summary="The public Milestone 17 inspect surface should summarize one packaged context bundle without custom code.",
            )
        )

    catalog = json.loads(
        bundle_paths[CONTEXT_QUERY_CATALOG_ARTIFACT_ID].read_text(encoding="utf-8")
    )
    payload = json.loads(
        bundle_paths[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID].read_text(encoding="utf-8")
    )
    state = json.loads(
        bundle_paths[CONTEXT_VIEW_STATE_ARTIFACT_ID].read_text(encoding="utf-8")
    )
    preset_payloads = payload["query_preset_payloads"]
    reduction_profile_ids = [
        str(preset_payloads[preset_id]["reduction_profile"]["reduction_profile_id"])
        for preset_id in sorted(preset_payloads)
    ]
    reduction_profiles_verified = {
        "balanced_neighborhood",
        "pathway_focus",
        "downstream_module_collapsed",
    }.issubset(set(reduction_profile_ids))
    if not reduction_profiles_verified:
        issues.append(
            _issue(
                severity="blocking",
                title="Whole-brain preset library no longer spans the expected reduction profiles",
                summary="The packaged Milestone 17 preset library should exercise balanced, pathway-focused, and collapsed downstream reductions.",
            )
        )

    overview_graph = payload["query_execution"]["overview_graph"]
    focused_subgraph = payload["query_execution"]["focused_subgraph"]
    overlay_ids = [
        str(item["overlay_id"]) for item in overview_graph["overlay_workflow_catalog"]
    ]
    metadata_facet_ids = [
        str(item["metadata_facet_id"])
        for item in overview_graph["metadata_facet_group_catalog"]
    ]
    pathway_cards = overview_graph["pathway_explanation_catalog"][0]["card_count"]
    node_role_ids = {
        str(item["node_role_id"]) for item in overview_graph["node_records"]
    }
    overlay_semantics_verified = (
        {
            "active_boundary",
            "upstream_graph",
            "downstream_graph",
            "bidirectional_context_graph",
            "pathway_highlight",
            "downstream_module",
            "metadata_facet_badges",
        }.issubset(set(overlay_ids))
        and {"cell_class", "neuropil"}.issubset(set(metadata_facet_ids))
        and pathway_cards > 0
        and {"active_selected", "context_only"}.issubset(node_role_ids)
    )
    if not overlay_semantics_verified:
        issues.append(
            _issue(
                severity="blocking",
                title="Whole-brain query payload no longer exposes the expected overlay or explanation semantics",
                summary="The readiness fixture should carry explicit overlays, metadata facets, pathway explanations, and active/context node roles.",
            )
        )

    if str(catalog["active_preset_id"]) != "overview_context":
        issues.append(
            _issue(
                severity="blocking",
                title="Whole-brain review package no longer lands on the overview preset",
                summary="The packaged review fixture should default to the richer `overview_context` preset.",
            )
        )
    if list(catalog["available_preset_ids"]) != [
        "overview_context",
        "upstream_halo",
        "downstream_halo",
        "pathway_focus",
        "dashboard_handoff",
        "showcase_handoff",
    ]:
        issues.append(
            _issue(
                severity="blocking",
                title="Whole-brain query preset discovery changed unexpectedly",
                summary="Milestone 17 readiness expects the shipped six-preset review library in stable discovery order.",
            )
        )
    if str(state["active_preset_id"]) != str(catalog["active_preset_id"]):
        issues.append(
            _issue(
                severity="blocking",
                title="Whole-brain view state no longer agrees with the packaged active preset",
                summary="The serialized Milestone 17 view state should land on the same preset recorded in the query catalog.",
            )
        )

    return {
        "overall_status": "pass" if not issues else "fail",
        "first_command": first_command,
        "second_command": second_command,
        "inspect_command": inspect_command,
        "metadata_path": str(metadata_path),
        "context_view_payload_path": str(
            bundle_paths[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID].resolve()
        ),
        "context_query_catalog_path": str(
            bundle_paths[CONTEXT_QUERY_CATALOG_ARTIFACT_ID].resolve()
        ),
        "context_view_state_path": str(
            bundle_paths[CONTEXT_VIEW_STATE_ARTIFACT_ID].resolve()
        ),
        "deterministic": deterministic,
        "active_query_profile_id": str(payload["query_execution"]["query_profile_id"]),
        "active_preset_id": str(catalog["active_preset_id"]),
        "available_preset_ids": list(catalog["available_preset_ids"]),
        "reduction_profile_ids": reduction_profile_ids,
        "reduction_profiles_verified": reduction_profiles_verified,
        "overlay_ids": overlay_ids,
        "metadata_facet_ids": metadata_facet_ids,
        "pathway_card_count": int(pathway_cards),
        "overview_root_count": int(overview_graph["summary"]["distinct_root_count"]),
        "focused_root_count": int(focused_subgraph["summary"]["distinct_root_count"]),
        "overlay_semantics_verified": overlay_semantics_verified,
        "issues": issues,
    }


def _audit_dashboard_bridge(
    *,
    repo_root: Path,
    python_executable: str,
    commands_dir: Path,
    fixture: Mapping[str, Any],
    context_metadata_path: Path,
) -> dict[str, Any]:
    issues = []
    build_command = _run_json_command(
        command=[
            python_executable,
            "scripts/29_dashboard_shell.py",
            "build",
            "--config",
            str(Path(fixture["config_path"]).resolve()),
            "--manifest",
            str(Path(fixture["manifest_path"]).resolve()),
            "--schema",
            str(Path(fixture["schema_path"]).resolve()),
            "--design-lock",
            str(Path(fixture["design_lock_path"]).resolve()),
            "--whole-brain-context-metadata",
            str(context_metadata_path.resolve()),
        ],
        cwd=repo_root,
        command_path=commands_dir / "dashboard_with_whole_brain_context_build.json",
    )
    if build_command["returncode"] != 0:
        issues.append(
            _issue(
                severity="blocking",
                title="Dashboard build with whole-brain context failed",
                summary="Milestone 17 readiness requires the packaged dashboard shell to consume the context session without ad hoc patches.",
            )
        )
        return {
            "overall_status": "fail",
            "build_command": build_command,
            "issues": issues,
            "overlay_semantics_verified": False,
        }

    dashboard_metadata_path = Path(build_command["parsed_summary"]["metadata_path"]).resolve()
    open_no_browser = _run_json_command(
        command=[
            python_executable,
            "scripts/29_dashboard_shell.py",
            "open",
            "--dashboard-session-metadata",
            str(dashboard_metadata_path),
            "--no-browser",
        ],
        cwd=repo_root,
        command_path=commands_dir / "dashboard_with_whole_brain_context_open_no_browser.json",
    )
    if open_no_browser["returncode"] != 0:
        issues.append(
            _issue(
                severity="blocking",
                title="Dashboard open --no-browser command failed for the whole-brain bridge session",
                summary="The packaged dashboard app shell should remain discoverable after linking Milestone 17 context metadata.",
            )
        )

    metadata = load_dashboard_session_metadata(dashboard_metadata_path)
    bundle_paths = discover_dashboard_session_bundle_paths(metadata)
    payload = json.loads(bundle_paths[SESSION_PAYLOAD_ARTIFACT_ID].read_text(encoding="utf-8"))
    app_shell_path = bundle_paths[APP_SHELL_INDEX_ARTIFACT_ID]
    bootstrap = _extract_embedded_json(
        app_shell_path.read_text(encoding="utf-8"),
        script_id="dashboard-app-bootstrap",
    )
    whole_brain = payload["pane_inputs"]["circuit"]["whole_brain_context"]
    representation_by_id = {
        item["representation_id"]: item for item in whole_brain["representation_catalog"]
    }
    overview_styles = {
        str(item["style_variant"])
        for item in representation_by_id["overview"]["node_catalog"]
    }
    focused_styles = {
        str(item["style_variant"])
        for item in representation_by_id["focused"]["node_catalog"]
    }
    overlay_semantics_verified = (
        whole_brain["availability"] in {"available", "partial"}
        and sorted(representation_by_id) == ["focused", "overview"]
        and representation_by_id["overview"]["availability"] == "available"
        and representation_by_id["focused"]["availability"] == "available"
        and {"active_selected", "context_only"}.issubset(overview_styles)
        and (
            "context_pathway_highlight" in focused_styles
            or "active_pathway_highlight" in focused_styles
        )
        and str(bootstrap["links"]["whole_brain_context_metadata"]).endswith(
            "whole_brain_context_session.json"
        )
        and str(bootstrap["links"]["whole_brain_context_view_payload"]).endswith(
            "context_view_payload.json"
        )
    )
    if not overlay_semantics_verified:
        issues.append(
            _issue(
                severity="blocking",
                title="Dashboard bridge payload no longer exposes the expected whole-brain context representations",
                summary="The packaged dashboard session should keep overview/focused context representations and explicit bridge links to the Milestone 17 package.",
            )
        )

    oversized = load_dashboard_whole_brain_context(
        metadata_path=context_metadata_path,
        selected_root_ids=payload["selection"]["selected_root_ids"],
        max_overview_node_count=2,
        max_overview_edge_count=1,
    )
    oversized_overview = next(
        item
        for item in oversized["representation_catalog"]
        if str(item["representation_id"]) == "overview"
    )
    summary_only_verified = (
        str(oversized_overview["availability"]) == "summary_only"
        and oversized_overview["node_catalog"] == []
        and "render budget" in str(oversized_overview["reason"])
    )
    if not summary_only_verified:
        issues.append(
            _issue(
                severity="blocking",
                title="Dashboard whole-brain context no longer degrades honestly when the overview graph is oversized",
                summary="Milestone 17 readiness expects larger context payloads to fall back to summary-only mode instead of pretending the full graph rendered.",
            )
        )

    return {
        "overall_status": "pass" if not issues else "fail",
        "build_command": build_command,
        "open_no_browser": open_no_browser,
        "metadata_path": str(dashboard_metadata_path),
        "app_shell_path": str(app_shell_path.resolve()),
        "representation_ids": sorted(representation_by_id),
        "overview_style_variants": sorted(overview_styles),
        "focused_style_variants": sorted(focused_styles),
        "overlay_semantics_verified": overlay_semantics_verified,
        "summary_only_verified": summary_only_verified,
        "bootstrap_links": {
            "whole_brain_context_metadata": bootstrap["links"]["whole_brain_context_metadata"],
            "whole_brain_context_view_payload": bootstrap["links"][
                "whole_brain_context_view_payload"
            ],
        },
        "issues": issues,
    }


def _audit_downstream_module_packaging(
    *,
    repo_root: Path,
    python_executable: str,
    commands_dir: Path,
    fixture: Mapping[str, Any],
    showcase_metadata_path: Path,
) -> dict[str, Any]:
    issues = []
    build_command = _run_json_command(
        command=_context_build_command(
            python_executable=python_executable,
            fixture=fixture,
            showcase_metadata_path=showcase_metadata_path,
            query_profile_id="downstream_module_review",
            selected_query_profile_ids=["downstream_module_review"],
            requested_downstream_module_role_ids=["simplified_readout_module"],
        ),
        cwd=repo_root,
        command_path=commands_dir / "whole_brain_context_downstream_module_build.json",
    )
    if build_command["returncode"] != 0:
        issues.append(
            _issue(
                severity="blocking",
                title="Whole-brain downstream-module packaging command failed",
                summary="Milestone 17 readiness requires one shipped command path that packages optional downstream-module metadata honestly.",
            )
        )
        return {
            "overall_status": "fail",
            "build_command": build_command,
            "issues": issues,
        }

    metadata_path = Path(build_command["parsed_summary"]["metadata_path"]).resolve()
    bundle_paths = discover_whole_brain_context_session_bundle_paths(
        load_whole_brain_context_session_metadata(metadata_path)
    )
    payload = json.loads(
        bundle_paths[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID].read_text(encoding="utf-8")
    )
    catalog = json.loads(
        bundle_paths[CONTEXT_QUERY_CATALOG_ARTIFACT_ID].read_text(encoding="utf-8")
    )
    modules = payload["query_execution"]["overview_graph"]["downstream_module_records"]
    if not modules:
        issues.append(
            _issue(
                severity="blocking",
                title="Whole-brain downstream-module review no longer packages any downstream modules",
                summary="The readiness fixture should package at least one simplified downstream module so the truthfulness and handoff semantics remain exercised.",
            )
        )
        return {
            "overall_status": "fail",
            "build_command": build_command,
            "metadata_path": str(metadata_path),
            "issues": issues,
        }

    module = modules[0]
    handoff_targets = {
        (
            str(item["linked_session_kind"]),
            str(item.get("source_preset_id")),
            str(item["target_preset_id"]),
        )
        for item in module["handoff_targets"]
    }
    expected_handoffs = {
        ("dashboard", "None", "dashboard_handoff"),
        ("showcase", "analysis_summary", "showcase_handoff"),
    }
    normalized_handoffs = {
        (
            session_kind,
            "None" if source_preset_id == "None" else source_preset_id,
            target_preset_id,
        )
        for session_kind, source_preset_id, target_preset_id in handoff_targets
    }
    module_verified = (
        str(module["downstream_module_role_id"]) == "simplified_readout_module"
        and bool(module["summary_labels"]["is_optional"])
        and bool(module["summary_labels"]["is_simplified"])
        and bool(module["summary_labels"]["is_context_oriented"])
        and bool(module["summary_labels"]["scientific_curation_required"])
        and str(module["lineage"]["source_query_profile_id"]) == "downstream_module_review"
        and expected_handoffs.issubset(normalized_handoffs)
    )
    if not module_verified:
        issues.append(
            _issue(
                severity="blocking",
                title="Whole-brain downstream-module package drifted from the declared M17 truthfulness or handoff semantics",
                summary="The readiness fixture should keep downstream modules labeled as optional simplified summaries and preserve dashboard/showcase handoff targets.",
            )
        )

    showcase_handoff_preset = next(
        item
        for item in catalog["available_query_presets"]
        if str(item["preset_id"]) == "showcase_handoff"
    )
    if list(showcase_handoff_preset["linked_session_target"]["source_preset_ids"]) != [
        "analysis_summary"
    ]:
        issues.append(
            _issue(
                severity="blocking",
                title="Showcase handoff preset lost its source-preset lineage",
                summary="The packaged `showcase_handoff` preset should stay traceable back to the showcase `analysis_summary` preset.",
            )
        )

    return {
        "overall_status": "pass" if not issues else "fail",
        "build_command": build_command,
        "metadata_path": str(metadata_path),
        "module_count": len(modules),
        "module_role_ids": [str(item["downstream_module_role_id"]) for item in modules],
        "handoff_target_pairs": sorted(normalized_handoffs),
        "active_preset_id": str(catalog["active_preset_id"]),
        "issues": issues,
    }


def _audit_documentation(*, repo_root: Path) -> dict[str, Any]:
    issues = []
    snippets_found: dict[str, dict[str, bool]] = {}
    for relative_path, snippets in DEFAULT_DOCUMENTATION_SNIPPETS.items():
        path = (repo_root / relative_path).resolve()
        text = path.read_text(encoding="utf-8")
        snippet_status = {snippet: snippet in text for snippet in snippets}
        snippets_found[relative_path] = snippet_status
        if not all(snippet_status.values()):
            missing = [snippet for snippet, found in snippet_status.items() if not found]
            issues.append(
                _issue(
                    severity="blocking",
                    title=f"Documentation missing Milestone 17 readiness snippets in {relative_path}",
                    summary=f"Expected snippets are missing from {relative_path}: {missing!r}.",
                )
            )
    follow_on_path = repo_root / "agent_tickets" / "milestone_17_follow_on_tickets.md"
    rationale_path = (
        repo_root / "docs" / "whole_brain_context_notes" / "FW-M17-008_rationale.md"
    )
    if not follow_on_path.exists():
        issues.append(
            _issue(
                severity="blocking",
                title="Milestone 17 follow-on ticket file is missing",
                summary="The readiness pass requires one explicit follow-on ticket file for the remaining Milestone 17 risks.",
            )
        )
    if not rationale_path.exists():
        issues.append(
            _issue(
                severity="blocking",
                title="Milestone 17 rationale note is missing",
                summary="FW-M17-008 requires a companion rationale note under docs/whole_brain_context_notes/.",
            )
        )
    return {
        "overall_status": "pass" if not issues else "fail",
        "snippets_found": snippets_found,
        "follow_on_ticket_path": str(follow_on_path.resolve()),
        "rationale_path": str(rationale_path.resolve()),
        "issues": issues,
    }


def _context_build_command(
    *,
    python_executable: str,
    fixture: Mapping[str, Any],
    showcase_metadata_path: Path,
    query_profile_id: str | None = None,
    selected_query_profile_ids: Sequence[str] | None = None,
    requested_downstream_module_role_ids: Sequence[str] | None = None,
) -> list[str]:
    command = [
        python_executable,
        "scripts/36_whole_brain_context_session.py",
        "build",
        "--config",
        str(Path(fixture["config_path"]).resolve()),
        "--showcase-session-metadata",
        str(showcase_metadata_path.resolve()),
        "--synapse-registry",
        str(Path(fixture["synapse_registry_path"]).resolve()),
    ]
    if query_profile_id is not None:
        command.extend(["--query-profile-id", query_profile_id])
    for profile_id in selected_query_profile_ids or ():
        command.extend(["--selected-query-profile-id", str(profile_id)])
    for role_id in requested_downstream_module_role_ids or ():
        command.extend(["--requested-downstream-module-role-id", str(role_id)])
    return command


def _verification_command_sequence(
    *,
    fixture: Mapping[str, Any],
    showcase_audit: Mapping[str, Any],
    context_review_audit: Mapping[str, Any],
    downstream_module_audit: Mapping[str, Any],
    dashboard_audit: Mapping[str, Any],
) -> list[str]:
    return [
        str(showcase_audit["build_command"]["command"]),
        str(context_review_audit["first_command"]["command"]),
        str(downstream_module_audit["build_command"]["command"]),
        str(dashboard_audit["build_command"]["command"]),
        (
            "python scripts/29_dashboard_shell.py open --dashboard-session-metadata "
            f"{dashboard_audit['metadata_path']} --no-browser"
        ),
    ]


def _issue(*, severity: str, title: str, summary: str) -> dict[str, str]:
    return {
        "severity": str(severity),
        "title": str(title),
        "summary": str(summary),
    }


def _run_json_command(
    *,
    command: Sequence[str],
    cwd: Path,
    command_path: Path,
) -> dict[str, Any]:
    result = subprocess.run(
        list(command),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    payload: dict[str, Any] = {
        "command": " ".join(str(item) for item in command),
        "cwd": str(cwd.resolve()),
        "returncode": int(result.returncode),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    parsed_summary = _parse_json_from_command_output(result.stdout)
    if parsed_summary is not None:
        payload["parsed_summary"] = parsed_summary
    command_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(payload, command_path)
    payload["command_path"] = str(command_path.resolve())
    return payload


def _parse_json_from_command_output(stdout: str) -> dict[str, Any] | None:
    stripped = stdout.strip()
    if not stripped:
        return None
    start = stripped.find("{")
    if start < 0:
        return None
    candidate = stripped[start:]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _extract_embedded_json(html_text: str, *, script_id: str) -> dict[str, Any]:
    match = re.search(
        rf'<script id="{re.escape(script_id)}" type="application/json">(.*?)</script>',
        html_text,
        re.DOTALL,
    )
    if match is None:
        raise ValueError(f"Could not find JSON script tag {script_id!r}.")
    return json.loads(html.unescape(match.group(1)))


def _render_milestone17_readiness_markdown(*, summary: Mapping[str, Any]) -> str:
    readiness = summary[FOLLOW_ON_READINESS_KEY]
    lines = [
        "# Milestone 17 Whole-Brain Context Readiness Report",
        "",
        f"- Report version: `{summary['report_version']}`",
        f"- Generated at: `{summary['generated_at_utc']}`",
        f"- Readiness status: `{readiness['status']}`",
        f"- Ready for follow-on work: `{readiness[READY_FOR_FOLLOW_ON_WORK_KEY]}`",
        f"- Ready for downstream work: `{', '.join(readiness.get('ready_for_milestones', []))}`",
        f"- Report directory: `{summary['report_dir']}`",
        "",
        "## Scope",
        "",
        str(summary["readiness_scope_note"]),
        "",
        "## Verification",
        "",
        f"- Documented verification command: `{summary['documented_verification_command']}`",
        f"- Explicit verification command: `{summary['explicit_verification_command']}`",
        "- End-to-end command sequence:",
    ]
    lines.extend(f"  - `{command}`" for command in summary["verification_command_sequence"])
    lines.extend(
        [
            "",
            "## Workflow Coverage",
            "",
        ]
    )
    for key, value in summary["workflow_coverage"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Verified Outputs",
            "",
            f"- Showcase session: `{summary['showcase_audit']['metadata_path']}`",
            f"- Whole-brain review context: `{summary['context_review_audit']['metadata_path']}`",
            f"- Whole-brain downstream-module review: `{summary['downstream_module_audit']['metadata_path']}`",
            f"- Dashboard bridge session: `{summary['dashboard_audit']['metadata_path']}`",
            f"- Markdown report: `{summary['markdown_path']}`",
            f"- JSON report: `{summary['json_path']}`",
            "",
            "## Remaining Risks",
            "",
        ]
    )
    for item in summary["remaining_risks"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Follow-On Tickets",
            "",
        ]
    )
    for ticket in summary["follow_on_tickets"]:
        lines.append(
            f"- `{ticket['ticket_id']}`: {ticket['title']} ({ticket['severity']})"
        )
        lines.append(f"  - {ticket['summary']}")
    return "\n".join(lines) + "\n"
