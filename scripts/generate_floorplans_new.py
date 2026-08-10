#!/usr/bin/env python3
"""Generate the TinyHouse work-area floor plan and instrumentation concept."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle


OUTPUT = Path("output/pdf/floorplans_new.pdf")
PAGE_W, PAGE_H = landscape(A4)

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#2563A6")
TEAL = colors.HexColor("#15807A")
GREEN = colors.HexColor("#3E8E5B")
ORANGE = colors.HexColor("#D97706")
RED = colors.HexColor("#B83232")
YELLOW = colors.HexColor("#F2C94C")
PURPLE = colors.HexColor("#7A4EAB")
INK = colors.HexColor("#17202A")
MUTED = colors.HexColor("#53606C")
LINE = colors.HexColor("#B8C2CC")
PALE = colors.HexColor("#F4F7FA")
PALE_BLUE = colors.HexColor("#EAF2FB")
PALE_TEAL = colors.HexColor("#E8F6F4")
PALE_ORANGE = colors.HexColor("#FFF3E3")
PALE_RED = colors.HexColor("#FDECEC")
WHITE = colors.white


styles = getSampleStyleSheet()
BODY = ParagraphStyle(
    "Body",
    parent=styles["BodyText"],
    fontName="Helvetica",
    fontSize=7.2,
    leading=9.0,
    textColor=INK,
    alignment=TA_LEFT,
    spaceAfter=0,
)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=6.2, leading=7.5)
TINY = ParagraphStyle("Tiny", parent=BODY, fontSize=5.2, leading=6.3)
BOX_HEAD = ParagraphStyle(
    "BoxHead", parent=BODY, fontName="Helvetica-Bold", fontSize=8.2, leading=9.5, textColor=NAVY
)
WHITE_HEAD = ParagraphStyle(
    "WhiteHead", parent=BODY, fontName="Helvetica-Bold", fontSize=7.3, leading=8.5, textColor=WHITE
)
TABLE_HEAD = ParagraphStyle(
    "TableHead", parent=BODY, fontName="Helvetica-Bold", fontSize=5.5, leading=6.5, textColor=WHITE
)
TABLE_CELL = ParagraphStyle("TableCell", parent=BODY, fontSize=5.25, leading=6.35)
TABLE_CELL_SMALL = ParagraphStyle("TableCellSmall", parent=BODY, fontSize=4.85, leading=5.75)
EVENT_CELL = ParagraphStyle("EventCell", parent=BODY, fontSize=5.45, leading=6.45)


def para(text: str, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(text, style)


def draw_paragraph(c: canvas.Canvas, text: str, x: float, y_top: float, width: float, style=BODY) -> float:
    item = para(text, style)
    _, height = item.wrap(width, PAGE_H)
    item.drawOn(c, x, y_top - height)
    return height


def page_header(c: canvas.Canvas, badge: str, title: str, subtitle: str, page_no: int) -> None:
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 18 * mm, PAGE_W, 18 * mm, fill=1, stroke=0)
    c.setFillColor(TEAL)
    c.roundRect(10 * mm, PAGE_H - 14.5 * mm, 29 * mm, 10 * mm, 2 * mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(24.5 * mm, PAGE_H - 11.1 * mm, badge)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(44 * mm, PAGE_H - 10.5 * mm, title)
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#D8E5F1"))
    c.drawRightString(PAGE_W - 10 * mm, PAGE_H - 9.8 * mm, subtitle)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6.5)
    c.drawString(10 * mm, 6 * mm, "TinyHouse concept plan - not a construction or certified safety drawing")
    c.drawRightString(PAGE_W - 10 * mm, 6 * mm, f"Page {page_no} of 9 | Revision 2026-08-10")


def panel(c: canvas.Canvas, x: float, y: float, w: float, h: float, title: str, fill=WHITE) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.7)
    c.roundRect(x, y, w, h, 2.5 * mm, fill=1, stroke=1)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 4 * mm, y + h - 7 * mm, title)
    c.setStrokeColor(LINE)
    c.line(x + 4 * mm, y + h - 9.5 * mm, x + w - 4 * mm, y + h - 9.5 * mm)


def draw_data_table(
    c: canvas.Canvas,
    data: list[list[str]],
    x: float,
    y_top: float,
    col_widths: list[float],
    cell_style=TABLE_CELL,
    header_bg=NAVY,
    repeat_rows=1,
) -> float:
    rows = []
    for r, row in enumerate(data):
        style = TABLE_HEAD if r == 0 else cell_style
        rows.append([para(cell, style) for cell in row])
    table = Table(rows, colWidths=col_widths, repeatRows=repeat_rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), header_bg),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
            ]
        )
    )
    _, height = table.wrap(sum(col_widths), PAGE_H)
    table.drawOn(c, x, y_top - height)
    return height


def tag(c: canvas.Canvas, x: float, y: float, text: str, color: colors.Color) -> None:
    c.setFillColor(color)
    c.roundRect(x, y, 22 * mm, 5.5 * mm, 2 * mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 6.2)
    c.drawCentredString(x + 11 * mm, y + 1.8 * mm, text)


def equipment(c: canvas.Canvas, x: float, y: float, w: float, h: float, label: str, fill, dashed=False) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(INK)
    c.setDash(4, 2) if dashed else c.setDash()
    c.roundRect(x, y, w, h, 2.2 * mm, fill=1, stroke=1)
    c.setDash()
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 6.1)
    lines = label.split("\n")
    start = y + h / 2 + (len(lines) - 1) * 3.2
    for i, line in enumerate(lines):
        c.drawCentredString(x + w / 2, start - i * 7, line)


def dimension(c: canvas.Canvas, x1: float, y1: float, x2: float, y2: float, label: str) -> None:
    c.setStrokeColor(MUTED)
    c.setFillColor(MUTED)
    c.setLineWidth(0.5)
    c.line(x1, y1, x2, y2)
    if abs(x2 - x1) >= abs(y2 - y1):
        c.line(x1, y1 - 3, x1, y1 + 3)
        c.line(x2, y2 - 3, x2, y2 + 3)
        c.setFont("Helvetica", 6)
        c.drawCentredString((x1 + x2) / 2, y1 + 3, label)
    else:
        c.line(x1 - 3, y1, x1 + 3, y1)
        c.line(x2 - 3, y2, x2 + 3, y2)
        c.saveState()
        c.translate(x1 + 4, (y1 + y2) / 2)
        c.rotate(90)
        c.setFont("Helvetica", 6)
        c.drawCentredString(0, 0, label)
        c.restoreState()


def draw_floorplan(c: canvas.Canvas, x: float, y: float, w: float) -> None:
    scale = w / 7.0
    h = 2.25 * scale
    c.setFillColor(colors.HexColor("#F9F4EA"))
    c.setStrokeColor(NAVY)
    c.setLineWidth(2)
    c.rect(x, y, w, h, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(MUTED)
    c.drawString(x + 2, y + h + 6, "NORTH / WINDOW WALL")

    # Window and entrance are diagrammatic because the scanned plan lacks survey coordinates.
    win_x1, win_x2 = x + 3.0 * scale, x + 4.2 * scale
    c.setStrokeColor(BLUE)
    c.setLineWidth(4)
    c.line(win_x1, y + h, win_x2, y + h)
    c.setFillColor(BLUE)
    c.setFont("Helvetica", 5.5)
    c.drawCentredString((win_x1 + win_x2) / 2, y + h - 8, "window - verify")

    door_x1, door_x2 = x + 3.05 * scale, x + 4.45 * scale
    c.setStrokeColor(WHITE)
    c.setLineWidth(5)
    c.line(door_x1, y, door_x2, y)
    c.setStrokeColor(ORANGE)
    c.setLineWidth(0.8)
    c.line(door_x1, y, door_x1, y + 0.65 * scale)
    c.line(door_x2, y, door_x2, y + 0.65 * scale)
    c.setFillColor(ORANGE)
    c.setFont("Helvetica-Bold", 5.5)
    c.drawCentredString((door_x1 + door_x2) / 2, y + 6, "entrance / keep clear")

    # Table T2 / WA-2. 120 cm along the north wall and 80 cm deep.
    equipment(c, x + 0.25 * scale, y + h - 0.80 * scale, 1.20 * scale, 0.80 * scale, "WA-2 / T2\n80 x 120 cm\nPAROL6", PALE_RED)
    c.setStrokeColor(RED)
    c.setDash(3, 2)
    c.circle(x + 0.85 * scale, y + h - 0.40 * scale, 0.68 * scale, fill=0, stroke=1)
    c.setDash()
    c.setFont("Helvetica", 5.2)
    c.setFillColor(RED)
    c.drawCentredString(x + 0.85 * scale, y + h - 1.12 * scale, "guard/reach envelope - survey")

    # Table T4 / WA-3. 127 cm along the south wall and 70 cm deep.
    equipment(c, x + 1.55 * scale, y, 1.27 * scale, 0.70 * scale, "WA-3 / T4\n70 x 127 cm\nASSEMBLY + TEST", PALE_TEAL)

    # Table T1 / WA-1. Rotated so 70 cm projects from the north wall.
    equipment(c, x + 5.75 * scale, y + h - 0.70 * scale, 0.46 * scale, 0.70 * scale, "WA-1 / T1\n70 x 46 cm\nP2S", PALE_ORANGE)

    # Table T3 / WA-4. L shape near the east control wall.
    wa4_x = x + 5.15 * scale
    equipment(c, wa4_x, y, 0.65 * scale, 0.70 * scale, "WA-4\nRECEIVE", PALE_BLUE)
    equipment(c, wa4_x + 0.65 * scale, y, 1.20 * scale, 0.55 * scale, "T3 / CONTROL\n120 x 55 cm", PALE_BLUE)
    c.setStrokeColor(PURPLE)
    c.setLineWidth(3)
    c.line(x + w, y + 0.1 * scale, x + w, y + 0.9 * scale)
    c.setFillColor(PURPLE)
    c.setFont("Helvetica", 5.2)
    c.drawRightString(x + w - 3, y + 0.95 * scale, "existing wall display / rack zone")

    # Transfer route.
    c.setStrokeColor(TEAL)
    c.setFillColor(TEAL)
    c.setLineWidth(1.5)
    route_y = y + 1.16 * scale
    c.line(x + 1.55 * scale, route_y, x + 5.55 * scale, route_y)
    c.line(x + 5.55 * scale, route_y, x + 5.45 * scale, route_y + 4)
    c.line(x + 5.55 * scale, route_y, x + 5.45 * scale, route_y - 4)
    c.setFont("Helvetica-Bold", 5.5)
    c.drawCentredString(x + 3.55 * scale, route_y + 4, "central transfer and evacuation route - width to be measured")

    dimension(c, x, y + h + 14, x + w, y + h + 14, "7.00 m working envelope (derived; verify)")
    dimension(c, x - 12, y, x - 12, y + h, "2.25 m derived internal width")


def overview_page(c: canvas.Canvas) -> None:
    page_header(c, "PLAN", "TinyHouse work-area floor plan", "Four work areas | four physical tables", 1)
    panel(c, 10 * mm, 20 * mm, 190 * mm, 160 * mm, "Proposed physical placement", PALE)
    draw_floorplan(c, 19 * mm, 58 * mm, 170 * mm)
    draw_paragraph(
        c,
        "<b>Coordinate convention.</b> West is the robot end. East is the control and network-rack end. "
        "The drawing uses a 7.00 x 2.25 m derived internal envelope. The source documents conflict on the external width: "
        "the scanned specification states 2.55 m while the concept text states 2.50 m. A measured survey controls installation.",
        18 * mm,
        48 * mm,
        174 * mm,
        SMALL,
    )

    panel(c, 205 * mm, 103 * mm, 82 * mm, 77 * mm, "WA-to-table mapping", WHITE)
    mapping = [
        ["WA", "Table footprint", "Assignment reason"],
        ["WA-1", "T1: 70 x 46 cm; rotated", "Compact machine station at upper-right. Rotation gives 70 cm nominal printer depth. Clearance remains unverified."],
        ["WA-2", "T2: 80 x 120 cm", "Largest rectangular surface for PAROL6 base, instrumented bins, and guarded observation."],
        ["WA-3", "T4: 70 x 127 cm", "Long surface separates assembly mat from test and calibration equipment."],
        ["WA-4", "T3: 65 x 70 + 120 x 55 cm", "L shape separates receiving/scale work from control, scheduling, and disclosure work."],
    ]
    draw_data_table(c, mapping, 210 * mm, 164 * mm, [12 * mm, 23 * mm, 41 * mm], TABLE_CELL_SMALL)

    panel(c, 205 * mm, 20 * mm, 82 * mm, 78 * mm, "Design basis and non-negotiable checks", WHITE)
    notes = (
        "<b>Existing infrastructure.</b> Current photographs show the 55-inch wall display, management desk, equipment rack, "
        "Annke camera, outlets, fire extinguisher, and first-aid point. The placement preserves the central entrance zone.<br/><br/>"
        "<b>Safety boundary.</b> Research sensors never replace printer interlocks, robot guarding, emergency stops, fire controls, "
        "thermal protection, or battery protection.<br/><br/>"
        "<b>Before installation.</b> Measure every table, machine footprint, service clearance, robot reach, guard footprint, door swing, "
        "evacuation width, outlet load, network drop, and ventilation path. Approve one floor-plan revision before equipment is fixed.<br/><br/>"
        "<b>Evidence rule.</b> A missing or conflicting required signal creates uncertainty or manual review. The system must not infer a successful event from a secondary sensor alone."
        "<br/><br/><b>Source set.</b> concepts/tinyhouse-workarea-cards.pdf; concepts/tables.png; concepts/floorplans.pdf; "
        "concepts/Overview.md; docs/EDV TinyHouse.xlsx; docs/sensors, mqtt, network, infrastructure, and current TinyHouse photographs."
    )
    draw_paragraph(c, notes, 210 * mm, 88 * mm, 72 * mm, SMALL)
    c.showPage()


WORKAREAS = {
    "WA-1": {
        "name": "Print / base quality",
        "station": "Combines ST-10 additive manufacturing with base inspection and reprint interaction",
        "input": "print job + approved material",
        "output": "accepted base",
        "table": "T1 - 70 x 46 cm; rotate so 70 cm projects from the wall",
        "warning": "HOLD POINT: verify the P2S footprint, rear cable bend, door/spool access, ventilation, fire control, and manufacturer service clearance. If the complete envelope does not fit, the WA-to-table mapping must be revised.",
        "bom": [
            ["Item", "Qty / source state", "Placement and role"],
            ["Bamboo Lab P2S printer", "1 documented; verify model and API", "Centered in a provisional 46 x 45 cm reserved envelope. Primary machine evidence comes from local telemetry."],
            ["Plug-level energy meter", "1 acquisition gap", "Between approved outlet and printer. Read real power in W and cumulative job energy in kWh."],
            ["MLX90640 thermal array + ESP32 C6", "1 of 2 documented; verify", "Rigid overhead/rear mount. Observe build-area heating and cooling without controlling the printer."],
            ["XIAO ESP32S3 Sense or IMX335 camera", "1 documented candidate; verify", "Overhead workpiece-only view. Detect base present/removed. Mask people and adjacent stations."],
            ["Raspberry Pi 5 + PoE + NVMe", "1 from inventory; assign", "Under-table ventilated enclosure. Printer adapter, meter adapter, timestamping, MQTT, and local buffer."],
            ["11-inch tablet or compact wall UI", "1 Samsung tablet documented", "Wall arm above inspection edge. Inspection, review, release, and reprint-energy interaction."],
            ["Inspection pad + optional 30 kg load cell", "1 pad; load cell available", "Front inspection zone. Weight change corroborates base placement and removal."],
            ["Material and tools", "Acquire/assign", "Approved filament, dry container, labeled spool, scraper, calipers, deburring tool, gloves per material procedure."],
        ],
        "rates": [
            ["Channel", "Commissioning target", "Retention / processing"],
            ["Printer adapter", "State on change + 1 Hz heartbeat", "Keep lifecycle records and faults. Bind authorization ID, work order, job ID, design revision, and material lot."],
            ["Energy meter", "1 Hz power; monotonic energy counter", "Keep interval summary and job total. Raw samples remain local under the approved retention policy."],
            ["MLX90640", "4 Hz feature extraction", "Keep max/mean/region features. Raw frames remain local unless the study protocol approves retention."],
            ["Workpiece camera", "5 frames/s local inference", "Keep presence episodes and approved evidence frames only. Exclude faces and adjacent work areas."],
            ["Inspection UI / load cell", "Explicit click; 10 Hz local weight", "The explicit decision is authoritative. Weight is supporting evidence only."],
        ],
        "events": [
            ["Activity", "Authoritative trigger", "Supporting observation", "Required event and object fields", "Failure or conflict rule"],
            ["Print base", "Printer adapter reports target job RUNNING after a valid print-authorization record.", "Power rises above calibrated idle band; thermal region warms; job ID matches UI.", "PrintStarted: event_id, source/ingestion time, run, work order, authorization, print job, base component, size, design revision, printer, material lot.", "No authorization or mismatched job ID blocks the event. Power alone never proves a start."],
            ["Print base complete", "Printer adapter reports COMPLETED for the same job ID.", "Power returns to idle; thermal cooling episode; camera shows base present.", "PrintCompleted: printer result, measured energy kWh, duration, adapter version, evidence IDs, quality flags.", "Fault, missing job identity, or supporting-sensor disagreement creates Print evidence conflict and manual review."],
            ["Inspect base", "Operator opens the inspection task for the linked base after the cooling hold point.", "Camera shows one base in the inspection region; optional load cell shows a stable positive transition.", "InspectionStarted: inspection ID, base ID, operator role/pseudonym, checklist version, evidence references.", "Missing base identity blocks the decision. Camera presence never identifies the component by itself."],
            ["Review base", "Operator submits PASS, REVIEW, or FAIL plus a defect code through the UI.", "Approved close-up evidence frame and dimensions from calipers may support the decision.", "BaseReviewed: decision, defect code, measurement values and units, procedure version, evidence IDs.", "An incomplete checklist or missing defect code for FAIL remains an open human task."],
            ["Schedule reprint energy", "Versioned scheduler records a new decision from a fresh complete energy snapshot.", "Inverter/BMS freshness and printer resource state are visible through the WA-1 UI.", "ReprintScheduled: schedule ID, input snapshot IDs, reprintEnergyKWh, reserveEnergyKWh, selected window, policy version.", "Do not reuse the prior print budget. Stale or incomplete energy data rejects the schedule."],
            ["Release base", "Operator selects RELEASE after PASS and identity checks.", "Camera or load-cell transition confirms removal from the station.", "BaseReleased: base ID, inspection ID, decision ID, destination WA-2/WA-3, source/ingestion time.", "Removal without release is an exception. Release without prior PASS is blocked."],
        ],
        "channels": "Primary: printer lifecycle + explicit inspection UI. Corroboration: plug meter + thermal array + workpiece camera + optional load cell. Edge: EMQX004 is the proposed node assignment in the concept. MQTT topic: tinyhouse/bayreuth/WA-1/<device>/<category>. Authoritative events: tinyhouse/bayreuth/activity/WA-1/<activity> with QoS 1 and event-ID deduplication.",
    },
    "WA-2": {
        "name": "Kit preparation",
        "station": "ST-30 robot kit preparation at the west end",
        "input": "labeled electronics bins",
        "output": "prepared electronics kit",
        "table": "T2 - 80 x 120 cm",
        "warning": "HOLD POINT: the table is only the work surface. A competent safety review must define the PAROL6 reach, guard, pinch and ejection hazards, mounting loads, emergency stop, safe reset, and human exclusion area before powered motion.",
        "bom": [
            ["Item", "Qty / source state", "Placement and role"],
            ["PAROL6 robot arm + controller", "1 documented; verify", "Bolted to the rear-center structural zone after load review. Controller lifecycle is the primary machine evidence."],
            ["Four instrumented component bins", "4 proposed; load cells available", "Left and right corners outside the central pickup/drop zone. Each bin has a unique component and sensor ID."],
            ["Prepared-kit tray + load cell", "1 proposed", "Front-center drop zone. Stable positive weight and camera presence corroborate kit completion."],
            ["IMX335 or XIAO camera", "1 documented candidate; verify", "Rigid overhead view of bins, gripper workspace, and kit tray. Exclude the operator area."],
            ["Guard door input + safety E-stop", "Acquire and validate independently", "E-stop at the accessible front edge. Guard input enters the safety controller; research receives read-only state."],
            ["Raspberry Pi 5 + PoE + NVMe", "1 from inventory; assign", "Outside the reach envelope in a protected under-table enclosure. Controller adapter and sensor gateway."],
            ["Robot-status tablet / beacon", "1 tablet available; beacon acquire", "Outside the guard. Shows robot job, expected kit, fault, and safe-state messages."],
            ["Materials", "From inventory and work order", "Nano/ESP board, sensor kit parts, wires, connectors, buttons, display/keypad as configured. Use labeled bins and ESD-safe tray."],
        ],
        "rates": [
            ["Channel", "Commissioning target", "Retention / processing"],
            ["PAROL6 controller adapter", "State on change + 10 Hz motion-state poll if supported", "Keep job lifecycle, controller faults, program version, and safe-state transitions. Do not derive safety state from vision."],
            ["Bin and tray load cells", "20 Hz local; 10 Hz filtered state", "Tare before each run. Store raw windows around transitions and stable deltas with units and calibration ID."],
            ["Workpiece camera", "10 frames/s local inference", "Keep part/kit presence episodes. Raw video remains local by default."],
            ["Guard and E-stop mirror", "State on change + 1 Hz heartbeat", "Read-only research copy. The independent safety circuit controls motion."],
        ],
        "events": [
            ["Activity", "Authoritative trigger", "Supporting observation", "Required event and object fields", "Failure or conflict rule"],
            ["Robot kit start", "Controller adapter reports the bound robot-job ID STARTED while the independent safety system permits motion.", "Expected bins have stable pre-job weights; camera sees clear pickup and tray regions.", "RobotKitStarted: event_id, source/ingestion time, run, work order, robot job, program version, robot, expected kit/BOM, bin baselines.", "Wrong job, missing work-order binding, open guard, or active E-stop blocks motion and event authority."],
            ["Pick component", "Controller program reports the named pick step for the bound robot job.", "The matching bin shows the calibrated negative delta; camera detects transfer from that bin.", "PartPicked: component type, bin ID, delta g, expected quantity, controller step, evidence IDs.", "A controller step without the expected bin delta creates Kit evidence conflict. Camera never overrides a controller fault."],
            ["Place in kit", "Controller program reports the named place step.", "Kit-tray weight rises by the expected tolerance band and camera detects part presence.", "PartPlaced: kit ID, component type, tray ID, delta g, sequence index, evidence IDs.", "Unexpected or duplicate part delta pauses the job and opens manual review."],
            ["Robot kit complete", "Controller reports SUCCESS for the same robot-job ID.", "All expected bin deltas occurred once; tray weight and camera indicate a complete kit.", "KitPrepared: kit ID, robot result, observed BOM, start/end times, calibration IDs, evidence completeness.", "Controller success without matching bin/tray evidence remains a candidate. No authoritative KitPrepared event is emitted."],
            ["Robot fault / abort", "Controller reports FAULT, STOPPED, or ABORTED.", "Guard and E-stop state, last completed step, load-cell state, and camera zone state provide context.", "RobotJobFailed: fault code, controller state, last step, safe-state references, affected objects.", "The failure remains a failure. Research sensors cannot clear or override the fault."],
            ["Move to WA-3", "Operator confirms transfer of the identified kit after KitPrepared.", "Kit tray shows stable removal; WA-3 camera or mat later confirms arrival.", "KitTransferred: kit ID, from WA-2, to WA-3, source/ingestion time, operator role.", "Removal without confirmation is an exception. WA-3 arrival must reference the same kit ID."],
        ],
        "channels": "Primary: PAROL6 controller lifecycle. Required corroboration: calibrated bin and kit-tray deltas. Context: workpiece camera. Safety: independent guard and E-stop with a read-only event mirror. Edge: EMQX005 is the proposed node assignment. MQTT topic: tinyhouse/bayreuth/WA-2/<device>/<category>.",
    },
    "WA-3": {
        "name": "Assembly / test",
        "station": "Combines ST-40 human assembly and ST-50 test/calibration",
        "input": "identified base + lid + prepared kit",
        "output": "approved sensor node",
        "table": "T4 - 70 x 127 cm",
        "warning": "PRIVACY AND QUALITY HOLD POINT: approve the workpiece-only camera mask and retention period. Approve the test-procedure version, electrical limits, reference loads, calibration method, and rework route before a deployment approval can be authoritative.",
        "bom": [
            ["Item", "Qty / source state", "Placement and role"],
            ["ESD-safe assembly mat + thin-film pressure sensors", "1 mat; 4-8 of 20 sensors", "Left 75 cm zone. Detect first part arrival, placement sequence, and clear-table state."],
            ["Instrumented part trays", "3 proposed; load cells available", "Rear-left: base, lid, and kit staging. Each tray has a unique sensor and component binding."],
            ["Workpiece camera", "1 XIAO or IMX335 candidate", "Overhead center. View hands only when unavoidable; crop faces and other work areas."],
            ["Arduino Nano serial test jig", "1 of 10 documented; build", "Right 42 cm test zone. USB serial to the Pi is the documented current path."],
            ["Reference scale + certified references", "1 network/local scale candidate; references acquire", "Right-front. Finished-node weight and calibration checks. Record tare and reference IDs."],
            ["Raspberry Pi 5 + PoE + NVMe", "1 from inventory; assign", "Under-table enclosure. Serial receiver, evidence fusion, MQTT, time, and local buffer."],
            ["Tablet/UI + approval button", "1 tablet/button available; configure", "Rear-right outside tool area. Shows checklist, test result, rework, and approval."],
            ["Tools and consumables", "Acquire/assign", "ESD wrist point, precision drivers, tweezers, cutters, wire stripper, crimper, multimeter, labels, fasteners, approved cable set."],
        ],
        "rates": [
            ["Channel", "Commissioning target", "Retention / processing"],
            ["Pressure mat", "50 Hz local; 10 Hz state features", "Record baseline, occupied zones, transitions, confidence, and sensor-health flags."],
            ["Part trays / reference scale", "20 Hz local; 10 Hz filtered state", "Record tare, stable deltas, final weight, unit, calibration ID, and uncertainty."],
            ["Workpiece camera", "10 frames/s local inference", "Keep part-state episodes and approved evidence frames. Raw video remains local by default."],
            ["Nano USB serial test jig", "Procedure-defined samples; timestamp every record", "Keep complete test and calibration record with firmware, procedure, and reference versions."],
            ["Approval UI", "Explicit action only", "Approval is human-authoritative and cannot be inferred from product removal or a green test indicator."],
        ],
        "events": [
            ["Activity", "Authoritative trigger", "Supporting observation", "Required event and object fields", "Failure or conflict rule"],
            ["Assemble node start", "Operator confirms matched base, lid, kit, size, and design revision; first identified part enters the assembly mat.", "Pressure transition plus correct tray removal and camera part presence.", "AssemblyStarted: event_id, source/ingestion time, run, work order, product unit, base, lid, kit, operator role, procedure version.", "Identity mismatch blocks assembly. Missing corroboration produces an uncertain candidate, not a guessed start."],
            ["Assembly step", "Operator advances a versioned checklist step or the test jig records a required connection step.", "Pressure-zone sequence, tray deltas, and workpiece camera state support the step.", "AssemblyStepCompleted: step ID, component IDs, tool/checklist version, evidence IDs, confidence and freshness.", "Unexpected order or missing part opens manual review. Vision alone never marks a checklist step complete."],
            ["Assemble node complete", "Operator confirms the final assembly checklist with all required component links.", "Expected tray deltas occurred; camera sees one closed node; pressure mat returns to the expected final state.", "AssemblyCompleted: product unit, component links, start/end times, checklist result, evidence completeness.", "Incomplete component links or missing confirmation blocks completion."],
            ["Test and calibrate", "Versioned Nano/serial procedure starts for the bound product-unit ID.", "Reference-scale state and camera presence confirm the intended unit remains in the test zone.", "TestStarted/TestResult: procedure, firmware, jig, product unit, measured values, units, limits, pass/fail, calibration references.", "Communication loss, missing unit identity, or missing limit version produces TEST INVALID, not PASS."],
            ["Resolve failure", "Operator records one disposition after a FAIL: rework, scrap, or engineering review.", "Failure code, serial trace, and approved evidence are attached.", "FailureResolved: test ID, disposition, defect code, operator role, notes/evidence references.", "A failed test cannot proceed directly to approval."],
            ["Rework sensor", "Operator starts a versioned rework instruction for the same product unit.", "Mat/tray/camera transitions support the rework interval.", "ReworkStarted/ReworkCompleted: rework ID, affected component, instruction version, start/end, outcome.", "Every rework requires a new test record. The prior failed record remains immutable."],
            ["Approve deployment", "Operator selects APPROVE only after the latest complete test and calibration record is PASS.", "Final scale and camera presence support product identity; they do not authorize approval.", "DeploymentApproved: product unit, passing test ID, calibration ID, approver role, policy/procedure versions, timestamp.", "Missing/failed/latest-invalid test blocks approval. Product removal without approval is an exception."],
        ],
        "channels": "Primary: explicit human checklist + versioned serial test record + explicit approval. Corroboration: pressure mat + instrumented trays + workpiece camera + reference scale. Edge: EMQX006 is the proposed node assignment. Existing USB serial is required; RX/TX remains a separate unverified development path.",
    },
    "WA-4": {
        "name": "Control / lid",
        "station": "Combines ST-00 control/energy with ST-20 lid receiving and verification",
        "input": "Munich lid + current energy state",
        "output": "verified lid + process record",
        "table": "T3 - L shape: 65 x 70 cm receiving wing + 120 x 55 cm control wing",
        "warning": "DATA HOLD POINT: live scheduling is blocked until the inverter/BMS interface, units, timestamp freshness, protected reserve, and measured printer-energy values are verified. The broker role, authentication, station ACLs, and Pi serial receiver also require commissioning.",
        "bom": [
            ["Item", "Qty / source state", "Placement and role"],
            ["Management PC / Lenovo laptop + keyboard/mouse", "1 documented", "Control wing. Register run, topology, schedule, Munich interaction, disclosure, and outcome."],
            ["Samsung Flip Pro 55-inch wall display", "1 documented and photographed", "Wall-mounted behind control wing. Shared process state only; no private camera feed by default."],
            ["Inverter and BMS read-only adapter", "Acquisition/integration gap", "Rack/wall service zone. Provide PV power kW, battery state of charge %, usable energy kWh, health, and freshness."],
            ["Network scale or 30 kg load cells", "Scale at 192.168.1.106 unverified", "Receiving wing. Tare before delivery. Detect lid arrival and removal."],
            ["XIAO workpiece camera", "1 candidate; verify", "Overhead receiving wing. Lid presence and configuration cues; workpiece-only privacy mask."],
            ["2D barcode scanner + manual fallback", "Scanner acquisition gap", "Front edge of receiving wing. Capture shipment, lid, size, and design revision IDs."],
            ["Raspberry Pi 5 + PoE + NVMe", "1 from inventory; assign", "Under control wing. Scale/camera adapters, local buffer, timestamping, MQTT, and event fusion."],
            ["Receiving materials", "Acquire/assign", "Labeled inbound tray, anti-static bag area, quarantine bin, inspection light, calipers, defect labels, acceptance/replacement button."],
        ],
        "rates": [
            ["Channel", "Commissioning target", "Retention / processing"],
            ["Inverter/BMS adapter", "1 Hz sampling; snapshot transaction on demand", "Reject a schedule input if any required field is missing, stale, has wrong units, or lacks adapter health."],
            ["Network scale/load cells", "20 Hz local; 10 Hz filtered state", "Tare for every receiving session. Record stable transitions, unit, calibration ID, and device health."],
            ["Workpiece camera", "5 frames/s local inference", "Keep lid-presence and configuration features. Raw frames remain local under approved retention."],
            ["ID scanner / manual entry", "One transaction per item", "Validate check digit/schema when available. Require explicit confirmation for manual entry."],
            ["Management UI + broker", "Audit every decision; 1 Hz health", "Keep source and ingestion time, actor role, policy version, evidence IDs, and delivery/collaboration message IDs."],
        ],
        "events": [
            ["Activity", "Authoritative trigger", "Supporting observation", "Required event and object fields", "Failure or conflict rule"],
            ["Register run", "Management UI commits a new experiment-run and work-order identity.", "Broker, edge health, clock offset, consent/policy references, and resource state are green.", "RunRegistered: event_id, source/ingestion time, run, work order, due window, design revision, requested sensor configuration.", "Duplicate identity or missing mandatory fields rejects registration."],
            ["Select topology", "Versioned rule/UI records LOCAL or DISTRIBUTED for the work order.", "Munich availability and local resource status are attached as inputs.", "TopologySelected: decision ID, topology, input IDs, policy version, actor/service.", "A rejected Munich commitment must create a new local schedule for the extra lid print."],
            ["Read solar and battery", "Adapter returns one complete timestamped snapshot transaction.", "PV, battery, adapter health, clock offset, and freshness checks pass.", "EnergySnapshotRead: PV kW, forecast kWh, battery SOC %, usable kWh, committed kWh, resource state, units, source IDs.", "Stale, incomplete, inconsistent-unit, or unhealthy readings reject the snapshot."],
            ["Optimize schedule", "Versioned scheduler evaluates candidate windows with the documented formula and ordered large/standard rules.", "Input object IDs and resource state reproduce the decision.", "ScheduleEvaluated: schedule ID, snapshot IDs, availableRenewableEnergyKWh, reserve, job estimates, eligible windows, objective order, policy version.", "No invented reserve or energy estimate is allowed. Missing verified values block interpretation."],
            ["Select standard / large", "Scheduler records the first eligible ordered rule and selected configuration.", "UI displays both thresholds and the selected candidate window.", "ConfigurationSelected: size, threshold inputs, schedule ID, due window, decision trace.", "The large estimate must exceed the standard estimate. Mutually exclusive conditions must be preserved."],
            ["Request matching lid", "Cross-site coordinator sends a commitment request with size and design revision.", "Message receipt/acknowledgement and correlation ID are recorded.", "LidRequested: commitment ID, work order, size, revision, due window, sender/recipient sites, disclosure fields.", "Do not share raw energy or video. Missing acknowledgement remains pending."],
            ["Evaluate decision / fallback", "Coordinator records Munich ACCEPT or REJECT. REJECT creates LOCAL fallback.", "Correlation ID matches the outstanding request.", "CommitmentEvaluated/TopologyFallbackSet: decision, commitment ID, reason code, new topology, timestamp.", "Late or duplicate decisions are deduplicated. Fallback cannot reuse the distributed energy budget."],
            ["Receive lid", "One stable positive scale transition and one matching scanned/manual identifier record occur in the receiving session.", "Camera shows one lid in the receiving region.", "LidReceived: shipment, lid, commitment, weight g, size, revision, scale/camera/ID evidence IDs.", "Weight without identity or identity without stable presence creates manual review, not receipt."],
            ["Verify lid", "Operator submits the versioned identity/configuration/quality checklist.", "Scale and camera support presence, size cues, and removal state.", "LidVerified: lid ID, expected/observed size, revision, checklist, decision, defect code, operator role.", "Mismatch creates ReplacementRequired. Camera classification never overrides the identifier record."],
            ["Accept delivery", "Operator selects ACCEPT after LidVerified is PASS.", "Scale remains stable until acceptance and later confirms removal to WA-3.", "DeliveryAccepted: shipment, lid, verification ID, work order, destination WA-3.", "Acceptance is blocked after mismatch, failed inspection, or missing identity."],
            ["Request replacement", "Operator selects REPLACE with a coded mismatch or defect.", "Quarantine-bin placement is optionally observed by load cell/camera.", "ReplacementRequested: original lid, commitment, reason, evidence, new request correlation.", "The replacement receives a new component identity. The commitment lineage remains linked."],
            ["Apply disclosure", "Versioned disclosure gateway records ALLOW or DENY for the candidate outcome payload.", "UI shows the exact fields selected for sharing.", "DisclosureApplied: policy version, input event IDs, allowed fields, removed fields, decision and actor/service.", "No payload leaves the site before ALLOW. Raw video, raw sensor streams, and direct identity stay local by default."],
            ["Share outcome", "Coordinator transmits the minimized approved milestone and records acknowledgement.", "Broker/transport health and correlation ID support delivery status.", "OutcomeShared: run, work order, milestone, approved fields, disclosure decision, message/correlation ID, source/ingestion time.", "Transmission failure remains pending/retryable. Do not fabricate remote receipt."],
        ],
        "channels": "Primary: management/scheduler/coordinator audit logs + identifier transaction + explicit inspection decision. Corroboration: inverter/BMS adapter health + scale + workpiece camera. Edge: EMQX004 is the proposed ST-00 assignment and EMQX005 the proposed ST-20 assignment; one WA-4 table may use both logical adapters. Pilot broker selection remains a commissioning decision.",
    },
}


def draw_layout(c: canvas.Canvas, wa: str, data: dict) -> None:
    x0, y0, w, h = 18 * mm, 40 * mm, 140 * mm, 118 * mm
    c.setFillColor(colors.HexColor("#E7D8BF"))
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.5)

    if wa == "WA-1":
        table_x, table_y, table_w, table_h = x0 + 37 * mm, y0, 58 * mm, 92 * mm
        c.roundRect(table_x, table_y, table_w, table_h, 3 * mm, fill=1, stroke=1)
        dimension(c, table_x, table_y - 8, table_x + table_w, table_y - 8, "46 cm along wall")
        dimension(c, table_x - 9, table_y, table_x - 9, table_y + table_h, "70 cm depth")
        equipment(c, table_x + 8 * mm, table_y + 38 * mm, 42 * mm, 45 * mm, "P2S printer\nprovisional envelope", PALE_ORANGE, True)
        equipment(c, table_x + 4 * mm, table_y + 5 * mm, 27 * mm, 25 * mm, "inspection pad\n+ load cell", PALE_TEAL)
        equipment(c, table_x + 34 * mm, table_y + 7 * mm, 19 * mm, 20 * mm, "tools +\nmaterial", PALE_BLUE)
        equipment(c, table_x + 2 * mm, table_y + 86 * mm, 16 * mm, 8 * mm, "Pi", PALE_BLUE)
        equipment(c, table_x + 38 * mm, table_y + 86 * mm, 17 * mm, 8 * mm, "meter", PALE_ORANGE)
        equipment(c, table_x + 18 * mm, table_y + 88 * mm, 19 * mm, 7 * mm, "camera + IR", colors.HexColor("#F2EAFE"))
        equipment(c, table_x + 58 * mm, table_y + 50 * mm, 22 * mm, 32 * mm, "wall tablet\ninspection UI", PALE_BLUE)
        c.setFillColor(RED)
        c.setFont("Helvetica-Bold", 6)
        c.drawString(table_x + 60 * mm, table_y + 40 * mm, "service clearance")
        c.drawString(table_x + 60 * mm, table_y + 35 * mm, "must be measured")
    elif wa == "WA-2":
        table_x, table_y, table_w, table_h = x0 + 12 * mm, y0 + 13 * mm, 112 * mm, 75 * mm
        c.roundRect(table_x, table_y, table_w, table_h, 3 * mm, fill=1, stroke=1)
        dimension(c, table_x, table_y - 8, table_x + table_w, table_y - 8, "120 cm")
        dimension(c, table_x - 9, table_y, table_x - 9, table_y + table_h, "80 cm")
        equipment(c, table_x + 43 * mm, table_y + 27 * mm, 28 * mm, 28 * mm, "PAROL6\nbase", PALE_RED)
        for bx, by, label in [(5, 47, "bin A\nload cell"), (5, 15, "bin B\nload cell"), (88, 47, "bin C\nload cell"), (88, 15, "bin D\nload cell")]:
            equipment(c, table_x + bx * mm, table_y + by * mm, 19 * mm, 15 * mm, label, PALE_BLUE)
        equipment(c, table_x + 40 * mm, table_y + 4 * mm, 34 * mm, 16 * mm, "kit tray + load cell", PALE_TEAL)
        equipment(c, table_x + 47 * mm, table_y + 66 * mm, 20 * mm, 7 * mm, "camera", colors.HexColor("#F2EAFE"))
        equipment(c, table_x + 94 * mm, table_y - 10 * mm, 16 * mm, 10 * mm, "E-stop", PALE_RED)
        c.setStrokeColor(RED)
        c.setDash(4, 3)
        c.circle(table_x + 57 * mm, table_y + 41 * mm, 54 * mm, fill=0, stroke=1)
        c.setDash()
        c.setFillColor(RED)
        c.setFont("Helvetica-Bold", 6)
        c.drawCentredString(table_x + 57 * mm, table_y + 102 * mm, "guard/reach envelope - survey and certify")
    elif wa == "WA-3":
        table_x, table_y, table_w, table_h = x0 + 4 * mm, y0 + 23 * mm, 128 * mm, 70 * mm
        c.roundRect(table_x, table_y, table_w, table_h, 3 * mm, fill=1, stroke=1)
        dimension(c, table_x, table_y - 8, table_x + table_w, table_y - 8, "127 cm")
        dimension(c, table_x - 9, table_y, table_x - 9, table_y + table_h, "70 cm")
        equipment(c, table_x + 5 * mm, table_y + 8 * mm, 68 * mm, 43 * mm, "ESD assembly mat\npressure zones P1-P8", PALE_TEAL)
        equipment(c, table_x + 7 * mm, table_y + 55 * mm, 18 * mm, 11 * mm, "base tray", PALE_BLUE)
        equipment(c, table_x + 28 * mm, table_y + 55 * mm, 18 * mm, 11 * mm, "lid tray", PALE_BLUE)
        equipment(c, table_x + 49 * mm, table_y + 55 * mm, 22 * mm, 11 * mm, "kit tray", PALE_BLUE)
        equipment(c, table_x + 78 * mm, table_y + 32 * mm, 24 * mm, 24 * mm, "Nano USB\ntest jig", PALE_ORANGE)
        equipment(c, table_x + 105 * mm, table_y + 31 * mm, 18 * mm, 25 * mm, "reference\nscale", PALE_BLUE)
        equipment(c, table_x + 79 * mm, table_y + 7 * mm, 42 * mm, 18 * mm, "approval UI + tools", PALE_RED)
        equipment(c, table_x + 53 * mm, table_y + 64 * mm, 22 * mm, 7 * mm, "camera", colors.HexColor("#F2EAFE"))
    else:
        table_x, table_y = x0 + 8 * mm, y0 + 20 * mm
        c.setFillColor(colors.HexColor("#E7D8BF"))
        c.roundRect(table_x, table_y, 47 * mm, 64 * mm, 3 * mm, fill=1, stroke=1)
        c.roundRect(table_x + 47 * mm, table_y, 78 * mm, 50 * mm, 3 * mm, fill=1, stroke=1)
        dimension(c, table_x, table_y - 8, table_x + 47 * mm, table_y - 8, "65 cm wing")
        dimension(c, table_x + 47 * mm, table_y - 8, table_x + 125 * mm, table_y - 8, "120 cm wing")
        equipment(c, table_x + 5 * mm, table_y + 25 * mm, 35 * mm, 29 * mm, "network scale\nreceiving tray", PALE_TEAL)
        equipment(c, table_x + 7 * mm, table_y + 7 * mm, 15 * mm, 12 * mm, "ID scanner", PALE_ORANGE)
        equipment(c, table_x + 25 * mm, table_y + 7 * mm, 16 * mm, 12 * mm, "quarantine", PALE_RED)
        equipment(c, table_x + 19 * mm, table_y + 57 * mm, 15 * mm, 8 * mm, "camera", colors.HexColor("#F2EAFE"))
        equipment(c, table_x + 54 * mm, table_y + 10 * mm, 40 * mm, 29 * mm, "management PC\nkeyboard + mouse", PALE_BLUE)
        equipment(c, table_x + 98 * mm, table_y + 8 * mm, 20 * mm, 31 * mm, "Pi +\nadapters", PALE_ORANGE)
        equipment(c, table_x + 59 * mm, table_y + 54 * mm, 52 * mm, 20 * mm, "55-inch wall display", colors.HexColor("#E8EAF6"))
        c.setFont("Helvetica-Bold", 6)
        c.setFillColor(PURPLE)
        c.drawString(table_x + 90 * mm, table_y + 58 * mm, "inverter/BMS + rack nearby")


def workarea_layout_page(c: canvas.Canvas, wa: str, data: dict, page_no: int) -> None:
    page_header(c, wa, f"{data['name']} - Top view and equipment placement", data["station"], page_no)
    tag(c, 11 * mm, PAGE_H - 27 * mm, "INPUT", BLUE)
    draw_paragraph(c, data["input"], 36 * mm, PAGE_H - 22.5 * mm, 58 * mm, BOX_HEAD)
    tag(c, 108 * mm, PAGE_H - 27 * mm, "OUTPUT", TEAL)
    draw_paragraph(c, data["output"], 133 * mm, PAGE_H - 22.5 * mm, 55 * mm, BOX_HEAD)
    tag(c, 202 * mm, PAGE_H - 27 * mm, "TABLE", ORANGE)
    draw_paragraph(c, data["table"], 227 * mm, PAGE_H - 22.5 * mm, 58 * mm, SMALL)

    panel(c, 10 * mm, 20 * mm, 146 * mm, 145 * mm, "Top-view table plan", PALE)
    draw_layout(c, wa, data)
    draw_paragraph(c, f"<b>Installation gate.</b> {data['warning']}", 16 * mm, 34 * mm, 134 * mm, SMALL)

    panel(c, 161 * mm, 74 * mm, 126 * mm, 91 * mm, "Hardware, tools, and material", WHITE)
    draw_data_table(c, data["bom"], 166 * mm, 150 * mm, [38 * mm, 32 * mm, 47 * mm], TABLE_CELL_SMALL)

    panel(c, 161 * mm, 20 * mm, 126 * mm, 49 * mm, "Sensor mounting and capture targets", WHITE)
    draw_data_table(c, data["rates"], 166 * mm, 55 * mm, [32 * mm, 30 * mm, 55 * mm], TABLE_CELL_SMALL)
    c.showPage()


def workarea_events_page(c: canvas.Canvas, wa: str, data: dict, page_no: int) -> None:
    page_header(c, wa, f"{data['name']} - Event observation matrix", "Every activity needs direct identity and evidence", page_no)
    draw_paragraph(
        c,
        "<b>Authority rule.</b> Machine lifecycle records and explicit human decisions are primary. Physical sensors corroborate presence, transfer, and state. "
        "Every derived record carries a unique event ID, source time, ingestion time, source identifiers, freshness, confidence, and abstraction-policy version.",
        11 * mm,
        PAGE_H - 23 * mm,
        275 * mm,
        SMALL,
    )
    y_top = PAGE_H - 31 * mm
    col_widths = [27 * mm, 55 * mm, 53 * mm, 70 * mm, 72 * mm]
    height = draw_data_table(c, data["events"], 10 * mm, y_top, col_widths, EVENT_CELL)
    note_y = max(19 * mm, y_top - height - 24 * mm)
    if note_y < 50 * mm:
        raise ValueError(f"{wa} event table leaves insufficient space for the verification panels")
    panel(c, 10 * mm, note_y, 277 * mm, 20 * mm, "Station data path and commissioning status", PALE_BLUE)
    draw_paragraph(c, data["channels"], 15 * mm, note_y + 10.5 * mm, 267 * mm, SMALL)

    panel(c, 10 * mm, 20 * mm, 167 * mm, 25 * mm, "Event abstraction path", PALE_TEAL)
    draw_paragraph(
        c,
        "<b>L0 raw:</b> local readings and machine records.  <b>L1 calibrated:</b> state episodes with units, health, and freshness.  "
        "<b>L2 candidate:</b> activity rule matches.  <b>Fusion:</b> identity, primary trigger, and required corroboration agree.  "
        "<b>Authoritative:</b> publish the station event and project it to OCEL 2.0. Conflicts branch to manual review and retain every evidence reference.",
        15 * mm,
        35 * mm,
        157 * mm,
        SMALL,
    )
    panel(c, 182 * mm, 20 * mm, 105 * mm, 25 * mm, "Experiment acceptance gates", PALE_ORANGE)
    draw_paragraph(
        c,
        "100% coverage of mandatory lifecycle and human-decision events in accepted runs. Held-out macro F1 at least 0.90 per station activity set. "
        "Expected-message availability at least 99% per measured activity interval. Edge clock offset at most 250 ms. Approved camera mask and retention policy before camera evidence enters a dataset.",
        187 * mm,
        35 * mm,
        95 * mm,
        SMALL,
    )
    c.showPage()


def build() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=landscape(A4), pageCompression=1)
    c.setTitle("TinyHouse Work-Area Floor Plan and Instrumentation")
    c.setAuthor("TinyHouse Laboratory")
    c.setSubject("Proposed WA-to-table mapping, hardware placement, and event observation design")
    c.setKeywords("TinyHouse, work area, floor plan, sensors, event observation, process mining")

    overview_page(c)
    page_no = 2
    for wa in ("WA-1", "WA-2", "WA-3", "WA-4"):
        workarea_layout_page(c, wa, WORKAREAS[wa], page_no)
        page_no += 1
        workarea_events_page(c, wa, WORKAREAS[wa], page_no)
        page_no += 1
    c.save()
    print(OUTPUT)


if __name__ == "__main__":
    build()
