# reports

Generated reports live here.

## Posting レポート（月次管理）

ポスティング関連レポートは `posting/YYYY-MM/` 以下に月次で格納します。

```
reports/posting/YYYY-MM/
├── monthly-summary.md      … 月次サマリ（運用在庫スナップショット）
├── monthly-aggregate.md    … 月次集計（備考: 262稼働分ベース）
├── daily/                  … 日次レポート
│   └── YYYY-MM-DD.md
└── members/                … メンバー別月次レポート
    └── member-XXX.md
```

### 生成方法

```bash
cd scripts
python3 run_posting_reports.py --month 2026-03
```

Examples:
- weekly summaries
- monthly business reports
- KPI snapshots
- analysis outputs
