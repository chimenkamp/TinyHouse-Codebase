from abc import ABC, abstractmethod

from typing_extensions import Optional


class SensorAdapter(ABC):
    @abstractmethod
    def parse(self, raw_line: str) -> Optional[dict]:

        pass

    @property
    @abstractmethod
    def sensor_type(self) -> str:
        pass


class PressureAdapter(SensorAdapter):
    """
    Adapter for Joy-IT SEN-Pressure02 Pressuresensor.

    Expects line: <SENSOR_ID>,<VOUT>,<RC>
    example: P1,2.341,15.234
    sensor_id: set in main
    line_prefix: set in main too, derived from sensor ID
    """

    def __init__(self, sensor_id: str, line_prefix: str):
        self.sensor_id = sensor_id
        self.line_prefix = line_prefix

    @property
    def sensor_type(self) -> str:
        return "pressure"

    def parse(self, raw_line: str) -> Optional[dict]:
        """parse raw line and split, fill reading dict with needed information"""

        parts = raw_line.strip().split(",")
        if len(parts) != 3:
            return None

        prefix = parts[0].strip()
        if prefix != self.line_prefix:
            return None

        try:
            vout = float(parts[1])
            rc = float(parts[2])
            if rc < 0:
                rc = None
        except (ValueError, IndexError):
            return None

        return {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "value": vout,
            "unit": "V",
            "raw": {
                "vout": vout,
                "rc": rc,
            },
        }
