"""Verify the real WA1 PLA/Kobra 3 print jobs and their saved configuration."""

import json
import re
import unittest
import xml.etree.ElementTree as ET
import zipfile
from hashlib import md5
from pathlib import Path
from typing import Self, TypeAlias

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
ROOT: Path = Path(__file__).resolve().parents[1]
PRINTS: Path = ROOT / "assets/3D/Workareas/wa1_button_holder/prints"
JOBS: tuple[str, ...] = (
    "wa1_button_holder_kobra3_PLA_04",
    "wa1_button_holder_covers_kobra3_PLA_04",
)
AXIS_PATTERN: re.Pattern[str] = re.compile(r"(?:^|\s)([XYZ])(-?\d+(?:\.\d+)?)")
AXIS_LIMITS_MM: dict[str, float] = {"X": 250.0, "Y": 250.0, "Z": 260.0}
PREVIOUS_BODY_SECONDS: int = 38189
COMPACT_BODY_DIMENSIONS_MM: tuple[float, float] = (184.0, 171.5)
CORE_NAMESPACE: str = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"


def check_explicit_motion(lines: list[str]) -> int:
    """Check explicit absolute moves without simulating the firmware startup macro.

    :param lines: Actual generated G-code lines.
    :return: Number of explicit coordinate values checked.
    """
    checked: int = 0
    absolute_xyz: bool = False
    line: str
    for line in lines:
        command: str = line.split(";", 1)[0].strip()
        opcode: str = command.split(" ", 1)[0]
        if opcode == "G90":
            absolute_xyz = True
        if opcode in ("G91", "G2", "G3", "G20"):
            raise ValueError("Relative XYZ or arc motion needs a different audit.")
        if opcode not in ("G0", "G1"):
            continue
        axis: str
        value: str
        for axis, value in AXIS_PATTERN.findall(command):
            if not absolute_xyz:
                raise ValueError("Absolute XYZ mode must be declared before motion.")
            coordinate: float = float(value)
            if not 0 <= coordinate <= AXIS_LIMITS_MM[axis]:
                raise ValueError(f"Out-of-volume explicit move: {command}")
            checked += 1
    return checked


class SlicedPrintTests(unittest.TestCase):
    """Check actual print outputs rather than profile declarations alone."""

    def test_body_job_contains_compact_geometry_and_takes_less_time(self: Self) -> None:
        """Reject stale sliced geometry and require a measured time reduction.

        :return: None.
        """
        with zipfile.ZipFile(PRINTS / f"{JOBS[0]}.3mf") as archive:
            paths: list[str] = [
                p
                for p in archive.namelist()
                if p.startswith("3D/Objects/") and p.endswith(".model")
            ]
            self.assertEqual(len(paths), 1)
            model: ET.Element = ET.fromstring(archive.read(paths[0]))
            vertices: list[ET.Element] = list(model.iter(CORE_NAMESPACE + "vertex"))
            axis: str
            size: float
            for axis, size in zip(("x", "y"), COMPACT_BODY_DIMENSIONS_MM):
                coordinates: list[float] = [float(v.attrib[axis]) for v in vertices]
                self.assertAlmostEqual(
                    max(coordinates) - min(coordinates), size, places=3
                )
            info: ET.Element = ET.fromstring(archive.read("Metadata/slice_info.config"))
            metadata: dict[str, str] = {
                n.attrib["key"]: n.attrib["value"] for n in info.iter("metadata")
            }
            self.assertGreater(int(metadata["prediction"]), 0)
            self.assertLess(int(metadata["prediction"]), PREVIOUS_BODY_SECONDS)

    def test_real_archives_and_required_profiles(self: Self) -> None:
        """Require both sliced projects with identical embedded/external G-code.

        :return: None.
        """
        job: str
        for job in JOBS:
            with self.subTest(job=job):
                gcode: bytes = (PRINTS / f"{job}.gcode").read_bytes()
                with zipfile.ZipFile(PRINTS / f"{job}.3mf") as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertEqual(
                        ET.fromstring(archive.read("3D/3dmodel.model")).attrib["unit"],
                        "millimeter",
                    )
                    self.assertEqual(archive.read("Metadata/plate_1.gcode"), gcode)
                    self.assertEqual(
                        bytes.fromhex(
                            archive.read("Metadata/plate_1.gcode.md5").decode().strip()
                        ),
                        md5(gcode).digest(),
                    )
                    settings: dict[str, JsonValue] = json.loads(
                        archive.read("Metadata/project_settings.config")
                    )
                self.assertEqual(settings["printer_model"], "Anycubic Kobra 3")
                self.assertEqual(settings["nozzle_diameter"], ["0.4"])
                self.assertEqual(settings["filament_type"], ["PLA"])
                self.assertEqual(
                    settings["printable_area"], ["0x0", "250x0", "250x250", "0x250"]
                )
                self.assertEqual(settings["printable_height"], "260")
                self.assertEqual(settings["layer_height"], "0.2")
                self.assertEqual(settings["wall_loops"], "4")
                self.assertEqual(settings["sparse_infill_density"], "25%")
                self.assertEqual(settings["sparse_infill_pattern"], "gyroid")
                self.assertEqual(settings["enable_support"], "1")
                self.assertEqual(settings["nozzle_temperature"], ["210"])
                self.assertEqual(settings["textured_plate_temp"], ["60"])
                self.assertEqual(settings["nozzle_temperature_initial_layer"], ["220"])
                self.assertGreater(
                    check_explicit_motion(gcode.decode().splitlines()), 100
                )
                self.assertIn(b"G9111 bedTemp=60 extruderTemp=220", gcode)
                self.assertIn(b"M140 S0", gcode)
                self.assertIn(b"M104 S0", gcode)

    def test_invalid_motion_is_rejected(self: Self) -> None:
        """Reject negative/out-of-bed coordinates, relative XYZ and unaudited arcs.

        :return: None.
        """
        command: str
        self.assertEqual(check_explicit_motion(["G90", "G1 X20 Y20 Z0.2"]), 3)
        for command in ("G1 X251", "G1 Y-1", "G1 Z261", "G91", "G2 X20 Y20", "G20"):
            with self.subTest(command=command), self.assertRaises(ValueError):
                check_explicit_motion(["G90", command])


if __name__ == "__main__":
    unittest.main()
