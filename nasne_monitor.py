#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nasne HDD容量監視 Discord通知システム (cron実行版)
cronで定期実行してnasneの残容量をDiscordに通知する
"""

import requests
import json
import datetime
import logging
import os
import argparse
from typing import Dict, Optional

def setup_logging(config: Dict):
    """
    ログ設定を行う（スクリプト直下のlogsディレクトリを使用）

    Args:
        config: 設定辞書
    """
    # スクリプトのディレクトリを取得
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # ログディレクトリの設定（設定ファイル > デフォルト（スクリプト直下のlogs））
    default_log_dir = os.path.join(script_dir, "logs")
    log_dir = config.get('log_dir', default_log_dir)

    # 相対パスの場合はスクリプトディレクトリからの相対として解釈
    if not os.path.isabs(log_dir):
        log_dir = os.path.join(script_dir, log_dir)

    log_level = config.get('log_level', 'INFO')

    # ログディレクトリ作成
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "nasne_monitor.log")

    # ログレベル設定
    level = getattr(logging, log_level.upper(), logging.INFO)

    # ログ設定
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

class NasneMonitor:
    def __init__(self, nasne_ip: str, discord_webhook_url: str = None, local_mode: bool = False):
        """
        nasne監視クラス

        Args:
            nasne_ip: nasneのIPアドレス
            discord_webhook_url: Discord WebhookのURL（local_modeがTrueの場合は不要）
            local_mode: ローカル出力モード（Discordに送信せず、コンソールに出力）
        """
        self.nasne_ip = nasne_ip
        self.discord_webhook_url = discord_webhook_url
        self.local_mode = local_mode

        # スクリプトのディレクトリを取得
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # dataディレクトリをスクリプト直下に作成
        data_dir = os.path.join(script_dir, "data")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)

        self.last_capacity_file = os.path.join(data_dir, "last_capacity.txt")
        self.last_check_date_file = os.path.join(data_dir, "last_check_date.txt")

        if not local_mode and not discord_webhook_url:
            raise ValueError("local_modeがFalseの場合、discord_webhook_urlは必須です")

    def get_hdd_info(self) -> Optional[Dict]:
        """
        nasneのHDD情報を取得する

        Returns:
            HDD情報辞書 または None
        """
        try:
            # nasne APIエンドポイント（ID=0は通常最初のHDD）
            url = f"http://{self.nasne_ip}:64210/status/HDDInfoGet?id=0"

            # Raspberry Pi用にタイムアウトを長めに設定
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # JSONレスポンスをパース
            hddinfo = response.json()

            if hddinfo.get('errorcode') != 0:
                logging.error(f"nasne API エラー: errorcode={hddinfo.get('errorcode')}")
                return None

            # HDD情報を抽出（バイト単位からGB単位に変換）
            free_volume_bytes = hddinfo['HDD']['freeVolumeSize']
            total_volume_bytes = hddinfo['HDD'].get('totalVolumeSize', 0)

            free_gb = free_volume_bytes / (1024 ** 3)  # バイトからGBに変換
            total_gb = total_volume_bytes / (1024 ** 3) if total_volume_bytes > 0 else 0
            used_gb = total_gb - free_gb if total_gb > 0 else 0
            usage_percent = (used_gb / total_gb * 100) if total_gb > 0 else 0

            return {
                'total_gb': total_gb,
                'free_gb': free_gb,
                'used_gb': used_gb,
                'usage_percent': usage_percent,
                'timestamp': datetime.datetime.now(),
                'raw_response': hddinfo
            }

        except requests.RequestException as e:
            logging.error(f"nasneからの情報取得に失敗: {e}")
            return None
        except (KeyError, TypeError, ValueError) as e:
            logging.error(f"JSONデータの解析に失敗: {e}")
            return None
        except Exception as e:
            logging.error(f"予期しないエラー: {e}")
            return None

    def format_capacity_message(self, hdd_info: Dict) -> str:
        """
        容量情報をDiscordメッセージ用にフォーマット

        Args:
            hdd_info: HDD情報辞書

        Returns:
            フォーマット済みメッセージ
        """
        timestamp = hdd_info['timestamp'].strftime('%Y-%m-%d %H:%M:%S')

        # 容量に応じた警告レベル
        usage_percent = hdd_info['usage_percent']
        if usage_percent >= 90:
            emoji = "🔴"
            status = "危険"
        elif usage_percent >= 80:
            emoji = "🟡"
            status = "注意"
        else:
            emoji = "🟢"
            status = "正常"

        message = f"""
{emoji} **nasne HDD容量レポート** {emoji}

