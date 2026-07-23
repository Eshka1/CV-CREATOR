import sqlite3
import json
import os

DB_FILE = "readygrad.db"


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn


def init_db():
    """Run once at startup — creates tables if they don't already exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    location TEXT,
    education TEXT, -- stored as JSON text
    experience TEXT, -- stored as JSON text
    skills TEXT, -- stored as JSON text
    projects TEXT, -- stored as JSON text
    certificates TEXT, -- stored as JSON text
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    title TEXT,
    company TEXT,
    industry TEXT,
    location TEXT,
    remote TEXT,
    experience TEXT,
    salary TEXT,
    required_skills TEXT, -- stored as JSON text
    description TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS saved_jobs (
    user_profile_id INTEGER,
    job_id INTEGER,
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_profile_id, job_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS applications (
    job_id INTEGER PRIMARY KEY,
    job_title TEXT,
    company TEXT,
    status TEXT,
    applied_at TEXT,
    readiness_score INTEGER,
    cover_letter TEXT,
    email TEXT
    )
    """)

    conn.commit()
    conn.close()


# ---------- PROFILE FUNCTIONS (replace profiles.json logic) ----------

def save_profile_db(profile):
    conn = get_connection()
    cur = conn.cursor()
    personal = profile.get("personal", {})
    cur.execute("""
    INSERT INTO profiles (name, email, location, education, experience, skills, projects, certificates)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
    personal.get("name", ""),
    personal.get("email", ""),
    personal.get("location", ""),
    json.dumps(profile.get("education", [])),
    json.dumps(profile.get("experience", [])),
    json.dumps(profile.get("skills", [])),
    json.dumps(profile.get("projects", [])),
    json.dumps(profile.get("certificates", [])),
    ))
    conn.commit()
    conn.close()


def load_latest_profile_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM profiles ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
    "personal": {"name": row["name"], "email": row["email"], "location": row["location"]},
    "education": json.loads(row["education"]),
    "experience": json.loads(row["experience"]),
    "skills": json.loads(row["skills"]),
    "projects": json.loads(row["projects"]),
    "certificates": json.loads(row["certificates"]),
    }


# ---------- JOB FUNCTIONS (replace hardcoded JOBS list) ----------

def seed_jobs_if_empty(jobs_list):
    """Loads your hardcoded JOBS list into the DB, only if the table is empty."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM jobs")
    count = cur.fetchone()[0]
    if count == 0:
        for j in jobs_list:
            cur.execute("""
            INSERT INTO jobs (id, title, company, industry, location, remote, experience, salary, required_skills, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
            j["id"], j["title"], j["company"], j["industry"], j["location"],
            j["remote"], j["experience"], j["salary"],
            json.dumps(j["required_skills"]), j["description"]
            ))
        conn.commit()
    conn.close()


def get_all_jobs_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs")
    rows = cur.fetchall()
    conn.close()
    return [dict_from_job_row(r) for r in rows]


def get_job_by_id_db(job_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    return dict_from_job_row(row) if row else None


def dict_from_job_row(row):
    return {
    "id": row["id"], "title": row["title"], "company": row["company"],
    "industry": row["industry"], "location": row["location"], "remote": row["remote"],
    "experience": row["experience"], "salary": row["salary"],
    "required_skills": json.loads(row["required_skills"]),
    "description": row["description"],
    }


# ---------- SAVED JOBS (replace saved_jobs.json) ----------

def load_saved_job_ids_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT job_id FROM saved_jobs")
    ids = [r["job_id"] for r in cur.fetchall()]
    conn.close()
    return ids


def save_job_id_db(job_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO saved_jobs (user_profile_id, job_id) VALUES (1, ?)", (job_id,))
    conn.commit()
    conn.close()


# ---------- APPLICATIONS (replace applications.json) ----------

def load_applications_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM applications")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_application_db(app_record):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO applications (job_id, job_title, company, status, applied_at, readiness_score, cover_letter, email)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(job_id) DO UPDATE SET
    status=excluded.status, applied_at=excluded.applied_at,
    readiness_score=excluded.readiness_score, cover_letter=excluded.cover_letter, email=excluded.email
    """, (
    app_record["job_id"], app_record["job_title"], app_record["company"],
    app_record["status"], app_record["applied_at"], app_record["readiness_score"],
    app_record["cover_letter"], app_record["email"],
    ))
    conn.commit()
    conn.close()
