#!/usr/bin/env python3

"""Build a sanitized inventory for public Google Sheets.

Examples:
  python3 scripts/sheet_inventory.py \
    --sheet office=1HsVBAAd_VMFqpOcslX79Y3c2TSt5cmawGBAGzX5RI-U \
    --sheet posting=1zUkpKOHO4ro35nvcCe-tfI-rNHWf3dJhPIVhPNuEla4
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile


NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

SENSITIVE_KEYWORDS = (
    "idpw",
    "id pw",
    "pw",
    "password",
    "api",
    "apiキー",
    "口座",
    "銀行",
    "生年月日",
    "住所",
    "電話",
    "tel",
    "mail",
    "メール",
    "請求",
    "支払",
    "契約者",
    "氏名",
    "member",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a sanitized sheet inventory.")
    parser.add_argument(
        "--sheet",
        action="append",
        default=[],
        metavar="LABEL=SHEET_ID",
        help="Sheet label and Google Sheets ID. Can be passed multiple times.",
    )
    parser.add_argument(
        "--output",
        help="Optional output markdown path. If omitted, prints to stdout.",
    )
    return parser.parse_args()


def xlsx_bytes(sheet_id: str) -> bytes:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall("a:si", NS):
        parts = [node.text or "" for node in item.findall(".//a:t", NS)]
        strings.append("".join(parts))
    return strings


def cell_value(cell: ET.Element, sst: list[str]) -> str:
    inline = cell.find("a:is", NS)
    if inline is not None:
        return "".join(node.text or "" for node in inline.findall(".//a:t", NS)).strip()

    value = cell.find("a:v", NS)
    if value is None or value.text is None:
        return ""

    raw = value.text.strip()
    if cell.attrib.get("t") == "s" and raw.isdigit():
        index = int(raw)
        if 0 <= index < len(sst):
            return sst[index].strip()
    return raw


def is_sensitive(title: str, headers: list[str]) -> bool:
    haystack = " ".join([title, *headers]).lower()
    return any(keyword in haystack for keyword in SENSITIVE_KEYWORDS)


def workbook_inventory(label: str, sheet_id: str) -> dict:
    data = xlsx_bytes(sheet_id)
    zf = zipfile.ZipFile(io.BytesIO(data))
    sst = shared_strings(zf)

    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}

    sheets = []
    for sheet in workbook.findall("a:sheets/a:sheet", NS):
        title = sheet.attrib["name"]
        rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = rel_map[rel_id]
        if not target.startswith("worksheets/"):
            continue

        worksheet = ET.fromstring(zf.read("xl/" + target))
        rows = worksheet.findall("a:sheetData/a:row", NS)
        first_nonempty: list[str] = []
        for row in rows[:10]:
            values = [cell_value(cell, sst) for cell in row.findall("a:c", NS)]
            if any(value.strip() for value in values):
                first_nonempty = values
                break

        headers = [value for value in first_nonempty if value.strip()]
        sensitive = is_sensitive(title, headers)
        sheets.append(
            {
                "title": title,
                "row_count": len(rows),
                "header_count": len(headers),
                "headers": headers,
                "sensitive": sensitive,
            }
        )

    return {"label": label, "sheet_id": sheet_id, "sheets": sheets}


def to_markdown(inventories: list[dict]) -> str:
    lines = []
    lines.append("# Sheet Inventory")
    lines.append("")
    lines.append(f"Generated: {dt.datetime.now(dt.UTC).isoformat()}")
    lines.append("")
    lines.append("> Sanitized output: values are not included. Sensitive tabs only show metadata.")
    lines.append("")

    for inventory in inventories:
        sheets = inventory["sheets"]
        sensitive_count = sum(1 for sheet in sheets if sheet["sensitive"])

        lines.append(f"## {inventory['label']}")
        lines.append("")
        lines.append(f"- Sheet count: {len(sheets)}")
        lines.append(f"- Sensitive sheet count: {sensitive_count}")
        lines.append("")
        lines.append("| Sheet | Rows | Header columns | Sensitive | Header preview |")
        lines.append("| --- | ---: | ---: | --- | --- |")
        for sheet in sheets:
            preview = "-"
            if not sheet["sensitive"]:
                preview = ", ".join(sheet["headers"][:6]) if sheet["headers"] else "-"
            lines.append(
                f"| {sheet['title']} | {sheet['row_count']} | {sheet['header_count']} | "
                f"{'yes' if sheet['sensitive'] else 'no'} | {preview} |"
            )
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if not args.sheet:
        print("No --sheet arguments supplied.", file=sys.stderr)
        return 1

    inventories = []
    for item in args.sheet:
        if "=" not in item:
            print(f"Invalid --sheet value: {item}", file=sys.stderr)
            return 1
        label, sheet_id = item.split("=", 1)
        inventories.append(workbook_inventory(label.strip(), sheet_id.strip()))

    output = to_markdown(inventories)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output)
            handle.write("\n")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
