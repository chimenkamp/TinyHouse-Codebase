"""Configure and start the WA1 evidence service from the repository root."""

from pathlib import Path

from Workareas.shared.configuration import StationConfig
from Workareas.shared.server import run

STATION: str = "WA1"
PORT: int = 8411
LOCAL_DIRECTORY: Path = Path(__file__).resolve().parent / "local"
SOURCE_IDS: dict[str, str] = {
    "authorization": "wa1-authorization",
    "camera": "wa1-camera",
    "inspection": "wa1-inspection",
    "meter": "wa1-meter",
    "operator": "wa1-operator",
    "printer": "wa1-printer",
    "schedule": "wa1-schedule",
    "thermal": "wa1-thermal",
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
