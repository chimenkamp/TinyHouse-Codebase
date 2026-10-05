# WA-1 tool-rack sensor adapter

This removable adapter adds seven sensor positions and a cable trough to the existing `wa1_tool_rack`. Install the rack with its flat base against the wall and its tool-support arms pointing outward. Tools pass vertically through the gaps between the arms. Two small C-shaped clamps attach the adapter to the rear bar of the rack's existing top cassette without drilling the rack.

Use one Keyestudio Hall Magnetic module and one securely retained magnet tag per monitored tool. Cables leave either end of the trough for Arduino boards mounted separately beside the rack. The adapter does not include Arduino enclosures or wall anchors.

For the currently selected **IDUINO SE054, 25 × 12 mm**, use the [rear-mounted sensor case](../wa1_hall_sensor_case/README.md). It retains the narrower PCB and exposes its 90° bent Hall element through one front opening. The adapter geometry below remains the original larger-module design.

## Files and dimensions

The [FreeCAD model](wa1_tool_rack_sensor_adapter.FCStd) and [STEP](wa1_tool_rack_sensor_adapter.step) use the original rack's assembly coordinates. The [confirmed top-mount STL](wa1_tool_rack_sensor_adapter_top_mount_v2.stl) and [3MF](wa1_tool_rack_sensor_adapter.3mf) preserve this axis orientation and shift the origin for printing with the broad rear face down. Their envelope is 180 × 65.7 × 24.3. All dimensions are millimetres; import STL using millimetres.

The [FreeCAD assembly](assembly.FCStd) includes the original rack and attached adapter. See the [installed assembly preview](assembly-preview.png) and [exploded preview](exploded-preview.png).

| Feature | Design dimension |
| --- | --- |
| Adapter envelope in rack coordinates | x = 0–180, y = 65.3–131, z = 8–32.3; 180 × 65.7 × 24.3 |
| Axes in the installed assembly | x across rack; increasing y upward; increasing z outward from wall |
| Existing flat rack base | z = 0–8, with the wall at z = 0 |
| Sensor centres across rack | x = 20, 42, 64, 88, 114, 140, 162 |
| Each open-front sensor bay | 20.6 wide × 31 high × 12 deep |
| Sensor bay region | y = 75–106, z = 11–23 |
| Rear backplate | z = 8–11 |
| Nominal module envelope | 20 wide × 30 high; actual thickness and projections require measurement |
| Cable trough clear section | 13 high × 10 deep; y = 118–131, z = 11–21; open at both x ends |
| Cable feed through trough floor | One 8 × 8 opening per sensor, x centre ± 4 and z = 12–20, through y = 115–118 |
| Board retaining slots above each PCB | Two 2.8-wide × 3-high slots, x centre ± 6; y = 107–110, z = 8–11 |
| Cassette-clamp positions | x = 73.5–80.5 and 95.5–102.5; legs y = 65.3–73, caps seated on y = 70 |
| Clamp groove | 3.6 clearance for the cassette's 3-thick rear bar at z = 24–27 |
| Clamp screw pilots | 2.6 diameter, centred at y = 68.5, directed toward the wall along −z |

The adapter's printed geometry stays at z ≥ 8, so its design does not require additional spacing between the rack and wall. The board-retaining tie strands run behind the backplate at z = 6.8–8, above the rack, leaving clearance to the wall at z = 0. Check the actual ties, wall fixings and cables during fitting. The rack's independent wall attachment must carry the rack and tools; the adapter clamps retain only the sensor adapter. Wall fixings and their load validation are not included.

The sensor row remains close to the wall. The adapter reserves vertical tool corridors at x centre ± 5 and z = 26–68; its two small clamps lie between them. The original rack already partly closes the central slot beneath its cassette, up to z = 50. The adapter does not remove that existing restriction. Keep magnets at a repeatable wall-facing position near the sensors, around y = 75. For the unobstructed slots, a position near the closed slot roots at z = 26 gives a short gap. Check the central tool separately: its tag may need to extend toward the sensor to achieve the tested working distance.

## Regenerating the model

To regenerate this adapter deliberately, adjust `AdapterConfig` in [cad/configuration.py](../../../../cad/configuration.py), then call its exporter from the repository root using FreeCAD's Python. Root `main.py` now regenerates only the sensor cases against the saved adapter:

```bash
PYTHONPATH=/Applications/FreeCAD.app/Contents/Resources/lib:$PWD /Applications/FreeCAD.app/Contents/Resources/bin/python -c 'from cad.configuration import AdapterConfig; from cad.export_adapter import run; run(AdapterConfig())'
PYTHONPATH=/Applications/FreeCAD.app/Contents/Resources/lib:$PWD /Applications/FreeCAD.app/Contents/Resources/bin/python -m unittest discover -s tests -v
```

The FreeCAD file records `BuildParameters` for traceability. These properties do not drive a native parametric feature tree; regenerate the geometry through Python after changing the configuration. Adjust the application paths above if FreeCAD is installed elsewhere.

The PNG previews show the supplied default geometry; the generator updates the CAD, mesh files and catalog, but does not regenerate these static illustrations.

## Sensor choice and inventory

