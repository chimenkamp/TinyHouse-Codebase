# TinyHouse non-safety printable fixtures

This directory contains 16 distinct parametric fixtures for the four Bayreuth work areas. Each part is supplied as editable FreeCAD (`.FCStd`), neutral STEP, STL, and 3MF.

## Safety boundary

These are research-fixture prototypes only. They are not robot guards, robot mounts, emergency-stop components, fire controls, printer ventilation parts, mains-voltage enclosures, structural wall/display mounts, or certified protective equipment. They must not carry safety functions or override manufacturer requirements. Use commercially rated hardware and a competent safety review wherever failure could injure a person, damage equipment, block an exit, or compromise electrical/fire protection.

Every catalog item declares `safety_class: non_safety_fixture` and `load_bearing: false`. Here, non-load-bearing means that the print is not rated for structural support, machine restraint, guarding, or human support; trays and holders still require a stable commercial table, scale, or fastening interface beneath them.

Fit-sensitive dimensions are declared assumptions, not measurements of the installed hardware. Print one fit-check article and verify the physical interface before producing the listed quantity. The generated files use millimetres; STL itself does not encode units.

## Default print profile

- Layer height: 0.2 mm
- Perimeters: 4
- Top/bottom layers: 5
- Infill: 25% gyroid or equivalent
- Dimensional compensation: calibrate on the selected printer and material
- Edges in contact with operators: deburr after printing
- ESD use: ordinary PETG is not presumed dissipative; use verified ESD-safe material or a separate ESD-safe liner where specified

## Inventory

| Area | Part key | Qty | Generated envelope | Material |
| --- | --- | ---: | --- | --- |
| `WA-1` | `wa1_inspection_tray` | 1 | 220 x 160 x 16 mm | PETG |
| `WA-1` | `wa1_tool_rack` | 1 | 180 x 70 x 68 mm | PETG |
| `WA-1` | `wa1_sensor_bridge_bracket` | 1 | 90 x 55 x 71 mm | PETG |
| `WA-2` | `wa2_component_bin` | 4 | 110 x 85 x 55 mm | PETG |
| `WA-2` | `wa2_bin_locator` | 4 | 122 x 97 x 8 mm | PETG |
| `WA-2` | `wa2_kit_tray` | 1 | 220 x 150 x 18 mm | PETG with removable ESD-safe liner |
| `WA-3` | `wa3_component_staging_tray` | 1 | 220 x 150 x 16 mm | Validated ESD-safe PETG or PETG outside the ESD mat |
| `WA-3` | `wa3_nano_test_jig_enclosure` | 1 | 110 x 80 x 28 mm | Validated ESD-safe PETG |
| `WA-3` | `wa3_reference_weight_caddy` | 1 | 180 x 70 x 18 mm | PETG |
| `WA-4` | `wa4_receiving_tray` | 1 | 240 x 180 x 18 mm | PETG |
| `WA-4` | `wa4_barcode_scanner_stand` | 1 | 130 x 100 x 130 mm | PETG |
| `WA-4` | `wa4_button_console` | 1 | 150 x 80 x 28 mm | PETG |
| `Shared` | `shared_camera_privacy_hood` | 4 | 76 x 80 x 58 mm | Matte black PETG |
| `Shared` | `shared_pi5_under_table_sled` | 4 | 130 x 100 x 18 mm | PETG |
| `Shared` | `shared_table_edge_cable_clip` | 12 | 35 x 42 x 36 mm | PETG |
| `Shared` | `shared_label_card_holder` | 8 | 100 x 30 x 42 mm | PETG |

## Files and traceability

`manifest.json` records quantities, generated bounds, materials, orientation, non-printed hardware, fit assumptions, mesh facet counts, solid volumes, relative file paths, and SHA-256 digests. Re-run the generator under FreeCAD and then run the independent validator before fabrication.

## Part details

### WA-1 cooled-part inspection tray

- Work area: `WA-1`
- Quantity: 1
- Purpose: Keeps the printed base inside a repeatable camera and load-cell inspection region.
- Generated envelope: 220 x 160 x 16 mm
- Material: PETG
- Print orientation: Flat on the tray bottom; no supports.
- Non-printed hardware: None

Fit assumptions:

- Usable inspection region is 212 x 152 mm.
- Verify the produced base envelope before printing.

### WA-1 sensor-ready scraper and caliper rack

