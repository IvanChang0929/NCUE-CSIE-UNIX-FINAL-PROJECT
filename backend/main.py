from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from db import get_connection, init_db

app = FastAPI()

init_db()


class JobCreate(BaseModel):
    language: str
    source_code: str


class JobUpdate(BaseModel):
    status: str
    output: str = ""
    error: str = ""


@app.get("/")
def home():
    return {
        "message": "Unix Sandbox Backend API is running"
    }


@app.post("/jobs")
def create_job(job: JobCreate):
    if job.language != "c":
        raise HTTPException(
            status_code=400,
            detail="Only C language is supported now"
        )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO jobs (language, source_code, status)
        VALUES (?, ?, ?)
    """, (job.language, job.source_code, "pending"))

    conn.commit()
    job_id = cursor.lastrowid
    conn.close()

    return {
        "message": "Job created",
        "job_id": job_id,
        "status": "pending"
    }


@app.get("/jobs")
def get_jobs():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, language, source_code, status, output, error, created_at, updated_at
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
        SELECT id, language, source_code, status, output, error, created_at, updated_at
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
        SELECT id, language, source_code, status, output, error, created_at, updated_at
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