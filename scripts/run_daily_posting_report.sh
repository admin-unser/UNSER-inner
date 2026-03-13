#!/bin/bash
# 毎日発行するポスティング日次レポートを生成し、Google Chat に送信するスクリプト
# cron 例: 0 8 * * * /path/to/scripts/run_daily_posting_report.sh
# Google Chat 送信: GOOGLE_CHAT_WEBHOOK_URL を環境変数に設定

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORTS_BASE="$(cd "$SCRIPT_DIR/../reports/posting" && pwd)"
DATE=$(date +%Y-%m-%d)
MONTH=$(date +%Y-%m)
OUTPUT_DIR="$REPORTS_BASE/$MONTH/daily"
OUTPUT="$OUTPUT_DIR/$DATE.md"
REMINDERS_JSON="$OUTPUT_DIR/${DATE}-reminders.json"

mkdir -p "$OUTPUT_DIR"
cd "$SCRIPT_DIR"

python3 generate_posting_daily_report_complete.py \
  --date "$DATE" \
  --output "$OUTPUT" \
  --reminders-json "$REMINDERS_JSON" \
  --unmask

echo "Generated: $OUTPUT"

if [ -n "$GOOGLE_CHAT_WEBHOOK_URL" ] && [ -f "$REMINDERS_JSON" ]; then
  python3 send_to_google_chat.py --reminders-json "$REMINDERS_JSON" && echo "Sent to Google Chat."
fi
