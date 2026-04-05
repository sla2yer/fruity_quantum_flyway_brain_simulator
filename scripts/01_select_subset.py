#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _startup import bootstrap_runtime

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def _bootstrap_dependencies():
    import flywire_wave.config as config_module
    import flywire_wave.selection as selection_module

    return config_module, selection_module


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

    dependencies = bootstrap_runtime("select", _bootstrap_dependencies)
    if dependencies is None:
        return 1
    config_module, selection_module = dependencies

    cfg = config_module.load_config(args.config)
    summary = selection_module.generate_subsets_from_config(
        cfg,
        config_path=config_module.get_config_path(cfg),
        preset_name=args.preset,
        generate_all=args.all_presets,
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
