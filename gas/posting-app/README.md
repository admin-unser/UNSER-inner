# ポスティングアプリ統合管理システム

物件リスト（posting シート）で動作する GAS。OCR・アーカイブ・請求書・差し戻し連絡などを担当。

## 機能一覧

| 関数名 | 説明 |
| --- | --- |
| `processOCR` | 配布写真を Gemini で OCR、物件名と比較して AI 判定 |
| `autoResetTasks` | 6ヶ月以上前の配布完了を未着手にリセット |
| `sendDailyRemandReport` | 差し戻し案件を担当者にメール送信 |
| `setRemandTrigger1130` | 毎日 11:30 に sendDailyRemandReport を実行するトリガーを設定 |
| `sendMonthlyInvoices` | 前月分の請求書を PDF でメール送信 |
| `archiveDataByStatus` | 配布完了・投函禁止をアーカイブシートに移管 |

## アーカイブ移管（archiveDataByStatus）

- **ソース**: アクティブなスプレッドシートの `物件リスト` タブ
- **先**: [配布完了確認シート](https://docs.google.com/spreadsheets/d/1wIE_FrIv4a7QoeMcKROAYesxbMIFmsHwAXFV6k-6h0Y)
  - `配布完了` タブ: ステータス「配布完了」「OK」の行
  - `投函禁止` タブ: ステータス「投函禁止」の行
- **元シート**: 移管後、未着手など残す行のみで上書き

※ 物件リストと物件リストV2 が同一か別かは要確認。現在は「物件リスト」を参照。

## セットアップ

### API キー（Gemini）

**Script Properties で管理することを推奨**（リポジトリに commit しない）:

1. Apps Script エディタ → **ファイル** → **プロジェクトのプロパティ** → **スクリプト プロパティ**
2. `GEMINI_API_KEY` を追加し、API キーを設定

コード内で `PropertiesService.getScriptProperties().getProperty("GEMINI_API_KEY")` を参照。

従来どおりコード内に直接書く場合は、`YOUR_API_KEY_HERE` を置き換えてください。

### トリガー

| 関数 | 推奨トリガー |
| --- | --- |
| sendDailyRemandReport | 毎日 11:30（setRemandTrigger1130 を1回手動実行で設定） |
| processOCR | 手動 または 時間主導型 |
| archiveDataByStatus | 手動（準備が整ってから） |
| sendMonthlyInvoices | 毎月1日 など |

## トリガー確認

1. スプレッドシート → **拡張機能** → **Apps Script**
2. 左サイドバー **トリガー**（時計アイコン）
3. 登録済みトリガーを確認 → `gas/posting-app/TRIGGER.md` に記録
