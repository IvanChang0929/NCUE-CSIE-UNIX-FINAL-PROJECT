from pathlib import Path
import subprocess


def run_in_sandbox(file_path):

    file_path = Path(file_path).resolve() #轉成絕對路徑

    print("EXISTS:", file_path.exists())
    print("PATH:", file_path)
    print("PARENT:", file_path.parent)
    print("NAME:", file_path.name)

    result = subprocess.run(
        [
            "docker", "run", "--rm",

            "--network", "none",
            "--memory", "128m",
            "--cpus", "0.5",
            "--pids-limit", "64",

            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",

            "-v", f"{file_path.parent}:/app",

            "-w", "/app",

            "gcc:latest",

            "bash", "-c",

            f"gcc {file_path.name} -o /tmp/main && /tmp/main"
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

#test
if __name__ == "__main__":

    result = run_in_sandbox("./tmp/test/main.c")

    print("STDOUT:")
    print(result["stdout"])

    print("STDERR:")
    print(result["stderr"])

    print("EXIT CODE:")
    print(result["exit_code"])