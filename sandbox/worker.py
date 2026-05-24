import subprocess
import time
import json
import shutil
from pathlib import Path
from api_client import *
from ..logger import log_info, log_warning, log_error, log_exception

def write_code_to_file(code, file_path):
    with open(file_path, "w") as f:
        f.write(code)

def run_job_with_sandbox(job_id):
    result_dir = Path(f"./sandbox/result/job_{job_id}")
    
    try:
        result = subprocess.run(
            [
                "sudo",
                "./sandbox/build/sandbox",
                str(job_id)
            ],
            capture_output=True,
            text=True
        )

        result_json_path = result_dir / "result.json"
        
        if result_json_path.exists():
            with open(result_json_path, "r") as f:
                sandbox_result = json.load(f)
        else:
            sandbox_result = {
                "error": "Sandbox crashed before generating result",
                "system_stderr": result.stderr # 把 C 程式的 stderr 抓回來除錯用
            }

    except subprocess.TimeoutExpired:
        sandbox_result = {
            "error": "Sandbox Timeout",
            "exit_code": -1
        }
        
    finally:
        if result_dir.exists():
            shutil.rmtree(result_dir, ignore_errors=True)

    return sandbox_result


def analyze_verdict(sandbox_result):
    """
    根據 Sandbox 產生的結果，分析並回傳標準的 OJ 判斷結果 (Verdict)。
    注意：請根據你實際 C 語言寫入 JSON 的 key 名稱，調整下方的 dict 讀取。
    """
    # 1. 系統層級錯誤防呆
    if "error" in sandbox_result:
        return "System Error"

    # 假設你的 JSON 結構有記錄 compile 和 execute 的 exit_code
    # 如果你的 JSON 結構是平的 (flat)，請直接讀取對應的 key，例如 sandbox_result.get("exit_code")
    comp_exit_code = sandbox_result.get("compile_exit_code", 0)
    exec_exit_code = sandbox_result.get("execute_exit_code", 0)

    # 2. 檢查編譯狀態
    if comp_exit_code != 0:
        return "Compilation Error (CE)"

    # 3. 檢查執行狀態 (0 代表順利執行完畢)
    if exec_exit_code == 0:
        return "Accepted (AC)"  # 備註：真實 OJ 還會去比對輸出是否正確 (WA)

    # --- 分析非 0 退出碼 (判斷異常死因) ---
    
    # 取得記憶體用量 (請替換成你 JSON 裡實際紀錄 Max RSS 的 key 名稱)
    # 假設上限是 256MB，我們抓個容錯值，超過 250000 KB (約 244MB) 就當作是爆記憶體
    max_rss_kb = sandbox_result.get("max_rss", 0) 
    MEMORY_LIMIT_THRESHOLD = 250000 
    
    # (A) Memory Limit Exceeded (MLE)
    # 139 (SIGSEGV) 或 137 (SIGKILL) 且記憶體逼近設定上限
    if exec_exit_code in (139, 137) and max_rss_kb >= MEMORY_LIMIT_THRESHOLD:
        return "Memory Limit Exceeded (MLE)"
    
    # (B) Time Limit Exceeded (TLE)
    # 152 (SIGXCPU 軟限制) 或 137 (SIGKILL 硬限制，且沒爆記憶體)
    if exec_exit_code in (152, 137):
        return "Time Limit Exceeded (TLE)"
    
    # (C) 特殊攔截判定：Security Violation
    # 159 (SIGSYS) 代表呼叫了 seccomp 禁用的系統呼叫
    if exec_exit_code == 159:
        return "Security Violation (Blocked by Seccomp)"

    # (D) 其他所有死因 (例如單純的 Segfault、Exit Code 1、除以零 136)
    return "Runtime Error (RE)"

def process_job(job):
    job_id = job["id"]
    code = job["code"]

    workdir = Path(f"/tmp/sandbox/job_{job_id}")

    app_dir = workdir / "app"
    app_dir.mkdir(parents=True, exist_ok=True)

    app_dir.chmod(0o777)

    source_file = app_dir / "main.c"
    write_code_to_file(code, source_file)
    source_file.chmod(0o666)

    print(f"[Worker] Write code -> {source_file}")
    log_info("Worker", f"Write code -> {source_file}")

    update_job_status(job_id, "running")

    # 1. 執行沙盒並取得原始 JSON
    result = run_job_with_sandbox(job_id)
    
    verdict = analyze_verdict(result)
    result["verdict"] = verdict
    print(f"[Worker] Job {job_id} Verdict -> {verdict}")
    
    # 3. 將包含 verdict 的完整資訊上傳給後端 API
    update_job_result(job_id, result)

def main():
    print("[Worker] Started. Waiting for jobs...")

    try:
        while True:
            job = get_pending_job()

            if not job:
                time.sleep(1)
                continue

            print(f"\n[Worker] Found job {job['id']}. Processing...")
            log_info("Worker", "Found job {job['id']}.")
            process_job(job)

    except KeyboardInterrupt:
        print("\n[Worker] Shutting down gracefully...")

if __name__ == "__main__":
    main()