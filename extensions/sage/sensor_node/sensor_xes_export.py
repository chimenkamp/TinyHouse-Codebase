import json
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent, tostring

from typing_extensions import Optional


def events_to_xes(events_jsonl: str, output_xes: str, sensor_id: Optional[dict] = None):
    """writes events to xes for each sensor"""
    cases: dict[str, list[dict]] = {}
    with open(events_jsonl, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)

            # Optional nach Sensor filtern
            if sensor_id and event.get("org:resource") != sensor_id:
                continue

            cid = event.get("case:concept:name", "unknown")
            if cid not in cases:
                cases[cid] = []
            cases[cid].append(event)

    # XES aufbauen
    log = Element("log")
    log.set("xes.version", "1849-2016")
    log.set("xes.features", "")
    log.set("xmlns", "http://www.xes-standard.org/")

    # Extensions
    for name, prefix, uri in [
        ("Concept", "concept", "http://www.xes-standard.org/concept.xesext"),
        ("Time", "time", "http://www.xes-standard.org/time.xesext"),
        ("Lifecycle", "lifecycle", "http://www.xes-standard.org/lifecycle.xesext"),
    ]:
        ext = SubElement(log, "extension")
        ext.set("name", name)
        ext.set("prefix", prefix)
        ext.set("uri", uri)

    # Globale Attribute
    _add_global(log, "trace", [("concept:name", "__INVALID__")])
    _add_global(
        log,
        "event",
        [
            ("concept:name", "__INVALID__"),
            ("time:timestamp", "1970-01-01T00:00:00+00:00"),
            ("lifecycle:transition", "complete"),
        ],
    )

    # Classifier
    cl = SubElement(log, "classifier")
    cl.set("name", "Activity")
    cl.set("keys", "concept:name lifecycle:transition")

    # Traces (= Cases)
    for cid, events in sorted(cases.items()):
        trace = SubElement(log, "trace")
        _add_string(trace, "concept:name", cid)

        for ev in sorted(events, key=lambda e: e.get("time:timestamp", "")):
            xes_event = SubElement(trace, "event")
            _add_string(xes_event, "concept:name", ev.get("concept:name", "unknown"))
            _add_date(xes_event, "time:timestamp", ev.get("time:timestamp", ""))
            _add_string(xes_event, "lifecycle:transition", "complete")

            # Sensor-ID as additional attribute
            if "org:resource" in ev:
                _add_string(xes_event, "org:resource", ev["org:resource"])

    # Schreiben
    tree = ElementTree(log)
    indent(tree, space="  ")
    Path(output_xes).parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_xes, encoding="unicode", xml_declaration=True)
    print(f"XES exportiert: {output_xes} ({len(cases)} Cases)")


def _add_global(log, scope, attrs):
    g = SubElement(log, "global")
    g.set("scope", scope)
    for key, default in attrs:
        _add_string(g, key, default)


def _add_string(parent, key, value):
    el = SubElement(parent, "string")
    el.set("key", key)
    el.set("value", str(value))


def _add_date(parent, key, iso_str):
    el = SubElement(parent, "date")
    el.set("key", key)
    el.set("value", iso_str)


_FIELD_TYPES = {
    "concept:name": "string",
    "time:timestamp": "date",
    "lifecycle:transition": "string",
    "org:resource": "string",
    "sensor:type": "string",
    "sensor:unit": "string",
    "sensor:value": "float",
}


def event_to_xes_fragment(event: dict) -> str:
    """
    Converts an event dict into an XES <event> XML fragment.

    Args:
        event: Event dict produced by EventGenerator (or Multisensor composite generator).
        Must contain XES-standard keys like concept:name, time:timestamp.

    Returns:
        XML string of a single <event> element, ready to be appended to an XES log or consumed by a monitoring system

    fields with value None are skipped

    """
    root = Element("event")

    for key, xes_type in _FIELD_TYPES.items():
        value = event.get(key)
        if value is None:
            continue

        el = SubElement(root, xes_type)
        el.set("key", key)
        el.set("value", str(value))
    return tostring(root, encoding="unicode")
