#!/usr/bin/env python3

"""Generate daily posting reports for all dates in a month that have data."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys

from generate_posting_report import fetch_workbook, records, sheet_rows
from generate_posting_daily_report import row_date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SHEET_ID = "1zUkpKOHO4ro35nvcCe-tfI-rNHWf3dJhPIVhPNuEla4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate daily reports for all dates in a month."
    )
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--sheet-id", default=SHEET_ID)
    parser.add_argument("--output-dir", required=True, help="Directory for daily/*.md")
    return parser.parse_args()


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

    dates_in_month = sorted(
        d for item in recs
        if (d := row_date(item)) and month_start <= d <= month_end
    )
    unique_dates = sorted(set(dates_in_month), reverse=True)

    if not unique_dates:
        print(f"No dated rows in 262 稼働分 for {args.month}.", file=sys.stderr)
        return 1

    os.makedirs(args.output_dir, exist_ok=True)
    failed = 0
    for d in unique_dates:
        out_path = os.path.join(args.output_dir, f"{d.isoformat()}.md")
        result = subprocess.run(
            [
                sys.executable,
                "generate_posting_daily_report.py",
                "--sheet-id", args.sheet_id,
                "--date", d.isoformat(),
                "--output", out_path,
            ],
            cwd=SCRIPT_DIR,
        )
        if result.returncode == 0:
            print(f"  {d.isoformat()}.md")
        else:
            failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