**日時**: {timestamp}
**状態**: {status}

**容量情報**:
• 総容量: {hdd_info['total_gb']:.1f} GB
• 使用量: {hdd_info['used_gb']:.1f} GB
• 残容量: {hdd_info['free_gb']:.1f} GB
• 使用率: {usage_percent:.1f}%

**プログレスバー**:
{self._create_progress_bar(usage_percent)}
        """.strip()

        return message

    def _create_progress_bar(self, percentage: float, length: int = 20) -> str:
        """
        テキストベースのプログレスバーを作成

        Args:
            percentage: 使用率（0-100）
            length: バーの長さ

        Returns:
            プログレスバー文字列
        """
        filled = int(percentage / 100 * length)
        bar = "█" * filled + "░" * (length - filled)
        return f"`{bar}` {percentage:.1f}%"

    def send_discord_notification(self, message: str) -> bool:
        """
        DiscordにWebhook経由でメッセージを送信（またはローカル出力）

        Args:
            message: 送信するメッセージ

        Returns:
            送信成功の場合True
        """
        if self.local_mode:
            # ローカルモード: コンソールに出力
            print("=" * 60)
            print("📢 nasne Monitor - ローカル出力モード")
            print("=" * 60)
            print(message)
            print("=" * 60)
            logging.info("ローカルモードでメッセージを出力しました")
            return True

        # 通常モード: Discordに送信
        try:
            payload = {
                "content": message,
                "username": "nasne Monitor",
                "avatar_url": "https://via.placeholder.com/64x64/7289da/ffffff?text=N"
            }

            response = requests.post(
                self.discord_webhook_url,
                json=payload,
                timeout=30  # Raspberry Pi用にタイムアウトを長めに設定
            )
            response.raise_for_status()

            logging.info("Discord通知送信成功")
            return True

        except requests.RequestException as e:
            logging.error(f"Discord通知送信失敗: {e}")
            return False

    def daily_check(self):
        """
        日次チェック実行（1日1回のみAPIアクセス）
        """
        # 今日既にチェック済みかを確認
        today = datetime.date.today()
        last_check_date = self._get_last_check_date()

        if last_check_date == today:
            logging.info(f"今日は既にチェック済みです: {today}")
            return

        logging.info("日次容量チェック開始")

        hdd_info = self.get_hdd_info()
        if hdd_info is None:
            error_msg = "❌ nasneの容量情報取得に失敗しました。nasneの接続状態を確認してください。"
            self.send_discord_notification(error_msg)
            return

        # 前回の値と比較（あなたの既存スクリプトの機能を踏襲）
        current_free_gb = int(hdd_info['free_gb'])
        last_free_gb = self._get_last_capacity()

        if last_free_gb is None or current_free_gb != last_free_gb:
            # 容量が変化した場合のみ通知
            message = self.format_capacity_message(hdd_info)
            success = self.send_discord_notification(message)

            if success:
                self._save_last_capacity(current_free_gb)
                logging.info(f"容量変化検知 - 前回: {last_free_gb}GB → 現在: {current_free_gb}GB")
            else:
                logging.error("Discord通知送信失敗")
        else:
            logging.info(f"容量変化なし - {current_free_gb}GB")

        # 今日のチェック完了を記録
        self._save_last_check_date(today)

    def _get_last_capacity(self) -> Optional[int]:
        """
        前回の容量値を取得

        Returns:
            前回の空き容量（GB）または None
        """
        try:
            if os.path.exists(self.last_capacity_file):
                with open(self.last_capacity_file, 'r') as f:
                    return int(f.read().strip())
        except (ValueError, IOError) as e:
            logging.warning(f"前回容量値の読み込みに失敗: {e}")
        return None

    def _save_last_capacity(self, capacity_gb: int):
        """
        現在の容量値を保存

        Args:
            capacity_gb: 空き容量（GB）
        """
        try:
            with open(self.last_capacity_file, 'w') as f:
                f.write(str(capacity_gb))
        except IOError as e:
            logging.error(f"容量値の保存に失敗: {e}")

    def _get_last_check_date(self) -> Optional['datetime.date']:
        """
        最後にチェックした日付を取得

        Returns:
            最後のチェック日付 または None
        """
        try:
            if os.path.exists(self.last_check_date_file):
                with open(self.last_check_date_file, 'r') as f:
                    date_str = f.read().strip()
                    return datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, IOError) as e:
            logging.warning(f"前回チェック日付の読み込みに失敗: {e}")
        return None

    def _save_last_check_date(self, check_date: 'datetime.date'):
        """
        チェック日付を保存

        Args:
            check_date: チェック日付
        """
        try:
            with open(self.last_check_date_file, 'w') as f:
                f.write(check_date.strftime('%Y-%m-%d'))
        except IOError as e:
            logging.error(f"チェック日付の保存に失敗: {e}")

    def force_check(self):
        """
        強制チェック実行（容量変化に関係なく通知）
        """
        logging.info("強制容量チェック開始")

        hdd_info = self.get_hdd_info()
        if hdd_info is None:
            error_msg = "❌ nasneの容量情報取得に失敗しました。nasneの接続状態を確認してください。"
            self.send_discord_notification(error_msg)
            return

        message = self.format_capacity_message(hdd_info)
        success = self.send_discord_notification(message)

        if success:
            current_free_gb = int(hdd_info['free_gb'])
            self._save_last_capacity(current_free_gb)
            logging.info(f"強制レポート送信完了 - 空き容量: {current_free_gb}GB")
        else:
            logging.error("強制レポート送信失敗")

def main():
    """
    メイン実行関数（cron実行版）
    """
    # コマンドライン引数の設定
    parser = argparse.ArgumentParser(description='nasne容量監視システム (cron実行版)')
    parser.add_argument('--local', action='store_true',
                       help='ローカル出力モード（Discordに送信しない）')
    parser.add_argument('--force', action='store_true',
                       help='強制実行モード（容量変化に関係なく通知）')
    parser.add_argument('--config', type=str, default=None,
                       help='設定ファイルのパス（YAML形式）')
    args = parser.parse_args()

    # 設定値の読み込み
    config = load_config(args.config)

    # ログ設定
    setup_logging(config)

    # 監視インスタンス作成
    if args.local:
        monitor = NasneMonitor(config['nasne_ip'], local_mode=True)
        logging.info("ローカル出力モードで実行")
    else:
        monitor = NasneMonitor(config['nasne_ip'], config['discord_webhook_url'], local_mode=False)
        logging.info("Discord通知モードで実行")

    # チェック実行
    if args.force:
        logging.info("強制実行モード")
        monitor.force_check()
    else:
        logging.info("通常実行モード")
        monitor.daily_check()

def load_config(config_path: str = None) -> Dict:
    """
    設定を読み込む（環境変数 > 設定ファイル > デフォルト値の優先順位）

    Args:
        config_path: 設定ファイルのパス

    Returns:
        設定辞書
    """
    config = {
        'nasne_ip': '<nasneのIPアドレス>',
        'discord_webhook_url': '<Discord WebhookのURL>'
    }

    # 設定ファイルから読み込み（YAML形式）
    if config_path and os.path.exists(config_path):
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f)
                config.update(file_config)
            logging.info(f"設定ファイルを読み込みました: {config_path}")
        except ImportError:
            logging.warning("PyYAMLがインストールされていません。pip install PyYAMLでインストールしてください")
        except Exception as e:
            logging.error(f"設定ファイルの読み込みに失敗: {e}")

    # 環境変数で上書き（最優先）
    config['nasne_ip'] = os.getenv('NASNE_IP', config['nasne_ip'])
    config['discord_webhook_url'] = os.getenv('DISCORD_WEBHOOK_URL', config['discord_webhook_url'])

    return config

if __name__ == "__main__":
    main()
