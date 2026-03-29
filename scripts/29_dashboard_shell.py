#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from collections.abc import Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flywire_wave.dashboard_session_contract import (
    APP_SHELL_INDEX_ARTIFACT_ID,
    discover_dashboard_session_bundle_paths,
    load_dashboard_session_metadata,
)
from flywire_wave.dashboard_exports import execute_dashboard_export
from flywire_wave.dashboard_session_planning import (
    package_dashboard_session,
    resolve_dashboard_session_plan,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "build":
        result = _build_dashboard(args)
    elif args.command == "export":
        result = _export_dashboard(args)
    else:
        result = _open_packaged_dashboard(
            Path(args.dashboard_session_metadata),
            open_browser=not args.no_browser,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build or open the deterministic Milestone 14 dashboard shell around "
            "packaged local session artifacts."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser(
        "build",
        help=(
            "Resolve a dashboard session from packaged local artifacts, write the "
            "deterministic app shell, and optionally open the result."
        ),
    )
    build.add_argument("--config", required=True, help="Path to the runtime config YAML.")
    build.add_argument("--manifest", help="Optional manifest path for manifest-driven planning.")
    build.add_argument("--schema", help="Manifest schema JSON path for manifest-driven planning.")
    build.add_argument(
        "--design-lock",
        help="Design-lock YAML path for manifest-driven planning.",
    )
    build.add_argument("--experiment-id", help="Experiment id for experiment-driven planning.")
    build.add_argument(
        "--baseline-bundle-metadata",
        help="Path to one baseline simulator_result_bundle.json.",
    )
    build.add_argument(
        "--wave-bundle-metadata",
        help="Path to one wave simulator_result_bundle.json.",
    )
    build.add_argument(
        "--analysis-bundle-metadata",
        help="Path to one experiment_analysis_bundle.json.",
    )
    build.add_argument(
        "--validation-bundle-metadata",
        help="Path to one validation_bundle.json.",
    )
    build.add_argument("--baseline-arm-id", help="Optional baseline arm id override.")
    build.add_argument("--wave-arm-id", help="Optional wave arm id override.")
    build.add_argument("--active-arm-id", help="Optional active arm id override.")
    build.add_argument("--preferred-seed", type=int, help="Optional shared seed override.")
    build.add_argument(
        "--preferred-condition-id",
        action="append",
        default=[],
        help="Optional preferred condition id. Repeat once per condition.",
    )
    build.add_argument("--selected-neuron-id", type=int, help="Optional selected neuron id.")
    build.add_argument("--selected-readout-id", help="Optional selected readout id.")
    build.add_argument("--active-overlay-id", help="Optional active overlay id.")
    build.add_argument("--comparison-mode", help="Optional comparison mode id.")
    build.add_argument(
        "--open",
        action="store_true",
        help="Open the generated app shell in the default browser after packaging.",
    )

    open_parser = subparsers.add_parser(
        "open",
        help="Open an already packaged dashboard session from local disk.",
    )
    open_parser.add_argument(
        "--dashboard-session-metadata",
        required=True,
        help="Path to dashboard_session.json.",
    )
    open_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Resolve the packaged app shell path without launching a browser.",
    )

    export_parser = subparsers.add_parser(
        "export",
        help="Write deterministic dashboard export artifacts from one packaged session.",
    )
    export_parser.add_argument(
        "--dashboard-session-metadata",
        required=True,
        help="Path to dashboard_session.json.",
    )
    export_parser.add_argument(
        "--export-target-id",
        required=True,
        help=(
            "Export target id, for example session_state_json, pane_snapshot_png, "
            "metrics_json, or replay_frame_sequence."
        ),
    )
    export_parser.add_argument(
        "--pane-id",
        help=(
            "Optional pane id override. Defaults depend on the target: analysis for "
            "snapshot/metrics, scene for replay frame sequence."
        ),
    )
    export_parser.add_argument("--sample-index", type=int, help="Optional replay sample index.")
    export_parser.add_argument("--selected-neuron-id", type=int, help="Optional selected neuron id override.")
    export_parser.add_argument("--selected-readout-id", help="Optional selected readout id override.")
    export_parser.add_argument("--active-overlay-id", help="Optional active overlay id override.")
    export_parser.add_argument("--comparison-mode", help="Optional comparison mode override.")
    export_parser.add_argument("--active-arm-id", help="Optional active arm id override.")
    return parser


def _build_dashboard(args: argparse.Namespace) -> dict[str, object]:
    preferred_condition_ids = args.preferred_condition_id or None
    plan_kwargs = {
        "config_path": Path(args.config),
        "manifest_path": None if args.manifest is None else Path(args.manifest),
        "schema_path": None if args.schema is None else Path(args.schema),
        "design_lock_path": None if args.design_lock is None else Path(args.design_lock),
        "experiment_id": args.experiment_id,
        "baseline_bundle_metadata_path": (
            None
            if args.baseline_bundle_metadata is None
            else Path(args.baseline_bundle_metadata)
        ),
        "wave_bundle_metadata_path": (
            None if args.wave_bundle_metadata is None else Path(args.wave_bundle_metadata)
        ),
        "analysis_bundle_metadata_path": (
            None
            if args.analysis_bundle_metadata is None
            else Path(args.analysis_bundle_metadata)
        ),
        "validation_bundle_metadata_path": (
            None
            if args.validation_bundle_metadata is None
            else Path(args.validation_bundle_metadata)
        ),
        "baseline_arm_id": args.baseline_arm_id,
        "wave_arm_id": args.wave_arm_id,
        "active_arm_id": args.active_arm_id,
        "preferred_seed": args.preferred_seed,
        "preferred_condition_ids": preferred_condition_ids,
        "selected_neuron_id": args.selected_neuron_id,
        "selected_readout_id": args.selected_readout_id,
        "active_overlay_id": args.active_overlay_id,
        "comparison_mode": args.comparison_mode,
    }
    plan = resolve_dashboard_session_plan(
        **{key: value for key, value in plan_kwargs.items() if value is not None}
    )
    packaged = package_dashboard_session(plan)
    if args.open:
        packaged["browser_opened"] = bool(webbrowser.open(packaged["app_shell_file_url"], new=2))
    else:
        packaged["browser_opened"] = False
    return packaged


def _open_packaged_dashboard(
    metadata_path: Path,
    *,
    open_browser: bool = True,
) -> dict[str, object]:
    metadata = load_dashboard_session_metadata(metadata_path)
    bundle_paths = discover_dashboard_session_bundle_paths(metadata)
    app_shell_path = bundle_paths[APP_SHELL_INDEX_ARTIFACT_ID].resolve()
    file_url = app_shell_path.as_uri()
    return {
        "metadata_path": str(metadata_path.resolve()),
        "app_shell_path": str(app_shell_path),
        "app_shell_file_url": file_url,
        "browser_opened": bool(webbrowser.open(file_url, new=2)) if open_browser else False,
    }


def _export_dashboard(args: argparse.Namespace) -> dict[str, object]:
    export_kwargs = {
        "dashboard_session_metadata_path": Path(args.dashboard_session_metadata),
        "export_target_id": args.export_target_id,
        "pane_id": args.pane_id,
        "sample_index": args.sample_index,
        "selected_neuron_id": args.selected_neuron_id,
        "selected_readout_id": args.selected_readout_id,
        "active_overlay_id": args.active_overlay_id,
        "comparison_mode": args.comparison_mode,
        "active_arm_id": args.active_arm_id,
    }
    return execute_dashboard_export(
        **{key: value for key, value in export_kwargs.items() if value is not None}
    )


if __name__ == "__main__":
    raise SystemExit(main())
