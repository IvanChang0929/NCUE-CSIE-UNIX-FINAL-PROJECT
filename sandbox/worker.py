import subprocess
import time
import json
import shutil
from pathlib import Path
from api_client import *
from logger import log_info, log_error, log_exception
import os
import traceback


def print_job_start(job_id):
    print()
    print(f"[JOB {job_id}] Preparing", flush=True)


def print_job_step(label, value, is_last=False):
    branch = "└─" if is_last else "├─"
    print(f"  {branch} {label:<8}: {value}", flush=True)


def init_workspace():
    base_dir = Path("/tmp/sandbox")
    base_dir.mkdir(parents=True, exist_ok=True)
    base_dir.chmod(0o777)


def safe_rmtree(path):
    path = Path(path)

    if not path.exists():
        return

    try:
        shutil.rmtree(path)
        return
    except PermissionError:
        pass
    except Exception as e:
        print(f"[Worker] shutil.rmtree failed: {path}: {e}", flush=True)

    # 有些 sandbox 產物可能是 root 建立的，worker 沒權限刪。
    # 用 sudo -n 避免卡住等密碼；若 sudoers 沒設好會直接失敗。
    subprocess.run(
        ["sudo", "-n", "rm", "-rf", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )


def write_code_to_file(code, file_path):
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
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


def make_system_error(message, system_stdout="", system_stderr="", exit_code=-1, extra=None):
    result = {
        "error": message,
        "system_stdout": system_stdout or "",
        "system_stderr": system_stderr or "",
        "exit_code": exit_code,
    }

    if extra:
        result.update(extra)

    return result


def load_sandbox_result_safe(result_json_path, job_id, process_result):
    """
    安全讀取 result.json。
    即使 sandbox 寫出壞掉的 JSON，worker 也不能整個 crash。
    """
    result_json_path = Path(result_json_path)

    if not result_json_path.exists():
        return make_system_error(
            "Sandbox crashed before generating result",
            system_stdout=process_result.stdout if process_result else "",
            system_stderr=process_result.stderr if process_result else "result.json not found",
            exit_code=process_result.returncode if process_result else -1,
        )

    try:
        raw = result_json_path.read_text(encoding="utf-8", errors="replace")

        if not raw.strip():
            return make_system_error(
                "Sandbox generated empty result.json",
                system_stdout=process_result.stdout if process_result else "",
                system_stderr=process_result.stderr if process_result else "empty result.json",
                exit_code=process_result.returncode if process_result else -1,
            )

        return json.loads(raw)

    except json.JSONDecodeError as e:
        raw_tail = ""

        try:
            raw_tail = result_json_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        except Exception:
            pass

        return make_system_error(
            "Sandbox generated invalid result.json",
            system_stdout=process_result.stdout if process_result else "",
            system_stderr=(
                f"JSONDecodeError: {e}\n"
                f"Result path: {result_json_path}\n"
                f"Hint: result_writer probably did not escape stdout/stderr/status_message correctly.\n"
                f"{process_result.stderr if process_result else ''}"
            ),
            exit_code=process_result.returncode if process_result else -1,
            extra={
                "raw_result_tail": raw_tail
            }
        )

    except Exception as e:
        return make_system_error(
            "Failed to read sandbox result",
            system_stdout=process_result.stdout if process_result else "",
            system_stderr=str(e),
            exit_code=process_result.returncode if process_result else -1,
        )


def run_job_with_sandbox(job_id, language, cpu, memory, timeout):
    result_dir = Path(f"./sandbox/result/job_{job_id}")
    process_result = None

    try:
        process_result = subprocess.run(
            [
                "sudo",
                "-n",
                "./sandbox/build/sandbox",
                str(job_id),
                str(language),
                str(cpu),
                str(memory),
                str(timeout),
            ],
            capture_output=True,
            text=True,
            timeout=int(timeout) + 20,
        )

        result_json_path = result_dir / "result.json"

        # 重點：
        # 不要直接 json.load，因為 result.json 可能被控制字元弄壞。
        # 這裡保證不管 JSON 是否合法，worker 都不會死掉。
        sandbox_result = load_sandbox_result_safe(result_json_path, job_id, process_result)
        return sandbox_result

    except subprocess.TimeoutExpired as e:
        return make_system_error(
            "Sandbox Timeout",
            system_stdout=e.stdout or "",
            system_stderr=(e.stderr or "") + "\n[Worker] sandbox subprocess timeout",
            exit_code=-1,
            extra={
                "execute": {
                    "exit_code": -1,
                    "status_message": "Sandbox Timeout"
                }
            }
        )

    except Exception as e:
        return make_system_error(
            "Worker failed while running sandbox",
            system_stderr=traceback.format_exc(),
            exit_code=-1,
        )

    finally:
        # 給 backend/UI 一點時間讀結果；之後清掉 result 目錄。
        time.sleep(3)
        safe_rmtree(result_dir)


def process_job(job):
    job_id = job["id"]
    code = job["code"]
    language = job["language"]
    cpu = job.get("cpu", 1.0)
    memory = job.get("memory", 256)
    timeout = job.get("timeout", 10)

    runtime = get_language_config(language)

    workdir = Path(
        f"/tmp/sandbox/job_{job_id}"
    )

    app_dir = workdir / "app"

    # 避免同 job_id 的舊目錄或 root-owned 目錄干擾。
    if workdir.exists():
        safe_rmtree(workdir)

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

    print_job_step("Source", source_file)

    print_job_step("Limit", f"{cpu} core / {memory} MB / {timeout} s")

    update_job_status(job_id, "running")

    print_job_step("API", "status -> running")

    result = run_job_with_sandbox(job_id, language, cpu, memory, timeout)

    print(f"[Worker] Job {job_id} Sandbox Execution Finished.", flush=True)

    update_job_result(job_id, result)


def mark_job_failed(job, message, exc=None):
    job_id = None

    try:
        job_id = job.get("id")
    except Exception:
        pass

    result = make_system_error(
        message,
        system_stderr=traceback.format_exc() if exc else "",
        exit_code=-1,
    )

    print(f"[Worker] Job failed unexpectedly. Job ID: {job_id}. {message}", flush=True)

    try:
        if job_id is not None:
            update_job_result(job_id, result)
    except Exception as e:
        print(f"[Worker] Failed to update job result: {e}", flush=True)

    try:
        if job_id is not None:
            update_job_status(job_id, "error")
    except Exception as e:
        print(f"[Worker] Failed to update job status: {e}", flush=True)


def main():
    init_workspace()
    print("[Worker] Started. Waiting for jobs...", flush=True)
    log_info("Worker", "Started. Waiting for jobs...")

    try:
        while True:
            job = get_pending_job()

            if not job:
                time.sleep(1)
                continue

            try:
                log_info("Worker", f"Get job. Job ID: {job['id']}")
                process_job(job)

            except Exception as e:
                # 重點：
                # 單一 job 出錯不能讓整個 worker 掛掉。
                log_exception("Worker", f"Job failed unexpectedly: {e}")
                mark_job_failed(job, "Worker crashed while processing job", e)
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n[Worker] Shutting down gracefully...", flush=True)
        log_info("Worker", "Worker shut down")


if __name__ == "__main__":
    main()
