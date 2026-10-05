"""Configure and start the WA3 evidence service from the repository root."""

from pathlib import Path

from Workareas.shared.configuration import StationConfig
from Workareas.shared.server import run

STATION: str = "WA3"
PORT: int = 8413
LOCAL_DIRECTORY: Path = Path(__file__).resolve().parent / "local"
SOURCE_IDS: dict[str, str] = {
    "assembly": "wa3-assembly",
    "calibration": "wa3-calibration",
    "camera": "wa3-camera",
    "identity": "wa3-identity",
    "operator": "wa3-operator",
    "scale": "wa3-scale",
    "test": "wa3-test",
}


def main() -> None:
    """
    Construct explicit settings and start this work area's evidence service.

    :return: None.
    """
    config: StationConfig = StationConfig(
        station=STATION,
        database=LOCAL_DIRECTORY / "events.sqlite3",
        token_file=LOCAL_DIRECTORY / "api.token",
        port=PORT,
        sources=SOURCE_IDS,
    )
    run(config)


if __name__ == "__main__":
    main()
