# reports/posting

ポスティングレポートを月次で管理します。

## ディレクトリ構成

```
posting/
└── YYYY-MM/
    ├── monthly-summary.md      … 月次サマリ（運用在庫スナップショット）
    ├── monthly-aggregate.md    … 月次集計（備考: 262稼働分ベース）
    ├── daily/                  … 日次レポート
    │   └── YYYY-MM-DD.md
    └── members/                … メンバー別月次レポート
        └── member-XXX.md
```

## 生成

```bash
cd scripts
python3 run_posting_reports.py --month 2026-03
```

オプション:
- `--skip-daily` … 日次レポートをスキップ
- `--skip-members` … メンバー別レポートをスキップ
- `--skip-aggregate` … 月次集計をスキップ
- `--unmask` … 担当者名を実名で表示（社内用。public には commit しないこと）

メンバー名を実名で出力する場合（社内用）:
```bash
python3 run_posting_reports.py --month 2026-03 --unmask
# または個別に:
python3 generate_posting_report.py --output ../reports/posting/2026-03/monthly-summary.md --unmask
python3 generate_posting_member_reports.py --month 2026-03 --output-dir ../reports/posting/2026-03/members --unmask
```

## 毎日発行レポート

配布完了確認シートベースの日次レポート（当月・当日実績、リマインド候補付き）:

```bash
cd scripts
python3 generate_posting_daily_report_complete.py \
  --output ../reports/posting/2026-03/daily/2026-03-13.md \
  --reminders-json ../reports/posting/2026-03/daily/2026-03-13-reminders.json \
  --unmask
```

GitHub Actions で毎日自動実行されます。詳細: `docs/ops/daily-posting-report.md`

## ジモティー担当者不在連携

担当者不在の都道府県別データは `scripts/export_unassigned_for_jimoty.py` でエクスポートできます。
詳細: `docs/ops/jimoty-unassigned-integration.md`
