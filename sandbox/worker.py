from pathlib import Path
from database import *

import subprocess


def write_code_to_file(code, file_path):

    with open(file_path, "w") as f:
        f.write(code)


def run_job_with_sandbox(source_file):

    result = subprocess.run(
        [
            "./build/sandbox",
            str(source_file)
        ],

        capture_output=True,
        text=True,
        timeout=5
    )

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.returncode
    }


def process_job(job):

    job_id = job["id"]
    code = job["code"]

    # 建立工作資料夾
    workdir = Path(f"./tmp/job_{job_id}")

    workdir.mkdir(parents=True, exist_ok=True)

    # source file
    source_file = workdir / "main.c"

    # 寫入 AI code
    write_code_to_file(code, source_file)

    print(f"[Worker] Write code -> {source_file}")

    update_job_status(job_id, "running")

    try:
        # 呼叫 sandbox runtime
        result = run_job_with_sandbox(source_file)

        update_job_status(job_id, "finished")

        update_job_result(job_id, result)
    except subprocess.TimeoutExpired:

        update_job_status(job_id, "timeout")

        update_job_result(
            job_id,
            {
                "stdout": "",
                "stderr": "Sandbox Timeout",
                "exit_code": -1
            }
        )


def main():

    job = get_pending_job()

    if not job:
        print("[Worker] No pending job")
        return

    process_job(job)


if __name__ == "__main__":
    main()