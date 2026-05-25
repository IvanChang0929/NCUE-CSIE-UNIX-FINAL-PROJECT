#!/bin/bash

# 想要設定的 Worker 數量限制
NUM_WORKERS=4
# 核心修正：路徑改成在 sandbox 資料夾底下
WORKER_SCRIPT="sandbox/worker.py"

# 自動偵測並取得專案根目錄的絕對路徑
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# 精準指向 venv 裡面的 python3
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"

# 切換到專案根目錄執行，確保 Python 進程的 CWD 正確，找得到 api_client
cd "$PROJECT_DIR" || exit 1

echo "正在啟動 $NUM_WORKERS 個 Sandbox Workers..."

for i in $(seq 1 $NUM_WORKERS); do
    # 使用虛擬環境的 python 執行正確路徑的 worker
    $VENV_PYTHON "$PROJECT_DIR/$WORKER_SCRIPT" > "$PROJECT_DIR/worker_$i.log" 2>&1 &
    echo "Worker $i 已啟動 (PID: $!)，Log 紀錄於 worker_$i.log"
done

echo "所有 Worker 啟動完畢！可以使用 'ps aux | grep python3' 查看。"