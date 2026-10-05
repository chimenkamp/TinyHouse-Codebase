"""Verify the three-button holder against the supplied case meshes."""

import tempfile
import unittest
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Self

import FreeCAD as App
import Mesh
import Part

from cad.button_holder import (
    BAY_COUNT,
    BAY_DEPTH_MM,
    BAY_WIDTH_MM,
    FACE_ANGLE_DEGREES,
    SOURCE_REAR_Z_MM,
    SOURCE_TOP_Z_MM,
    build_holder,
    holder_width,
    installed_bay,
    print_body,
    validate_config,
)
from cad.configuration import ButtonHolderConfig
from cad.display_mount import add_display_mount
from cad.export_button_holder import load_display_references, load_references, run

VOLUME_TOLERANCE_MM3: float = 0.0001
POSITION_TOLERANCE_MM: float = 0.0001


class ButtonHolderTests(unittest.TestCase):
    """Check layout, retained PCB interfaces, cables and real exported geometry."""

    config: ButtonHolderConfig
    reference_body: Part.Shape
    reference_lid: Part.Shape
    holder: Part.Shape
    source_hashes: dict[Path, str]

    @classmethod
    def setUpClass(cls: type[Self]) -> None:
        """Build the new holder and retain independent original-reference solids.

        :return: None.
        """
        cls.config = ButtonHolderConfig()
        cls.reference_body, cls.reference_lid = load_references(cls.config)
        cls.source_hashes = {
            p: sha256(p.read_bytes()).hexdigest()
            for p in (cls.config.body_reference, cls.config.lid_reference)
        }
        display: Part.Shape
        display, _ = load_display_references(cls.config)
        cls.holder = add_display_mount(
            build_holder(cls.reference_body, cls.config), display, cls.config
        )

    def test_one_valid_closed_body(self: Self) -> None:
        """Require one printable connected solid.

        :return: None.
        """
        self.assertTrue(self.holder.isValid())
        self.assertTrue(self.holder.isClosed())
        self.assertEqual(len(self.holder.Solids), 1)
        self.assertAlmostEqual(self.holder.BoundBox.XLength, 184, places=4)
        self.assertAlmostEqual(self.holder.BoundBox.YLength, 171.5, places=4)
        self.assertAlmostEqual(self.holder.BoundBox.ZMin, 0, places=4)

    def test_three_aligned_apertures_on_a_45_degree_face(self: Self) -> None:
        """Require three source-sized openings in one horizontal row at 45 degrees.

        :return: None.
        """
        normal: App.Vector = App.Rotation(
            App.Vector(1, 0, 0), FACE_ANGLE_DEGREES
        ).multVec(App.Vector(0, 0, 1))
        faces: list[Part.Face] = [
            f for f in self.holder.Faces if f.normalAt(0, 0).dot(normal) > 0.99999
        ]
        face: Part.Face = max(faces, key=lambda f: f.Area)
        self.assertEqual(len(face.Wires), BAY_COUNT + 1)
        centres: list[App.Vector] = sorted(
            [
                w.CenterOfMass
                for w in face.Wires
                if w is not face.OuterWire and w.Length < 100
            ],
            key=lambda v: v.x,
        )
        self.assertEqual(len(centres), 3)
        self.assertAlmostEqual(normal.y, -(2**-0.5), places=6)
        self.assertAlmostEqual(normal.z, 2**-0.5, places=6)
        self.assertAlmostEqual(centres[1].x - centres[0].x, 44.5, places=4)
        self.assertAlmostEqual(centres[2].x - centres[1].x, 44.5, places=4)
        self.assertLess(
            max(c.y for c in centres) - min(c.y for c in centres), POSITION_TOLERANCE_MM
        )
        self.assertLess(
            max(c.z for c in centres) - min(c.z for c in centres), POSITION_TOLERANCE_MM
        )

    def test_source_pcb_mount_and_button_case_geometry_are_preserved(
        self: Self,
    ) -> None:
        """Compare every complete bay against the original, including its PCB guides.

        :return: None.
        """
        local_region: Part.Shape = Part.makeBox(
            BAY_WIDTH_MM,
            BAY_DEPTH_MM,
            SOURCE_TOP_Z_MM - SOURCE_REAR_Z_MM,
            App.Vector(0, 0, SOURCE_REAR_Z_MM),
        )
        index: int
        for index in range(BAY_COUNT):
            original: Part.Shape = installed_bay(
                self.reference_body, index, self.config
            )
            region: Part.Shape = installed_bay(local_region, index, self.config)
            actual: Part.Shape = self.holder.common(region)
            self.assertLess(actual.cut(original).Volume, VOLUME_TOLERANCE_MM3)
            self.assertLess(original.cut(actual).Volume, VOLUME_TOLERANCE_MM3)

    def test_lids_have_no_added_collision_or_blocked_withdrawal(self: Self) -> None:
        """Preserve the reference snap fit and allow removal toward the open rear.

        :return: None.
        """
        reference_overlap: float = self.reference_body.common(self.reference_lid).Volume
        index: int
        distance: float
        for index in range(BAY_COUNT):
            lid: Part.Shape = installed_bay(self.reference_lid, index, self.config)
            self.assertAlmostEqual(
                self.holder.common(lid).Volume,
                reference_overlap,
                delta=VOLUME_TOLERANCE_MM3,
            )
            for distance in (2, 5, 10, 15):
                shifted: Part.Shape = self.reference_lid.copy()
                shifted.translate(App.Vector(0, 0, -distance))
                moved: Part.Shape = installed_bay(shifted, index, self.config)
                original: Part.Shape = installed_bay(
                    self.reference_body, index, self.config
                )
                self.assertLess(
                    self.holder.common(moved).Volume - original.common(moved).Volume,
                    VOLUME_TOLERANCE_MM3,
                )

    def test_three_plug_clearance_regions_are_open(self: Self) -> None:
        """Leave ten millimetres beside each reference connector opening.

        :return: None.
        """
        plug: Part.Shape = Part.makeBox(10, 6, 6, App.Vector(34.05, 9, -1.5))
        index: int
        for index in range(BAY_COUNT):
            self.assertLess(
                self.holder.common(installed_bay(plug, index, self.config)).Volume,
                VOLUME_TOLERANCE_MM3,
            )

    def test_shared_trough_and_rear_outlet_are_clear(self: Self) -> None:
        """Keep a useful common cable space connected to the open rear outlet.

        :return: None.
        """
        trough: Part.Shape = Part.makeBox(170, 12.8, 7.8, App.Vector(7, 30.1, 2.1))
        outlet: Part.Shape = Part.makeBox(
            11.8, 8, 7.8, App.Vector(holder_width(self.config) / 2 - 5.9, 41, 3.1)
        )
        self.assertLess(self.holder.common(trough).Volume, VOLUME_TOLERANCE_MM3)
        self.assertLess(self.holder.common(outlet).Volume, VOLUME_TOLERANCE_MM3)

    def test_print_orientation_preserves_size_and_puts_floor_on_bed(self: Self) -> None:
        """Keep the enlarged display-case floor flat on the bed without scaling.

        :return: None.
        """
        printed: Part.Shape = print_body(self.holder)
        self.assertAlmostEqual(
            printed.Volume, self.holder.Volume, delta=VOLUME_TOLERANCE_MM3
        )
        self.assertAlmostEqual(printed.BoundBox.ZMin, 0, places=5)
        self.assertAlmostEqual(
            printed.BoundBox.ZLength, self.holder.BoundBox.ZLength, places=4
        )
        self.assertLess(printed.BoundBox.XLength, 250)
        self.assertLess(printed.BoundBox.YLength, 250)
        self.assertLess(printed.BoundBox.ZLength, 260)
        faces: list[Part.Face] = [
            f
            for f in printed.Faces
            if f.normalAt(0, 0).z < -0.99999
            and abs(f.BoundBox.ZMin) < POSITION_TOLERANCE_MM
        ]
        self.assertTrue(faces)

    def test_invalid_fit_and_stand_parameters_are_rejected(self: Self) -> None:
        """Reject insufficient cable gaps, thin material and invalid dimensions.

        :return: None.
        """
        invalid_configs: list[ButtonHolderConfig] = [
            replace(self.config, bay_gap_mm=9),
            replace(self.config, end_clearance_mm=9),
            replace(self.config, wall_mm=1),
            replace(self.config, base_depth_mm=40),
            replace(self.config, face_z_mm=4),
            replace(self.config, bay_gap_mm=float("nan")),
            replace(self.config, tray_back_y_mm=43),
            replace(self.config, tray_height_mm=4),
            replace(self.config, brace_rib_mm=1),
        ]
        config: ButtonHolderConfig
        for config in invalid_configs:
            with self.subTest(config=config), self.assertRaises(ValueError):
                validate_config(config)

    def test_wrong_reference_cover_is_rejected(self: Self) -> None:
        """Reject accidental use of the case body as its matching cover.

        :return: None.
        """
        with self.assertRaises(ValueError):
            load_references(
                replace(self.config, lid_reference=self.config.body_reference)
            )

    def test_real_export_formats_round_trip(self: Self) -> None:
        """Load native CAD, STEP, STL and 3MF and count body/lid components.

        :return: None.
        """
        with tempfile.TemporaryDirectory() as folder:
            output: Path = Path(folder)
            run(replace(self.config, output_directory=output))
            document: App.Document = App.openDocument(
                str(output / "wa1_button_holder.FCStd")
            )
            try:
                self.assertTrue(document.getObject("Holder").Shape.isValid())
                self.assertEqual(len(document.getObject("Holder").Shape.Solids), 1)
                self.assertEqual(
                    len(
                        [o for o in document.Objects if o.Name.startswith("BackCover")]
                    ),
                    3,
                )
            finally:
                App.closeDocument(document.Name)
            step: Part.Shape = Part.Shape()
            step.read(str(output / "wa1_button_holder.step"))
            self.assertTrue(step.isValid())
            self.assertAlmostEqual(step.Volume, self.holder.Volume, delta=0.001)
            extension: str
            for extension in ("stl", "3mf"):
                mesh: Mesh.Mesh = Mesh.Mesh(
                    str(output / f"wa1_button_holder.{extension}")
                )
                lids: Mesh.Mesh = Mesh.Mesh(
                    str(output / f"wa1_button_holder_back_covers_3.{extension}")
                )
                self.assertTrue(mesh.isSolid())
                self.assertEqual(mesh.countComponents(), 1)
                self.assertTrue(lids.isSolid())
                self.assertEqual(lids.countComponents(), 3)
                self.assertAlmostEqual(mesh.BoundBox.ZMin, 0, places=4)
        for source, digest in self.source_hashes.items():
            self.assertEqual(sha256(source.read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
