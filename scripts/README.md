# scripts

Automation scripts live here.

## Posting レポート

- `run_posting_reports.py` … 月次・日次・メンバー別レポートを一括生成
- `generate_posting_report.py` … 週次相当サマリ（運用在庫）
- **`generate_posting_daily_report_complete.py`** … **毎日発行用日次レポート**（配布完了確認シートベース、リマインド候補付き）
- `generate_posting_daily_report.py` … 日次レポート（262 稼働分ベース）
- `generate_posting_member_reports.py` … メンバー別月次レポート
- `generate_posting_monthly_aggregate.py` … 月次集計（備考）
- `export_unassigned_for_jimoty.py` … 担当者不在の都道府県別エクスポート（ジモティー求人用）
- `run_daily_posting_report.sh` … 毎日レポート用シェル（cron 向け、GOOGLE_CHAT_WEBHOOK_URL で Chat 送信）
- `send_to_google_chat.py` … リマインドを Google Chat に送信

Examples:
- sheet import scripts
- report generation scripts
- validation tools
- scheduled job utilities
