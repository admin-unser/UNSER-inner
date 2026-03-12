# data/posting

Posting-related source data lives here.

Examples:
- posting spreadsheets
- prefecture summaries
- distribution logs
- raw CSV exports

## ジモティー求人用エクスポート

`scripts/export_unassigned_for_jimoty.py` で担当者不在の都道府県別件数・戸数を出力できます。

```bash
cd scripts
python3 export_unassigned_for_jimoty.py --output ../data/posting/unassigned-by-pref.json
```

詳細: `docs/ops/jimoty-unassigned-integration.md`
