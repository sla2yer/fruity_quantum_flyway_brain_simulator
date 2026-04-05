#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flywire_wave.whole_brain_context_contract import (
    CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
    CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
    CONTEXT_VIEW_STATE_ARTIFACT_ID,
    discover_whole_brain_context_session_bundle_paths,
    load_whole_brain_context_session_metadata,
)
from flywire_wave.whole_brain_context_planning import (
    discover_whole_brain_context_query_presets,
    package_whole_brain_context_session,
    resolve_whole_brain_context_session_plan,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build or inspect the deterministic Milestone 17 whole-brain context "
            "package from packaged local artifacts."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser(
        "build",
        help=(
            "Resolve one whole-brain context session plan, package the local "
            "bundle, and print the packaged paths."
        ),
    )
    build.add_argument("--config", required=True, help="Path to the runtime config YAML.")
    build.add_argument("--manifest", help="Optional manifest path for manifest-driven planning.")
    build.add_argument("--schema", help="Manifest schema JSON path for manifest-driven planning.")
    build.add_argument(
        "--design-lock",
        help="Design-lock YAML path for manifest-driven planning.",
    )
    build.add_argument("--experiment-id", help="Optional experiment id override.")
    build.add_argument("--subset-name", help="Optional named subset for subset-driven planning.")
    build.add_argument(
        "--selection-preset",
        help="Optional selection preset id for subset-driven planning.",
    )
    build.add_argument(
        "--subset-manifest",
        help="Optional explicit subset_manifest.json path.",
    )
    build.add_argument(
        "--dashboard-session-metadata",
        help="Path to one packaged dashboard_session.json.",
    )
    build.add_argument(
        "--showcase-session-metadata",
        help="Path to one packaged showcase_session.json.",
    )
    build.add_argument(
        "--synapse-registry",
        help="Optional explicit local synapse registry CSV override.",
    )
    build.add_argument(
        "--query-profile-id",
        help="Optional active query profile id override.",
    )
    build.add_argument(
        "--selected-query-profile-id",
        action="append",
        default=[],
        help="Optional query profile id to keep available in the packaged plan. Repeatable.",
    )
    build.add_argument(
        "--fixture-mode",
        help="Optional whole-brain fixture mode override.",
    )
    build.add_argument(
        "--default-overlay-id",
        help="Optional default overlay id override.",
    )
    build.add_argument(
        "--reduction-profile-id",
        help="Optional default reduction profile id override.",
    )
    build.add_argument(
        "--enabled-overlay-id",
        action="append",
        default=[],
        help="Optional overlay id to enable in the packaged query state. Repeatable.",
    )
    build.add_argument(
        "--enabled-metadata-facet-id",
        action="append",
        default=[],
        help="Optional metadata facet id to enable in the packaged query state. Repeatable.",
    )
    build.add_argument(
        "--requested-downstream-module-role-id",
        action="append",
        default=[],
        help="Optional downstream-module role id request. Repeatable.",
    )

    inspect = subparsers.add_parser(
        "inspect",
        help="Load one packaged whole-brain context session and print a normalized summary.",
    )
    inspect.add_argument(
        "--whole-brain-context-metadata",
        required=True,
        help="Path to one packaged whole_brain_context_session.json.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "build":
        result = _build_context(args)
    else:
        result = _inspect_context(Path(args.whole_brain_context_metadata))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _build_context(args: argparse.Namespace) -> dict[str, object]:
    explicit_artifact_references = _explicit_artifact_references(args)
    plan_kwargs = {
        "config_path": Path(args.config),
        "manifest_path": None if args.manifest is None else Path(args.manifest),
        "schema_path": None if args.schema is None else Path(args.schema),
        "design_lock_path": None if args.design_lock is None else Path(args.design_lock),
        "experiment_id": args.experiment_id,
        "subset_name": args.subset_name,
        "selection_preset": args.selection_preset,
        "subset_manifest_path": (
            None if args.subset_manifest is None else Path(args.subset_manifest)
        ),
        "dashboard_session_metadata_path": (
            None
            if args.dashboard_session_metadata is None
            else Path(args.dashboard_session_metadata)
        ),
        "showcase_session_metadata_path": (
            None
            if args.showcase_session_metadata is None
            else Path(args.showcase_session_metadata)
        ),
        "explicit_artifact_references": explicit_artifact_references,
        "query_profile_id": args.query_profile_id,
        "query_profile_ids": args.selected_query_profile_id or None,
        "fixture_mode": args.fixture_mode,
        "default_overlay_id": args.default_overlay_id,
        "reduction_profile_id": args.reduction_profile_id,
        "enabled_overlay_ids": args.enabled_overlay_id or None,
        "enabled_metadata_facet_ids": args.enabled_metadata_facet_id or None,
        "requested_downstream_module_role_ids": (
            args.requested_downstream_module_role_id or None
        ),
    }
    plan = resolve_whole_brain_context_session_plan(
        **{key: value for key, value in plan_kwargs.items() if value is not None}
    )
    packaged = package_whole_brain_context_session(plan)
    catalog = json.loads(
        Path(packaged["context_query_catalog_path"]).read_text(encoding="utf-8")
    )
    payload = json.loads(
        Path(packaged["context_view_payload_path"]).read_text(encoding="utf-8")
    )
    return {
        **packaged,
        "source_mode": str(plan["source_mode"]),
        "fixture_mode": str(plan["fixture_mode"]),
        "active_query_profile_id": str(
            plan["query_profile_resolution"]["active_query_profile_id"]
        ),
        "active_preset_id": str(catalog["active_preset_id"]),
        "available_preset_ids": list(catalog["available_preset_ids"]),
        "overview_root_count": int(
            payload["query_execution"]["overview_graph"]["summary"]["distinct_root_count"]
        ),
        "focused_root_count": int(
            payload["query_execution"]["focused_subgraph"]["summary"]["distinct_root_count"]
        ),
    }


def _inspect_context(metadata_path: Path) -> dict[str, object]:
    metadata = load_whole_brain_context_session_metadata(metadata_path)
    bundle_paths = discover_whole_brain_context_session_bundle_paths(metadata)
    catalog_path = bundle_paths[CONTEXT_QUERY_CATALOG_ARTIFACT_ID]
    payload_path = bundle_paths[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID]
    state_path = bundle_paths[CONTEXT_VIEW_STATE_ARTIFACT_ID]
    catalog = (
        json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}
    )
    payload = (
        json.loads(payload_path.read_text(encoding="utf-8")) if payload_path.exists() else {}
    )
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    query_execution = payload.get("query_execution", {})
    return {
        "bundle_id": str(metadata["bundle_id"]),
        "contract_version": str(metadata["contract_version"]),
        "metadata_path": str(bundle_paths["metadata_json"].resolve()),
        "context_view_payload_path": str(payload_path.resolve()),
        "context_query_catalog_path": str(catalog_path.resolve()),
        "context_view_state_path": str(state_path.resolve()),
        "experiment_id": str(metadata["experiment_id"]),
        "query_profile_id": str(metadata["query_state"]["query_profile_id"]),
        "active_preset_id": catalog.get("active_preset_id"),
        "available_preset_ids": list(catalog.get("available_preset_ids", [])),
        "discovered_preset_ids": [
            str(item["preset_id"]) for item in discover_whole_brain_context_query_presets(catalog)
        ],
        "overview_root_count": (
            int(query_execution["overview_graph"]["summary"]["distinct_root_count"])
            if query_execution
            else 0
        ),
        "focused_root_count": (
            int(query_execution["focused_subgraph"]["summary"]["distinct_root_count"])
            if query_execution
            else 0
        ),
        "active_state_preset_id": state.get("active_preset_id"),
    }


def _explicit_artifact_references(args: argparse.Namespace) -> list[dict[str, str]] | None:
    refs: list[dict[str, str]] = []
    if args.synapse_registry is not None:
        path = Path(args.synapse_registry).resolve()
        refs.append(
            {
                "artifact_role_id": "synapse_registry",
                "path": str(path),
                "bundle_id": f"explicit:synapse_registry:{path.name}",
                "artifact_id": "synapse_registry",
            }
        )
    return refs or None


if __name__ == "__main__":
    raise SystemExit(main())
