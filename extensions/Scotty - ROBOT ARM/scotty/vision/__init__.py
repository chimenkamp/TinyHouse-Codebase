"""Vision utilities: LEGO detection + pixel→world projection."""

from .detector import LegoDetector, Detection
from .pixel_to_world import pixel_to_table_xy

__all__ = ["LegoDetector", "Detection", "pixel_to_table_xy"]
