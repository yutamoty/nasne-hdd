# nasne HDD容量監視 Discord通知システム

nasne の HDD 残容量を定期的にチェックし、Discord に通知するスクリプトです。

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. 設定ファイルの作成

```bash
cp config.yaml.example config.yaml
```

`config.yaml` を編集して、nasne の IP アドレスと Discord Webhook URL を設定してください。

環境変数でも設定可能です（環境変数が最優先）:

```bash
export NASNE_IP="192.168.1.xxx"
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

## 使い方

### 通常実行（容量変化時のみ通知）

```bash
python nasne_monitor.py --config config.yaml
```

### 強制実行（容量変化に関係なく通知）

```bash
python nasne_monitor.py --config config.yaml --force
```

### ローカル出力モード（Discord に送信せずコンソール出力）

```bash
python nasne_monitor.py --config config.yaml --local
```

## cron 設定例

毎日 8:00 に実行:

```cron
0 8 * * * cd /path/to/nasne-hdd && /usr/bin/python3 nasne_monitor.py --config config.yaml
```
