"""Configure and start the Nano acquisition application from repository root."""

from __future__ import annotations

import os

from Workareas.shared.serial_capture import SerialCaptureConfig, run_capture


def main() -> None:
    """Construct explicit device configuration and start JSONL capture.

    :return: None.
    """
    config: SerialCaptureConfig = SerialCaptureConfig(
        port=os.environ["WORKAREA_SERIAL_PORT"],
        workstation=os.environ["WORKAREA_ID"],
        source_id=os.environ["WORKAREA_SOURCE_ID"],
    )
    run_capture(config)


if __name__ == "__main__":
    main()
