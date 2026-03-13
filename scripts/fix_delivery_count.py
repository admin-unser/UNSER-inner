#!/usr/bin/env python3

"""
配布完了シートの実配付枚数エラーを修正する。

- 実配付 > 総戸数 → 実配付 = 総戸数 に修正
- --dry-run: 認証不要で xlsx から対象を確認
- 実際の更新: Google Sheets API（要: サービスアカウント認証）

使い方:
  python3 fix_delivery_count.py --dry-run  # 認証不要で確認
  # 更新する場合:
  # 1. pip install gspread google-auth
  # 2. サービスアカウント作成、シート共有
  # 3. GOOGLE_APPLICATION_CREDENTIALS 設定
  python3 fix_delivery_count.py
"""

from __future__ import annotations

import argparse
import os
import sys

DISTRIBUTION_COMPLETE_SHEET_ID = "1wIE_FrIv4a7QoeMcKROAYesxbMIFmsHwAXFV6k-6h0Y"
SHEET_NAME = "配布完了"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fix 実配付枚数 errors in 配布完了 sheet."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apply no changes. Uses xlsx export (no auth needed).",
    )
    parser.add_argument(
        "--credentials",
        default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
        help="Path to service account JSON. Or set GOOGLE_APPLICATION_CREDENTIALS.",
    )
    return parser.parse_args()


def to_number(value) -> float:
    if value is None:
        return 0.0
    text = str(value).replace(",", "").strip()
    if not text or text in {"-", "#DIV/0!", "#REF!"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def get_records_via_xlsx() -> list[dict]:
    """xlsx エクスポートでレコード取得（認証不要）。"""
    from generate_posting_report import fetch_workbook, records, sheet_rows

    zf, shared, workbook, rel_map = fetch_workbook(DISTRIBUTION_COMPLETE_SHEET_ID)
    rows = sheet_rows(zf, shared, workbook, rel_map, SHEET_NAME)
    return records(rows)


def get_records_via_api(credentials_path: str) -> tuple[list[dict], object, object]:
    """gspread でレコード取得（行番号付き）。"""
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(DISTRIBUTION_COMPLETE_SHEET_ID)
    wks = sh.worksheet(SHEET_NAME)
    records = wks.get_all_records()
    return records, sh, wks


def main() -> int:
    args = parse_args()

    if args.dry_run:
        records = get_records_via_xlsx()
        headers = list(records[0].keys()) if records else []
        col_total = headers.index("総戸数") if "総戸数" in headers else None
        col_delivered = headers.index("実配付枚数") if "実配付枚数" in headers else None
        if col_total is None or col_delivered is None:
            print("Error: 総戸数 または 実配付枚数 列が見つかりません。", file=sys.stderr)
            return 1
        fixes = []
        for i, row in enumerate(records):
            total = int(to_number(row.get("総戸数", 0)))
            delivered = int(to_number(row.get("実配付枚数", 0)))
            if total > 0 and delivered > total:
                fixes.append({
                    "row": i + 2,
                    "id": row.get("ID", ""),
                    "total": total,
                    "delivered": delivered,
                    "property": (row.get("物件名", "") or "")[:30],
                })
        if not fixes:
            print("修正対象はありません。")
            return 0
        print(f"[--dry-run] 修正対象: {len(fixes)} 件")
        for f in fixes[:15]:
            print(f"  行{f['row']}: ID={f['id']} 総戸数={f['total']} 実配付={f['delivered']} → {f['total']}  {f['property']}")
        if len(fixes) > 15:
            print(f"  ... 他 {len(fixes) - 15} 件")
        print("\n実際に修正するには認証を設定して --dry-run なしで実行してください。")
        return 0

    if not args.credentials or not os.path.isfile(args.credentials):
        print(
            "Error: GOOGLE_APPLICATION_CREDENTIALS を設定するか --credentials で JSON パスを指定してください。",
            file=sys.stderr,
        )
        return 1

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print(
            "Error: gspread と google-auth が必要です。\n  pip install gspread google-auth",
            file=sys.stderr,
        )
        return 1

    records, sh, wks = get_records_via_api(args.credentials)
    headers = wks.row_values(1)
    col_total = headers.index("総戸数") + 1 if "総戸数" in headers else None
    col_delivered = headers.index("実配付枚数") + 1 if "実配付枚数" in headers else None

    if not col_total or not col_delivered:
        print("Error: 総戸数 または 実配付枚数 列が見つかりません。", file=sys.stderr)
        return 1

    fixes = []
    for i, row in enumerate(records):
        row_num = i + 2  # 1-based, skip header
        total = int(to_number(row.get("総戸数", 0)))
        delivered = int(to_number(row.get("実配付枚数", 0)))
        if total <= 0:
            continue
        if delivered > total:
            fixes.append({
                "row": row_num,
                "id": row.get("ID", ""),
                "total": total,
                "delivered": delivered,
                "property": (row.get("物件名", "") or "")[:30],
            })

    if not fixes:
        print("修正対象はありません。")
        return 0

    print(f"修正対象: {len(fixes)} 件")
    for f in fixes[:10]:
        print(f"  行{f['row']}: ID={f['id']} 総戸数={f['total']} 実配付={f['delivered']} → {f['total']}  {f['property']}")
    if len(fixes) > 10:
        print(f"  ... 他 {len(fixes) - 10} 件")

    def col_to_letter(n: int) -> str:
        s = ""
        while n > 0:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    col_letter = col_to_letter(col_delivered)
    body = {
        "valueInputOption": "USER_ENTERED",
        "data": [
            {
                "range": f"{SHEET_NAME}!{col_letter}{f['row']}",
                "values": [[str(f["total"])]],
            }
            for f in fixes
        ],
    }

    sh.values_batch_update(body)
    print(f"\n{len(fixes)} 件を修正しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
