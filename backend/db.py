import sqlite3

DB_NAME = "sandbox.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            language TEXT NOT NULL,
            source_code TEXT NOT NULL,
            status TEXT NOT NULL,
            output TEXT DEFAULT '',
            error TEXT DEFAULT '',
            mode TEXT DEFAULT 'basic',
            cpu_limit REAL DEFAULT 1.0,
            memory_limit INTEGER DEFAULT 256,
            timeout_limit INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()