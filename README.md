# DbRheoCLI - DB/DA-AIエージェント

DbRheoは、データベース操作/データ分析CLIエージェントです。自然言語でのデータベースクエリ実行、スキーマ探索、リスク評価機能、またPythonを使ってデータ分析能力を提供します。

## クイックスタート

```bash
# 1. リポジトリのクローン
git clone https://github.com/Din829/DbRheo-CLI.git
cd DbRheo-CLI

# 2. 依存関係のインストール
pip install -r requirements.txt
# または Windows の場合: install_dependencies.bat

# 3. 環境設定
cp .env.example .env
# .envファイルでGOOGLE_API_KEYを設定

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

### 対応データベース
- PostgreSQL 12以上
- MySQL 8.0以上
- SQLite 3.35以上

## インストール手順

### 1. リポジトリのクローン
```bash
git clone https://github.com/Din829/DbRheo-CLI.git
cd DbRheo-CLI
```

### 2. Python環境の構築
```bash
# 仮想環境の作成
python -m venv venv

# 仮想環境の有効化
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 依存関係のインストール
pip install -r requirements.txt

# Windows用の自動インストールスクリプト（オプション）
# install_dependencies.bat
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
```bash
# パッケージをインストールしてから起動
dbrheo

# データベースファイル指定
dbrheo --db-file /path/to/database.db

# デバッグモード（レベル0-5）
dbrheo --debug 3

# ログ出力有効化
dbrheo --log

# カラー出力無効化
dbrheo --no-color

# 設定ファイル指定
dbrheo --config /path/to/config.yaml

# ヘルプ表示
dbrheo --help
```

#### 開発モード（推奨）
```bash
# 方法1: 開発用スクリプト（推奨）
cd packages/cli
python cli.py

# 方法2: 直接main.pyを実行
python packages/cli/src/dbrheo_cli/main.py

# 引数の例
python packages/cli/src/dbrheo_cli/main.py --debug 3 --log

# Webサーバー起動（開発用）
python packages/core/src/dbrheo/__main__.py --host localhost --port 8000 --reload
```

### 設定例
`.env`ファイルの設定例：
```env
# Google AI設定（必須）
GOOGLE_API_KEY=your_google_api_key_here

# モデル設定
DBRHEO_MODEL=gemini-2.5-flash

# サーバー設定
DBRHEO_HOST=localhost
DBRHEO_PORT=8000
DBRHEO_DEBUG=true

# ログ設定
DBRHEO_LOG_LEVEL=INFO

# Agent設定
DBRHEO_MAX_TURNS=100
DBRHEO_AUTO_EXECUTE=false
DBRHEO_ALLOW_DANGEROUS=false

# 入力拡張機能
DBRHEO_ENHANCED_INPUT=true
DBRHEO_MULTILINE_ENABLED=true
DBRHEO_AUTO_PASTE_DETECTION=true

# コード実行設定（オプション）
CODE_EXECUTION_LANGUAGES=python,javascript,shell,sql
CODE_EXECUTION_MAX_OUTPUT=1048576
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

## プロジェクト構成

```
DbRheo/
├── packages/
│   ├── core/           # コアビジネスロジック（v1.0.0）
│   ├── cli/            # コマンドラインインターフェース（v0.1.0）
│   └── web/            # WebインターフェースMVP（基本実装済み）
├── requirements.in     # 高レベル依存関係
├── requirements.txt    # 固定バージョン依存関係
├── .env.example        # 環境設定テンプレート
└── testdata/           # テストデータ
```

## 開発環境

### 開発用依存関係のインストール
```bash
# 開発用依存関係を含めてインストール
pip install -e "packages/core[dev]"
pip install -e "packages/cli[dev]"

# 拡張機能（オプション）
pip install -e "packages/cli[enhanced]"
```

### コード品質チェック
```bash
# フォーマット
black packages/
ruff check packages/

# 型チェック
mypy packages/

# テスト実行
pytest packages/core/tests/
pytest packages/cli/tests/
```

## セキュリティ

### リスク評価機能
- DROP、DELETE文の実行前警告
- 大量データ操作の確認プロンプト
- 本番環境での危険操作の制限

### データ保護
- API キーの安全な管理
- データベース認証情報の暗号化
- 操作ログの詳細記録

## トラブルシューティング

### よくある問題

**インポートエラー**
```bash
# 仮想環境が有効化されているか確認
which python

# 必要な依存関係のインストール確認
pip install -r requirements.txt

# パッケージの再インストール（必要に応じて）
pip install -e packages/core -e packages/cli

# 依存関係の競合チェック
pip check
```

**CLIコマンドが見つからない**
```bash
# パッケージのインストール状況確認
pip show dbrheo-cli

# 開発モードでの直接実行（推奨）
cd packages/cli
python cli.py

# または直接main.pyを実行
python packages/cli/src/dbrheo_cli/main.py

# パッケージをインストールしてから実行
cd packages/cli && pip install -e . && cd ../.. && dbrheo
```

**API キーエラー**
```bash
# 環境変数の確認
echo $GOOGLE_API_KEY

# .envファイルの読み込み確認
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('GOOGLE_API_KEY'))"
```

**コード実行エラー**
```bash
# Python実行環境の確認
python --version

# 必要なライブラリのインストール
pip install pandas matplotlib numpy
```

## ライセンス

MIT License - 詳細は[LICENSE](LICENSE)ファイルを参照してください。

## 貢献

プロジェクトへの貢献を歓迎します。Issue報告やプルリクエストをお待ちしています。

### 開発ガイドライン
1. フォーク後、機能ブランチを作成
2. コード品質チェックの実行
3. テストの追加・更新
4. プルリクエストの作成

## 注意事項

### Webインターフェースについて
現在、Webインターフェース（`packages/web/`）はMVP（最小実行可能製品）状態です。基本的なアーキテクチャは実装済みですが、完全な機能体験にはCLIインターフェースをご利用ください。

### パフォーマンス最適化
- 大規模データセットでの操作時は、適切なインデックスの設定を推奨
- 長時間実行されるクエリには、タイムアウト設定の調整が必要な場合があります

## サポート

技術的な質問やバグ報告は、GitHubのIssueページをご利用ください。

## 更新履歴

### Core v1.0.0 / CLI v0.1.0
- 初期リリース
- 基本的なデータベース操作機能
- Gemini API統合
- マルチデータベース対応
- Pythonコード実行機能
- WebインターフェースMVP実装
