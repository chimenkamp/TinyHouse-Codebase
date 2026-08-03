"""
CLI entry point for parol6-server command.

This module provides the command-line interface for starting the PAROL6 headless controller.
"""

from parol6.utils.env_loader import load_env_files

# Load .env files BEFORE importing parol6.config (which reads env vars at import time).
load_env_files()

from parol6.server.cli import main  # noqa: E402


def main_entry():
    """Entry point for the parol6-server command."""
    return main()


if __name__ == "__main__":
    main_entry()
