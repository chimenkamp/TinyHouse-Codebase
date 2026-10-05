"""Check the exported compact holder against the previous oversized design."""

import unittest
from pathlib import Path
from typing import Self

import FreeCAD as App
import Part

ASSET: Path = (
    Path(__file__).resolve().parents[1] / "assets/3D/Workareas/wa1_button_holder"
)
MAX_WIDTH_MM: float = 184.0
MAX_DEPTH_MM: float = 171.5
MAX_VOLUME_MM3: float = 130000.0


class CompactHolderTests(unittest.TestCase):
    """Require actual exported geometry to remove unused footprint and material."""

    def test_exported_body_is_smaller_and_has_an_open_front_floor(self: Self) -> None:
        """Inspect native geometry, including the real floor opening.

        :return: None.
        """
        document: App.Document = App.openDocument(
            str(ASSET / "wa1_button_holder.FCStd")
        )
        try:
            body: Part.Shape = document.getObject("Holder").Shape
            self.assertTrue(body.isValid() and body.isClosed())
            self.assertEqual(len(body.Solids), 1)
            self.assertLessEqual(body.BoundBox.XLength, MAX_WIDTH_MM + 0.0001)
            self.assertLessEqual(body.BoundBox.YLength, MAX_DEPTH_MM + 0.0001)
            self.assertLess(body.Volume, MAX_VOLUME_MM3)
            opening: Part.Shape = Part.makeBox(160, 24, 1.8, App.Vector(12, 4, 0.1))
            self.assertLess(body.common(opening).Volume, 0.001)
        finally:
            App.closeDocument(document.Name)


if __name__ == "__main__":
    unittest.main()
