
# DbRheoCLI - DataBase/DataAnalysis エージェント

DbRheoは、データベース操作/データ分析CLIエージェントです。自然言語でのデータベースクエリ実行、スキーマ探索、リスク評価機能、またPythonを使ってデータ分析能力を提供します。

## ⚠️ 注意事項

**Google APIの不安定性について**: 初回対話入力後、Google APIの応答が不安定なため処理が停止する場合があります。その際は`Ctrl+C`でプロセスを終了し、python cli.pyで再度メッセージを送信してください。

## クイックスタート

```bash
# 1. リポジトリのクローン
git clone https://github.com/Din829/DbRheo-CLI.git
cd DbRheo-CLI

# 2. Dependenciesのインストール
pip install -r requirements.txt


# 3. 環境設定
cp .env.example .env
# .envファイルでGOOGLE_API_KEY、OPENAI_API_KEYいずれを設定
#　現時点でClaudeモデルはPromptCashingが適用されていませんのでおすすめしません


# 4. CLI起動
cd packages/cli
python cli.py
```

## 主要機能

### コア機能
- **自然言語クエリ処理**: 日本語でのデータベース操作指示
- **インテリジェントSQL生成**: 安全で最適化されたクエリの自動生成
- **スキーマ自動探索**: データベース構造の動的解析
- **リスク評価システム**: 危険な操作の事前検出と警告
- **Pythonコード実行**: データ分析、可視化、自動化スクリプトの実行
- **データエクスポート**: CSV、JSON、Excel形式での結果出力

### 技術特徴
- **非同期処理**: 高性能なasync/await実装
- **マルチデータベース対応**: PostgreSQL、MySQL、SQLite対応
- **モジュラー設計**: 拡張可能なプラグインアーキテクチャ
- **包括的ログ**: 詳細な操作履歴とデバッグ情報
- **インテリジェント入力**: 自動多行検出、ペースト処理
- **ストリーミング出力**: リアルタイムレスポンス表示
- **国際化対応**: 多言語サポート（日本語、英語）

## システム要件

### 必須環境
- Python 3.9以上
- Node.js 20以上（Web UI開発時のみ）

### 対応データベース（DEMOのため、今後拡張予定）
- PostgreSQL 12以上
- MySQL 8.0以上
- SQLite 3.35以上

## インストール手順

### 1. リポジトリのクローン
```bash
git clone https://github.com/Din829/DbRheo-CLI.git
cd DbRheo-CLI
```

または
https://dev.azure.com/HPSMDI/POC_Agent/_git/db-rheo-cli
　

### 2. Python環境の構築
```bash

# 依存関係のインストール
pip install -r requirements.txt

```

### 3. パッケージのインストール（オプション）
```bash
# コアパッケージのインストール
cd packages/core
pip install -e .
cd ../..

# CLIパッケージのインストール
cd packages/cli
pip install -e .
cd ../..

# インストール確認
pip show dbrheo-core dbrheo-cli
```

**注意**: パッケージをインストールしなくても、開発モードで直接実行できます。

### 4. 環境設定
```bash
# 設定ファイルのコピー
cp .env.example .env

# .envファイルを編集し、以下を設定:
# - Google API キー
# - データベース接続情報
```

## 起動方法

### CLIモードでの起動

#### パッケージインストール後

# ヘルプ表示
/help

#　モデル指定
/model
```




## 使用方法

### 基本的な対話例
```
DbRheo> ユーザーテーブルの構造を教えて
[スキーマ探索を実行中...]
テーブル 'users' の構造:
- id: INTEGER (主キー)
- name: VARCHAR(100)
- email: VARCHAR(255)
- created_at: TIMESTAMP

DbRheo> 最新の10件のユーザーを表示して
[SQLクエリを生成中...]
SELECT * FROM users ORDER BY created_at DESC LIMIT 10;
[実行結果を表示...]
```

### データ分析機能
```
DbRheo> 売上データをPythonで分析して可視化して
[Pythonコードを生成中...]
import pandas as pd
import matplotlib.pyplot as plt

# データベースから売上データを取得
df = pd.read_sql("SELECT * FROM sales", connection)

# 月別売上集計
monthly_sales = df.groupby('month')['amount'].sum()

# グラフ作成
plt.figure(figsize=(10, 6))
monthly_sales.plot(kind='bar')
plt.title('月別売上推移')
plt.savefig('sales_analysis.png')

[実行結果: グラフファイル sales_analysis.png を生成しました]
```

### 高度なSQL機能
```
DbRheo> 売上データの月別集計を作成
[複雑なクエリを生成中...]
SELECT
    DATE_TRUNC('month', order_date) as month,
    SUM(amount) as total_sales
FROM orders
GROUP BY month
ORDER BY month;
```



