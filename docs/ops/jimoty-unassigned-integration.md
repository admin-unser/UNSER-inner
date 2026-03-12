# ジモティー求人投稿 × 担当者不在 連携

担当者不在キューの都道府県別データをジモティー求人投稿（Claude Code Agent 等）で活用するためのガイドです。

## 概要

- **担当者不在**: posting シートの `担当者不在` タブに、担当者が割り当てられていない物件が蓄積されています。
- **ジモティー**: 地域密着の求人・案件投稿で、担当者不在解消のための募集に活用できます。
- **連携**: 本リポジトリのスクリプトで都道府県別の件数・戸数をエクスポートし、Claude Code Agent 等が求人コピー作成に利用できます。

## データ出力

### エクスポートスクリプト

```bash
cd scripts
python3 export_unassigned_for_jimoty.py --output ../data/posting/unassigned-by-pref.json
```

または CSV:

```bash
python3 export_unassigned_for_jimoty.py --format csv --output ../data/posting/unassigned-by-pref.csv
```

### 出力例（JSON）

```json
[
  {"prefecture": "東京都", "properties": 21630, "units": 1150902},
  {"prefecture": "北海道", "properties": 7970, "units": 411422},
  {"prefecture": "埼玉県", "properties": 7381, "units": 349932},
  ...
]
```

### オプション

- `--min-units N`: 戸数が N 件以上ある都道府県のみ出力（小規模地域を除外）

## Claude Code Agent との連携

1. **週次運用**: 上記スクリプトを定期実行し、`data/posting/unassigned-by-pref.json` を更新

2. **Agent への入力**: ジモティー投稿用 Agent に、JSON ファイルのパスまたは内容を渡す

3. **求人コピー例**: Agent が地域別に件数・戸数を参照し、求人文を生成
   - 例: 「東京都で 21,630 件、約 115 万戸のポスティング案件。週1回〜、日払い可。」

## 注意事項

- 機微情報（個人名、連絡先など）は出力に含めません
- 件数・戸数は集計値のみで、物件詳細は含みません
- ジモティー投稿は別途 Claude Code Agent 等で実装してください

## 関連

- `scripts/export_unassigned_for_jimoty.py` … エクスポートスクリプト
- `docs/ops/sheets-automation-roadmap.md` … posting シート自動化の方針
