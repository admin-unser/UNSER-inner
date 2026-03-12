#!/usr/bin/env python3

"""Generate monthly aggregate report (備考: 262稼働分ベースの日次集計)."""

from __future__ import annotations

import argparse
import datetime as dt
from collections import Counter

from generate_posting_report import (
    fetch_workbook,
    records,
    sheet_rows,
    to_number,
)

SHEET_ID = "1zUkpKOHO4ro35nvcCe-tfI-rNHWf3dJhPIVhPNuEla4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate monthly aggregate (備考)."
    )
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--sheet-id", default=SHEET_ID)
    parser.add_argument("--output", required=True)
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


def main() -> int:
    args = parse_args()
    year, month = map(int, args.month.split("-"))
    month_start = dt.date(year, month, 1)
    if month == 12:
        month_end = dt.date(year, month, 31)
    else:
        month_end = dt.date(year, month + 1, 1) - dt.timedelta(days=1)

    zf, shared, workbook, rel_map = fetch_workbook(args.sheet_id)
    current_rows = sheet_rows(zf, shared, workbook, rel_map, "262 稼働分")
    recs = records(current_rows)

    in_month = [r for r in recs if (d := row_date(r)) and month_start <= d <= month_end and r.get("ID", "").strip()]

    total_properties = len(in_month)
    total_units = sum(int(to_number(r.get("総戸数", ""))) for r in in_month)
    total_delivered = sum(int(to_number(r.get("実配付枚数", ""))) for r in in_month)
    status_counter: Counter[str] = Counter()
    by_date: dict[dt.date, dict] = {}
    workers: set[str] = set()

    for r in in_month:
        day = row_date(r)
        if not day:
            continue
        status_counter[r.get("ステータス", "").strip()] += 1
        workers.add(r.get("担当者", "").strip() or "(未設定)")
        if day not in by_date:
            by_date[day] = {"properties": 0, "units": 0, "delivered": 0}
        by_date[day]["properties"] += 1
        by_date[day]["units"] += int(to_number(r.get("総戸数", "")))
        by_date[day]["delivered"] += int(to_number(r.get("実配付枚数", "")))

    lines = []
    lines.append("# Posting Monthly Aggregate (備考)")
    lines.append("")
    lines.append(f"対象月: {year}-{month:02d}")
    lines.append("")
    lines.append("## 月次集計サマリ")
    lines.append("")
    lines.append(f"- 総物件数: **{total_properties:,}件**")
    lines.append(f"- 総戸数: **{total_units:,}戸**")
    lines.append(f"- 実配付枚数: **{total_delivered:,}枚**")
    fill = (total_delivered / total_units * 100) if total_units else 0
    lines.append(f"- 実配付率: **{fill:.1f}%**")
    lines.append(f"- 稼働メンバー数: **{len(workers)}名**")
    lines.append(f"- 稼働日数: **{len(by_date)}日**")
    lines.append("")
    lines.append("## ステータス内訳")
    lines.append("")
    lines.append("| ステータス | 件数 |")
    lines.append("| --- | ---: |")
    for status, count in status_counter.most_common():
        lines.append(f"| {status} | {count:,} |")
    lines.append("")
    lines.append("## 日別集計")
    lines.append("")
    lines.append("| 日付 | 物件数 | 総戸数 | 実配付枚数 | 実配付率 |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for day in sorted(by_date.keys()):
        d = by_date[day]
        rate = (d["delivered"] / d["units"] * 100) if d["units"] else 0
        lines.append(f"| {day.isoformat()} | {d['properties']:,} | {d['units']:,} | {d['delivered']:,} | {rate:.1f}% |")
    lines.append("")
    lines.append("---")
    lines.append("備考: 262 稼働分タブの日付（終了日時/開始日時）でフィルタした集計です。")
    lines.append("")

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
