# 実配付枚数エラーの修正

配布完了シートで「実配付 > 総戸数」となっているレコードを自動修正します。

## 修正対象

- **実配付 > 総戸数**: 実配付枚数を総戸数に修正（物理的にあり得ないため）

※ 実配付=0、実配付率<5% は正しい値が不明なため手動確認が必要です。

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. サービスアカウントの作成

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. **APIとサービス** → **認証情報** → **サービスアカウントを作成**
3. サービスアカウントの **キー** を JSON 形式で作成・ダウンロード

### 3. シートの共有

配布完了確認シートを、サービスアカウントのメールアドレス（`xxx@xxx.iam.gserviceaccount.com`）に **編集** 権限で共有してください。

### 4. 環境変数の設定

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

## 実行方法

```bash
cd scripts

# 修正対象の確認（実際の更新は行わない）
python3 fix_delivery_count.py --dry-run

# 修正を実行
python3 fix_delivery_count.py
```

## 注意

- 実行前に必ず `--dry-run` で確認してください
- サービスアカウントの JSON はリポジトリに commit しないでください
