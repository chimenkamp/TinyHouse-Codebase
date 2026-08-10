#!/usr/bin/env python3
"""Structural and content checks for the TinyHouse work-area floor-plan PDF."""

from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader


EXPECTED_PAGE_MARKERS = {
    1: ("TinyHouse work-area floor plan", "WA-to-table mapping"),
    2: ("WA-1", "Top view and equipment placement"),
    3: ("WA-1", "Event observation matrix"),
    4: ("WA-2", "Top view and equipment placement"),
    5: ("WA-2", "Event observation matrix"),
    6: ("WA-3", "Top view and equipment placement"),
    7: ("WA-3", "Event observation matrix"),
    8: ("WA-4", "Top view and equipment placement"),
    9: ("WA-4", "Event observation matrix"),
}

REQUIRED_TERMS = (
    "P2S",
    "PAROL6",
    "MLX90640",
    "Raspberry Pi",
    "MQTT",
    "source time",
    "ingestion time",
    "camera",
    "load cell",
    "inverter",
    "battery",
)


def main() -> int:
    pdf_path = Path(sys.argv[1] if len(sys.argv) > 1 else "output/pdf/floorplans_new.pdf")
    if not pdf_path.is_file():
        raise SystemExit(f"missing PDF: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) == 9, f"expected 9 pages, found {len(reader.pages)}"
    assert reader.metadata.title == "TinyHouse Work-Area Floor Plan and Instrumentation"

    all_text = []
    for page_number, page in enumerate(reader.pages, start=1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        assert width > height, f"page {page_number} is not landscape"
        text = page.extract_text() or ""
        assert len(text.strip()) > 500, f"page {page_number} appears blank or incomplete"
        for marker in EXPECTED_PAGE_MARKERS[page_number]:
            assert marker in text, f"page {page_number} lacks marker: {marker}"
        all_text.append(text)

    document_text = "\n".join(all_text)
    for term in REQUIRED_TERMS:
        assert term.casefold() in document_text.casefold(), f"document lacks required term: {term}"

    for prohibited in ("TODO", "TBD", "PLACEHOLDER"):
        assert prohibited not in document_text, f"document contains prohibited marker: {prohibited}"

    print(f"PASS: {pdf_path} has 9 landscape pages and all required content markers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
