"""Check the user-selected display case in the WA1 button holder."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Self

import FreeCAD as App
import Mesh
import Part

from cad.button_holder import build_holder, installed_bay
from cad.configuration import ButtonHolderConfig
from cad.display_mount import add_display_mount, installed_display
from cad.export_button_holder import load_display_references, load_references, run

VOLUME_TOLERANCE_MM3: float = 0.001


class DisplayMountTests(unittest.TestCase):
    """Verify original mounting geometry, service access and actual exports."""

    config: ButtonHolderConfig
    display: Part.Shape
    cover: Part.Shape
    button_lid: Part.Shape
    stand: Part.Shape
    holder: Part.Shape

    @classmethod
    def setUpClass(cls: type[Self]) -> None:
        """Build the integrated holder from all four source meshes.

        :return: None.
        """
        cls.config = ButtonHolderConfig()
        button: Part.Shape
        button, cls.button_lid = load_references(cls.config)
        cls.display, cls.cover = load_display_references(cls.config)
        cls.stand = build_holder(button, cls.config)
        cls.holder = add_display_mount(cls.stand, cls.display, cls.config)

    def test_original_display_case_is_preserved_at_full_scale(self: Self) -> None:
        """Require the complete selected case with no obstructed internal features.

        :return: None.
        """
        original: Part.Shape = installed_display(self.display, self.config)
        region: Part.Shape = installed_display(
            Part.makeBox(119.5, 184, 20), self.config
        )
        actual: Part.Shape = self.holder.common(region)
        self.assertLess(original.cut(actual).Volume, VOLUME_TOLERANCE_MM3)
        self.assertLess(actual.cut(original).Volume, VOLUME_TOLERANCE_MM3)
        self.assertTrue(self.holder.isValid())
        self.assertTrue(self.holder.isClosed())
        self.assertEqual(len(self.holder.Solids), 1)
        self.assertAlmostEqual(self.holder.BoundBox.XLength, 184, places=4)
        self.assertAlmostEqual(self.holder.BoundBox.YLength, 171.5, places=4)

    def test_display_cover_gains_no_interference_and_lifts_clear(self: Self) -> None:
        """Keep the original cover fit and allow vertical removal.

        :return: None.
        """
        reference_overlap: float = self.display.common(self.cover).Volume
        cover: Part.Shape = installed_display(self.cover, self.config)
        self.assertAlmostEqual(
            self.holder.common(cover).Volume,
            reference_overlap,
            delta=VOLUME_TOLERANCE_MM3,
        )
        distance: float
        for distance in (2, 5, 10, 20):
            moved: Part.Shape = cover.copy()
            moved.translate(App.Vector(0, 0, distance))
            original: Part.Shape = installed_display(self.display, self.config)
            self.assertLess(
                self.holder.common(moved).Volume - original.common(moved).Volume,
                VOLUME_TOLERANCE_MM3,
            )

    def test_buttons_remain_serviceable_and_display_layout_is_rejected_if_too_small(
        self: Self,
    ) -> None:
        """Keep the existing button-cover removal path and reject bad placements.

        :return: None.
        """
        index: int
        for index in range(3):
            lid: Part.Shape = self.button_lid.copy()
            lid.translate(App.Vector(0, 0, -15))
            moved: Part.Shape = installed_bay(lid, index, self.config)
            self.assertLess(
                self.holder.common(moved).Volume - self.stand.common(moved).Volume,
                VOLUME_TOLERANCE_MM3,
            )
        config: ButtonHolderConfig
        for config in (
            replace(self.config, end_clearance_mm=12),
            replace(self.config, base_depth_mm=170),
            replace(self.config, display_front_y_mm=50),
            replace(self.config, display_front_y_mm=float("nan")),
        ):
            with self.subTest(config=config), self.assertRaises(ValueError):
                add_display_mount(self.stand, self.display, config)

    def test_wrong_display_cover_is_rejected(self: Self) -> None:
        """Reject using the case body in place of its matching removable cover.

        :return: None.
        """
        with self.assertRaises(ValueError):
            load_display_references(
                replace(
                    self.config, display_lid_reference=self.config.display_reference
                )
            )

    def test_low_rear_connector_opening_reaches_outside_the_base(self: Self) -> None:
        """Keep the source opening that starts just above its two-millimetre floor.

        :return: None.
        """
        passage: Part.Shape = installed_display(
            Part.makeBox(6.5, 28, 0.9, App.Vector(-6.5, 105, 2.1)),
            self.config,
        )
        self.assertLess(self.holder.common(passage).Volume, VOLUME_TOLERANCE_MM3)

    def test_native_display_cover_and_print_meshes_round_trip(self: Self) -> None:
        """Reopen the integrated CAD assembly and the separate display-cover plate.

        :return: None.
        """
        with tempfile.TemporaryDirectory() as folder:
            output: Path = Path(folder)
            run(replace(self.config, output_directory=output))
            document: App.Document = App.openDocument(
                str(output / "wa1_button_holder.FCStd")
            )
            try:
                saved: Part.Shape = document.getObject("Holder").Shape
                self.assertAlmostEqual(
                    saved.Volume, self.holder.Volume, delta=VOLUME_TOLERANCE_MM3
                )
                self.assertTrue(document.getObject("DisplayCover").Shape.isValid())
            finally:
                App.closeDocument(document.Name)
            extension: str
            for extension in ("stl", "3mf"):
                mesh: Mesh.Mesh = Mesh.Mesh(
                    str(output / f"wa1_button_holder_display_cover.{extension}")
                )
                self.assertTrue(mesh.isSolid())
                self.assertEqual(mesh.countComponents(), 1)
                self.assertAlmostEqual(mesh.BoundBox.ZMin, 0, places=4)
                self.assertAlmostEqual(mesh.BoundBox.XLength, 184, places=4)
                self.assertAlmostEqual(mesh.BoundBox.YLength, 119.5, places=4)


if __name__ == "__main__":
    unittest.main()
