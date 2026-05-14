import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))


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
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    lesson_tag      TEXT,
    status          TEXT NOT NULL DEFAULT 'in_progress',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS assignment_files (
    id              SERIAL PRIMARY KEY,
    assignment_id   INTEGER NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    extracted_text  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS problems (
    id                      SERIAL PRIMARY KEY,
    assignment_id           INTEGER NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    problem_number          INTEGER NOT NULL,
    problem_text            TEXT NOT NULL,
    solution_code           TEXT,
    solution_explanation    TEXT,
    status                  TEXT NOT NULL DEFAULT 'pending',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ,
    UNIQUE(assignment_id, problem_number)
);

CREATE TABLE IF NOT EXISTS qa_log (
    id              SERIAL PRIMARY KEY,
    problem_id      INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lessons (
    id              SERIAL PRIMARY KEY,
    lesson_number   INTEGER UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lesson_materials (
    id              SERIAL PRIMARY KEY,
    lesson_id       INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    extracted_text  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mcq_attempts (
    id              SERIAL PRIMARY KEY,
    lesson_id       INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    question        TEXT NOT NULL,
    options_json    TEXT NOT NULL,
    correct_answer  TEXT NOT NULL,
    user_answer     TEXT,
    is_correct      BOOLEAN,
    explanation     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coding_attempts (
    id                  SERIAL PRIMARY KEY,
    lesson_id           INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    problem             TEXT NOT NULL,
    expected_behavior   TEXT,
    user_code           TEXT,
    execution_stdout    TEXT,
    execution_stderr    TEXT,
    execution_success   BOOLEAN,
    ai_review           TEXT,
    score               INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
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


def _get_dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL is not set. On Railway this is auto-injected when the "
            "Postgres service is attached to your web service via the Railway "
            "reference syntax (${{Postgres.DATABASE_URL}}). For local development, "
            "set DATABASE_URL to a Postgres connection string."
        )
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]
    return dsn


@contextmanager
def get_conn():
    _ensure_dirs()
    conn = psycopg.connect(_get_dsn(), row_factory=dict_row, autocommit=False)
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
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute("SELECT lesson_number FROM lessons")
            existing = {row["lesson_number"] for row in cur.fetchall()}
            for num, title in LESSON_CATALOG:
                if num not in existing:
                    cur.execute(
                        "INSERT INTO lessons (lesson_number, title) VALUES (%s, %s)",
                        (num, title),
                    )
