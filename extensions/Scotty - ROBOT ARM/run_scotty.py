#!/usr/bin/env python3
"""Top-level launcher for the Scotty suite.

Run with the project venv:

    .venv/bin/python scotty.py
"""

from scotty.ui.main_window import run

if __name__ == "__main__":
    raise SystemExit(run())
