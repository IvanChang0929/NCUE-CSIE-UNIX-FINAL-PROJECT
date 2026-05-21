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


def update_job_result(job_id, result):
    """
    將 sandbox 執行結果回傳給後端
    """

    if result["exit_code"] == 0:
        status = "done"
    else:
        status = "error"

    response = requests.patch(
        f"{API_URL}/jobs/{job_id}",
        json={
            "status": status,
            "output": result["stdout"],
            "error": result["stderr"]
        }
    )

    response.raise_for_status()

    print(f"[API] Update Result for Job {job_id}")
    print("========== RESULT ==========")
    print(f"Exit Code: {result['exit_code']}")

    print("\n----- STDOUT -----")
    print(result["stdout"])

    print("----- STDERR -----")
    print(result["stderr"])

    print("============================")