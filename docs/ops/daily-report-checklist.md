# 日次レポート発行チェックリスト

毎日正しいレポートが発行されるための確認項目です。

## 自動実行（GitHub Actions）

- **スケジュール**: 毎日 UTC 23:00（JST 翌朝 08:00）
- **対象ブランチ**: main（スケジュールは main でのみ実行）
- **出力**: `reports/posting/YYYY-MM/daily/YYYY-MM-DD.md` を自動 commit

### 確認方法

1. GitHub リポジトリ → **Actions** タブ
2. 「Daily Posting Report」ワークフローを選択
3. 最新の実行結果を確認
4. 手動実行: **Run workflow** ボタンで実行可能

### 動作しない場合

- **main にマージ済みか**: スケジュールは main でのみ有効
- **GOOGLE_CHAT_WEBHOOK_URL**: Secrets に設定するとリマインドを送信（未設定でもレポートは生成される）
- **push 失敗**: ブランチ保護ルールで GITHUB_TOKEN の push が拒否されている場合

## 手動実行

```bash
cd scripts
python3 generate_posting_daily_report_complete.py \
  --output ../reports/posting/2026-03/daily/$(date +%Y-%m-%d).md \
  --reminders-json ../reports/posting/2026-03/daily/$(date +%Y-%m-%d)-reminders.json
```

### 実名表示（社内用）

```bash
python3 generate_posting_daily_report_complete.py \
  --output ../reports/posting/2026-03/daily/$(date +%Y-%m-%d).md \
  --unmask
```

## データソース

- **配布完了実績**: [配布完了確認シート](https://docs.google.com/spreadsheets/d/1wIE_FrIv4a7QoeMcKROAYesxbMIFmsHwAXFV6k-6h0Y) の `配布完了` タブ
- **今月目標数**: [posting シート](https://docs.google.com/spreadsheets/d/1zUkpKOHO4ro35nvcCe-tfI-rNHWf3dJhPIVhPNuEla4) の `メンバーマスタ` H列

## レポート内容

- 当月実績サマリ
- 今月目標数 vs 実配付枚数（達成率）
- 当日（直近稼働日）実績
- リマインド候補（進捗率 85% 未満）
- 実配付枚数 要確認（実配付>総戸数、実配付=0、実配付率<5%）
