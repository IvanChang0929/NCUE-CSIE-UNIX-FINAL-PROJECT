import subprocess
import time
import json
import shutil
from pathlib import Path
from api_client import *
import os

def init_workspace():
    base_dir = Path("/tmp/sandbox")
    if not base_dir.exists():
        # 如果不存在，建立它並給予 777 權限，確保 C (sudo) 和 Python 都不會被卡住
        base_dir.mkdir(parents=True, exist_ok=True)
        base_dir.chmod(0o777)

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
            "execute": {"exit_code": -1}
        }
        
    finally:
        # 清理 Host 端的實體檔案輸出 (C 沙盒已經負責清除了 /tmp 內的系統檔案)
        if result_dir.exists():
            shutil.rmtree(result_dir)

    return sandbox_result


def analyze_verdict(sandbox_result):
    # 1. 系統層級崩潰
    if "error" in sandbox_result:
        return "System Error"

    compile_data = sandbox_result.get("compile", {})
    execute_data = sandbox_result.get("execute", {})

    comp_exit_code = compile_data.get("exit_code", -1)
    exec_exit_code = execute_data.get("exit_code", -1)

    if comp_exit_code != 0:
        return "Compilation Error "

    if exec_exit_code == 0:
        return "Accepted"  

    if exec_exit_code == 153:
        return "Output Limit Exceeded (OLE)"

    if exec_exit_code == 137:
        return "Time / Memory Limit Exceeded (TLE/MLE)"
    
    if exec_exit_code == 159:
        return "Security Violation (Blocked by Seccomp)"


    if exec_exit_code == 139:
        return "Runtime Error (Segmentation Fault)"
    if exec_exit_code == 136:
        return "Runtime Error (Floating Point Exception)"
    if exec_exit_code == 134:
        return "Runtime Error (Aborted / Assert Failed)"

    return f"Runtime Error (Exit Code {exec_exit_code})"

def process_job(job):
    job_id = job["id"]
    code = job["code"]
    uid = os.getuid()
    gid = os.getgid()

    workdir = Path(f"/tmp/sandbox/job_{job_id}")

    app_dir = workdir / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    os.chown(app_dir, uid, gid)
    app_dir.chmod(0o755)

    source_file = app_dir / "main.c"
    write_code_to_file(code, source_file)
    os.chown(source_file, uid, gid)
    source_file.chmod(0o644)

    print(f"[Worker] Write code -> {source_file}")

    update_job_status(job_id, "running")

    # 1. 執行沙盒並取得原始 JSON
    result = run_job_with_sandbox(job_id)
    
    # 2. 判斷狀態
    verdict = analyze_verdict(result)
    result["verdict"] = verdict
    print(f"[Worker] Job {job_id} Verdict -> {verdict}")
    
    # 3. 將包含 verdict 的完整資訊上傳給後端 API
    update_job_result(job_id, result)

def main():
    init_workspace()
    print("[Worker] Started. Waiting for jobs...")

    try:
        while True:
            job = get_pending_job()

            if not job:
                time.sleep(1)
                continue

            print(f"\n[Worker] Found job {job['id']}. Processing...")
            process_job(job)

    except KeyboardInterrupt:
        print("\n[Worker] Shutting down gracefully...")

if __name__ == "__main__":
    main()