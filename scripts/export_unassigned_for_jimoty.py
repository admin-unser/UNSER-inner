#!/usr/bin/env python3

"""
担当者不在キューの都道府県別件数・戸数をエクスポートする。

ジモティー求人投稿（Claude Code Agent 等）で、地域別の求人コピー作成に利用できます。
出力: JSON / CSV（--format で指定）
"""

from __future__ import annotations

import argparse
import json
import sys

from generate_posting_report import (
    fetch_workbook,
    records,
    sheet_rows,
    to_number,
)

SHEET_ID = "1zUkpKOHO4ro35nvcCe-tfI-rNHWf3dJhPIVhPNuEla4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export unassigned properties by prefecture for ジモティー job postings."
    )
    parser.add_argument("--sheet-id", default=SHEET_ID)
    parser.add_argument(
        "--output",
        default="-",
        help="Output path. Use - for stdout.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Output format.",
    )
    parser.add_argument(
        "--min-units",
        type=int,
        default=0,
        help="Minimum units per prefecture to include.",
    )
    return parser.parse_args()


def summarize_unassigned(items: list[dict[str, str]]) -> list[dict]:
    pref_counter: dict[str, int] = {}
    unit_counter: dict[str, int] = {}
    for item in items:
        if not item.get("ID"):
            continue
        pref = item.get("都道府県", "").strip()
        if not pref:
            continue
        units = int(to_number(item.get("総戸数", "")))
        pref_counter[pref] = pref_counter.get(pref, 0) + 1
        unit_counter[pref] = unit_counter.get(pref, 0) + units

    return [
        {"prefecture": p, "properties": pref_counter[p], "units": unit_counter[p]}
        for p in sorted(pref_counter.keys(), key=lambda x: -unit_counter[x])
        if unit_counter[p] >= 0  # min-units filter applied below
    ]


def main() -> int:
    args = parse_args()
    zf, shared, workbook, rel_map = fetch_workbook(args.sheet_id)
    unassigned_rows = sheet_rows(zf, shared, workbook, rel_map, "担当者不在")
    recs = records(unassigned_rows)
    data = summarize_unassigned(recs)
    data = [d for d in data if d["units"] >= args.min_units]

    out = sys.stdout if args.output == "-" else open(args.output, "w", encoding="utf-8")
    try:
        if args.format == "json":
            json.dump(data, out, ensure_ascii=False, indent=2)
        else:
            out.write("都道府県,物件数,戸数\n")
            for d in data:
                out.write(f"{d['prefecture']},{d['properties']},{d['units']}\n")
    finally:
        if out is not sys.stdout:
            out.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
