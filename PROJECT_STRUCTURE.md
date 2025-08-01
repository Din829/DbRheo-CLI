# DbRheo プロジェクト構造

## プロジェクト概要

**プロジェクト名**: DbRheo - 智能数据库Agent  
**タイプ**: AI駆動データベース管理システム  
**技術スタック**: Python (FastAPI, SQLAlchemy) + TypeScript (React) + Google Gemini API  
**ベースアーキテクチャ**: Gemini CLI Architecture

## ディレクトリツリー

```
dbrheo/
├── packages/                      # モノレポ構造のパッケージディレクトリ
│   ├── cli/                      # CLIインターフェースパッケージ
│   │   ├── CLI_DESIGN_PLAN.md   # CLI設計計画書
│   │   ├── README.md            # CLIパッケージ説明書
│   │   ├── README_ENHANCED_LAYOUT.md  # 拡張レイアウト設計書
│   │   ├── cli.py              # 旧CLIエントリーポイント
│   │   ├── pyproject.toml      # CLIパッケージ設定
│   │   ├── setup_enhanced_layout.py  # レイアウト設定スクリプト
│   │   └── src/                # CLIソースコード
│   │       ├── dbrheo_cli/     # CLIメインモジュール
│   │       │   ├── __init__.py
│   │       │   ├── app/        # アプリケーション層
│   │       │   │   ├── cli.py  # CLIメインロジック
│   │       │   │   └── config.py  # 設定管理
│   │       │   ├── constants.py   # 定数定義
│   │       │   ├── handlers/      # イベントハンドラー
│   │       │   │   ├── event_handler.py    # イベント処理
│   │       │   │   ├── input_handler.py    # 入力処理
│   │       │   │   └── tool_handler.py     # ツール実行処理
│   │       │   ├── i18n.py       # 国際化サポート
│   │       │   ├── main.py       # エントリーポイント
│   │       │   └── ui/           # UIコンポーネント
│   │       │       ├── ascii_art.py        # ASCIIアート表示
│   │       │       ├── console.py          # コンソール管理
│   │       │       ├── layout_manager.py   # レイアウト管理
│   │       │       ├── messages.py         # メッセージ表示
│   │       │       ├── simple_multiline_input.py  # 複数行入力
│   │       │       ├── startup.py          # 起動画面
│   │       │       ├── streaming.py        # ストリーミング表示
│   │       │       └── tools.py           # ツール関連UI
│   │       └── tests/           # テストコード
│   │
│   ├── core/                    # コアビジネスロジックパッケージ
│   │   ├── pyproject.toml      # コアパッケージ設定
│   │   └── src/
│   │       └── dbrheo/         # コアモジュール
│   │           ├── __init__.py
│   │           ├── __main__.py
│   │           ├── adapters/   # データベースアダプター層
│   │           │   ├── adapter_factory.py   # アダプター生成
│   │           │   ├── base.py             # 基底クラス
│   │           │   ├── connection_manager.py  # 接続管理
│   │           │   ├── connection_string.py   # 接続文字列パーサー
│   │           │   ├── dialect_parser.py      # 方言パーサー
│   │           │   ├── mysql_adapter.py       # MySQLアダプター
│   │           │   ├── postgresql_adapter.py  # PostgreSQLアダプター
│   │           │   ├── sqlite_adapter.py      # SQLiteアダプター
│   │           │   └── transaction_manager.py # トランザクション管理
│   │           ├── api/        # Web API層
│   │           │   ├── app.py  # FastAPIアプリケーション
│   │           │   ├── dependencies.py  # 依存性注入
│   │           │   └── routes/          # APIルート
│   │           │       ├── chat.py      # チャットエンドポイント
│   │           │       ├── database.py  # データベース操作
│   │           │       └── websocket.py # WebSocket通信
│   │           ├── config/     # 設定管理
│   │           │   ├── base.py         # 基本設定
│   │           │   └── test_config.py  # テスト設定
│   │           ├── core/       # コアロジック（Gemini CLI準拠）
│   │           │   ├── chat.py         # チャット管理
│   │           │   ├── client.py       # Geminiクライアント
│   │           │   ├── compression.py  # データ圧縮
│   │           │   ├── environment.py  # 環境管理
│   │           │   ├── memory.py       # メモリ管理
│   │           │   ├── next_speaker.py # 次話者判定
│   │           │   ├── prompts.py      # プロンプト管理
│   │           │   ├── scheduler.py    # スケジューラー
│   │           │   └── turn.py         # ターン管理
│   │           ├── prompts/    # プロンプトテンプレート
│   │           │   ├── database_agent_prompt.py    # DB Agent用
│   │           │   ├── optimized_database_prompt.py # 最適化版
│   │           │   └── safe_response.md            # 安全応答
│   │           ├── services/   # サービス層
│   │           │   └── gemini_service.py  # Gemini API連携
│   │           ├── telemetry/  # テレメトリー
│   │           │   ├── logger.py   # ロギング
│   │           │   ├── metrics.py  # メトリクス
│   │           │   └── tracer.py   # トレーシング
│   │           ├── tools/      # ツール実装
│   │           │   ├── base.py                    # 基底クラス
│   │           │   ├── code_execution_tool.py     # コード実行
│   │           │   ├── database_connect_tool.py   # DB接続
│   │           │   ├── database_export_tool.py    # データエクスポート
│   │           │   ├── directory_list_tool.py     # ディレクトリ一覧
│   │           │   ├── file_read_tool.py          # ファイル読み取り
│   │           │   ├── file_write_tool.py         # ファイル書き込み
│   │           │   ├── registry.py                # ツールレジストリ
│   │           │   ├── risk_evaluator.py          # リスク評価
│   │           │   ├── schema_discovery.py        # スキーマ探索
│   │           │   ├── shell_tool.py              # シェル実行
│   │           │   ├── sql_tool.py                # SQL実行
│   │           │   ├── table_details_tool.py      # テーブル詳細
│   │           │   ├── web_fetch_tool.py          # Web取得
│   │           │   └── web_search_tool.py         # Web検索
│   │           ├── types/      # 型定義
│   │           │   ├── core_types.py  # コア型
│   │           │   ├── file_types.py  # ファイル型
│   │           │   └── tool_types.py  # ツール型
│   │           └── utils/      # ユーティリティ
│   │               ├── debug_logger.py          # デバッグログ
│   │               ├── encoding_utils.py        # エンコーディング
│   │               ├── errors.py                # エラー定義
│   │               ├── function_response.py     # 関数レスポンス
│   │               ├── log_integration.py       # ログ統合
│   │               ├── parameter_sanitizer.py   # パラメータ検証
│   │               ├── realtime_logger.py       # リアルタイムログ
│   │               ├── retry.py                 # リトライ機構
│   │               ├── retry_with_backoff.py    # バックオフ付きリトライ
│   │               └── type_converter.py        # 型変換
│   │
│   └── web/                    # Webフロントエンドパッケージ
│       ├── index.html         # エントリーHTML
│       ├── package.json       # Node.js設定
│       ├── src/              # ソースコード
│       │   ├── App.tsx       # メインアプリケーション
│       │   ├── components/   # Reactコンポーネント
│       │   │   ├── chat/     # チャットUI
│       │   │   │   └── ChatContainer.tsx
│       │   │   └── database/ # データベースUI
│       │   │       ├── QueryEditor.tsx   # クエリエディター
│       │   │       └── ResultTable.tsx   # 結果テーブル
│       │   ├── main.tsx      # エントリーポイント
│       │   └── styles/       # スタイルシート
│       │       └── global.css
│       ├── tailwind.config.js # Tailwind CSS設定
│       ├── tsconfig.json      # TypeScript設定
│       └── vite.config.ts     # Viteビルド設定
│
├── Makefile                   # ビルド・実行コマンド
├── PROJECT_STATUS.md          # プロジェクト状態ドキュメント
├── README.md                  # プロジェクト概要
├── chat_cli.py               # CLIチャットスクリプト（開発用）
├── dbrheo.log                # アプリケーションログ
├── log_config.yaml           # ログ設定
├── pyproject.toml            # プロジェクト全体の設定
├── requirements.txt          # Python依存関係
└── 各種テスト・開発用ファイル
```

