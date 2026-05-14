import json

from core.db import get_conn


def list_lessons() -> list[dict]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, lesson_number, title FROM lessons ORDER BY lesson_number"
        ).fetchall()


def get_lesson(lesson_id: int) -> dict | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, lesson_number, title FROM lessons WHERE id = %s",
            (lesson_id,),
        ).fetchone()


def get_lesson_by_number(lesson_number: int) -> dict | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, lesson_number, title FROM lessons WHERE lesson_number = %s",
            (lesson_number,),
        ).fetchone()


def list_lesson_materials(lesson_id: int) -> list[dict]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, filename, file_type, file_path, extracted_text, created_at "
            "FROM lesson_materials WHERE lesson_id = %s ORDER BY id",
            (lesson_id,),
        ).fetchall()


def add_lesson_material(lesson_id: int, parsed_file: dict) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO lesson_materials "
            "(lesson_id, filename, file_type, file_path, extracted_text) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (lesson_id, parsed_file["filename"], parsed_file["file_type"],
             parsed_file["file_path"], parsed_file.get("extracted_text")),
        ).fetchone()
        return row["id"]


def delete_lesson_material(material_id: int) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT file_path FROM lesson_materials WHERE id = %s",
            (material_id,),
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM lesson_materials WHERE id = %s", (material_id,))
    return row["file_path"]


def delete_all_lesson_materials(lesson_id: int) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT file_path FROM lesson_materials WHERE lesson_id = %s",
            (lesson_id,),
        ).fetchall()
        conn.execute(
            "DELETE FROM lesson_materials WHERE lesson_id = %s",
            (lesson_id,),
        )
    return [r["file_path"] for r in rows]


def add_mcq_attempt(
    lesson_id: int,
    question: str,
    options: list[str],
    correct_answer: str,
    user_answer: str,
    is_correct: bool,
    explanation: str,
) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO mcq_attempts "
            "(lesson_id, question, options_json, correct_answer, "
            " user_answer, is_correct, explanation) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (lesson_id, question, json.dumps(options), correct_answer,
             user_answer, is_correct, explanation),
        ).fetchone()
        return row["id"]


def list_mcq_attempts(lesson_id: int, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, question, options_json, correct_answer, user_answer, "
            "is_correct, explanation, created_at "
            "FROM mcq_attempts WHERE lesson_id = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (lesson_id, limit),
        ).fetchall()
    for r in rows:
        r["options"] = json.loads(r["options_json"])
    return rows


def add_coding_attempt(
    lesson_id: int,
    problem: str,
    expected_behavior: str,
    user_code: str,
    stdout: str,
    stderr: str,
    success: bool,
    ai_review: str,
    score: int,
) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO coding_attempts "
            "(lesson_id, problem, expected_behavior, user_code, "
            " execution_stdout, execution_stderr, execution_success, "
            " ai_review, score) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (lesson_id, problem, expected_behavior, user_code,
             stdout, stderr, success, ai_review, score),
        ).fetchone()
        return row["id"]


def list_coding_attempts(lesson_id: int, limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, problem, expected_behavior, user_code, "
            "execution_stdout, execution_stderr, execution_success, "
            "ai_review, score, created_at "
            "FROM coding_attempts WHERE lesson_id = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (lesson_id, limit),
        ).fetchall()


def get_progress(lesson_id: int) -> dict:
    with get_conn() as conn:
        mcq = conn.execute(
            "SELECT COUNT(*)::int AS total, "
            "SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)::int AS correct "
            "FROM mcq_attempts WHERE lesson_id = %s",
            (lesson_id,),
        ).fetchone()
        code = conn.execute(
            "SELECT COUNT(*)::int AS total, "
            "AVG(score)::int AS avg_score "
            "FROM coding_attempts WHERE lesson_id = %s",
            (lesson_id,),
        ).fetchone()
    return {
        "mcq_total":   mcq["total"] or 0,
        "mcq_correct": mcq["correct"] or 0,
        "code_total":  code["total"] or 0,
        "code_avg":    code["avg_score"] or 0,
    }
