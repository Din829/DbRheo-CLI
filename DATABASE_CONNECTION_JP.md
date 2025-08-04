# データベース接続ガイド

DbRheoのデータベース接続機能について説明します。

## サポートされているデータベース

- **MySQL/MariaDB** - 完全対応
- **PostgreSQL** - 完全対応  
- **SQLite** - 完全対応
- **SQL Server** - ドライバーのインストールが必要
- **Oracle** - ドライバーのインストールが必要

## 接続方法

### 1. ローカルデータベース
```
/database
```
AIが対話的に接続情報を収集します。

### 2. リモートデータベース（SSHトンネル経由）
企業環境でよく使用される接続方法：
```
リモートデータベースにはSSHトンネルが必要です。
SSH情報（ホスト、ユーザー、鍵ファイル）を提供してください。
```

### 3. 接続文字列の直接指定
```
mysql://user:password@localhost:3306/database
postgresql://user:password@localhost:5432/database
```

## 接続設定の保存

### 保存
接続成功後、AIが自動的に保存を提案します：
```
この接続を保存しますか？（action="save"）
```

### 読み込み
保存した接続を再利用：
```
保存した接続 "prod_db" を使用
```

### 設定ファイル
接続情報は `.dbrheo/connections.yaml` に保存されます：
- パスワードは暗号化されません（セキュリティに注意）
- チーム共有可能

### プロンプト例
データベースホスト：EC2インスタンスのプライベートIP 52.192.50.251
データベースポート：3306
データベースユーザー：root
データベースパスワード：xxx
データベース名：colleague_news_db
SSHトンネル情報：52.192.50.251 ec2-user C:\Users\q9951\Desktop\AIplatJava\colleague-news-key.pem