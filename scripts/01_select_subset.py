#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.config import get_config_path, load_config
from flywire_wave.selection import generate_subsets_from_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate reproducible FlyWire subset selections from config presets.")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML config file. Relative paths inside config.paths resolve from the repository root.",
    )
    parser.add_argument("--preset", help="Generate only this named preset.")
    parser.add_argument(
        "--all-presets",
        action="store_true",
        help="Generate every preset defined under selection.presets.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    summary = generate_subsets_from_config(
        cfg,
        config_path=get_config_path(cfg),
        preset_name=args.preset,
        generate_all=args.all_presets,
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
