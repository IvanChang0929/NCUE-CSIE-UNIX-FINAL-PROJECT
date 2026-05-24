import subprocess
import time
import json
import shutil
from pathlib import Path
from api_client import *
import os

def print_job_start(job_id):
    print()
    print(f"[JOB {job_id}] Preparing")


def print_job_step(label, value, is_last=False):
    branch = "└─" if is_last else "├─"
    print(f"  {branch} {label:<8}: {value}")


def init_workspace():
    base_dir = Path("/tmp/sandbox")
    if not base_dir.exists():
        base_dir.mkdir(parents=True,exist_ok=True)
        base_dir.chmod(0o777)

def write_code_to_file(code, file_path):
    with open(file_path, "w") as f:
        f.write(code)

def get_language_config(language):
    runtimes = {
        "c": {
            "source_file": "main.c"
        },
        "python": {
            "source_file": "main.py"
        }
    }

    if language not in runtimes:
        raise ValueError(
            f"Unsupported language: {language}"
        )

    return runtimes[language]


def run_job_with_sandbox(job_id, language):
    result_dir = Path(
        f"./sandbox/result/job_{job_id}"
    )
    try:
        result = subprocess.run(
            [
                "sudo",
                "./sandbox/build/sandbox",
                str(job_id),
                language
            ],
            capture_output=True,
            text=True
        )
        result_json_path = (
            result_dir / "result.json"
        )

        if result_json_path.exists():
            with open(result_json_path, "r") as f:
                sandbox_result = json.load(f)
        else:
            sandbox_result = {
                "error": "Sandbox crashed before generating result",
                "system_stderr": result.stderr,
                "exit_code": result.returncode
            }
    except subprocess.TimeoutExpired:
        sandbox_result = {
            "error": "Sandbox Timeout",
            "execute": {
                "exit_code": -1
            }
        }
    finally:
        if result_dir.exists():
            shutil.rmtree(result_dir)
    return sandbox_result


def process_job(job):

    job_id = job["id"]
    code = job["code"]
    language = job["language"]

    runtime = get_language_config(language)

    workdir = Path(
        f"/tmp/sandbox/job_{job_id}"
    )

    app_dir = workdir / "app"

    app_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    source_file = (
        app_dir / runtime["source_file"]
    )

    write_code_to_file(
        code,
        source_file
    )

    print_job_start(job_id)

    print_job_step("Language", language)

    print_job_step("Source",source_file) 

    update_job_status(job_id, "running")

    print_job_step("API","status -> running")

    result = run_job_with_sandbox(job_id,language)

    print(f"[Worker] Job {job_id} Sandbox Execution Finished.")

    update_job_result(job_id,result)

def main():
    init_workspace()
    print("[Worker] Started. Waiting for jobs...")

    try:
        while True:
            job = get_pending_job()

            if not job:
                time.sleep(1)
                continue

            process_job(job)

    except KeyboardInterrupt:
        print("\n[Worker] Shutting down gracefully...")

if __name__ == "__main__":
    main()