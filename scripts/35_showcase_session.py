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

from flywire_wave.showcase_session_planning import (
    DEFAULT_SHOWCASE_DISPLAY_NAME,
    DEFAULT_SHOWCASE_ID,
    SHOWCASE_FIXTURE_MODE_REHEARSAL,
    package_showcase_session,
    resolve_showcase_session_plan,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve and package one deterministic Milestone 16 showcase session "
            "from packaged local artifacts."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser(
        "build",
        help=(
            "Resolve one showcase session plan, package the rehearsal bundle, "
            "and print the packaged paths."
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
        "--dashboard-session-metadata",
        help="Path to one packaged dashboard_session.json.",
    )
    build.add_argument(
        "--suite-package-metadata",
        help="Path to one packaged experiment_suite_package.json.",
    )
    build.add_argument(
        "--suite-review-summary",
        help="Optional path to one suite-review summary JSON.",
    )
    build.add_argument(
        "--table-dimension-id",
        action="append",
        default=[],
        help="Optional suite table-dimension id. Repeat once per dimension.",
    )
    build.add_argument(
        "--fixture-mode",
        default=SHOWCASE_FIXTURE_MODE_REHEARSAL,
        help="Showcase fixture mode. Defaults to the Milestone 16 rehearsal profile.",
    )
    build.add_argument(
        "--showcase-id",
        default=DEFAULT_SHOWCASE_ID,
        help="Optional showcase id override.",
    )
    build.add_argument(
        "--display-name",
        default=DEFAULT_SHOWCASE_DISPLAY_NAME,
        help="Optional showcase display name override.",
    )
    build.add_argument(
        "--highlight-phenomenon-id",
        help="Optional explicit highlight phenomenon id.",
    )
    build.add_argument(
        "--highlight-artifact-role-id",
        help="Optional artifact role id for the explicit highlight.",
    )
    build.add_argument(
        "--highlight-locator",
        help="Optional locator for the explicit highlight.",
    )
    build.add_argument(
        "--highlight-citation-label",
        help="Optional citation label for the explicit highlight.",
    )
    return parser


def _highlight_override_from_args(args: argparse.Namespace) -> dict[str, object] | None:
    if args.highlight_phenomenon_id is None:
        return None
    payload: dict[str, object] = {
        "phenomenon_id": args.highlight_phenomenon_id,
    }
    if args.highlight_artifact_role_id is not None:
        payload["artifact_role_id"] = args.highlight_artifact_role_id
    if args.highlight_locator is not None:
        payload["locator"] = args.highlight_locator
    if args.highlight_citation_label is not None:
        payload["citation_label"] = args.highlight_citation_label
    return payload


def _build_showcase(args: argparse.Namespace) -> dict[str, object]:
    plan = resolve_showcase_session_plan(
        config_path=Path(args.config),
        manifest_path=None if args.manifest is None else Path(args.manifest),
        schema_path=None if args.schema is None else Path(args.schema),
        design_lock_path=None if args.design_lock is None else Path(args.design_lock),
        experiment_id=args.experiment_id,
        dashboard_session_metadata_path=(
            None
            if args.dashboard_session_metadata is None
            else Path(args.dashboard_session_metadata)
        ),
        suite_package_metadata_path=(
            None
            if args.suite_package_metadata is None
            else Path(args.suite_package_metadata)
        ),
        suite_review_summary_path=(
            None if args.suite_review_summary is None else Path(args.suite_review_summary)
        ),
        fixture_mode=args.fixture_mode,
        showcase_id=args.showcase_id,
        display_name=args.display_name,
        table_dimension_ids=args.table_dimension_id or None,
        highlight_override=_highlight_override_from_args(args),
    )
    packaged = package_showcase_session(plan)
    packaged["fixture_mode"] = str(plan["fixture_mode"])
    packaged["story_arc_preset_ids"] = dict(
        plan["narrative_preset_catalog"]["story_arc_preset_ids"]
    )
    packaged["highlight_metadata"] = dict(plan["highlight_selection"])
    return packaged


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "build":
        result = _build_showcase(args)
    else:
        raise ValueError(f"Unsupported showcase_session command {args.command!r}.")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
