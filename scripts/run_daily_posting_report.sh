#!/bin/bash
# 毎日発行するポスティング日次レポートを生成するスクリプト
# cron 例: 0 8 * * * /path/to/scripts/run_daily_posting_report.sh

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
echo "Reminders: $REMINDERS_JSON"
