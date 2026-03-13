#!/usr/bin/env python3

"""
毎日発行するポスティング日次レポート（配布完了確認シートベース）。

- 当月実績・当日（直近稼働日）実績
- メンバー別サマリ
- 配布進捗率が閾値未満のスタッフをリマインド候補として出力
- リマインド文ドラフト・JSON（メール/Slack連携用）を生成
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

from generate_posting_report import (
    DISTRIBUTION_COMPLETE_SHEET_ID,
    build_member_name_map,
    fetch_workbook,
    records,
    sheet_rows,
    to_number,
)

SHEET_ID = "1zUkpKOHO4ro35nvcCe-tfI-rNHWf3dJhPIVhPNuEla4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate daily posting report from 配布完了確認 sheet."
    )
    parser.add_argument(
        "--date",
        help="Target date YYYY-MM-DD. Default: today. Uses latest available if no data.",
    )
    parser.add_argument(
        "--distribution-complete-sheet-id",
        default=DISTRIBUTION_COMPLETE_SHEET_ID,
    )
    parser.add_argument(
        "--reminder-threshold",
        type=float,
        default=85.0,
        help="Progress rate threshold % for reminder. Below this = reminder candidate.",
    )
    parser.add_argument(
        "--min-units-for-reminder",
        type=int,
        default=50,
        help="Minimum total units to be considered for reminder (skip small assignments).",
    )
    parser.add_argument("--output", required=True, help="Output markdown path")
    parser.add_argument(
        "--reminders-json",
        help="Optional: output reminder candidates as JSON for automation.",
    )
    parser.add_argument(
        "--unmask",
        action="store_true",
        help="Show real member names.",
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
        parsed = parse_datetime(item.get(field, ""))
        if parsed:
            return parsed.date()
    return None


def _dedupe_by_id_date(recs: list[dict[str, str]]) -> list[dict[str, str]]:
    """同一 ID + 終了日時の重複を除外（終了日時で実配付枚数が紐づくため）。"""
    seen: set[tuple[str, str]] = set()
    out = []
    for r in recs:
        rid = str(r.get("ID", "")).strip()
        d = row_date(r)
        key = (rid, d.isoformat() if d else "")
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def summarize_by_date(
    recs: list[dict[str, str]],
    target_date: dt.date | None,
) -> tuple[dt.date, dict]:
    """指定日（または直近稼働日）のメンバー別集計。終了日時で重複除外。"""
    recs = _dedupe_by_id_date(recs)
    dates = sorted({row_date(r) for r in recs if row_date(r)})
    if not dates:
        raise RuntimeError("No dated rows in 配布完了 sheet.")

    use_date = target_date or dates[-1]
    if use_date not in dates:
        use_date = max(d for d in dates if d <= use_date) if use_date >= dates[0] else dates[-1]

    by_member: dict[str, dict] = {}
    total_props, total_units, total_delivered = 0, 0, 0

    for r in recs:
        if not r.get("ID"):
            continue
        d = row_date(r)
        if d != use_date:
            continue
        member = r.get("担当者", "").strip() or "(未設定)"
        u = int(to_number(r.get("総戸数", "")))
        dl = int(to_number(r.get("実配付枚数", "")))

        total_props += 1
        total_units += u
        total_delivered += dl

        m = by_member.setdefault(member, {"properties": 0, "units": 0, "delivered": 0})
        m["properties"] += 1
        m["units"] += u
        m["delivered"] += dl

    ranked = sorted(
        by_member.items(),
        key=lambda x: (x[1]["delivered"], x[1]["units"]),
        reverse=True,
    )
    return use_date, {
        "date": use_date,
        "total_properties": total_props,
        "total_units": total_units,
        "total_delivered": total_delivered,
        "members": ranked,
    }


def summarize_month(
    recs: list[dict[str, str]],
    year: int,
    month: int,
) -> dict:
    """当月のメンバー別集計。終了日時で重複除外。"""
    recs = _dedupe_by_id_date(recs)
    month_start = dt.date(year, month, 1)
    month_end = dt.date(year, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.date(year, 12, 31)

    by_member: dict[str, dict] = {}
    total_props, total_units, total_delivered = 0, 0, 0

    for r in recs:
        if not r.get("ID"):
            continue
        d = row_date(r)
        if not d or not (month_start <= d <= month_end):
            continue
        member = r.get("担当者", "").strip() or "(未設定)"
        u = int(to_number(r.get("総戸数", "")))
        dl = int(to_number(r.get("実配付枚数", "")))

        total_props += 1
        total_units += u
        total_delivered += dl

        m = by_member.setdefault(member, {"properties": 0, "units": 0, "delivered": 0})
        m["properties"] += 1
        m["units"] += u
        m["delivered"] += dl

    ranked = sorted(
        by_member.items(),
        key=lambda x: (x[1]["delivered"], x[1]["units"]),
        reverse=True,
    )
    return {
        "total_properties": total_props,
        "total_units": total_units,
        "total_delivered": total_delivered,
        "members": ranked,
    }


def load_monthly_targets(member_recs: list[dict[str, str]]) -> dict[str, int]:
    """メンバーマスタから 今月目標数（H列）を取得。メールアドレス -> 目標数"""
    targets: dict[str, int] = {}
    for r in member_recs:
        mail = r.get("メールアドレス", "").strip()
        val = r.get("今月目標数", "").strip()
        if not mail:
            continue
        try:
            targets[mail] = int(float(str(val).replace(",", ""))) if val and val != "-" else 0
        except (ValueError, TypeError):
            targets[mail] = 0
    return targets


def detect_delivery_anomalies(recs: list[dict[str, str]]) -> list[dict]:
    """実配付枚数がおかしいレコードを検出。重複はIDで除外。"""
    seen: set[tuple[str, str]] = set()
    anomalies = []
    for r in recs:
        if not r.get("ID"):
            continue
        total = int(to_number(r.get("総戸数", "")))
        delivered = int(to_number(r.get("実配付枚数", "")))
        if total <= 0:
            continue
        rate = (delivered / total * 100) if total else 0
        kind = None
        if delivered > total:
            kind = "実配付>総戸数"
        elif delivered == 0 and total >= 5:
            kind = "実配付=0"
        elif rate < 5 and total >= 20:
            kind = "実配付率<5%"
        if kind:
            key = (str(r.get("ID", "")), kind)
            if key in seen:
                continue
            seen.add(key)
            anomalies.append({
                "kind": kind,
                "id": r.get("ID", ""),
                "total": total,
                "delivered": delivered,
                "rate": round(rate, 1),
                "member": r.get("担当者", "").strip(),
                "property_name": (r.get("物件名", "") or "")[:40],
            })
    return anomalies


def reminder_candidates(
    members: list[tuple[str, dict]],
    threshold: float,
    min_units: int,
    name_map: dict[str, str] | None,
    unmask: bool,
) -> list[dict]:
    """進捗率が閾値未満のスタッフをリマインド候補として抽出。"""
    candidates = []
    for member_key, m in members:
        if m["units"] < min_units:
            continue
        progress = (m["delivered"] / m["units"] * 100) if m["units"] else 0
        if progress >= threshold:
            continue
        display = name_map.get(member_key, member_key) if unmask else member_key
        candidates.append({
            "member_key": member_key,
            "display_name": display,
            "properties": m["properties"],
            "units": m["units"],
            "delivered": m["delivered"],
            "progress": round(progress, 1),
            "threshold": threshold,
        })
    return candidates


def build_markdown(
    report_date: dt.date,
    month_data: dict,
    daily_data: dict,
    reminders: list[dict],
    threshold: float,
    name_map: dict[str, str] | None,
    unmask: bool,
    target_vs_actual: list[dict] | None = None,
    tehai_vs_delivered: list[dict] | None = None,
    anomalies: list[dict] | None = None,
) -> str:
    def disp(key: str) -> str:
        return name_map.get(key, key) if unmask else key

    lines = []
    lines.append("# Posting 日次レポート")
    lines.append("")
    lines.append(f"発行日: {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    lines.append(f"対象日: {report_date.isoformat()}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 当月サマリ
    y, m = report_date.year, report_date.month
    lines.append("## 当月実績サマリ")
    lines.append("")
    lines.append(f"**{y}年{m}月**")
    lines.append("")
    lines.append(f"- 件数: **{month_data['total_properties']:,}件**")
    lines.append(f"- 総戸数: **{month_data['total_units']:,}戸**")
    lines.append(f"- 実配付: **{month_data['total_delivered']:,}枚**")
    if month_data["total_units"]:
        mr = month_data["total_delivered"] / month_data["total_units"] * 100
        lines.append(f"- 実配付率: **{mr:.1f}%**")
    lines.append("")

    # 今月目標数 vs 配布枚数（当月の照合・目標枚数から起算）
    if tehai_vs_delivered:
        total_target = sum(r["tehai"] for r in tehai_vs_delivered)
        total_delivered = sum(r["delivered"] for r in tehai_vs_delivered)
        diff_total = total_target - total_delivered
        lines.append("## 今月目標数 vs 配布枚数（当月照合）")
        lines.append("")
        lines.append(f"- **今月目標枚数合計**: **{total_target:,}枚**（メンバーマスタ 今月目標数）")
        lines.append(f"- **現在の配布枚数**: **{total_delivered:,}枚**（配布完了確認シート 実配付）")
        lines.append(f"- **差分**: **{diff_total:+,}枚**（正=残り、負=オーバー）")
        lines.append("")
        lines.append("### メンバー別 今月目標数 vs 配布枚数")
        lines.append("")
        lines.append("| 担当者 | 今月目標数 | 配布枚数 | 差分 |")
        lines.append("| --- | ---: | ---: | ---: |")
        for row in tehai_vs_delivered:
            diff = row["tehai"] - row["delivered"]
            diff_str = f"{diff:+,}" if diff != 0 else "0"
            lines.append(f"| {row['display_name']} | {row['tehai']:,} | {row['delivered']:,} | {diff_str} |")
        lines.append("")
        # 差分の内訳（メンバー別）
        lines.append("### 差分の内訳（メンバー別）")
        lines.append("")
        lines.append("| 担当者 | 差分 | 内訳 |")
        lines.append("| --- | ---: | ---: |")
        for row in tehai_vs_delivered:
            diff = row["tehai"] - row["delivered"]
            if diff == 0:
                continue
            diff_str = f"{diff:+,}"
            pct = (diff / diff_total * 100) if diff_total else 0
            lines.append(f"| {row['display_name']} | {diff_str} | {pct:.1f}% |")
        lines.append("")

    # 今月目標数 vs 実配付枚数
    if target_vs_actual:
        lines.append("## 今月目標数 vs 実配付枚数")
        lines.append("")
        lines.append("- メンバーマスタ H列「今月目標数」と配布完了の実配付枚数（当月）を比較")
        lines.append("")
        lines.append("| 担当者 | 今月目標数 | 実配付枚数 | 達成率 |")
        lines.append("| --- | ---: | ---: | ---: |")
        for row in target_vs_actual:
            target = row["target"]
            actual = row["delivered"]
            rate = (actual / target * 100) if target else 0
            lines.append(f"| {row['display_name']} | {target:,} | {actual:,} | {rate:.1f}% |")
        lines.append("")

    # 当日サマリ
    lines.append("## 当日（直近稼働日）実績")
    lines.append("")
    lines.append(f"**{daily_data['date'].isoformat()}**")
    lines.append("")
    lines.append(f"- 件数: **{daily_data['total_properties']:,}件**")
    lines.append(f"- 総戸数: **{daily_data['total_units']:,}戸**")
    lines.append(f"- 実配付: **{daily_data['total_delivered']:,}枚**")
    if daily_data["total_units"]:
        dr = daily_data["total_delivered"] / daily_data["total_units"] * 100
        lines.append(f"- 実配付率: **{dr:.1f}%**")
    lines.append("")

    # メンバー別（当日）
    lines.append("### メンバー別（当日）")
    lines.append("")
    lines.append("| 担当者 | 件数 | 総戸数 | 実配付枚数 | 進捗率 |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for member_key, m in daily_data["members"]:
        progress = (m["delivered"] / m["units"] * 100) if m["units"] else 0
        lines.append(f"| {disp(member_key)} | {m['properties']:,} | {m['units']:,} | {m['delivered']:,} | {progress:.1f}% |")
    lines.append("")

    # リマインド候補
    lines.append("## リマインド候補")
    lines.append("")
    lines.append(f"- 基準: 進捗率 **{threshold:.1f}%** 未満（総戸数50戸以上）")
    lines.append("")
    if reminders:
        lines.append("| 担当者 | 進捗率 | 総戸数 | 実配付枚数 |")
        lines.append("| --- | ---: | ---: | ---: |")
        for r in reminders:
            lines.append(f"| {r['display_name']} | {r['progress']:.1f}% | {r['units']:,} | {r['delivered']:,} |")
        lines.append("")
        lines.append("### リマインド文ドラフト（コピー用）")
        lines.append("")
        for r in reminders:
            msg = (
                f"{r['display_name']}さん、本日（{daily_data['date'].isoformat()}）の配布進捗は {r['progress']:.1f}% です。"
                f"（実配付 {r['delivered']:,}枚 / 総戸数 {r['units']:,}戸）"
                f" 目標 {threshold:.0f}% に届いていません。状況確認をお願いします。"
            )
            lines.append(f"**【{r['display_name']}】**")
            lines.append(msg)
            lines.append("")
    else:
        lines.append("- リマインド候補はありません。")
    lines.append("")

    # 実配付枚数 要確認
    if anomalies:
        lines.append("## 実配付枚数 要確認")
        lines.append("")
        lines.append("- 実配付 > 総戸数、実配付=0、実配付率<5% などのレコード")
        lines.append("")
        by_kind: dict[str, list] = {}
        for a in anomalies:
            by_kind.setdefault(a["kind"], []).append(a)
        for kind in ("実配付>総戸数", "実配付=0", "実配付率<5%"):
            if kind not in by_kind:
                continue
            items = by_kind[kind]
            lines.append(f"### {kind} ({len(items)}件)")
            lines.append("")
            lines.append("| ID | 総戸数 | 実配付 | 率 | 担当者 | 物件名 |")
            lines.append("| --- | ---: | ---: | ---: | --- | --- |")
            for a in items[:20]:
                lines.append(
                    f"| {a['id']} | {a['total']:,} | {a['delivered']:,} | {a['rate']:.1f}% | "
                    f"{disp(a['member']) if a['member'] else '-'} | {a['property_name'][:25]} |"
                )
            if len(items) > 20:
                lines.append(f"| ... | 他 {len(items) - 20} 件 |")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*配布完了確認シートの `配布完了` タブを参照*")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    target = dt.date.fromisoformat(args.date) if args.date else dt.date.today()

    zf_dc, shared_dc, workbook_dc, rel_map_dc = fetch_workbook(
        args.distribution_complete_sheet_id
    )
    zf_post, shared_post, workbook_post, rel_map_post = fetch_workbook(SHEET_ID)

    recs = records(sheet_rows(zf_dc, shared_dc, workbook_dc, rel_map_dc, "配布完了"))
    member_recs = records(sheet_rows(zf_post, shared_post, workbook_post, rel_map_post, "メンバーマスタ"))
    name_map = build_member_name_map(member_recs) if args.unmask else None

    report_date, daily_data = summarize_by_date(recs, target)
    month_data = summarize_month(recs, report_date.year, report_date.month)

    reminders = reminder_candidates(
        daily_data["members"],
        args.reminder_threshold,
        args.min_units_for_reminder,
        name_map,
        args.unmask,
    )

    # メンバー全員（ポスリストV2 メンバーマスタをマスタとする）
    all_member_keys = [
        r.get("メールアドレス", "").strip()
        for r in member_recs
        if r.get("メールアドレス", "").strip()
    ]

    # 今月目標数 vs 実配付枚数（全員分）
    targets = load_monthly_targets(member_recs)
    delivered_by_member = {k: m["delivered"] for k, m in month_data["members"]}
    target_vs_actual = []
    for member_key in all_member_keys:
        target = targets.get(member_key, 0)
        delivered = delivered_by_member.get(member_key, 0)
        target_vs_actual.append({
            "display_name": (name_map or {}).get(member_key, member_key),
            "target": target,
            "delivered": delivered,
        })
    target_vs_actual.sort(key=lambda x: (-x["delivered"], -x["target"]))

    # 今月目標数 vs 配布枚数（メンバー別・全員分・目標枚数から起算）
    tehai_vs_delivered = []
    for member_key in all_member_keys:
        target = targets.get(member_key, 0)
        delivered = delivered_by_member.get(member_key, 0)
        tehai_vs_delivered.append({
            "display_name": (name_map or {}).get(member_key, member_key),
            "tehai": target,  # 今月目標数で起算
            "delivered": delivered,
        })
    tehai_vs_delivered.sort(key=lambda x: (-x["delivered"], -x["tehai"]))

    # 実配付枚数 要確認
    anomalies = detect_delivery_anomalies(recs)

    md = build_markdown(
        report_date,
        month_data,
        daily_data,
        reminders,
        args.reminder_threshold,
        name_map,
        args.unmask,
        target_vs_actual=target_vs_actual,
        tehai_vs_delivered=tehai_vs_delivered,
        anomalies=anomalies,
    )

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(md)

    if args.reminders_json:
        payload = {
            "report_date": report_date.isoformat(),
            "threshold": args.reminder_threshold,
            "candidates": [
                {
                    "member_key": r["member_key"],
                    "display_name": r["display_name"],
                    "progress": r["progress"],
                    "units": r["units"],
                    "delivered": r["delivered"],
                    "message": (
                        f"{r['display_name']}さん、本日（{report_date.isoformat()}）の配布進捗は {r['progress']:.1f}% です。"
                        f"（実配付 {r['delivered']:,}枚 / 総戸数 {r['units']:,}戸）"
                        f" 目標 {args.reminder_threshold:.0f}% に届いていません。状況確認をお願いします。"
                    ),
                }
                for r in reminders
            ],
        }
        with open(args.reminders_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
