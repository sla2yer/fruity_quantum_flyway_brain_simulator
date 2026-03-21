#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import re
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT / ".env"
DEFAULT_AUTH_SERVER = "https://global.daf-apis.com"
EXISTING_TOKEN_PATH = "/auth/api/v1/user/token"
NEW_TOKEN_PATH = "/auth/api/v1/create_token"
VERIFY_COMMAND = "python scripts/00_verify_access.py --config config/local.yaml"
TOKEN_PATTERN = re.compile(r"^\s*(?:export\s+)?FLYWIRE_TOKEN\s*=.*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open the FlyWire/CAVE browser flow for retrieving a local API token."
    )
    parser.add_argument(
        "--new-token",
        action="store_true",
        help=(
            "Open the create-token page instead of the existing-token list. "
            "Creating a new token may invalidate the previous token."
        ),
    )
    parser.add_argument(
        "--write-env",
        action="store_true",
        help="Prompt for the token after launch and write/update FLYWIRE_TOKEN in .env.",
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help="Path to the .env file used with --write-env. Default: repo_root/.env",
    )
    return parser.parse_args()


def build_auth_url(make_new: bool) -> str:
    path = NEW_TOKEN_PATH if make_new else EXISTING_TOKEN_PATH
    return f"{DEFAULT_AUTH_SERVER}{path}"


def display_path(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(ROOT)
    except ValueError:
        return str(path)
    return "." if not relative.parts else str(Path(".") / relative)


def upsert_env_token(env_file: Path, token: str) -> None:
    new_line = f"FLYWIRE_TOKEN={token}"

    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    updated = False
    result: list[str] = []

    for line in lines:
        if TOKEN_PATTERN.match(line):
            if not updated:
                result.append(new_line)
                updated = True
            continue
        result.append(line)

    if not updated:
        if result and result[-1] != "":
            result.append("")
        result.append(new_line)

    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text("\n".join(result).rstrip() + "\n", encoding="utf-8")


def prompt_for_token(env_file: Path) -> bool:
    print()
    print(f"When you have copied the token, return here to update {display_path(env_file)}.")
    try:
        token = getpass.getpass(
            "Paste your FlyWire/CAVE API token (input hidden, blank to skip): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        print("Skipped .env update.")
        return False

    if not token:
        print("Skipped .env update.")
        return False

    upsert_env_token(env_file, token)
    print(f"Saved FLYWIRE_TOKEN to {display_path(env_file)}.")
    return True


def main() -> int:
    args = parse_args()
    env_file = Path(args.env_file).expanduser()
    auth_url = build_auth_url(make_new=args.new_token)

    print("FlyWire token setup helper")
    print()
    print("This project uses FlyWire Codex for browser/UI downloads and CAVE/fafbseg for")
    print("programmatic access from local Python scripts.")
    print("Your FlyWire Codex browser login does not automatically populate the API token")
    print("expected by local tooling.")
    print()
    print(
        "Opening the CAVE/FlyWire API token flow to "
        + ("create a new token." if args.new_token else "retrieve an existing token.")
    )
    print(f"URL: {auth_url}")
    if args.new_token:
        print("Warning: creating a new token may invalidate the previous token.")

    print()
    opened = False
    try:
        opened = webbrowser.open(auth_url, new=2)
    except Exception as exc:
        print(f"Browser launch failed: {exc}")

    if opened:
        print("Browser launch requested.")
    else:
        print("Browser did not open automatically. Copy the URL above into your browser.")

    print()
    print("Next steps:")
    print("1. This opens the CAVE/FlyWire API token flow.")
    print("2. This is separate from your FlyWire Codex website login.")
    print("3. Copy the token from the browser page.")
    if args.write_env:
        print(f"4. Return here so this helper can save it into {display_path(env_file)}.")
    else:
        print(f"4. Paste it into {display_path(env_file)} as FLYWIRE_TOKEN=...")
        print("   Optional: rerun this helper with --write-env to update .env interactively.")
    print("5. Optional: after install, use caveclient.auth.save_token(...) for machine-wide")
    print("   CAVE/fafbseg secret storage.")
    print(f"6. Then rerun {VERIFY_COMMAND}")

    if args.write_env:
        wrote_env = prompt_for_token(env_file)
        if wrote_env:
            print(f"Then rerun {VERIFY_COMMAND}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
