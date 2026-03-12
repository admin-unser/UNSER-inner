# Sheets Automation Roadmap

このドキュメントは、UNSER の Google シート運用を自動化していく最初の方針をまとめたものです。

## 対象

- office シート
- posting シート

## 先にやること

### 1. 構造の棚卸し

最初に、各シートの

- タブ一覧
- ヘッダ行
- 行数
- 機微情報の有無

を棚卸しします。

そのための再実行可能なスクリプトとして `scripts/sheet_inventory.py` を追加しています。

## office シートの方針

office シートは、事業計画、売上、費用、契約、支払、各種管理台帳などが混在する可能性が高く、
機微情報や認証情報が含まれる前提で扱います。

### 初期方針

- 機微情報を含むタブを先に分類する
- raw データのまま public な成果物に出さない
- 最初は「構造把握」と「集計対象の切り分け」を優先する

### 最初の自動化候補

1. シート棚卸しレポート
2. 月次売上・費用サマリの抽出
3. 支払期限や申請期限の一覧化

## posting シートの方針

posting シートは、配布対象物件、担当者、勤怠、月次報告、未割当物件などを一つの運用基盤として扱える可能性が高いです。

### 初期方針

- 物件リストを主データとみなす
- メンバーマスタと担当者不在データを組み合わせる
- 週次レポートを最初の成果物にする

### 最初の自動化候補

1. 未割当物件レポート
2. 都道府県別・担当者別の進捗レポート
3. 月次報告と勤怠ログの確認レポート

### レポート運用（月次管理）

- **月次・日次・メンバー別**: `scripts/run_posting_reports.py --month YYYY-MM`
- 出力先: `reports/posting/YYYY-MM/`（monthly-summary, daily/, members/, monthly-aggregate）
- **配布完了実績**: [配布完了確認シート](https://docs.google.com/spreadsheets/d/1wIE_FrIv4a7QoeMcKROAYesxbMIFmsHwAXFV6k-6h0Y) の `配布完了` タブを参照
- **担当者不在 × ジモティー**: `scripts/export_unassigned_for_jimoty.py` で都道府県別エクスポート
  - 詳細: `docs/ops/jimoty-unassigned-integration.md`

## おすすめの実装順

1. `scripts/sheet_inventory.py` で構造把握を固定化
2. posting シートの週次運用レポートを実装
3. office シートの月次管理サマリを実装

## 注意

- 認証情報、API キー、個人情報、口座情報をレポートへそのまま出力しない
- public リポジトリへ raw データを commit しない
- 生成レポートは用途に応じてマスキングする
