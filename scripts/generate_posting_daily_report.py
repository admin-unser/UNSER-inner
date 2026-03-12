#!/usr/bin/env python3

"""Generate a daily posting operations report from the current run sheet."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
from collections import Counter

from generate_posting_report import fetch_workbook, records, sheet_rows, to_number


SHEET_ID = "1zUkpKOHO4ro35nvcCe-tfI-rNHWf3dJhPIVhPNuEla4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate daily posting report markdown.")
    parser.add_argument("--sheet-id", default=SHEET_ID, help="Google Sheets ID")
    parser.add_argument("--output", required=True, help="Output markdown path")
    parser.add_argument(
        "--date",
        help="Target date in YYYY-MM-DD. If omitted, the latest date found in 262 稼働分 is used.",
    )
    parser.add_argument(
        "--reminder-threshold",
        type=float,
        default=90.0,
        help="Progress rate threshold for reminder candidates.",
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


def member_label(raw: str) -> str:
    return "member-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:6]


def row_date(item: dict[str, str]) -> dt.date | None:
    for field in ("終了日時", "開始日時"):
        value = item.get(field, "")
        parsed = parse_datetime(value)
        if parsed:
            return parsed.date()
    return None


def load_name_map(member_records: list[dict[str, str]]) -> dict[str, str]:
    name_map = {}
    for item in member_records:
        mail = item.get("メールアドレス", "").strip()
        name = item.get("氏名", "").strip()
        if mail and name:
            name_map[mail] = name
    return name_map


def summarize_daily(
    current_records: list[dict[str, str]],
    member_records: list[dict[str, str]],
    target_date: dt.date | None,
    threshold: float,
) -> tuple[dt.date, dict]:
    available_dates = sorted({day for item in current_records if (day := row_date(item))}, reverse=True)
    if not available_dates:
        raise RuntimeError("No dated rows found in 262 稼働分.")

    date_value = target_date or available_dates[0]
    name_map = load_name_map(member_records)

    per_member: dict[str, dict] = {}
    status_counter: Counter[str] = Counter()
    ai_counter: Counter[str] = Counter()
    reminder_candidates = []
    active_member_labels = set()

    total_properties = 0
    total_units = 0
    total_delivered = 0

    for item in current_records:
        day = row_date(item)
        if day != date_value:
            continue
        if not item.get("ID", "").strip():
            continue

        total_properties += 1
        total_units += int(to_number(item.get("総戸数", "")))
        total_delivered += int(to_number(item.get("実配付枚数", "")))

        member_key = item.get("担当者", "").strip() or "(未設定)"
        label = member_label(member_key)
        active_member_labels.add(label)
        display_name = name_map.get(member_key, label)

        metrics = per_member.setdefault(
            label,
            {
                "display_name": display_name,
                "properties": 0,
                "units": 0,
                "delivered": 0,
                "completed": 0,
                "statuses": Counter(),
                "review_flags": Counter(),
            },
        )

        status = item.get("ステータス", "").strip()
        ai_result = item.get("AI判定", "").strip() or "(blank)"
        delivered_units = int(to_number(item.get("実配付枚数", "")))
        total_row_units = int(to_number(item.get("総戸数", "")))
        ng_count = int(to_number(item.get("NG枚数", "")))
        has_ocr = bool(item.get("OCR結果", "").strip())

        metrics["properties"] += 1
        metrics["units"] += total_row_units
        metrics["delivered"] += delivered_units
        metrics["statuses"][status] += 1

        if status == "配布完了":
            metrics["completed"] += 1
        if ng_count > 0:
            metrics["review_flags"]["NG枚数あり"] += 1
        if status == "差し戻し":
            metrics["review_flags"]["差し戻し"] += 1
        if status == "保留":
            metrics["review_flags"]["保留"] += 1
        if status == "配布完了" and ai_result != "OK":
            metrics["review_flags"]["AI判定要確認"] += 1
        if status == "配布完了" and not has_ocr:
            metrics["review_flags"]["OCR結果なし"] += 1
        if status == "配布完了" and delivered_units < total_row_units:
            metrics["review_flags"]["総戸数未達"] += 1

        status_counter[status] += 1
        ai_counter[ai_result] += 1

    ranked = sorted(
        per_member.items(),
        key=lambda item: (item[1]["delivered"], item[1]["units"]),
        reverse=True,
    )

    for label, metrics in ranked:
        progress = (metrics["delivered"] / metrics["units"] * 100) if metrics["units"] else 0.0
        remind_reasons = []
        if progress < threshold:
            remind_reasons.append(f"進捗率 {progress:.1f}%")
        if metrics["review_flags"]:
            remind_reasons.append("要確認あり")
        if metrics["statuses"].get("差し戻し", 0):
            remind_reasons.append("差し戻しあり")
        if metrics["statuses"].get("保留", 0):
            remind_reasons.append("保留あり")
        if remind_reasons:
            reminder_candidates.append(
                {
                    "label": label,
                    "display_name": metrics["display_name"],
                    "progress": progress,
                    "reasons": remind_reasons,
                    "units": metrics["units"],
                    "delivered": metrics["delivered"],
                }
            )

    return date_value, {
        "total_properties": total_properties,
        "total_units": total_units,
        "total_delivered": total_delivered,
        "active_members": len(active_member_labels),
        "status_counter": status_counter,
        "ai_counter": ai_counter,
        "members": ranked,
        "reminders": reminder_candidates,
    }


def build_markdown(target_date: dt.date, data: dict, threshold: float) -> str:
    overall_progress = (data["total_delivered"] / data["total_units"] * 100) if data["total_units"] else 0.0

    lines = []
    lines.append("# Posting Daily Report v1")
    lines.append("")
    lines.append(f"Generated: {dt.datetime.now(dt.UTC).isoformat()}")
    lines.append(f"Target date: {target_date.isoformat()}")
    lines.append("")
    lines.append("## Daily summary")
    lines.append("")
    lines.append(f"- 当日配布対象: **{data['total_properties']:,}件**")
    lines.append(f"- 当日総戸数: **{data['total_units']:,}戸**")
    lines.append(f"- 当日実配付枚数: **{data['total_delivered']:,}枚**")
    lines.append(f"- 当日全体進捗率: **{overall_progress:.1f}%**")
    lines.append(f"- 稼働メンバー数: **{data['active_members']}名**")
    lines.append("")
    lines.append("## Status summary")
    lines.append("")
    lines.append("| ステータス | 件数 |")
    lines.append("| --- | ---: |")
    for status, count in data["status_counter"].most_common():
        lines.append(f"| {status} | {count:,} |")
    lines.append("")
    lines.append("## Member daily performance")
    lines.append("")
    lines.append("- public リポジトリ向けに、担当者識別子はマスクしています。")
    lines.append("")
    lines.append("| 担当者 | 物件数 | 総戸数 | 実配付枚数 | 進捗率 | 配布完了件数 | 差し戻し | 保留 | 要確認件数 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for label, metrics in data["members"]:
        progress = (metrics["delivered"] / metrics["units"] * 100) if metrics["units"] else 0.0
        review_count = sum(metrics["review_flags"].values())
        lines.append(
            f"| {label} | {metrics['properties']:,} | {metrics['units']:,} | {metrics['delivered']:,} | "
            f"{progress:.1f}% | {metrics['completed']:,} | {metrics['statuses'].get('差し戻し', 0):,} | "
            f"{metrics['statuses'].get('保留', 0):,} | {review_count:,} |"
        )
    lines.append("")
    lines.append("## Reminder candidates")
    lines.append("")
    lines.append(f"- 基準: 進捗率 **{threshold:.1f}%** 未満、または差し戻し / 保留 / 要確認あり")
    lines.append("")
    if data["reminders"]:
        lines.append("| 担当者 | 進捗率 | 総戸数 | 実配付枚数 | 理由 |")
        lines.append("| --- | ---: | ---: | ---: | --- |")
        for item in data["reminders"]:
            lines.append(
                f"| {item['label']} | {item['progress']:.1f}% | {item['units']:,} | {item['delivered']:,} | "
                f"{', '.join(item['reasons'])} |"
            )
        lines.append("")
        lines.append("### Reminder draft")
        lines.append("")
        for item in data["reminders"]:
            lines.append(
                f"- {item['label']}: 本日の進捗は {item['progress']:.1f}% "
                f"（実配付 {item['delivered']:,} / 総戸数 {item['units']:,}）です。"
                f" {', '.join(item['reasons'])}。状況確認をお願いします。"
            )
    else:
        lines.append("- リマインド候補はありません。")
    lines.append("")
    lines.append("## AI / review signals")
    lines.append("")
    lines.append("| AI判定 | 件数 |")
    lines.append("| --- | ---: |")
    for result, count in data["ai_counter"].most_common():
        lines.append(f"| {result} | {count:,} |")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    target_date = dt.date.fromisoformat(args.date) if args.date else None
    zf, shared, workbook, rel_map = fetch_workbook(args.sheet_id)
    current_rows = sheet_rows(zf, shared, workbook, rel_map, "262 稼働分")
    member_rows = sheet_rows(zf, shared, workbook, rel_map, "メンバーマスタ")

    report_date, data = summarize_daily(
        records(current_rows),
        records(member_rows),
        target_date=target_date,
        threshold=args.reminder_threshold,
    )
    markdown = build_markdown(report_date, data, args.reminder_threshold)
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
