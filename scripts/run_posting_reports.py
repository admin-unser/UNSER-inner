#!/usr/bin/env python3

"""
月次・日次・メンバー別のポスティングレポートを一括生成するオーケストレータ。

出力先: reports/posting/YYYY-MM/
  - monthly-summary.md      … 月次サマリ（週次相当の運用在庫スナップショット）
  - monthly-aggregate.md    … 月次集計（備考: 262稼働分ベースの日次集計）
  - daily/YYYY-MM-DD.md     … 日次レポート
  - members/member-XXX.md   … メンバー別月次レポート
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys

# scripts/ からの相対パス
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_BASE = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "reports", "posting"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate monthly, daily, and per-member posting reports."
    )
    parser.add_argument(
        "--month",
        required=True,
        help="Target month in YYYY-MM format.",
    )
    parser.add_argument(
        "--sheet-id",
        default="1zUkpKOHO4ro35nvcCe-tfI-rNHWf3dJhPIVhPNuEla4",
        help="Google Sheets ID",
    )
    parser.add_argument(
        "--skip-daily",
        action="store_true",
        help="Skip daily report generation.",
    )
    parser.add_argument(
        "--skip-members",
        action="store_true",
        help="Skip per-member report generation.",
    )
    parser.add_argument(
        "--skip-aggregate",
        action="store_true",
        help="Skip monthly aggregate (備考).",
    )
    parser.add_argument(
        "--unmask",
        action="store_true",
        help="担当者名を実名で表示（社内用）",
    )
    return parser.parse_args()


def run_cmd(cmd: list[str]) -> bool:
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    return result.returncode == 0


def main() -> int:
    args = parse_args()
    try:
        year, month = map(int, args.month.split("-"))
        target_month = dt.date(year, month, 1)
    except ValueError:
        print(f"Invalid --month: {args.month}. Use YYYY-MM.", file=sys.stderr)
        return 1

    month_dir = os.path.join(REPORTS_BASE, args.month)
    daily_dir = os.path.join(month_dir, "daily")
    members_dir = os.path.join(month_dir, "members")

    for d in (month_dir, daily_dir, members_dir):
        os.makedirs(d, exist_ok=True)

    # 1. 月次サマリ（週次相当の運用在庫スナップショット）
    summary_path = os.path.join(month_dir, "monthly-summary.md")
    summary_cmd = [
        sys.executable,
        "generate_posting_report.py",
        "--sheet-id", args.sheet_id,
        "--output", summary_path,
    ]
    if args.unmask:
        summary_cmd.append("--unmask")
    if not run_cmd(summary_cmd):
        print("Failed to generate monthly summary.", file=sys.stderr)
        return 1
    print(f"Generated: {summary_path}")

    # 2. 日次レポート（当月にデータがある日付を自動検出して生成）
    if not args.skip_daily:
        daily_ok = run_cmd(
            [
                sys.executable,
                "generate_posting_reports_monthly.py",
                "--month", args.month,
                "--sheet-id", args.sheet_id,
                "--output-dir", daily_dir,
            ]
        )
        if not daily_ok:
            print("Warning: daily report generation had issues.", file=sys.stderr)
        else:
            print(f"Generated daily reports in: {daily_dir}")

    # 3. メンバー別月次レポート
    if not args.skip_members:
        members_cmd = [
            sys.executable,
            "generate_posting_member_reports.py",
            "--month", args.month,
            "--sheet-id", args.sheet_id,
            "--output-dir", members_dir,
        ]
        if args.unmask:
            members_cmd.append("--unmask")
        members_ok = run_cmd(members_cmd)
        if not members_ok:
            print("Warning: member report generation had issues.", file=sys.stderr)
        else:
            print(f"Generated member reports in: {members_dir}")

    # 4. 月次集計（備考）
    if not args.skip_aggregate:
        agg_path = os.path.join(month_dir, "monthly-aggregate.md")
        agg_ok = run_cmd(
            [
                sys.executable,
                "generate_posting_monthly_aggregate.py",
                "--month", args.month,
                "--sheet-id", args.sheet_id,
                "--output", agg_path,
            ]
        )
        if agg_ok:
            print(f"Generated: {agg_path}")
        else:
            print("Warning: monthly aggregate generation had issues.", file=sys.stderr)

    print(f"\nReports saved under: {month_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
