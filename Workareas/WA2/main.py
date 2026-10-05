"""Configure and start the WA2 evidence service from the repository root."""

from pathlib import Path

from Workareas.shared.configuration import StationConfig
from Workareas.shared.server import run

STATION: str = "WA2"
PORT: int = 8412
LOCAL_DIRECTORY: Path = Path(__file__).resolve().parent / "local"
SOURCE_IDS: dict[str, str] = {
    "bins": "wa2-bins",
    "camera": "wa2-camera",
    "controller": "wa2-controller",
    "kit_plan": "wa2-kit_plan",
    "safety": "wa2-safety",
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
