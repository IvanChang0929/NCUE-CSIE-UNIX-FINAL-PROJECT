import requests
import textwrap

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
        "language": job.get("language", "c"),
        "code": job["source_code"],
        "mode": job.get("mode", "basic"),
        "cpu": job.get("cpu_limit", 1.0),
        "memory": job.get("memory_limit", 256),
        "timeout": job.get("timeout_limit", 10),
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
    #log("API", f"Job {job_id} -> {status}")


def update_job_result(job_id, sandbox_result):
    """
    將 sandbox 執行結果回傳給後端
    """

    # 1. sandbox 本身掛掉，沒有產生 result.json
    if "compile" not in sandbox_result and "execute" not in sandbox_result:
        status = "error"
        output = sandbox_result.get("system_stdout", "")

        error = format_system_error(sandbox_result)

        patch_job_result(job_id, status, output, error)
        print_system_error(job_id, sandbox_result)
        return

    # compile exit_code != 0  → error，顯示 Compile Error
    # compile 成功但 execute exit_code != 0 → error，顯示 Runtime Error
    # compile 和 execute 都成功 → done，output 顯示 execute.stdout

    compile_result = sandbox_result.get("compile", {})
    execute_result = sandbox_result.get("execute", {})

    compile_exit_code = compile_result.get("exit_code", -1)
    execute_exit_code = execute_result.get("exit_code", -1)

    compile_stdout = compile_result.get("stdout", "")
    compile_stderr = compile_result.get("stderr", "")

    execute_stdout = execute_result.get("stdout", "")
    execute_stderr = execute_result.get("stderr", "")
    
    # 從 JSON 中抓取 status_message，預設為 Normal Exit
    status_message = execute_result.get("status_message", "Normal Exit")

    # 編譯失敗
    if compile_exit_code != 0:
        status = "error"
        output = compile_stdout
        error = format_compile_error(
            compile_exit_code,
            compile_stdout,
            compile_stderr
        )

    # 編譯成功，但執行失敗
    elif execute_exit_code != 0:
        status = "error"

        # 執行失敗時，不要把 stdout 顯示到前端
        # 避免 OLE / 無限輸出導致畫面很亂
        output = ""

        status_message = execute_result.get("status_message", "")

        error = format_runtime_error(
            execute_exit_code,
            execute_stdout,
            execute_stderr,
            status_message
        )

    # 編譯成功，執行成功
    else:
        status = "done"
        output = execute_stdout

        # 成功時不要硬塞空的 error
        # 只有 stderr 真的有內容才放進 error
        error_parts = []

        if compile_stderr.strip():
            error_parts.append("[Compile STDERR]\n" + compile_stderr.strip())

        if execute_stderr.strip():
            error_parts.append("[Execute STDERR]\n" + execute_stderr.strip())

        error = "\n\n".join(error_parts)

    patch_job_result(job_id, status, output, error)

    print_job_result(
        job_id=job_id,
        status=status,
        compile_exit_code=compile_exit_code,
        execute_exit_code=execute_exit_code,
        output=output,
        error=error
    )


def patch_job_result(job_id, status, output, error):
    """
    更新 job 最終結果到後端
    """

    response = requests.patch(
        f"{API_URL}/jobs/{job_id}",
        json={
            "status": status,
            "output": output,
            "error": error
        }
    )

    response.raise_for_status()


def format_compile_error(exit_code, stdout, stderr):
    parts = [
        "Compile Error",
        f"Exit Code: {exit_code}"
    ]

    if stdout.strip():
        parts.append("Compile STDOUT:\n" + indent_text(stdout))

    if stderr.strip():
        parts.append("Compile STDERR:\n" + indent_text(stderr))

    return "\n\n".join(parts)


def format_runtime_error(exit_code, stdout, stderr, status_message=""):
    title = get_runtime_error_title(exit_code)

    parts = [
        title,
        f"Exit Code: {exit_code}"
    ]

    if status_message.strip():
        parts.append(f"Reason: {status_message}")

    # 錯誤時不要完整顯示 stdout，避免 OLE 爆畫面
    if stdout.strip():
        parts.append("STDOUT: <hidden because job failed>")

    if stderr.strip():
        parts.append("Execute STDERR:\n" + indent_text(stderr))

    return "\n\n".join(parts)


def format_system_error(sandbox_result):
    parts = [
        "Sandbox System Error",
        sandbox_result.get("error", "Unknown sandbox error")
    ]

    system_stderr = sandbox_result.get("system_stderr", "")
    if system_stderr.strip():
        parts.append("System STDERR:\n" + indent_text(system_stderr))

    return "\n\n".join(parts)


def indent_text(text, prefix="  "):
    """
    將多行文字縮排，讓錯誤訊息比較好讀
    """

    text = text.rstrip()

    if not text:
        return ""

    return textwrap.indent(text, prefix)


def log(component, message):
    print(f"[{component:<7}] {message}")


def print_box(title, lines):
    width = 72

    print("┌" + "─" * (width - 2) + "┐")
    print(f"│ {title:<{width - 4}} │")
    print("├" + "─" * (width - 2) + "┤")

    for line in lines:
        line = str(line)

        if len(line) <= width - 4:
            print(f"│ {line:<{width - 4}} │")
        else:
            # 太長的行自動換行
            wrapped_lines = textwrap.wrap(line, width=width - 4)
            for wrapped in wrapped_lines:
                print(f"│ {wrapped:<{width - 4}} │")

    print("└" + "─" * (width - 2) + "┘")


def print_job_result(job_id, status, compile_exit_code, execute_exit_code, output, error):
    lines = [
        f"Job ID        : {job_id}",
        f"Final Status  : {status}",
        f"Compile Exit  : {compile_exit_code}",
        f"Execute Exit  : {execute_exit_code}",
        "",
        "OUTPUT:"
    ]

    if output.strip():
        for line in output.rstrip().splitlines():
            lines.append(f"  {line}")
    else:
        lines.append("  <empty>")

    lines.append("")
    lines.append("ERROR:")

    if error.strip():
        for line in error.rstrip().splitlines():
            lines.append(f"  {line}")
    else:
        lines.append("  <empty>")

    print_box("SANDBOX RESULT", lines)


def print_system_error(job_id, sandbox_result):
    lines = [
        f"Job ID        : {job_id}",
        "Final Status  : error",
        "",
        "SYSTEM ERROR:",
        f"  {sandbox_result.get('error', 'Unknown sandbox error')}"
    ]

    system_stderr = sandbox_result.get("system_stderr", "")

    if system_stderr.strip():
        lines.append("")
        lines.append("SYSTEM STDERR:")
        for line in system_stderr.rstrip().splitlines():
            lines.append(f"  {line}")

    print_box("SANDBOX SYSTEM ERROR", lines)

def get_runtime_error_title(exit_code):
    if exit_code == 153:
        return "Output Limit Exceeded (OLE)"

    if exit_code == 137:
        return "Time / Memory Limit Exceeded (TLE/MLE)"

    if exit_code == 159:
        return "Security Violation"

    if exit_code == 139:
        return "Runtime Error (Segmentation Fault)"

    if exit_code == 136:
        return "Runtime Error (Floating Point Exception)"

    if exit_code == 134:
        return "Runtime Error (Aborted / Assert Failed)"

    return "Runtime Error"