The [KS0487 kit documentation](https://docs.keyestudio.com/projects/KS0487/en/latest/ks0487.html#project-12-hall-magnetic) specifies a nominal 30 × 20 mm module, digital on/off output, and magnetic detection up to 30 mm. It wires `+` to 5 V, `−` to GND, and `S` to a digital input. The maximum distance is magnet-dependent and is not a guaranteed working gap.

Hall sensing suits a stationary tagged tool without requiring contact force or a reflective handle surface. It detects the tag's magnetic field; ordinary tool metal alone does not establish presence. The [manufacturer's Hall explanation](https://www.keyestudio.com/blog/how-to-use-hall-magnetic-sensor-with-microbit-166) identifies an A3144E sensing element. Its magnetic polarity and sensing-face orientation must be checked on the actual module. The [Allegro application guide](https://dev.allegromicro.com/-/media/files/application-notes/an27701-hall-effect-ic-application-guide.pdf) explains the required field direction through the sensing face.

The inventory workbook, `docs/EDV TinyHouse.xlsx`, lists five Keyestudio kits in `Tabelle1!A2/C2`. Their contents and condition have not been physically checked. Seven-slot operation needs seven confirmed Hall modules, so at least two additional modules are needed if each complete kit supplies one. A partially populated adapter can monitor only its fitted and commissioned positions.

The documented sensor interface provides four digital inputs per Arduino-class node. A four-sensor group on one side and a three-sensor group on the other is a proposed wiring allocation for two separately mounted nodes. Pin assignments, power capacity, firmware and data handling require confirmation; this addition changes no firmware.

## Printing and assembly

The prepared [Kobra 3 G-code](wa1_adapter_kobra3_PLA_04.gcode) uses the confirmed PLA filament and 0.4 mm nozzle, with a 0.2 layer height, four perimeters and 25% gyroid infill. See [USB printing instructions and verification](PRINTING.md), the [saved slicer project](wa1_adapter_kobra3_PLA_04.3mf), and the [actual toolpath preview](toolpath-preview.png). The original `wa1_tool_rack_sensor_adapter.3mf` is a geometry export; the separately named `wa1_adapter_kobra3_PLA_04.3mf` contains the sliced project.

The broad rear face is down, with the model's native z = 8 face on the build plate. The prepared file includes supports beneath the C-shaped clamps and a 5 mm brim. Remove supports and deburr the clamp grooves, board bays and cable openings before fitting electronics.

Additional hardware: two nylon M3 × 8 clamp screws; an M3 tap for the two printed 2.6 pilot holes; seven verified Hall modules; seven retained magnet tags; fourteen 150-long nonconductive cable ties, no wider than 2.5 and no thicker than 1.2; and three-conductor low-voltage harnesses. Sensor dimensions, connector clearance, tie-head dimensions and tag size must be checked before selecting the final hardware or printing multiple adapters.

1. Fit and wire the boards before attaching the adapter to the rack. Tap the two 2.6 pilot holes M3, and remove tools from the rack while fitting.
2. Place each module with its 20-wide direction across x and 30-high direction along y. Put its bottom at y = 75, with the Hall element downward, header upward, and components facing outward along +z. The nominal board support is the backplate at z = 11. Confirm the actual chip's sensing face and magnet polarity before fastening the module.
3. Use two cable ties per board. Pass each tie through one upper slot, downward over the board's front while avoiding components, under the carrier floor, then upward behind the backplate. The planned strand route runs at z = 23–24.2 in front, y = 70.8–72 beneath the floor, and z = 6.8–8 behind. Keep both heads at the front above the board, around y = 107–110. No PCB drilling or assumed mounting-hole pattern is required.
4. Route each three-wire harness upward through its feed opening into the trough, then toward the appropriate side Arduino. Leave service slack at connectors and check the actual plug and bend clearances.
5. Remove any sensor already installed in the cassette. Seat the two C-shaped clamps over its rear bar, with their caps resting on its top at y = 70. Fit the two nylon M3 × 8 screws from the room-facing side at z = 32.3, pointing toward the wall. Tighten gently, only enough to retain the adapter without deforming the rack.
6. Retain the harnesses outside the adapter and check the complete tie loops, screw heads and cables against the rack, wall and tool passages.
7. Attach each tool's magnet securely on its wall-facing side near the tested slot-root position. Confirm unobstructed vertical removal and return before commissioning sensing.

## Fit and sensing checks

CAD and mesh checks can establish solid geometry, dimensions and modeled clearances, including the cable-tie loops against the rack and nominal PCB envelope. They do not establish printed fit, clamp strength, actual PCB fit, component clearance beneath the ties, cable bend clearance, or reliable tool detection. Check one printed adapter against the installed rack and measured electronics before producing more.

Measure the PCB, component projections, Hall-element position, header and attached plug envelope. Detection requires a repeatable magnet position close to the sensor. A tool or magnet resting near the outer arm ends at z = 68 can be beyond the documented maximum range; the adapter does not establish detection throughout the full slot depth. Check the selected seated position and its allowed wobble.

The tool-slot centres are only 22–26 apart, so a sensor capable of responding at 30 could respond to a neighbouring tag. Choose and test a short working gap, including combinations with the adjacent slots occupied and empty. A sensor that cannot distinguish these combinations has not been commissioned for that position.

Confirm detected and empty signal levels, repeat insertion and removal, and verify debouncing and failure handling. A single digital signal does not inherently distinguish an empty rack from a disconnected sensor or a stuck output; the receiving implementation needs a defined way to mark invalid evidence as `unknown`. This adapter provides mechanical accommodation only. It is research telemetry, not a protective control, and a removed tool does not prove its correct use.
