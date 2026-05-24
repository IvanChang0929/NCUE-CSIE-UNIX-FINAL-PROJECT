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
        if result_dir.exists():
            shutil.rmtree(result_dir)

    return sandbox_result

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
    
    # 2. Worker 不再進行任何 Verdict 判斷，直接將原始數據上傳給後端 API
    print(f"[Worker] Job {job_id} Sandbox Execution Finished.")
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