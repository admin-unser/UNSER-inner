#!/usr/bin/env python3

"""
リマインド候補またはレポート内容を Google Chat に送信する。

Webhook URL は環境変数 GOOGLE_CHAT_WEBHOOK_URL で指定。
Google Chat のスペースで Webhook を作成: スペース設定 > アプリを管理 > Webhook を追加
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send reminders or report to Google Chat."
    )
    parser.add_argument(
        "--reminders-json",
        help="Path to reminders JSON from generate_posting_daily_report_complete.py",
    )
    parser.add_argument(
        "--report-md",
        help="Path to daily report markdown. Sends summary as text.",
    )
    parser.add_argument(
        "--webhook-url",
        default=os.environ.get("GOOGLE_CHAT_WEBHOOK_URL"),
        help="Google Chat webhook URL. Default: GOOGLE_CHAT_WEBHOOK_URL env.",
    )
    return parser.parse_args()


def send_to_chat(webhook_url: str, payload: dict) -> bool:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json; charset=UTF-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        print(f"HTTP error: {e.code} {e.reason}", file=sys.stderr)
        if e.fp:
            print(e.fp.read().decode(), file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False


def build_message_from_reminders(reminders: dict) -> dict:
    """リマインド JSON から Google Chat メッセージを構築。"""
    report_date = reminders.get("report_date", "")
    threshold = reminders.get("threshold", 85)
    candidates = reminders.get("candidates", [])

    if not candidates:
        return {
            "text": (
                f"📋 ポスティング日次レポート ({report_date})\n\n"
                f"✅ リマインド候補はありません。（進捗率 {threshold:.0f}% 以上）"
            )
        }

    lines = [
        f"📋 ポスティング日次レポート ({report_date})",
        f"⚠️ 進捗率 {threshold:.0f}% 未満のスタッフ（リマインド候補）",
        "",
    ]
    for c in candidates:
        lines.append(f"• {c['display_name']}: {c['progress']:.1f}% （{c['delivered']:,}枚 / {c['units']:,}戸）")
        lines.append(f"  → {c['message']}")
        lines.append("")

    return {"text": "\n".join(lines)}


def build_message_from_report_md(content: str) -> dict:
    """レポート Markdown から配布レポート要約を抽出してメッセージを構築。"""
    lines = content.strip().split("\n")
    out = ["📋 ポスティング日次レポート（配布レポート）", ""]

    def collect_section(start_marker: str, end_markers: tuple[str, ...], max_lines: int = 15) -> list[str]:
        section = []
        in_section = False
        for line in lines:
            if line.strip().startswith(start_marker):
                in_section = True
                continue
            if in_section:
                if any(line.strip().startswith(m) for m in end_markers):
                    break
                if line.strip():
                    section.append(line)
                    if len(section) >= max_lines:
                        break
        return section

    # 当月実績サマリ
    month = collect_section("## 当月実績サマリ", ("## ",), 10)
    if month:
        out.extend(month)
        out.append("")

    # 手配枚数 vs 配布枚数
    tehai = collect_section("## 手配枚数 vs 配布枚数", ("## ",), 25)
    if tehai:
        out.extend(tehai)
        out.append("")

    # 当日（直近稼働日）実績
    daily = collect_section("## 当日（直近稼働日）実績", ("## ",), 10)
    if daily:
        out.extend(daily)
        out.append("")

    # リマインド候補
    if "## リマインド候補" in content:
        idx = content.find("## リマインド候補")
        block = content[idx:idx + 800].split("\n")
        for line in block[:12]:
            if line.strip() and not line.strip().startswith("## "):
                out.append(line)
        out.append("")

    text = "\n".join(out).strip()
    if len(text) > 28000:
        text = text[:28000] + "\n\n...(省略)"
    return {"text": text}


def main() -> int:
    args = parse_args()
    if not args.webhook_url:
        print(
            "Error: GOOGLE_CHAT_WEBHOOK_URL を設定するか --webhook-url を指定してください。",
            file=sys.stderr,
        )
        return 1

    if args.reminders_json:
        with open(args.reminders_json, encoding="utf-8") as f:
            reminders = json.load(f)
        payload = build_message_from_reminders(reminders)
    elif args.report_md:
        with open(args.report_md, encoding="utf-8") as f:
            content = f.read()
        payload = build_message_from_report_md(content)
    else:
        print("Error: --reminders-json または --report-md を指定してください。", file=sys.stderr)
        return 1

    if send_to_chat(args.webhook_url, payload):
        print("Sent to Google Chat.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
