# Kobra 3 USB print file

Copy **[wa1_adapter_kobra3_PLA_04.gcode](wa1_adapter_kobra3_PLA_04.gcode)** onto the printer's USB drive. Insert the drive, select that file on the Anycubic Kobra 3, and print with PLA loaded. Remove the brim and supports after cooling, then check the clamp fit before installing electronics. The file was generated for the original **Anycubic Kobra 3 with a 0.4 mm nozzle**, as confirmed by the supplied label and nozzle answer.

The [Anycubic Kobra 3 manual](https://wiki.anycubic.com/k3/anycubic_kobra_3_user_manual-en-v1.3.pdf) documents G-code and USB printing. This file has been digitally checked but has not been run on the physical printer.

## Settings and estimates

| Setting | Value |
| --- | --- |
| Slicer | Official AnycubicSlicerNext 2.0.0.3, macOS arm64 |
| Printer profile | Anycubic Kobra 3 0.4 nozzle |
| Filament profile | Anycubic PLA @Anycubic Kobra 3 0.4 nozzle; 1.75 mm |
| Nozzle temperature | 220 °C first layer, 210 °C thereafter |
| Bed | Standard textured PEI assumption; 60 °C |
| Model dimensions | 180 × 65.7 × 24.3 mm; 100% scale |
| Placement | Broad rear face flat on bed; rotated in the bed plane by automatic arrangement |
| Layers | 0.2 mm model layers; supports use independent layer heights |
| Walls / solid shells | Four walls, five top and five bottom layers |
| Infill | 25% gyroid |
| Supports | Normal automatic, snug; also allowed on the model; 0.2 mm top/bottom contact gaps |
| Adhesion | 5 mm outer brim |
| Slicer estimate, normal mode | 2 h 31 min 55 s; 69.61 g / 23.34 m PLA, including supports and brim |

The actual PLA brand and its calibration have not been supplied. The file uses the manufacturer's standard PLA profile; check that the spool supports these temperatures. The estimate is a slicer estimate, not a measured print time. No ACE colour changes or timelapse commands are included.

The latest bundled profile declares a 255 × 255 mm bed. This project restricts it to the **250 × 250 × 260 mm** volume on the supplied printer label. The official machine start/end sequences are preserved, including `G9111 bedTemp=60 extruderTemp=220`. The slicer rounds the model's top to its layer grid: final printed layer Z is 24.2 mm for the nominal 24.3 mm model height. This is layer quantisation, not rescaling.

## Evidence and limitations

| Requirement | Status | Implementation evidence | Verification evidence |
| --- | --- | --- | --- |
| Slice the confirmed design for Kobra 3 / PLA / 0.4 mm | Implemented exactly | G-code and `wa1_adapter_kobra3_PLA_04.3mf` | Official slicer exited 0; project identifies Kobra 3, PLA and 0.4 mm |
| Preserve model size and corrected design | Implemented exactly | Source `wa1_tool_rack_sensor_adapter_top_mount_v2.stl` | Source SHA-256 checked; embedded mesh dimensions and unit-scale transform checked |
| Include supports and remain inside printer limits | Implemented exactly | G-code support paths and saved settings | 12,027 support extrusion segments; supports checked under both clamp jaws; explicit XYZ movements within 250 × 250 × 260 mm |
| Physical printing and fit | Not verified | No print was started | Requires the actual printer, rack, filament and electronics |

The [toolpath preview](toolpath-preview.png) plots real G-code extrusion paths at the first layer and representative clamp support heights. Orange paths are removable supports. The [verification record](print-verification.json) contains hashes, dimensions, bounds and slicer estimates. Explicit motion bounds include the manufacturer's end parking move at X = 250; the printer's internal implementation of `G9111` cannot be inspected from the G-code.

Checks executed:

- Official slicer CLI: `--arrange 1 --orient 0 --scale 1 --slice 0`, loading resolved bundled machine/process/filament profiles with the settings above; exit 0.
- `MPLCONFIGDIR=/private/tmp/wa1-slicing/matplotlib python3 /private/tmp/wa1-slicing/verify_print.py`: passed model hash, millimetres, mesh dimensions, unit scale, flat placement, settings, explicit motion bounds, clamp support coverage, and matching embedded/standalone G-code checks; rendered the preview.
- SHA-256 comparison after copying the final deliverables: G-code and source STL match the verification record.
- `git diff --check`: passed.

The slicer also recorded two advisory warnings: `bed_temperature_too_high_than_filament` and `not_support_traditional_timelapse`. The file retains the official PLA profile's 60 °C bed setting, equal to its configured 60 °C vitrification value. Timelapse was not enabled and its G-code is empty. These warnings are recorded here rather than suppressed.

No change to the requested design or print material was made during slicing. Hardware fit, support removal, first-layer adhesion, shrinkage, clamp strength and sensor operation remain unverified. Print one adapter and check fit before producing more.

## Files and provenance

Created for this print: G-code, sliced 3MF project, toolpath PNG, verification JSON and this guide. Updated the adapter README to describe the confirmed PLA setup and the catalog's STL path to the existing source file. The STL and CAD geometry are unchanged.

The confirmed `wa1_tool_rack_sensor_adapter_top_mount_v2.stl` was used. The older canonical filename `wa1_tool_rack_sensor_adapter.stl` was absent at delivery verification; it was not recreated. The adapter README and catalog now link to the existing confirmed file. The initial old-filename check failed with `FileNotFoundError`; verification against the confirmed source passed.

The sliced 3MF stores the effective settings and geometry, so it can be reopened in [AnycubicSlicerNext](https://www.anycubic.com/slicerNextDownload). It is separate from the geometry-only FreeCAD 3MF. The software was downloaded from Anycubic's current official download service and run locally; no print was started or sent over the network.

Source STL SHA-256: `95167b2b61fa19d6f184185400aad041c7d2f8212ce5ca3035a37ff2a245aab9`.

G-code SHA-256: `9eac66ef1c3db52b554aae966e1d4db73b7b2d27333b4c43de8f6c7339c82d06`.
