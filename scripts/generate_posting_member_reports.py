#!/usr/bin/env python3

"""Generate per-member monthly posting reports from 262 稼働分."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import hashlib
import os
from collections import Counter

from generate_posting_report import (
    fetch_workbook,
    records,
    sheet_rows,
    to_number,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SHEET_ID = "1zUkpKOHO4ro35nvcCe-tfI-rNHWf3dJhPIVhPNuEla4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate per-member monthly reports."
    )
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--sheet-id", default=SHEET_ID)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--unmask",
        action="store_true",
        help="Use real member names (for internal use only).",
    )
    return parser.parse_args()


def parse_datetime(value: str) -> dt.datetime | None:
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%a %b %d %Y %H:%M:%S GMT%z (%Z)", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        serial = float(text)
        return dt.datetime(1899, 12, 30) + dt.timedelta(days=serial)
    except ValueError:
        return None


def row_date(item: dict[str, str]) -> dt.date | None:
    for field in ("終了日時", "開始日時"):
        value = item.get(field, "")
        parsed = parse_datetime(value)
        if parsed:
            return parsed.date()
    return None


def member_label(raw: str) -> str:
    return "member-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:6]


def summarize_member_monthly(
    current_records: list[dict[str, str]],
    year: int,
    month: int,
) -> dict[str, dict]:
    month_start = dt.date(year, month, 1)
    if month == 12:
        month_end = dt.date(year, month, 31)
    else:
        month_end = dt.date(year, month + 1, 1) - dt.timedelta(days=1)

    by_member: dict[str, dict] = {}
    for item in current_records:
        day = row_date(item)
        if not day or not (month_start <= day <= month_end):
            continue
        if not item.get("ID", "").strip():
            continue

        member_raw = item.get("担当者", "").strip() or "(未設定)"
        label = member_label(member_raw)
        status = item.get("ステータス", "").strip()
        total_units = int(to_number(item.get("総戸数", "")))
        delivered = int(to_number(item.get("実配付枚数", "")))
        ng_count = int(to_number(item.get("NG枚数", "")))
        ai_result = item.get("AI判定", "").strip()
        has_photo = bool(item.get("配布写真", "").strip())
        has_ocr = bool(item.get("OCR結果", "").strip())

        m = by_member.setdefault(
            member_raw,
            {
                "label": label,
                "properties": 0,
                "total_units": 0,
                "delivered_units": 0,
                "completed": 0,
                "status": Counter(),
                "review_flags": 0,
                "days_active": set(),
            },
        )
        m["properties"] += 1
        m["total_units"] += total_units
        m["delivered_units"] += delivered
        m["status"][status] += 1
        m["days_active"].add(day)

        if status == "配布完了":
            m["completed"] += 1
        if ng_count > 0 or status in ("差し戻し", "保留"):
            m["review_flags"] += 1
        elif status == "配布完了" and (ai_result != "OK" or not has_ocr or delivered < total_units):
            m["review_flags"] += 1

    return by_member


def build_member_markdown(
    member_name: str,
    label: str,
    metrics: dict,
    year: int,
    month: int,
    unmask: bool,
) -> str:
    lines = []
    display = member_name if unmask else label
    lines.append(f"# Posting Member Report: {display}")
    lines.append("")
    lines.append(f"対象月: {year}-{month:02d}")
    lines.append("")
    lines.append("## 月次サマリ")
    lines.append("")
    lines.append(f"- 物件数: **{metrics['properties']:,}件**")
    lines.append(f"- 総戸数: **{metrics['total_units']:,}戸**")
    lines.append(f"- 実配付枚数: **{metrics['delivered_units']:,}枚**")
    fill_rate = (metrics["delivered_units"] / metrics["total_units"] * 100) if metrics["total_units"] else 0
    lines.append(f"- 実配付率: **{fill_rate:.1f}%**")
    lines.append(f"- 配布完了件数: **{metrics['completed']:,}件**")
    lines.append(f"- レビュー候補: **{metrics['review_flags']:,}件**")
    lines.append(f"- 稼働日数: **{len(metrics['days_active'])}日**")
    lines.append("")
    lines.append("## ステータス内訳")
    lines.append("")
    lines.append("| ステータス | 件数 |")
    lines.append("| --- | ---: |")
    for status, count in metrics["status"].most_common():
        lines.append(f"| {status} | {count:,} |")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    year, month = map(int, args.month.split("-"))

    zf, shared, workbook, rel_map = fetch_workbook(args.sheet_id)
    current_rows = sheet_rows(zf, shared, workbook, rel_map, "262 稼働分")
    recs = records(current_rows)

    by_member = summarize_member_monthly(recs, year, month)
    if not by_member:
        print(f"No data for members in {args.month}.", file=sys.stderr)
        return 1

    os.makedirs(args.output_dir, exist_ok=True)
    for member_name, metrics in sorted(
        by_member.items(),
        key=lambda x: (x[1]["delivered_units"], x[1]["total_units"]),
        reverse=True,
    ):
        label = metrics["label"]
        md = build_member_markdown(
            member_name, label, metrics, year, month, args.unmask
        )
        out_path = os.path.join(args.output_dir, f"{label}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"  {label}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
