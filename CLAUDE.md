# CLAUDE.md

## プロジェクト概要

nasne の HDD 残容量を定期的にチェックし、Discord に通知する Python スクリプト。
cron で定期実行する想定。

## 技術スタック

- Python 3
- 依存: `requests`, `PyYAML`

## コマンド

```bash
# 依存インストール
pip install -r requirements.txt

# 通常実行
python nasne_monitor.py --config config.yaml

# 強制実行（容量変化に関係なく通知）
python nasne_monitor.py --config config.yaml --force

# ローカルモード（Discord送信なし）
python nasne_monitor.py --config config.yaml --local
```

## プロジェクト構成

- `nasne_monitor.py` — メインスクリプト（全ロジックがこの1ファイル）
- `config.yaml.example` — 設定ファイルのテンプレート
- `requirements.txt` — Python 依存パッケージ

## 設定

`config.yaml` または環境変数 (`NASNE_IP`, `DISCORD_WEBHOOK_URL`) で設定する。
`--local` モード時は `discord_webhook_url` は不要。

## コーディング規約

- 日本語でコメント・docstring を記述
- 型ヒントを使用
