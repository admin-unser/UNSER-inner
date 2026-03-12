#!/usr/bin/env python3

"""Generate a sanitized posting operations report from the shared Google Sheet."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter


SHEET_ID = "1zUkpKOHO4ro35nvcCe-tfI-rNHWf3dJhPIVhPNuEla4"
NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate posting report markdown.")
    parser.add_argument("--sheet-id", default=SHEET_ID, help="Google Sheets ID")
    parser.add_argument("--output", required=True, help="Output markdown path")
    return parser.parse_args()


def fetch_workbook(sheet_id: str) -> tuple[zipfile.ZipFile, list[str], ET.Element, dict[str, str]]:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    data = urllib.request.urlopen(url, timeout=60).read()
    zf = zipfile.ZipFile(io.BytesIO(data))

    shared = []
    if "xl/sharedStrings.xml" in zf.namelist():
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for item in root.findall("a:si", NS):
            shared.append("".join(node.text or "" for node in item.findall(".//a:t", NS)))

    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    return zf, shared, workbook, rel_map


def col_index(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref)
    if not match:
        return 0
    value = 0
    for char in match.group(1):
        value = value * 26 + (ord(char) - 64)
    return value - 1


def cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    inline = cell.find("a:is", NS)
    if inline is not None:
        return "".join(node.text or "" for node in inline.findall(".//a:t", NS))

    value = cell.find("a:v", NS)
    if value is None or value.text is None:
        return ""

    raw = value.text
    if cell.attrib.get("t") == "s" and raw.isdigit():
        index = int(raw)
        if 0 <= index < len(shared_strings):
            return shared_strings[index]
    return raw


def sheet_rows(
    zf: zipfile.ZipFile,
    shared_strings: list[str],
    workbook: ET.Element,
    rel_map: dict[str, str],
    title: str,
) -> list[list[str]]:
    for sheet in workbook.findall("a:sheets/a:sheet", NS):
        if sheet.attrib["name"] != title:
            continue
        rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        worksheet = ET.fromstring(zf.read("xl/" + rel_map[rel_id]))
        rows: list[list[str]] = []
        for row in worksheet.findall("a:sheetData/a:row", NS):
            values: list[str] = []
            for cell in row.findall("a:c", NS):
                idx = col_index(cell.attrib.get("r", "A1"))
                while len(values) <= idx:
                    values.append("")
                values[idx] = cell_text(cell, shared_strings).strip()
            rows.append(values)
        return rows
    raise KeyError(f"Sheet not found: {title}")


def records(rows: list[list[str]], header_index: int = 0) -> list[dict[str, str]]:
    header = [value.strip() for value in rows[header_index]]
    items: list[dict[str, str]] = []
    for row in rows[header_index + 1 :]:
        padded = row + [""] * (len(header) - len(row))
        items.append({header[i]: padded[i] for i in range(len(header))})
    return items


def to_number(value: str) -> float:
    if value is None:
        return 0.0
    text = str(value).replace(",", "").strip()
    if not text or text in {"-", "#DIV/0!", "#REF!"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def ratio(part: float, whole: float) -> float:
    if whole == 0:
        return 0.0
    return part / whole


def summarize_queue(items: list[dict[str, str]]) -> dict:
    status_counter: Counter[str] = Counter()
    line_counter: Counter[str] = Counter()
    pref_counter: Counter[str] = Counter()
    unit_counter: Counter[str] = Counter()

    total_properties = 0
    total_units = 0
    nonempty_schedule = 0
    nonempty_started = 0
    nonempty_finished = 0
    nonempty_photo = 0

    for item in items:
        if not item.get("ID"):
            continue
        total_properties += 1
        units = int(to_number(item.get("総戸数", "")))
        total_units += units

        status = item.get("ステータス", "").strip()
        if status and not re.fullmatch(r"\d+(\.\d+)?", status):
            status_counter[status] += 1

        line = item.get("回線名", "").strip()
        if line:
            line_counter[line] += 1

        pref = item.get("都道府県", "").strip()
        if pref:
            pref_counter[pref] += 1
            unit_counter[pref] += units

        if item.get("配布予定日", "").strip():
            nonempty_schedule += 1
        if item.get("開始日時", "").strip():
            nonempty_started += 1
        if item.get("終了日時", "").strip():
            nonempty_finished += 1
        if item.get("配布写真", "").strip():
            nonempty_photo += 1

    return {
        "properties": total_properties,
        "units": total_units,
        "status": status_counter,
        "line": line_counter,
        "pref": pref_counter,
        "pref_units": unit_counter,
        "schedule_filled": nonempty_schedule,
        "started_filled": nonempty_started,
        "finished_filled": nonempty_finished,
        "photo_filled": nonempty_photo,
    }


def summarize_summary_sheet(items: list[dict[str, str]]) -> dict:
    total_row = None
    prefectures: list[dict[str, float | str]] = []
    for item in items:
        pref = item.get("都道府県", "").strip()
        if not pref:
            continue
        if pref == "総計":
            total_row = item
            continue
        prefectures.append(
            {
                "prefecture": pref,
                "properties": to_number(item.get("物件数", "")),
                "planned": to_number(item.get("配布枚数", "")),
                "delivered": to_number(item.get("実配付枚数", "")),
                "no_box": to_number(item.get("宅配ボックス無し", "")),
                "no_box_rate": to_number(item.get("#DIV/0!", "")),
            }
        )
    return {"total": total_row or {}, "prefectures": prefectures}


def summarize_members(items: list[dict[str, str]]) -> dict:
    active = 0
    active_roles: Counter[str] = Counter()
    target_total = 0
    for item in items:
        if not item.get("氏名", "").strip():
            continue
        if item.get("ステータス", "").strip() == "有効":
            active += 1
            role = item.get("権限", "").strip()
            if role:
                active_roles[role] += 1
            target_total += int(to_number(item.get("今月目標数", "")))
    return {"active": active, "roles": active_roles, "target_total": target_total}


def summarize_monthly(items: list[dict[str, str]]) -> dict:
    responses = 0
    requested_units = 0
    interview_requests = 0
    months: Counter[str] = Counter()
    mood_scores = []
    for item in items:
        if not item.get("ID", "").strip():
            continue
        responses += 1
        requested_units += int(to_number(item.get("来月希望枚数", "")))
        if "希望" in item.get("面談希望", ""):
            interview_requests += 1
        month = item.get("対象月", "").strip()
        if month:
            months[month] += 1
        mood = item.get("今のモチベーション", "").strip()
        if mood and mood[0].isdigit():
            mood_scores.append(int(mood[0]))
    avg_mood = sum(mood_scores) / len(mood_scores) if mood_scores else 0.0
    return {
        "responses": responses,
        "requested_units": requested_units,
        "interview_requests": interview_requests,
        "months": months,
        "avg_mood": avg_mood,
    }


def summarize_attendance(items: list[dict[str, str]]) -> dict:
    logs = 0
    workers: set[str] = set()
    kinds: Counter[str] = Counter()
    for item in items:
        if not item.get("ID", "").strip():
            continue
        logs += 1
        worker = item.get("打刻者", "").strip()
        if worker:
            workers.add(worker)
        kinds[item.get("ステータス", "").strip()] += 1
    return {"logs": logs, "unique_workers": len(workers), "kinds": kinds}


def summarize_feedback(items: list[dict[str, str]]) -> dict:
    total = 0
    done = 0
    pending_topics = []
    for item in items:
        if not any(value.strip() for value in item.values()):
            continue
        total += 1
        if item.get("自動化済　☑️", "").strip() == "1":
            done += 1
        else:
            topic = item.get("項目", "").strip() or item.get("コメント", "").strip()
            if topic:
                pending_topics.append(topic)
    return {"total": total, "done": done, "pending_topics": pending_topics[:5]}


def summarize_current_run(items: list[dict[str, str]]) -> dict:
    by_member: dict[str, dict] = {}
    status_counter: Counter[str] = Counter()
    ai_counter: Counter[str] = Counter()
    review_counter: Counter[str] = Counter()

    for item in items:
        if not item.get("ID", "").strip():
            continue

        member = item.get("担当者", "").strip() or "(未設定)"
        status = item.get("ステータス", "").strip()
        ai_result = item.get("AI判定", "").strip()
        total_units = int(to_number(item.get("総戸数", "")))
        delivered_units = int(to_number(item.get("実配付枚数", "")))
        ng_count = int(to_number(item.get("NG枚数", "")))
        has_photo = bool(item.get("配布写真", "").strip())
        has_ocr = bool(item.get("OCR結果", "").strip())

        status_counter[status] += 1
        ai_counter[ai_result or "(blank)"] += 1

        metrics = by_member.setdefault(
            member,
            {
                "properties": 0,
                "total_units": 0,
                "delivered_units": 0,
                "completed_properties": 0,
                "review_flags": 0,
                "status": Counter(),
            },
        )

        metrics["properties"] += 1
        metrics["total_units"] += total_units
        metrics["delivered_units"] += delivered_units
        metrics["status"][status] += 1

        flagged = False
        if status == "配布完了":
            metrics["completed_properties"] += 1
            if not has_photo:
                review_counter["完了だが写真なし"] += 1
                flagged = True
            if ai_result != "OK":
                review_counter["完了だがAI判定OK以外"] += 1
                flagged = True
            if not has_ocr:
                review_counter["完了だがOCR結果なし"] += 1
                flagged = True
            if delivered_units < total_units:
                review_counter["総戸数より実配付枚数が少ない完了"] += 1
                flagged = True
        if ng_count > 0:
            review_counter["NG枚数あり"] += 1
            flagged = True
        if status == "差し戻し":
            review_counter["差し戻し"] += 1
            flagged = True
        if status == "保留":
            review_counter["保留"] += 1
            flagged = True

        if flagged:
            metrics["review_flags"] += 1

    ranked_members = sorted(
        by_member.items(),
        key=lambda item: (item[1]["delivered_units"], item[1]["total_units"]),
        reverse=True,
    )

    return {
        "members": ranked_members,
        "status": status_counter,
        "ai": ai_counter,
        "review": review_counter,
    }


def top_prefecture_rows(counter: Counter[str], unit_counter: Counter[str], limit: int = 5) -> list[str]:
    rows = []
    for pref, count in counter.most_common(limit):
        rows.append(f"| {pref} | {count:,} | {unit_counter[pref]:,} |")
    return rows


def top_line_rows(counter: Counter[str], total: int) -> list[str]:
    rows = []
    for name, count in counter.most_common():
        rows.append(f"| {name} | {count:,} | {ratio(count, total) * 100:.1f}% |")
    return rows


def top_status_rows(counter: Counter[str], total: int) -> list[str]:
    rows = []
    for name, count in counter.most_common(6):
        rows.append(f"| {name} | {count:,} | {ratio(count, total) * 100:.1f}% |")
    return rows


def top_summary_pref_rows(prefectures: list[dict], limit: int = 5) -> list[str]:
    ordered = sorted(prefectures, key=lambda item: item["planned"], reverse=True)[:limit]
    rows = []
    for item in ordered:
        completion = ratio(item["delivered"], item["planned"]) * 100
        no_box_rate = float(item["no_box_rate"]) * 100
        rows.append(
            f"| {item['prefecture']} | {int(item['planned']):,} | {int(item['delivered']):,} | "
            f"{completion:.1f}% | {no_box_rate:.1f}% |"
        )
    return rows


def member_rows(members: list[tuple[str, dict]], limit: int = 10) -> list[str]:
    rows = []
    for name, metrics in members[:limit]:
        fill_rate = ratio(metrics["delivered_units"], metrics["total_units"]) * 100
        member_label = "member-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]
        rows.append(
            f"| {member_label} | {metrics['properties']:,} | {metrics['total_units']:,} | "
            f"{metrics['delivered_units']:,} | {fill_rate:.1f}% | {metrics['completed_properties']:,} | {metrics['review_flags']:,} |"
        )
    return rows


def simple_counter_rows(counter: Counter[str], limit: int = 10) -> list[str]:
    rows = []
    for key, value in counter.most_common(limit):
        rows.append(f"| {key} | {value:,} |")
    return rows


def build_markdown(summary: dict) -> str:
    assigned = summary["assigned"]
    unassigned = summary["unassigned"]
    managed_properties = assigned["properties"] + unassigned["properties"]
    managed_units = assigned["units"] + unassigned["units"]
    aggregate = summary["aggregate_total"]
    planned = to_number(aggregate.get("配布枚数", ""))
    delivered = to_number(aggregate.get("実配付枚数", ""))
    no_box = to_number(aggregate.get("宅配ボックス無し", ""))
    completion = ratio(delivered, planned) * 100

    members = summary["members"]
    monthly = summary["monthly"]
    attendance = summary["attendance"]
    feedback = summary["feedback"]
    current_run = summary["current_run"]

    lines = []
    lines.append("# Posting Operations Report v1")
    lines.append("")
    lines.append(f"Generated: {dt.datetime.now(dt.UTC).isoformat()}")
    lines.append("")
    lines.append("## Executive summary")
    lines.append("")
    lines.append(
        f"- 管理対象は **{managed_properties:,}件 / {managed_units:,}戸**。うち割当済み **{assigned['properties']:,}件**、担当者不在 **{unassigned['properties']:,}件**。"
    )
    lines.append(
        f"- `データ集計` タブ上の総計では、配布予定 **{int(planned):,}枚** に対して実配付 **{int(delivered):,}枚**、進捗は **{completion:.1f}%**。"
    )
    lines.append(
        f"- 有効メンバーは **{members['active']}名**。メンバーマスタ上の今月目標数合計は **{members['target_total']:,}枚**。"
    )
    lines.append(
        f"- 月次報告の回答は **{monthly['responses']}件**、回答上の来月希望枚数は **{monthly['requested_units']:,}枚**。"
    )
    lines.append(
        f"- フィードバック起点の自動化テーマは **{feedback['total']}件**、うち **{feedback['done']}件** が完了、**{feedback['total'] - feedback['done']}件** が未完了。"
    )
    lines.append("")
    lines.append("## Reading notes")
    lines.append("")
    lines.append("- このレポートは、現時点では **週次実績** というより **運用在庫と進捗のスナップショット** に近い読み方が適切です。")
    lines.append(
        f"- `物件リスト` のうち `配布予定日` が埋まっているのは **{assigned['schedule_filled']:,}件 ({ratio(assigned['schedule_filled'], assigned['properties']) * 100:.1f}%)**、`開始日時` は **{assigned['started_filled']:,}件 ({ratio(assigned['started_filled'], assigned['properties']) * 100:.1f}%)**。"
    )
    lines.append("- `物件リスト` と `担当者不在` は別キューとして扱い、単純合算しています。")
    lines.append("- メンバー別の実績は `262 稼働分` タブをベースにしているため、直近稼働分の把握に向いています。")
    lines.append("")
    lines.append("## Queue health")
    lines.append("")
    lines.append("| Queue | Properties | Units | Share |")
    lines.append("| --- | ---: | ---: | ---: |")
    lines.append(
        f"| 割当済み (`物件リスト`) | {assigned['properties']:,} | {assigned['units']:,} | {ratio(assigned['properties'], managed_properties) * 100:.1f}% |"
    )
    lines.append(
        f"| 担当者不在 (`担当者不在`) | {unassigned['properties']:,} | {unassigned['units']:,} | {ratio(unassigned['properties'], managed_properties) * 100:.1f}% |"
    )
    lines.append("")
    lines.append("### 割当済みキューのステータス")
    lines.append("")
    lines.append("| Status | Count | Share |")
    lines.append("| --- | ---: | ---: |")
    lines.extend(top_status_rows(assigned["status"], assigned["properties"]))
    lines.append("")
    lines.append("### 担当者不在キューのステータス")
    lines.append("")
    lines.append("| Status | Count | Share |")
    lines.append("| --- | ---: | ---: |")
    lines.extend(top_status_rows(unassigned["status"], unassigned["properties"]))
    lines.append("")
    lines.append("## 回線別の構成")
    lines.append("")
    lines.append("### 割当済み")
    lines.append("")
    lines.append("| 回線 | 件数 | 構成比 |")
    lines.append("| --- | ---: | ---: |")
    lines.extend(top_line_rows(assigned["line"], assigned["properties"]))
    lines.append("")
    lines.append("### 担当者不在")
    lines.append("")
    lines.append("| 回線 | 件数 | 構成比 |")
    lines.append("| --- | ---: | ---: |")
    lines.extend(top_line_rows(unassigned["line"], unassigned["properties"]))
    lines.append("")
    lines.append("## 地域別の優先確認先")
    lines.append("")
    lines.append("### 割当済みが多い都道府県")
    lines.append("")
    lines.append("| 都道府県 | 件数 | 戸数 |")
    lines.append("| --- | ---: | ---: |")
    lines.extend(top_prefecture_rows(assigned["pref"], assigned["pref_units"]))
    lines.append("")
    lines.append("### 担当者不在が多い都道府県")
    lines.append("")
    lines.append("| 都道府県 | 件数 | 戸数 |")
    lines.append("| --- | ---: | ---: |")
    lines.extend(top_prefecture_rows(unassigned["pref"], unassigned["pref_units"]))
    lines.append("")
    lines.append("## 都道府県別配布サマリ（`データ集計` ベース）")
    lines.append("")
    lines.append(f"- 総計: 物件 **{int(to_number(aggregate.get('物件数', ''))):,}件** / 配布予定 **{int(planned):,}枚** / 実配付 **{int(delivered):,}枚**")
    lines.append(f"- 宅配ボックス無し: **{int(no_box):,}件** / 未導入率 **{to_number(aggregate.get('#DIV/0!', '')) * 100:.1f}%**")
    lines.append("")
    lines.append("| 都道府県 | 配布予定枚数 | 実配付枚数 | 実配付率 | 宅配ボックス無し率 |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    lines.extend(top_summary_pref_rows(summary["prefecture_summary"]))
    lines.append("")
    lines.append("## Member performance (`262 稼働分` ベース)")
    lines.append("")
    lines.append("- public リポジトリ向けに、担当者識別子はマスクしています。")
    lines.append("")
    lines.append("| 担当者 | 物件数 | 総戸数 | 実配付枚数 | 実配付率 | 配布完了件数 | レビュー候補 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    lines.extend(member_rows(current_run["members"]))
    lines.append("")
    lines.append("### Current run status")
    lines.append("")
    lines.append("| ステータス | 件数 |")
    lines.append("| --- | ---: |")
    lines.extend(simple_counter_rows(current_run["status"]))
    lines.append("")
    lines.append("### AI / OCR review signals")
    lines.append("")
    lines.append("| 項目 | 件数 |")
    lines.append("| --- | ---: |")
    lines.extend(simple_counter_rows(current_run["review"]))
    lines.append("")
    lines.append("| AI判定 | 件数 |")
    lines.append("| --- | ---: |")
    lines.extend(simple_counter_rows(current_run["ai"]))
    lines.append("")
    lines.append("## Team signals")
    lines.append("")
    lines.append(f"- 有効メンバー: **{members['active']}名**")
    lines.append(
        f"- 役割構成: " + ", ".join(f"{role} {count}名" for role, count in members["roles"].most_common()) if members["roles"] else "- 役割構成: 取得なし"
    )
    lines.append(f"- 月次報告回答: **{monthly['responses']}件** / 回答ベース希望枚数 **{monthly['requested_units']:,}枚**")
    lines.append(
        f"- 面談希望: **{monthly['interview_requests']}件** / 勤怠ログ: **{attendance['logs']}件** / 打刻者数: **{attendance['unique_workers']}名**"
    )
    if monthly["months"]:
        lines.append(
            "- 月次報告の対象月: " + ", ".join(f"{month} ({count})" for month, count in monthly["months"].items())
        )
    lines.append("")
    lines.append("## Automation backlog")
    lines.append("")
    lines.append(f"- フィードバック起点の自動化テーマ: **{feedback['total']}件**")
    lines.append(f"- 完了: **{feedback['done']}件** / 未完了: **{feedback['total'] - feedback['done']}件**")
    if feedback["pending_topics"]:
        lines.append("- 未完了テーマ例:")
        for topic in feedback["pending_topics"]:
            lines.append(f"  - {topic}")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    lines.append("1. **週次運用レポートの自動化**")
    lines.append("   - まずは `物件リスト` / `担当者不在` / `データ集計` を束ねた週次サマリを固定化する。")
    lines.append("2. **担当者不在キューの割当改善**")
    lines.append("   - 東京都、北海道、埼玉県、福岡県、大阪府の優先順位で割当解消ルールを作る。")
    lines.append("3. **日付と実績入力の整備**")
    lines.append("   - `配布予定日` / `開始日時` / `終了日時` の入力率を上げ、週次レポートを真の週次運用へ寄せる。")
    lines.append("4. **希望枚数・月次報告・勤怠の接続**")
    lines.append("   - 月次報告の希望枚数とメンバーマスタの目標、勤怠ログをつなげてキャパ計画に使う。")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    zf, shared_strings, workbook, rel_map = fetch_workbook(args.sheet_id)

    assigned_rows = sheet_rows(zf, shared_strings, workbook, rel_map, "物件リスト")
    unassigned_rows = sheet_rows(zf, shared_strings, workbook, rel_map, "担当者不在")
    member_rows = sheet_rows(zf, shared_strings, workbook, rel_map, "メンバーマスタ")
    monthly_rows = sheet_rows(zf, shared_strings, workbook, rel_map, "月次報告")
    attendance_rows = sheet_rows(zf, shared_strings, workbook, rel_map, "勤怠ログ")
    feedback_rows = sheet_rows(zf, shared_strings, workbook, rel_map, "フィードバック")
    summary_rows = sheet_rows(zf, shared_strings, workbook, rel_map, "データ集計")
    current_run_rows = sheet_rows(zf, shared_strings, workbook, rel_map, "262 稼働分")

    summary_data = {
        "assigned": summarize_queue(records(assigned_rows)),
        "unassigned": summarize_queue(records(unassigned_rows)),
        "members": summarize_members(records(member_rows)),
        "monthly": summarize_monthly(records(monthly_rows)),
        "attendance": summarize_attendance(records(attendance_rows)),
        "feedback": summarize_feedback(records(feedback_rows)),
        "current_run": summarize_current_run(records(current_run_rows)),
    }

    aggregate = summarize_summary_sheet(records(summary_rows, header_index=1))
    summary_data["aggregate_total"] = aggregate["total"]
    summary_data["prefecture_summary"] = aggregate["prefectures"]

    markdown = build_markdown(summary_data)
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