- Work area: `WA-1`
- Quantity: 1
- Purpose: Separates hand tools from the cooled-part inspection surface and holds one removable Hall-sensor module behind the designated monitored slot.
- Generated envelope: 180 x 70 x 68 mm
- Material: PETG
- Print orientation: Base on the build plate; support the rear sensor-cassette floor and front lip only where the selected slicer requires it.
- Non-printed hardware: 2 x M4 washers; 2 x M4 screws for optional bench attachment; 1 x Keyestudio Hall Magnetic module, nominal PCB 30 x 20 mm; 1 x 8 x 3 mm neodymium magnet or equivalent tool-mounted magnetic tag; 1 x three-wire extra-low-voltage sensor harness

Fit assumptions:

- Seven 10 mm open tool slots are provided.
- Tool handles wider than 10 mm rest in the front channel.
- The integrated cassette monitors one designated tool slot only.
- The official module envelope is 30 x 20 mm; PCB thickness, Hall-element position, connector keep-out, and component height require a physical fit check.
- Validate magnet distance and every allowed resting orientation; an empty slot is not evidence of correct tool use or operator identity.
- The presence sensor is research telemetry, not a safety interlock, and must not control the printer or protective functions.
- Monitoring all seven slots requires seven sensors and verified additional digital-input capacity; the workbook lists five complete sensor kits.

### WA-1 optical and thermal sensor bridge bracket

- Work area: `WA-1`
- Quantity: 1
- Purpose: Provides a non-safety adapter surface for a camera and MLX90640 sensor pod.
- Generated envelope: 90 x 55 x 71 mm
- Material: PETG
- Print orientation: On one broad side of the L profile; supports under the opposite flange.
- Non-printed hardware: 2 x M4 screws and washers; 2 x M3 camera-module screws

Fit assumptions:

- Optical opening is 44 x 28 mm.
- Hole spacing is a prototype and must be checked against the selected sensor carrier.

### WA-2 instrumented component bin

- Work area: `WA-2`
- Quantity: 4
- Purpose: Holds one identified component type over a dedicated weighing point.
- Generated envelope: 110 x 85 x 55 mm
- Material: PETG
- Print orientation: Flat on the bin bottom; no supports.
- Non-printed hardware: None

Fit assumptions:

- Internal envelope is approximately 104 x 79 x 52 mm.
- Do not use for loose conductive parts without an ESD-safe liner.

### WA-2 component-bin locator plate

- Work area: `WA-2`
- Quantity: 4
- Purpose: Returns each component bin to the same load-cell and camera position.
- Generated envelope: 122 x 97 x 8 mm
- Material: PETG
- Print orientation: Flat on the plate bottom; no supports.
- Non-printed hardware: 4 x M4 low-profile screws; Load-cell platform supplied separately

Fit assumptions:

- Recess accepts a 110 x 85 mm bin base.
- Verify screw positions against the load-cell platform before drilling.

### WA-2 prepared-kit tray

- Work area: `WA-2`
- Quantity: 1
- Purpose: Separates prepared electronics into three observable kit compartments.
- Generated envelope: 220 x 150 x 18 mm
- Material: PETG with removable ESD-safe liner
- Print orientation: Flat on the tray bottom; no supports.
- Non-printed hardware: ESD-safe liner

Fit assumptions:

- Three equal nominal compartments are provided.
- The printed polymer is not assumed to be electrically dissipative.

### WA-3 base, lid, and kit staging tray

- Work area: `WA-3`
- Quantity: 1
- Purpose: Provides three separated identity-preserving staging pockets before assembly.
- Generated envelope: 220 x 150 x 16 mm
- Material: Validated ESD-safe PETG or PETG outside the ESD mat
- Print orientation: Flat on the tray bottom; no supports.
- Non-printed hardware: ESD-safe pocket liners when ordinary PETG is used

Fit assumptions:

- Each pocket is approximately 65 x 138 mm.
- Verify component envelopes and surface-resistivity requirements.

### WA-3 Nano serial test-jig enclosure

- Work area: `WA-3`
- Quantity: 1
- Purpose: Protects a low-voltage carrier board and provides controlled USB cable exit.
- Generated envelope: 110 x 80 x 28 mm
- Material: Validated ESD-safe PETG
- Print orientation: Flat on the enclosure bottom; no supports.
- Non-printed hardware: 4 x M3 screws; 4 x M3 insulating washers

