"""Load environment variables from .env files.

Resolution order (later files override earlier ones, but existing OS env vars
always win — `override=False`):

  1. .env in the current working directory
  2. .env in the nearest parent directory containing pyproject.toml (project root)
  3. ~/.parol6/.env (user-level overrides)

Existing OS environment variables are never overwritten, so explicit shell
exports always take precedence over .env files.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _find_project_root(start: Path) -> Path | None:
    for parent in [start, *start.parents]:
        if (parent / "pyproject.toml").is_file():
            return parent
    return None


def load_env_files() -> None:
    """Load .env files from CWD, project root, and user config dir.

    Silently no-ops if python-dotenv is not installed.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.debug("python-dotenv not installed; skipping .env loading")
        return

    cwd = Path.cwd()
    candidates: list[Path] = []

    cwd_env = cwd / ".env"
    if cwd_env.is_file():
        candidates.append(cwd_env)

    root = _find_project_root(cwd)
    if root is not None:
        root_env = root / ".env"
        if root_env.is_file() and root_env != cwd_env:
            candidates.append(root_env)

    user_env = Path.home() / ".parol6" / ".env"
    if user_env.is_file() and user_env not in candidates:
        candidates.append(user_env)

    for path in candidates:
        load_dotenv(dotenv_path=path, override=False)
        logger.info(f"Loaded environment from {path}")


def loaded_env_summary() -> list[str]:
    """Return list of .env file paths that exist (for debugging/CLI display)."""
    cwd = Path.cwd()
    paths: list[Path] = []
    for p in (cwd / ".env", Path.home() / ".parol6" / ".env"):
        if p.is_file() and p not in paths:
            paths.append(p)
    root = _find_project_root(cwd)
    if root is not None:
        rp = root / ".env"
        if rp.is_file() and rp not in paths:
            paths.append(rp)
    return [str(p) for p in paths]
