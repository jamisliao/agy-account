#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${HOME}/.local/bin"

mkdir -p "${TARGET_DIR}"

ln -sf "${SCRIPT_DIR}/agy_account.py" "${TARGET_DIR}/agy-account"
chmod +x "${TARGET_DIR}/agy-account"

echo "✅ 成功安裝 agy-account 至 ${TARGET_DIR}/agy-account"
echo "請確保 ${TARGET_DIR} 已加入你的 PATH 中。"
