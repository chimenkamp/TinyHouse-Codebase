from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, load_runtime_config
from .shell import NativeTerminalError, ShellTargetError, run_native_terminal_session


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open a TinyHouse native terminal session.")
    parser.add_argument(
        "--mode",
        choices=["local", "tunnel"],
        required=True,
        help="Dashboard connection mode.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the dashboard config file.",
    )
    parser.add_argument(
        "--target",
        default="",
        help="Optional configured target identifier.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_runtime_config(Path(args.config).resolve())

    try:
        run_native_terminal_session(
            config,
            args.mode,
            target_id=args.target.strip() or None,
        )
    except (NativeTerminalError, ShellTargetError) as error:
        print(f"Native terminal failed: {error}", file=sys.stderr)
        input("Press Enter to close this terminal...")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
