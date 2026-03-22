#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.retinal_workflow import (
    inspect_retinal_bundle_workflow,
    record_resolved_retinal_bundle,
    replay_retinal_bundle_workflow,
    resolve_retinal_bundle_input,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Record deterministic retinal input bundles from canonical stimulus bundles "
            "or scene descriptions, and replay the cached retinal assets offline."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser(
        "record",
        help="Resolve one canonical visual source and write a reusable retinal bundle.",
    )
    _add_source_arguments(record_parser, require_source=True, allow_bundle_metadata=False)

    replay_parser = subparsers.add_parser(
        "replay",
        help="Replay an existing retinal bundle or resolve its canonical path from source inputs.",
    )
    _add_source_arguments(replay_parser, require_source=False, allow_bundle_metadata=True)
    replay_parser.add_argument(
        "--time-ms",
        action="append",
        type=float,
        default=[],
        help="Optional replay time sample. Repeat to inspect multiple times.",
    )

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Generate a static offline world-view versus fly-view retinal inspection report.",
    )
    _add_source_arguments(inspect_parser, require_source=False, allow_bundle_metadata=True)

    args = parser.parse_args()
    _validate_source_args(parser, args)
    if args.command == "record":
        resolved_input = resolve_retinal_bundle_input(
            config_path=args.config,
            manifest_path=args.manifest,
            scene_path=args.scene,
            retinal_config_path=args.retinal_config,
            schema_path=args.schema,
            design_lock_path=args.design_lock,
            processed_stimulus_dir=args.processed_stimulus_dir,
            processed_retinal_dir=args.processed_retinal_dir,
        )
        summary = record_resolved_retinal_bundle(resolved_input)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.command == "inspect":
        resolved_input = None
        if args.bundle_metadata is None:
            resolved_input = resolve_retinal_bundle_input(
                config_path=args.config,
                manifest_path=args.manifest,
                scene_path=args.scene,
                retinal_config_path=args.retinal_config,
                schema_path=args.schema,
                design_lock_path=args.design_lock,
                processed_stimulus_dir=args.processed_stimulus_dir,
                processed_retinal_dir=args.processed_retinal_dir,
            )
        summary = inspect_retinal_bundle_workflow(
            bundle_metadata_path=args.bundle_metadata,
            resolved_input=resolved_input,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    resolved_input = None
    if args.bundle_metadata is None:
        resolved_input = resolve_retinal_bundle_input(
            config_path=args.config,
            manifest_path=args.manifest,
            scene_path=args.scene,
            retinal_config_path=args.retinal_config,
            schema_path=args.schema,
            design_lock_path=args.design_lock,
            processed_stimulus_dir=args.processed_stimulus_dir,
            processed_retinal_dir=args.processed_retinal_dir,
        )
    summary = replay_retinal_bundle_workflow(
        bundle_metadata_path=args.bundle_metadata,
        resolved_input=resolved_input,
        time_ms=args.time_ms,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _add_source_arguments(
    parser: argparse.ArgumentParser,
    *,
    require_source: bool,
    allow_bundle_metadata: bool,
) -> None:
    parser.add_argument(
        "--config",
        help="Path to a YAML config that resolves a canonical stimulus plus retinal geometry.",
    )
    parser.add_argument(
        "--manifest",
        help="Path to an experiment manifest that resolves a canonical stimulus.",
    )
    parser.add_argument(
        "--scene",
        help="Path to a local scene entrypoint YAML that defines scene plus retinal geometry.",
    )
    parser.add_argument(
        "--retinal-config",
        help="Path to a retinal config used with --manifest when the manifest omits retinal geometry.",
    )
    parser.add_argument(
        "--schema",
        default=str(ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"),
        help="Schema used when --manifest is provided.",
    )
    parser.add_argument(
        "--design-lock",
        default=str(ROOT / "config" / "milestone_1_design_lock.yaml"),
        help="Design lock used when --manifest is provided.",
    )
    parser.add_argument(
        "--processed-stimulus-dir",
        help="Optional override for the processed stimulus root directory.",
    )
    parser.add_argument(
        "--processed-retinal-dir",
        help="Optional override for the processed retinal root directory.",
    )
    if allow_bundle_metadata:
        parser.add_argument(
            "--bundle-metadata",
            help="Replay directly from an existing retinal_input_bundle.json path.",
        )


def _validate_source_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    source_count = (
        int(args.config is not None)
        + int(args.manifest is not None)
        + int(args.scene is not None)
    )
    if getattr(args, "bundle_metadata", None) is not None:
        source_count += 1

    if args.command == "record" and source_count != 1:
        parser.error("record requires exactly one of --config, --manifest, or --scene.")
    if args.command in {"replay", "inspect"} and source_count != 1:
        parser.error(
            f"{args.command} requires exactly one of --config, --manifest, --scene, or --bundle-metadata."
        )
    if args.manifest is not None and args.retinal_config is None and getattr(args, "bundle_metadata", None) is None:
        parser.error("--manifest requires --retinal-config for retinal geometry and sampling options.")
    if args.retinal_config is not None and args.manifest is None:
        parser.error("--retinal-config is only valid with --manifest.")


if __name__ == "__main__":
    raise SystemExit(main())
