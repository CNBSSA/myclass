import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DB_PATH = DATA_DIR / "myclass.db"

LESSON_CATALOG = [
    (1, "Course Introduction"),
    (2, "Introduction to Data Science"),
    (3, "Numpy"),
    (4, "Working With Pandas"),
    (5, "Data Visualization"),
    (6, "Math and Statistics Fundamentals"),
    (7, "Probability Distribution"),
    (8, "Advanced Statistics"),
    (9, "Data Wrangling"),
    (10, "Feature Engineering"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    lesson_tag      TEXT,
    status          TEXT NOT NULL DEFAULT 'in_progress',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS assignment_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id   INTEGER NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    extracted_text  TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS problems (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id           INTEGER NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    problem_number          INTEGER NOT NULL,
    problem_text            TEXT NOT NULL,
    solution_code           TEXT,
    solution_explanation    TEXT,
    status                  TEXT NOT NULL DEFAULT 'pending',
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at            TEXT,
    UNIQUE(assignment_id, problem_number)
);

CREATE TABLE IF NOT EXISTS qa_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id      INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lessons (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_number   INTEGER UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lesson_materials (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id       INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    extracted_text  TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mcq_attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id       INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    question        TEXT NOT NULL,
    options_json    TEXT NOT NULL,
    correct_answer  TEXT NOT NULL,
    user_answer     TEXT,
    is_correct      INTEGER,
    explanation     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS coding_attempts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id           INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    problem             TEXT NOT NULL,
    expected_behavior   TEXT,
    user_code           TEXT,
    execution_stdout    TEXT,
    execution_stderr    TEXT,
    execution_success   INTEGER,
    ai_review           TEXT,
    score               INTEGER,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_problems_assignment ON problems(assignment_id);
CREATE INDEX IF NOT EXISTS idx_qa_problem            ON qa_log(problem_id);
CREATE INDEX IF NOT EXISTS idx_mcq_lesson            ON mcq_attempts(lesson_id);
CREATE INDEX IF NOT EXISTS idx_coding_lesson         ON coding_attempts(lesson_id);
"""


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "uploads").mkdir(exist_ok=True)
    (DATA_DIR / "exports").mkdir(exist_ok=True)


@contextmanager
def get_conn():
    _ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    _ensure_dirs()
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        existing = {row["lesson_number"] for row in conn.execute("SELECT lesson_number FROM lessons")}
        for num, title in LESSON_CATALOG:
            if num not in existing:
                conn.execute(
                    "INSERT INTO lessons (lesson_number, title) VALUES (?, ?)",
                    (num, title),
                )