## アーキテクチャ概要

### 1. 全体アーキテクチャ

DbRheoは、Gemini CLIアーキテクチャをベースにした3層構造のアプリケーションです：

- **プレゼンテーション層**: CLI（コマンドライン）とWeb（React）の2つのインターフェース
- **ビジネスロジック層**: Gemini CLI準拠のコアシステム（Turn、Memory、Scheduler）
- **データアクセス層**: マルチデータベース対応のアダプター層

### 2. Gemini CLIアーキテクチャとの整合性

DbRheoは以下のGemini CLIコンポーネントを継承・拡張しています：

- **Turn System**: 会話のターン管理（`core/turn.py`）
- **Memory Management**: 双方向履歴管理（`core/memory.py`）
- **Tool System**: プラグイン可能なツールアーキテクチャ（`tools/`）
- **Next Speaker Logic**: 次の発話者判定（`core/next_speaker.py`）
- **Prompt Engineering**: 構造化されたプロンプト管理（`prompts/`）

### 3. データベース特化機能

- **マルチデータベース対応**: SQLite、MySQL、PostgreSQL対応
- **インテリジェントリスク評価**: SQL実行前の自動リスク判定
- **スキーマ探索**: 段階的なデータベース構造の理解
- **トランザクション管理**: 安全なデータ操作

