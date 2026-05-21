import requests

API_URL = "http://127.0.0.1:8000"


def get_pending_job():
    """
    從後端 API 取得一筆 pending job
    """

    response = requests.get(f"{API_URL}/jobs/pending")
    response.raise_for_status()

    jobs = response.json()

    if len(jobs) == 0:
        return None

    job = jobs[0]

    return {
        "id": job["id"],
        "code": job["source_code"]
    }


def update_job_status(job_id, status):
    """
    更新 job 狀態
    後端目前只接受：pending / running / done / error
    """

    response = requests.patch(
        f"{API_URL}/jobs/{job_id}",
        json={
            "status": status,
            "output": "",
            "error": ""
        }
    )

    response.raise_for_status()

    print(f"[API] Job {job_id} -> {status}")


def update_job_result(job_id, sandbox_result):
    # 沒產生 result.json
    if "compile" not in sandbox_result and "execute" not in sandbox_result:
        status = "error"
        output = sandbox_result.get("system_stdout", "")
        error = (
            "Sandbox System Error\n\n"
            f"{sandbox_result.get('error', 'Unknown sandbox error')}\n\n"
            "----- SYSTEM STDERR -----\n"
            f"{sandbox_result.get('system_stderr', '')}"
        )

        response = requests.patch(
            f"{API_URL}/jobs/{job_id}",
            json={
                "status": status,
                "output": output,
                "error": error
            }
        )

        response.raise_for_status()
        print(f"[API] Update Result for Job {job_id}")
        print(error)
        return

    #compile exit_code != 0  → error，顯示 Compile Error
    #compile 成功但 execute exit_code != 0 → error，顯示 Runtime Error
    #compile 和 execute 都成功 → done，output 顯示 execute.stdout

    compile_result = sandbox_result.get("compile", {})
    execute_result = sandbox_result.get("execute", {})

    compile_exit_code = compile_result.get("exit_code", -1)
    compile_stdout = compile_result.get("stdout", "")
    compile_stderr = compile_result.get("stderr", "")

    execute_exit_code = execute_result.get("exit_code", -1)
    execute_stdout = execute_result.get("stdout", "")
    execute_stderr = execute_result.get("stderr", "")

    # 1. 編譯失敗
    if compile_exit_code != 0:
        status = "error"
        output = compile_stdout
        error = (
            "Compile Error\n\n"
            f"Exit Code: {compile_exit_code}\n\n"
            "----- COMPILE STDOUT -----\n"
            f"{compile_stdout}\n\n"
            "----- COMPILE STDERR -----\n"
            f"{compile_stderr}"
        )

    # 2. 編譯成功，但執行失敗
    elif execute_exit_code != 0:
        status = "error"
        output = execute_stdout
        error = (
            "Runtime Error\n\n"
            f"Exit Code: {execute_exit_code}\n\n"
            "----- EXECUTE STDOUT -----\n"
            f"{execute_stdout}\n\n"
            "----- EXECUTE STDERR -----\n"
            f"{execute_stderr}"
        )

    # 3. 編譯成功，執行成功
    else:
        status = "done"
        output = execute_stdout
        error = execute_stderr

    response = requests.patch(
        f"{API_URL}/jobs/{job_id}",
        json={
            "status": status,
            "output": output,
            "error": error
        }
    )

    response.raise_for_status()

    print(f"[API] Update Result for Job {job_id}")
    print("========== SANDBOX RESULT ==========")
    print(f"Compile Exit Code: {compile_exit_code}")
    print(f"Execute Exit Code: {execute_exit_code}")
    print(f"Final Status: {status}")

    print("\n----- OUTPUT -----")
    print(output)

    print("----- ERROR -----")
    print(error)

    print("====================================")