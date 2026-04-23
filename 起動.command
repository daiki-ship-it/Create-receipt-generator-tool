#!/bin/bash
# このファイルをダブルクリックすると、ターミナルが開いて領収書アプリが起動します。
# 終了するときはターミナルで Ctrl+C を押してください。

set -e
cd "$(dirname "$0")"

echo ""
echo "  ─ 領収書生成ツール を準備しています ─"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "エラー: python3 が見つかりません。Python をインストールしてください。"
  echo "https://www.python.org/downloads/"
  read -r _
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "初回のみ: 専用の環境を作成しています（1〜2分かかることがあります）..."
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
  echo "準備が完了しました。"
  echo ""
fi

exec .venv/bin/python3 receipt_app.py
