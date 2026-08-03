"""Scotty — full robot-arm suite (camera + calibration + vision + grasp)."""

import os
from pathlib import Path

# Keep native math runtimes conservative before Qt, OpenCV, or Torch load.
# Mixed OpenMP thread pools can hard-crash the process on macOS.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

PACKAGE_ROOT: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = PACKAGE_ROOT.parent
DATA_DIR: Path = PACKAGE_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


def load_env() -> None:
    """Load repo-local secrets such as ROBOFLOW_API_KEY from .env."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for path in (REPO_ROOT / ".env", Path.home() / ".parol6" / ".env"):
        if path.is_file():
            load_dotenv(dotenv_path=path, override=False)


load_env()
