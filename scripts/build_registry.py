#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.config import load_config
from flywire_wave.registry import build_registry


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build canonical FlyWire neuron/connectivity registries and the local synapse registry when configured."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML config file. Relative paths inside config.paths resolve from the repository root.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    summary = build_registry(cfg)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