## 技術スタック

### バックエンド
- **言語**: Python 3.9+
- **Webフレームワーク**: FastAPI 0.115.0+
- **データベースORM**: SQLAlchemy 2.0.36+（非同期対応）
- **AI/ML**: Google Generative AI 0.8.3+
- **非同期処理**: asyncio, uvicorn

### フロントエンド
- **言語**: TypeScript
- **UIフレームワーク**: React
- **スタイリング**: Tailwind CSS
- **ビルドツール**: Vite

### インフラ・監視
- **テレメトリー**: OpenTelemetry 1.28.0+
- **ロギング**: Python logging + YAML設定
- **テスト**: pytest, pytest-asyncio

## 主要コンポーネント

### 1. CLI（`packages/cli/`）
- **役割**: ターミナルベースのユーザーインターフェース
- **主要機能**:
  - インタラクティブな複数行入力（ペースト検出対応）
  - リアルタイムストリーミング表示
  - 国際化対応（i18n）
  - ツール実行の確認・承認フロー

### 2. Core（`packages/core/`）
- **役割**: ビジネスロジックとGemini API連携
- **主要機能**:
  - Gemini APIとの通信管理
  - ツールの登録・実行管理
  - データベースアダプターの管理
  - セッション状態管理

### 3. Web（`packages/web/`）
- **役割**: ブラウザベースのユーザーインターフェース
- **主要機能**:
  - リアルタイムチャット
  - SQLクエリエディター
  - 結果の視覚的表示
  - WebSocket通信

### 4. Tools（`packages/core/src/dbrheo/tools/`）
- **データベース操作ツール**:
  - `sql_tool.py`: SQL実行
  - `schema_discovery.py`: スキーマ探索
  - `database_export_tool.py`: データエクスポート
- **ファイルシステムツール**:
  - `file_read_tool.py`: ファイル読み取り
  - `file_write_tool.py`: ファイル書き込み
- **その他のツール**:
  - `web_fetch_tool.py`: Web情報取得
  - `shell_tool.py`: シェルコマンド実行

## 開発・デプロイメント

### 開発環境セットアップ
```bash
# 依存関係のインストール
pip install -r requirements.txt

# 開発モードでの起動
make dev
```

### ビルド
```bash
# プロダクションビルド
make build

# Dockerイメージビルド
make docker-build
```

### テスト
```bash
# 単体テスト実行
pytest

# カバレッジレポート
pytest --cov=dbrheo
```

## 設計原則

1. **Gemini CLI準拠**: 既存のGemini CLIアーキテクチャとの完全な互換性
2. **モジュラー設計**: 各コンポーネントの独立性と再利用性
3. **安全性優先**: データベース操作の徹底的なリスク管理
4. **拡張性**: 新しいデータベースやツールの追加が容易
5. **ユーザー体験**: 直感的で応答性の高いインターフェース