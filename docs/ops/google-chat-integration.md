# Google Chat 連携

ポスティング日次レポートのリマインドを Google Chat に自動送信します。

## 1. Google Chat で Webhook を作成

1. Google Chat でスペースを開く（または新規作成）
2. スペース名の横の **▼** → **スペースを管理**
3. **アプリを管理** → **Webhook** を追加
4. 名前を入力（例: ポスティングレポート）→ **保存**
5. 表示された **Webhook URL** をコピー

## 2. Webhook URL の設定

### 手動実行時

```bash
export GOOGLE_CHAT_WEBHOOK_URL="https://chat.googleapis.com/v1/spaces/XXXXX/messages?key=XXXXX&token=XXXXX"
python3 scripts/send_to_google_chat.py --reminders-json reports/posting/2026-03/daily/2026-03-13-reminders.json
```

### cron で毎日実行する場合

`crontab -e` で環境変数を設定:

```bash
GOOGLE_CHAT_WEBHOOK_URL="https://chat.googleapis.com/v1/spaces/XXXXX/messages?key=XXXXX&token=XXXXX"
0 8 * * * /path/to/UNSER-inner/scripts/run_daily_posting_report.sh
```

または、`run_daily_posting_report.sh` の先頭に追加:

```bash
export GOOGLE_CHAT_WEBHOOK_URL="https://chat.googleapis.com/..."
```

### GitHub Actions で実行する場合

1. リポジトリの **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** で `GOOGLE_CHAT_WEBHOOK_URL` を追加
3. ワークフローで `env` に設定（下記参照）

## 3. 送信内容

- **リマインド候補あり**: 対象日のレポート日付、進捗率が閾値未満のスタッフ一覧とメッセージ
- **リマインド候補なし**: 「リマインド候補はありません」と表示

## 4. 使い方

### リマインド JSON から送信

```bash
python3 scripts/send_to_google_chat.py --reminders-json reports/posting/2026-03/daily/2026-03-13-reminders.json
```

### レポート Markdown から要約を送信

```bash
python3 scripts/send_to_google_chat.py --report-md reports/posting/2026-03/daily/2026-03-13.md
```

### 日次レポート生成 + Google Chat 送信（一括）

```bash
export GOOGLE_CHAT_WEBHOOK_URL="https://..."
./scripts/run_daily_posting_report.sh
```

## 5. セキュリティ

- **Webhook URL は秘密情報**です。リポジトリに commit しないでください。
- GitHub Secrets や環境変数で管理してください。
- Webhook が漏洩した場合は、Google Chat で Webhook を削除し、新しい URL を発行してください。
