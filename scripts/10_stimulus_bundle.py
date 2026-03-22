#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.stimulus_bundle import (
    record_stimulus_bundle,
    replay_stimulus_bundle,
    resolve_stimulus_input,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Record canonical stimulus bundles with deterministic local paths and replay them offline."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser(
        "record",
        help="Resolve a canonical stimulus from config or manifest input and write a reusable local bundle.",
    )
    _add_source_arguments(record_parser, require_source=True, allow_bundle_metadata=False)
    record_parser.add_argument(
        "--preview-frame-index",
        action="append",
        type=int,
        default=[],
        help="Optional explicit preview frame index. Repeat to choose multiple frames.",
    )

    replay_parser = subparsers.add_parser(
        "replay",
        help="Replay an existing recorded stimulus bundle offline using the cached frame archive when available.",
    )
    _add_source_arguments(replay_parser, require_source=False, allow_bundle_metadata=True)
    replay_parser.add_argument(
        "--time-ms",
        action="append",
        type=float,
        default=[],
        help="Optional time sample to resolve through the sample-hold replay rule. Repeat to inspect multiple times.",
    )

    args = parser.parse_args()
    _validate_source_args(parser, args)
    if args.command == "record":
        resolved_input = resolve_stimulus_input(
            config_path=args.config,
            manifest_path=args.manifest,
            schema_path=args.schema,
            design_lock_path=args.design_lock,
            processed_stimulus_dir=args.processed_stimulus_dir,
        )
        summary = record_stimulus_bundle(
            resolved_input,
            preview_frame_indices=args.preview_frame_index or None,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    resolved_input = None
    if args.bundle_metadata is None:
        resolved_input = resolve_stimulus_input(
            config_path=args.config,
            manifest_path=args.manifest,
            schema_path=args.schema,
            design_lock_path=args.design_lock,
            processed_stimulus_dir=args.processed_stimulus_dir,
        )
    summary = replay_stimulus_bundle(
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
        help="Path to a YAML config that resolves one canonical stimulus.",
    )
    parser.add_argument(
        "--manifest",
        help="Path to an experiment manifest that resolves one canonical stimulus.",
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
    if allow_bundle_metadata:
        parser.add_argument(
            "--bundle-metadata",
            help="Replay directly from an existing stimulus_bundle.json path.",
        )


def _validate_source_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    source_count = int(args.config is not None) + int(args.manifest is not None)
    if getattr(args, "bundle_metadata", None) is not None:
        source_count += 1

    if args.command == "record" and source_count != 1:
        parser.error("record requires exactly one of --config or --manifest.")
    if args.command == "replay" and source_count != 1:
        parser.error("replay requires exactly one of --config, --manifest, or --bundle-metadata.")


if __name__ == "__main__":
    raise SystemExit(main())
