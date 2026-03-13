# ポスティング日次レポート（毎日発行）

配布完了確認シートをベースに、毎日レポートを発行し、配布進捗率が低いスタッフへのリマインドを支援します。

## レポート内容

- **当月実績サマリ**: 今月の配布完了件数・戸数・実配付枚数
- **当日（直近稼働日）実績**: 対象日のメンバー別実績
- **リマインド候補**: 進捗率が閾値（デフォルト85%）未満のスタッフ
- **リマインド文ドラフト**: コピー＆ペーストで送れる文面

## 実行方法

### 手動実行

```bash
cd scripts

# 今日の日付でレポート生成（実名表示）
python3 generate_posting_daily_report_complete.py \
  --output ../reports/posting/2026-03/daily/2026-03-13.md \
  --unmask

# リマインド候補を JSON 出力（メール/Slack 連携用）
python3 generate_posting_daily_report_complete.py \
  --output ../reports/posting/2026-03/daily/2026-03-13.md \
  --reminders-json ../reports/posting/2026-03/daily/2026-03-13-reminders.json \
  --unmask

# 進捗率閾値の変更（例: 90% 未満でリマインド）
python3 generate_posting_daily_report_complete.py \
  --reminder-threshold 90 \
  --output ../reports/posting/2026-03/daily/2026-03-13.md \
  --unmask
```

### 毎日自動実行（cron）

```bash
# スクリプトに実行権限を付与
chmod +x scripts/run_daily_posting_report.sh

# crontab に追加（毎朝 8:00 に実行）
# crontab -e
0 8 * * * /path/to/UNSER-inner/scripts/run_daily_posting_report.sh
```

### GitHub Actions で毎日実行

`.github/workflows/daily-posting-report.yml` が含まれています。

- **スケジュール**: 毎日 UTC 23:00（JST 翌朝 08:00）
- **手動実行**: Actions タブから "Run workflow" で実行可能
- **出力**: `reports/posting/YYYY-MM/daily/` に Markdown を commit
- **注意**: 自動実行時は担当者名をマスク（public リポジトリ向け）。実名・リマインド JSON が必要な場合は手動で `--unmask` と `--reminders-json` 付きで実行し、`shared/` 等に保存（reminders JSON はメールアドレスを含むため public には commit しないこと）

従来の例（参考）:

```yaml
name: Daily Posting Report
on:
  schedule:
    - cron: '0 23 * * *'  # UTC 23:00 = JST 08:00
  workflow_dispatch:
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Generate report
        run: |
          cd scripts
          DATE=$(date -u +%Y-%m-%d)
          MONTH=$(date -u +%Y-%m)
          mkdir -p ../reports/posting/$MONTH/daily
          python3 generate_posting_daily_report_complete.py \
            --date $DATE \
            --output ../reports/posting/$MONTH/daily/$DATE.md \
            --reminders-json ../reports/posting/$MONTH/daily/${DATE}-reminders.json
      - name: Commit and push
        run: |
          git config user.name "bot"
          git config user.email "bot@example.com"
          git add reports/posting/
          git diff --staged --quiet || git commit -m "chore: daily posting report $(date -u +%Y-%m-%d)"
          git push
```

## リマインドの送信

### オプション 1: 手動でコピー＆送信

レポートの「リマインド文ドラフト」をコピーし、メールやチャットで送信。

### オプション 2: JSON を利用した自動送信

`--reminders-json` で出力される JSON を、メール送信スクリプトや Slack webhook に渡す。

```json
{
  "report_date": "2026-03-12",
  "threshold": 85,
  "candidates": [
    {
      "member_key": "xxx@gmail.com",
      "display_name": "山田太郎",
      "progress": 72.5,
      "units": 500,
      "delivered": 362,
      "message": "山田太郎さん、本日（2026-03-12）の配布進捗は 72.5% です。..."
    }
  ]
}
```

- `candidates` が空ならリマインド不要
- 各 `message` をメール本文や Slack メッセージに使用可能

### オプション 3: メール連携（要実装）

`scripts/send_reminders.py` 等で、reminders JSON を読み取り、SMTP でメール送信するスクリプトを追加可能。メールアドレスは メンバーマスタ から取得。

## オプション一覧

| オプション | デフォルト | 説明 |
| --- | --- | --- |
| `--date` | 今日 | 対象日 YYYY-MM-DD |
| `--reminder-threshold` | 85 | 進捗率がこの値未満でリマインド候補 |
| `--min-units-for-reminder` | 50 | 総戸数がこの値未満はリマインド対象外 |
| `--reminders-json` | - | リマインド候補を JSON 出力 |
| `--unmask` | - | 担当者名を実名表示 |

## 出力先

- レポート: `reports/posting/YYYY-MM/daily/YYYY-MM-DD.md`
- リマインド JSON: `reports/posting/YYYY-MM/daily/YYYY-MM-DD-reminders.json`（指定時）
