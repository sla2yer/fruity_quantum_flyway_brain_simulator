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
from flywire_wave.showcase_player import (
    SUPPORTED_SHOWCASE_PLAYER_MODES,
    execute_showcase_player_command,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build and drive the deterministic Milestone 16 showcase player "
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

    status = subparsers.add_parser(
        "status",
        help="Load one packaged showcase session and print the normalized player state summary.",
    )
    _add_player_session_args(status, include_state_output=True)

    play = subparsers.add_parser(
        "play",
        help="Advance the scripted showcase in guided autoplay or rehearsal mode.",
    )
    _add_player_session_args(play, include_state_output=True, include_mode=True)
    play.add_argument(
        "--advance-steps",
        type=int,
        help="Optional number of deterministic step transitions to apply.",
    )
    play.add_argument(
        "--until-end",
        action="store_true",
        help="Advance deterministically to the last story beat.",
    )

    pause = subparsers.add_parser(
        "pause",
        help="Pause the current showcase state without changing the active beat.",
    )
    _add_player_session_args(pause, include_state_output=True)

    resume = subparsers.add_parser(
        "resume",
        help="Resume the current showcase state from the serialized checkpoint.",
    )
    _add_player_session_args(resume, include_state_output=True, include_mode=True)
    resume.add_argument(
        "--advance-steps",
        type=int,
        help="Optional number of deterministic step transitions to apply after resuming.",
    )
    resume.add_argument(
        "--until-end",
        action="store_true",
        help="Advance deterministically to the last story beat after resuming.",
    )

    seek = subparsers.add_parser(
        "seek",
        help="Scrub the replay cursor on the current showcase beat.",
    )
    _add_player_session_args(seek, include_state_output=True)
    seek.add_argument(
        "--sample-index",
        type=int,
        required=True,
        help="Replay sample index on the packaged shared timebase.",
    )

    next_step = subparsers.add_parser(
        "next-step",
        help="Jump to the next deterministic showcase beat.",
    )
    _add_player_session_args(next_step, include_state_output=True)

    previous_step = subparsers.add_parser(
        "previous-step",
        help="Jump to the previous deterministic showcase beat.",
    )
    _add_player_session_args(previous_step, include_state_output=True)

    jump_step = subparsers.add_parser(
        "jump-step",
        help="Jump directly to one named showcase beat.",
    )
    _add_player_session_args(jump_step, include_state_output=True)
    jump_step.add_argument(
        "--step-id",
        required=True,
        help="Showcase step id, for example scene_selection or activity_propagation.",
    )

    jump_preset = subparsers.add_parser(
        "jump-preset",
        help="Jump directly to one named showcase preset.",
    )
    _add_player_session_args(jump_preset, include_state_output=True)
    jump_preset.add_argument(
        "--preset-id",
        required=True,
        help="Saved preset id, for example paired_comparison or analysis_summary.",
    )

    reset = subparsers.add_parser(
        "reset",
        help="Reset the showcase state back to the opening beat or a requested checkpoint.",
    )
    _add_player_session_args(reset, include_state_output=True, include_mode=True)
    reset.add_argument("--step-id", help="Optional reset step id override.")
    reset.add_argument("--preset-id", help="Optional reset preset id override.")
    return parser


def _add_player_session_args(
    parser: argparse.ArgumentParser,
    *,
    include_state_output: bool,
    include_mode: bool = False,
) -> None:
    parser.add_argument(
        "--showcase-session-metadata",
        required=True,
        help="Path to one packaged showcase_session.json.",
    )
    parser.add_argument(
        "--state",
        help=(
            "Optional path to one serialized showcase state file. Defaults to the "
            "packaged showcase_state.json."
        ),
    )
    if include_state_output:
        parser.add_argument(
            "--state-output",
            help=(
                "Optional output path for the updated serialized showcase state. "
                "Defaults to --state when provided, otherwise the packaged "
                "showcase_state.json."
            ),
        )
    if include_mode:
        parser.add_argument(
            "--mode",
            choices=SUPPORTED_SHOWCASE_PLAYER_MODES,
            help=(
                "Optional runtime mode override. guided_autoplay enables deterministic "
                "auto-advance; presenter_rehearsal preserves manual beat control."
            ),
        )


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


def _drive_showcase(args: argparse.Namespace) -> dict[str, object]:
    command = args.command.replace("-", "_")
    return execute_showcase_player_command(
        showcase_session_metadata_path=Path(args.showcase_session_metadata),
        command=command,
        serialized_state_path=(
            None if args.state is None else Path(args.state)
        ),
        state_output_path=(
            None if getattr(args, "state_output", None) is None else Path(args.state_output)
        ),
        runtime_mode=getattr(args, "mode", None),
        step_id=getattr(args, "step_id", None),
        preset_id=getattr(args, "preset_id", None),
        replay_sample_index=getattr(args, "sample_index", None),
        advance_steps=getattr(args, "advance_steps", None),
        until_end=bool(getattr(args, "until_end", False)),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "build":
        result = _build_showcase(args)
    else:
        result = _drive_showcase(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
