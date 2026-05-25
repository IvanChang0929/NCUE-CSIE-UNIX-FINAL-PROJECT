from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from .db import get_connection, init_db
import asyncio
import json
from pathlib import Path

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent.parent
init_db()


class JobCreate(BaseModel):
    language: str
    source_code: str
    mode: str = "basic"
    cpu: float = 1.0
    memory: int = 256
    timeout: int = 10


class JobUpdate(BaseModel):
    status: str
    output: str = ""
    error: str = ""


@app.get("/")
def home():
    return {
        "message": "Unix Sandbox Backend API is running"
    }


SUPPORTED_LANGUAGES = {
    "c",
    "python"
}

@app.post("/jobs")
def create_job(job: JobCreate):

    if job.language not in SUPPORTED_LANGUAGES:

        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {job.language}"
        )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO jobs (
            language,
            source_code,
            status,
            mode,
            cpu_limit,
            memory_limit,
            timeout_limit
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        job.language,
        job.source_code,
        "pending",
        job.mode,
        job.cpu,
        job.memory,
        job.timeout
    ))

    conn.commit()

    job_id = cursor.lastrowid

    conn.close()

    return {
        "message": "Job created",
        "job_id": job_id,
        "language": job.language,
        "status": "pending"
    }

@app.get("/jobs")
def get_jobs():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, language, source_code, status, output, error,
                mode, cpu_limit, memory_limit, timeout_limit,
                created_at, updated_at
        FROM jobs
        ORDER BY id DESC
    """)

    jobs = cursor.fetchall()
    conn.close()

    return [dict(job) for job in jobs]


@app.get("/jobs/pending")
def get_pending_jobs():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, language, source_code, status, output, error,
                mode, cpu_limit, memory_limit, timeout_limit,
                created_at, updated_at
        FROM jobs
        WHERE status = ?
        ORDER BY id ASC
    """, ("pending",))

    jobs = cursor.fetchall()
    conn.close()

    return [dict(job) for job in jobs]


@app.get("/jobs/{job_id}")
def get_job(job_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, language, source_code, status, output, error,
                mode, cpu_limit, memory_limit, timeout_limit,
                created_at, updated_at
        FROM jobs
        WHERE id = ?
    """, (job_id,))

    job = cursor.fetchone()
    conn.close()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return dict(job)


@app.patch("/jobs/{job_id}")
def update_job(job_id: int, job: JobUpdate):
    allowed_status = ["pending", "running", "done", "error"]

    if job.status not in allowed_status:
        raise HTTPException(
            status_code=400,
            detail="Invalid status"
        )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    existing_job = cursor.fetchone()

    if existing_job is None:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    cursor.execute("""
        UPDATE jobs
        SET status = ?,
            output = ?,
            error = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (job.status, job.output, job.error, job_id))

    conn.commit()
    conn.close()

    return {
        "message": "Job updated",
        "job_id": job_id,
        "status": job.status
    }

@app.websocket("/ws/jobs/{job_id}/monitor")
async def job_monitor_ws(websocket: WebSocket, job_id: int):
    await websocket.accept()

    monitor_path = BASE_DIR / "sandbox" / "result" / f"job_{job_id}" / "monitor.log"
    last_line_count = 0

    try:
        while True:
            if monitor_path.exists():
                lines = monitor_path.read_text().splitlines()

                new_lines = lines[last_line_count:]
                last_line_count = len(lines)

                for line in new_lines:
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    await websocket.send_json(data)

                    # compile 也可能 status=done
                    # 所以只能 execute done 才關閉 websocket
                    if data.get("stage") == "execute" and data.get("status") == "done":
                        await websocket.send_json({
                            "job_id": str(job_id),
                            "status": "closed",
                            "message": "monitor done"
                        })
                        await websocket.close()
                        return

            await asyncio.sleep(0.2)

    except WebSocketDisconnect:
        print(f"[WebSocket] client disconnected: job {job_id}")