from core.db import get_conn


def list_assignments() -> list[dict]:
    with get_conn() as conn:
        return conn.execute("""
            SELECT id, name, lesson_tag, status, created_at, completed_at
            FROM assignments
            ORDER BY
                CASE status WHEN 'in_progress' THEN 0 ELSE 1 END,
                created_at DESC
        """).fetchall()


def get_assignment(assignment_id: int) -> dict | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, name, lesson_tag, status, created_at, completed_at "
            "FROM assignments WHERE id = %s",
            (assignment_id,),
        ).fetchone()


def create_assignment(name: str, lesson_tag: str | None = None) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO assignments (name, lesson_tag) VALUES (%s, %s) "
            "RETURNING id",
            (name, lesson_tag),
        ).fetchone()
        return row["id"]


def delete_assignment(assignment_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM assignments WHERE id = %s", (assignment_id,))


def mark_assignment_complete(assignment_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE assignments SET status = 'completed', "
            "completed_at = NOW() WHERE id = %s",
            (assignment_id,),
        )


def add_assignment_file(assignment_id: int, parsed_file: dict) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO assignment_files "
            "(assignment_id, filename, file_type, file_path, extracted_text) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (assignment_id, parsed_file["filename"], parsed_file["file_type"],
             parsed_file["file_path"], parsed_file.get("extracted_text")),
        ).fetchone()
        return row["id"]


def list_assignment_files(assignment_id: int) -> list[dict]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, filename, file_type, file_path, extracted_text, created_at "
            "FROM assignment_files WHERE assignment_id = %s ORDER BY id",
            (assignment_id,),
        ).fetchall()


def add_problem(assignment_id: int, number: int, text: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO problems (assignment_id, problem_number, problem_text) "
            "VALUES (%s, %s, %s) RETURNING id",
            (assignment_id, number, text),
        ).fetchone()
        return row["id"]


def list_problems(assignment_id: int) -> list[dict]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, problem_number, problem_text, solution_code, "
            "solution_explanation, status, created_at, completed_at "
            "FROM problems WHERE assignment_id = %s ORDER BY problem_number",
            (assignment_id,),
        ).fetchall()


def get_problem(problem_id: int) -> dict | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, assignment_id, problem_number, problem_text, "
            "solution_code, solution_explanation, status, created_at, completed_at "
            "FROM problems WHERE id = %s",
            (problem_id,),
        ).fetchone()


def save_solution(problem_id: int, code: str, explanation: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE problems "
            "SET solution_code = %s, solution_explanation = %s, "
            "    status = CASE WHEN status = 'pending' THEN 'in_progress' ELSE status END "
            "WHERE id = %s",
            (code, explanation, problem_id),
        )


def mark_problem_complete(problem_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE problems SET status = 'completed', "
            "completed_at = NOW() WHERE id = %s",
            (problem_id,),
        )


def reopen_problem(problem_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE problems SET status = 'in_progress', completed_at = NULL "
            "WHERE id = %s",
            (problem_id,),
        )


def add_qa_entry(problem_id: int, role: str, content: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO qa_log (problem_id, role, content) "
            "VALUES (%s, %s, %s) RETURNING id",
            (problem_id, role, content),
        ).fetchone()
        return row["id"]


def list_qa(problem_id: int) -> list[dict]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, role, content, created_at FROM qa_log "
            "WHERE problem_id = %s ORDER BY id",
            (problem_id,),
        ).fetchall()


def list_qa_by_assignment(assignment_id: int) -> dict[int, list[dict]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT q.problem_id, q.role, q.content, q.created_at "
            "FROM qa_log q JOIN problems p ON p.id = q.problem_id "
            "WHERE p.assignment_id = %s ORDER BY q.id",
            (assignment_id,),
        ).fetchall()
    grouped: dict[int, list[dict]] = {}
    for r in rows:
        grouped.setdefault(r["problem_id"], []).append({
            "role": r["role"],
            "content": r["content"],
            "created_at": r["created_at"],
        })
    return grouped
