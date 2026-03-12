#!/usr/bin/env python3

"""Generate an OCR double-check report for posting operations."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
from collections import Counter

from generate_posting_report import fetch_workbook, records, sheet_rows


SHEET_ID = "1zUkpKOHO4ro35nvcCe-tfI-rNHWf3dJhPIVhPNuEla4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate OCR review queue report.")
    parser.add_argument("--sheet-id", default=SHEET_ID, help="Google Sheets ID")
    parser.add_argument("--output", required=True, help="Output markdown path")
    return parser.parse_args()


def member_label(raw: str) -> str:
    return "member-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:6]


def normalize_name(text: str) -> str:
    value = text or ""
    value = value.lower()
    value = value.replace("マンション名", "")
    value = re.sub(r"[\\s\\-ー―‐・./:：()（）【】\\[\\]　]", "", value)
    return value


def overlap_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    set_a = {a[i : i + 2] for i in range(max(len(a) - 1, 1))}
    set_b = {b[i : i + 2] for i in range(max(len(b) - 1, 1))}
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def suggest_action(status: str, ai_result: str, property_name: str, ocr_result: str) -> str:
    normalized_property = normalize_name(property_name)
    normalized_ocr = normalize_name(ocr_result)
    score = overlap_score(normalized_property, normalized_ocr)

    if ocr_result in {"", "不明"}:
        return "OCR読取不可。目視で建物名確認"
    if status == "差し戻し" and ai_result == "判定NG" and score >= 0.25:
        return "表記ゆれ候補。物件名と照合してOKなら完了へ"
    if status == "差し戻し" and ai_result == "判定NG":
        return "建物名不一致の可能性。写真を目視確認"
    if ai_result == "判定NG":
        return "AI判定NG。OCR結果と写真を確認"
    return "確認"


def collect_review_items(records_list: list[dict[str, str]], source: str) -> list[dict[str, str]]:
    items = []
    for item in records_list:
        item_id = item.get("ID", "").strip()
        if not item_id:
            continue
        status = item.get("ステータス", "").strip()
        ai_result = item.get("AI判定", "").strip() or "(blank)"
        if not (status == "差し戻し" or ai_result not in {"OK", "(blank)"}):
            continue

        property_name = item.get("物件名", "").strip()
        ocr_result = item.get("OCR結果", "").strip()
        member = item.get("担当者", "").strip() or "(未設定)"

        items.append(
            {
                "source": source,
                "id": item_id,
                "member": member_label(member),
                "status": status,
                "ai_result": ai_result,
                "property_name": property_name,
                "ocr_result": ocr_result or "(blank)",
                "ng_count": item.get("NG枚数", "").strip() or "0",
                "delivered_units": item.get("実配付枚数", "").strip() or "0",
                "suggestion": suggest_action(status, ai_result, property_name, ocr_result),
            }
        )
    return items


def build_markdown(items: list[dict[str, str]]) -> str:
    source_counter = Counter(item["source"] for item in items)
    member_counter = Counter(item["member"] for item in items)
    status_counter = Counter(item["status"] for item in items)
    ai_counter = Counter(item["ai_result"] for item in items)

    lines = []
    lines.append("# Posting OCR Review Report v1")
    lines.append("")
    lines.append(f"Generated: {dt.datetime.now(dt.UTC).isoformat()}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- レビュー対象件数: **{len(items)}件**")
    if items:
        lines.append(
            "- ソース別: " + ", ".join(f"{source} {count}件" for source, count in source_counter.items())
        )
        lines.append(
            "- ステータス別: " + ", ".join(f"{status or '(blank)'} {count}件" for status, count in status_counter.items())
        )
        lines.append(
            "- AI判定別: " + ", ".join(f"{result} {count}件" for result, count in ai_counter.items())
        )
    lines.append("")
    lines.append("## Review queue")
    lines.append("")
    lines.append("- public リポジトリ向けに、担当者識別子はマスクしています。")
    lines.append("")
    lines.append("| Source | ID | 担当者 | ステータス | AI判定 | 物件名 | OCR結果 | NG枚数 | 実配付枚数 | 推奨アクション |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- |")
    for item in items:
        lines.append(
            f"| {item['source']} | {item['id']} | {item['member']} | {item['status'] or '(blank)'} | "
            f"{item['ai_result']} | {item['property_name']} | {item['ocr_result']} | {item['ng_count']} | "
            f"{item['delivered_units']} | {item['suggestion']} |"
        )
    lines.append("")
    lines.append("## Member load")
    lines.append("")
    lines.append("| 担当者 | 件数 |")
    lines.append("| --- | ---: |")
    for member, count in member_counter.most_common():
        lines.append(f"| {member} | {count} |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- 対象条件は `ステータス = 差し戻し` または `AI判定 != OK` です。")
    lines.append("- `AI判定` が空欄のものは、このレポートでは対象外です。")
    lines.append("- OCR結果が `不明` または空欄のものは、表記ゆれ判定よりも先に目視確認が必要です。")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    zf, shared, workbook, rel_map = fetch_workbook(args.sheet_id)
    property_rows = records(sheet_rows(zf, shared, workbook, rel_map, "物件リスト"))
    current_rows = records(sheet_rows(zf, shared, workbook, rel_map, "262 稼働分"))

    items = []
    items.extend(collect_review_items(property_rows, "物件リスト"))
    items.extend(collect_review_items(current_rows, "262稼働分"))
    items.sort(key=lambda item: (item["source"], item["status"], item["member"], item["id"]))

    markdown = build_markdown(items)
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