Fit assumptions:

- Prototype post pattern is 58 x 36 mm.
- Carrier-board dimensions and electrical clearances require a physical fit check.

### WA-3 reference-weight caddy

- Work area: `WA-3`
- Quantity: 1
- Purpose: Keeps four calibration references identified and separated from active test parts.
- Generated envelope: 180 x 70 x 18 mm
- Material: PETG
- Print orientation: Flat on the caddy bottom; no supports.
- Non-printed hardware: Certified reference weights supplied separately

Fit assumptions:

- Blind pockets have radii 18, 15, 12, and 9 mm.
- Measure the certified references before production printing.

### WA-4 scale-compatible lid receiving tray

- Work area: `WA-4`
- Quantity: 1
- Purpose: Defines the receiving and camera region while distributing load on the scale.
- Generated envelope: 240 x 180 x 18 mm
- Material: PETG
- Print orientation: Flat on the tray bottom; no supports.
- Non-printed hardware: Non-slip scale mat

Fit assumptions:

- Usable region is 232 x 172 mm.
- Verify the scale platform and largest lid envelope.

### WA-4 barcode-scanner stand

- Work area: `WA-4`
- Quantity: 1
- Purpose: Keeps a handheld scanner in a repeatable position beside the receiving tray.
- Generated envelope: 130 x 100 x 130 mm
- Material: PETG
- Print orientation: On the rear face; supports under the cradle and base as required.
- Non-printed hardware: 4 x adhesive rubber feet

Fit assumptions:

- Handle slot is 40 mm wide.
- Confirm scanner handle width and trigger clearance.

### WA-4 low-voltage decision-button console

- Work area: `WA-4`
- Quantity: 1
- Purpose: Houses three low-voltage buttons for accept, replace, and manual-review decisions.
- Generated envelope: 150 x 80 x 28 mm
- Material: PETG
- Print orientation: Top panel on the build plate; supports in the cable slot only if required.
- Non-printed hardware: 3 x 22 mm extra-low-voltage panel buttons; Low-voltage cable gland

Fit assumptions:

- Cutouts are 22.5 mm diameter.
- This enclosure is prohibited for mains voltage or safety circuits.

### Shared workpiece-camera privacy hood

- Work area: `Shared`
- Quantity: 4
- Purpose: Limits glare and narrows incidental visibility outside each workpiece region.
- Generated envelope: 76 x 80 x 58 mm
- Material: Matte black PETG
- Print orientation: On one side wall; no internal supports.
- Non-printed hardware: 2 x M3 screws; 2 x M3 washers

Fit assumptions:

- Clear optical channel is 68 x 50 mm.
- The hood supplements but does not replace software privacy masking.

### Shared Raspberry Pi 5 under-table sled

- Work area: `Shared`
- Quantity: 4
- Purpose: Provides ventilated, removable edge-node retention below each work surface.
- Generated envelope: 130 x 100 x 18 mm
- Material: PETG
- Print orientation: Flat on the sled bottom; no supports.
- Non-printed hardware: 4 x M3 screws and insulating washers; 2 x metal under-table straps

Fit assumptions:

- Board-hole pattern is 58 x 49 mm.
- Verify the selected Pi case, PoE hardware, and NVMe carrier envelope.

### Shared table-edge cable clip

- Work area: `Shared`
- Quantity: 12
- Purpose: Routes extra-low-voltage sensor cables without placing loose loops on work surfaces.
- Generated envelope: 35 x 42 x 36 mm
- Material: PETG
- Print orientation: On one 35 x 36 mm side; no supports.
- Non-printed hardware: Reusable hook-and-loop cable tie

Fit assumptions:

- Open throat is 25 mm high and 33 mm deep.
- Use only after measuring the actual table edge; never route mains or safety wiring.

### Shared work-order label-card holder

- Work area: `Shared`
- Quantity: 8
- Purpose: Keeps removable work-order and component identity cards visible at transfer points.
- Generated envelope: 100 x 30 x 42 mm
- Material: PETG
- Print orientation: On the back panel; supports under the base if required.
- Non-printed hardware: 90 x 35 mm paper or polymer label card; Removable adhesive strip

Fit assumptions:

- Card channel is approximately 17 mm deep.
- Use pseudonymous identifiers when privacy policy requires them.

