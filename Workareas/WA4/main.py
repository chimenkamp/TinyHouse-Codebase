"""Configure and start the WA4 evidence service from the repository root."""

from pathlib import Path

from Workareas.shared.configuration import StationConfig
from Workareas.shared.server import run

STATION: str = "WA4"
PORT: int = 8414
LOCAL_DIRECTORY: Path = Path(__file__).resolve().parent / "local"
SOURCE_IDS: dict[str, str] = {
    "camera": "wa4-camera",
    "commitment": "wa4-commitment",
    "delivery": "wa4-delivery",
    "disclosure": "wa4-disclosure",
    "energy": "wa4-energy",
    "identity": "wa4-identity",
    "inspection": "wa4-inspection",
    "operator": "wa4-operator",
    "registration": "wa4-registration",
    "request": "wa4-request",
    "scale": "wa4-scale",
    "schedule": "wa4-schedule",
    "topology": "wa4-topology",
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
