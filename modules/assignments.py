import re
from pathlib import Path

import streamlit as st

from core import ai, parsers
from core.db import DATA_DIR, LESSON_CATALOG
from core.pdf_export import generate_assignment_pdf
from modules import assignments_db as db


def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("a_view", "list")
    ss.setdefault("a_current_id", None)
    ss.setdefault("a_current_problem_id", None)
    ss.setdefault("a_pack_bytes", None)
    ss.setdefault("a_pack_filename", None)


def _extract_python_block(text: str) -> str:
    m = re.search(r"```python\s*\n(.*?)\n```", text, re.DOTALL)
    return m.group(1) if m else ""


def _status_badge(status: str) -> str:
    return {"pending": "○", "in_progress": "◐", "completed": "✓"}.get(status, "·")


def _problem_label(p: dict) -> str:
    return f"{_status_badge(p['status'])} Problem {p['problem_number']}"


def _initial_user_prompt(problem: dict) -> str:
    return (
        f"Problem {problem['problem_number']}:\n\n"
        f"{problem['problem_text']}\n\n"
        "Provide a thorough solution per your guidelines: brief restatement, "
        "approach, complete runnable code in a single fenced ```python block, "
        "line-by-line explanation, and any caveats or follow-up exercises."
    )


@st.dialog("Create new assignment", width="large")
def _create_dialog() -> None:
    name = st.text_input(
        "Assignment name",
        placeholder="e.g., Lesson 3 — NumPy fundamentals",
    )

    lesson_options = ["(none)"] + [
        f"Lesson {n:02d} — {t}" for n, t in LESSON_CATALOG
    ]
    lesson_choice = st.selectbox("Course lesson (optional)", lesson_options)

    uploaded = st.file_uploader(
        "Upload assignment materials",
        accept_multiple_files=True,
        type=[ext.lstrip(".") for ext in sorted(parsers.ALL_SUPPORTED_EXTS)],
        help="PDF, image (PNG/JPG/GIF/WebP), Jupyter notebook, CSV, Excel, or markdown/text.",
    )

    disabled = not name.strip() or not uploaded
    if st.button(
        "Create & Extract Problems",
        type="primary",
        disabled=disabled,
        use_container_width=True,
    ):
        lesson_tag = None if lesson_choice == "(none)" else lesson_choice

        with st.spinner("Creating assignment record..."):
            aid = db.create_assignment(name=name.strip(), lesson_tag=lesson_tag)

        dest = DATA_DIR / "uploads" / f"assignment_{aid}"
        parsed_files: list[dict] = []
        progress = st.progress(0.0, text="Saving and parsing uploaded files...")
        for i, uf in enumerate(uploaded):
            pf = parsers.save_and_parse(uf.name, uf.getvalue(), dest)
            db.add_assignment_file(aid, pf)
            parsed_files.append(pf)
            progress.progress(
                (i + 1) / (len(uploaded) + 1),
                text=f"Parsed {pf['filename']}",
            )

        progress.progress(0.9, text="Extracting problems with Claude…")
        text_blob = parsers.aggregate_text(parsed_files)
        img_paths = parsers.image_paths(parsed_files)
        try:
            problems = ai.extract_problems(text_blob, image_paths=img_paths or None)
        except Exception as e:
            st.error(f"Failed to extract problems: {e}")
            return

        if not problems:
            st.warning(
                "No problems were detected in the uploaded materials. "
                "You can delete this assignment and try again with different files."
            )
            return

        for p in problems:
            db.add_problem(aid, p["problem_number"], p["problem_text"])

        progress.progress(1.0, text=f"Created {len(problems)} problems.")

        st.session_state.a_view = "solve"
        st.session_state.a_current_id = aid
        st.session_state.a_current_problem_id = None
        st.rerun()


def _render_list() -> None:
    st.title("📘 Assignments")

    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.caption(
            "Tutor-mode. I write the solution with thorough explanation; "
            "you copy into VS Code to run."
        )
    with head_r:
        if st.button("+ New Assignment", type="primary", use_container_width=True):
            _create_dialog()

    assignments = db.list_assignments()
    if not assignments:
        st.info("No assignments yet. Click **+ New Assignment** to create one.")
        return

    for a in assignments:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([5, 2, 2, 1])
            with c1:
                emoji = "🟢" if a["status"] == "in_progress" else "✅"
                st.markdown(f"**{emoji}&nbsp; {a['name']}**")
                meta = []
                if a["lesson_tag"]:
                    meta.append(a["lesson_tag"])
                meta.append(f"Created {a['created_at'].strftime('%b %d, %Y')}")
                st.caption(" · ".join(meta))
            with c2:
                problems = db.list_problems(a["id"])
                done = sum(1 for p in problems if p["status"] == "completed")
                st.metric(
                    "Progress",
                    f"{done} / {len(problems)}",
                    label_visibility="collapsed",
                )
            with c3:
                if st.button("Open ▸", key=f"open_{a['id']}",
                             use_container_width=True):
                    st.session_state.a_view = "solve"
                    st.session_state.a_current_id = a["id"]
                    st.session_state.a_current_problem_id = None
                    st.rerun()
            with c4:
                with st.popover("🗑", use_container_width=True):
                    st.warning(
                        f"Delete **{a['name']}**? This removes all problems, "
                        f"Q&A, and uploaded files."
                    )
                    if st.button(
                        "Confirm delete",
                        key=f"del_confirm_{a['id']}",
                        type="primary",
                    ):
                        db.delete_assignment(a["id"])
                        st.rerun()


def _stream_initial_solution(problem: dict) -> None:
    messages = [{"role": "user", "content": _initial_user_prompt(problem)}]
    chunks: list[str] = []
    with st.chat_message("assistant"):
        ph = st.empty()
        try:
            for chunk in ai.stream_chat(messages):
                chunks.append(chunk)
                ph.markdown("".join(chunks) + "▌")
            ph.markdown("".join(chunks))
        except Exception as e:
            full = "".join(chunks)
            if full.strip():
                db.save_solution(
                    problem["id"],
                    code=_extract_python_block(full),
                    explanation=full + f"\n\n_[Stream interrupted: {e}]_",
                )
            st.error(f"Streaming failed: {e}")
            return

    full = "".join(chunks)
    db.save_solution(
        problem["id"],
        code=_extract_python_block(full),
        explanation=full,
    )


def _stream_followup(problem: dict, prompt: str, attached_files=None) -> None:
    parsed_attachments: list[dict] = []
    if attached_files:
        dest = (
            DATA_DIR / "uploads"
            / f"assignment_{problem['assignment_id']}" / "qa"
        )
        for uf in attached_files:
            pf = parsers.save_and_parse(uf.name, uf.getvalue(), dest)
            parsed_attachments.append(pf)

    if parsed_attachments:
        attachment_lines = "\n".join(
            f"- {f['filename']} ({f['file_type']})"
            for f in parsed_attachments
        )
        display_text = f"{prompt}\n\n**📎 Attached:**\n{attachment_lines}"
    else:
        display_text = prompt

    user_text_for_claude = prompt
    non_image = [
        f for f in parsed_attachments if f["file_type"] != "image"
    ]
    if non_image:
        extras = parsers.aggregate_text(non_image)
        user_text_for_claude = (
            f"{prompt}\n\n--- Attached file contents ---\n{extras}"
        )

    image_paths = parsers.image_paths(parsed_attachments) or None

    db.add_qa_entry(problem["id"], "user", display_text)

    messages: list[dict] = [
        {"role": "user", "content": _initial_user_prompt(problem)},
        {"role": "assistant",
         "content": problem.get("solution_explanation") or ""},
    ]
    qa_entries = db.list_qa(problem["id"])
    for entry in qa_entries[:-1]:
        messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": user_text_for_claude})

    with st.chat_message("user"):
        st.markdown(display_text)
    chunks: list[str] = []
    with st.chat_message("assistant"):
        ph = st.empty()
        try:
            for chunk in ai.stream_chat(messages, image_paths=image_paths):
                chunks.append(chunk)
                ph.markdown("".join(chunks) + "▌")
            ph.markdown("".join(chunks))
        except Exception as e:
            full = "".join(chunks)
            if full.strip():
                db.add_qa_entry(
                    problem["id"], "assistant",
                    full + f"\n\n_[Stream interrupted: {e}]_",
                )
            st.error(f"Streaming failed: {e}")
            return

    db.add_qa_entry(problem["id"], "assistant", "".join(chunks))


def _generate_pack(assignment: dict, problems: list[dict]) -> None:
    qa_logs = db.list_qa_by_assignment(assignment["id"])
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", assignment["name"]).strip("_")
    output_path = (
        DATA_DIR
        / "exports"
        / f"assignment_{assignment['id']}_{safe_name}.pdf"
    )

    with st.spinner("Generating PDF pack..."):
        generate_assignment_pdf(
            assignment={
                "name": assignment["name"],
                "lesson_tag": assignment.get("lesson_tag"),
                "created_at": assignment["created_at"],
            },
            problems=problems,
            qa_logs=qa_logs,
            output_path=output_path,
        )

    if all(p["status"] == "completed" for p in problems):
        db.mark_assignment_complete(assignment["id"])

    st.session_state.a_pack_bytes = output_path.read_bytes()
    st.session_state.a_pack_filename = output_path.name


def _render_solve() -> None:
    aid = st.session_state.a_current_id
    assignment = db.get_assignment(aid)
    if not assignment:
        st.error("Assignment not found.")
        st.session_state.a_view = "list"
        st.rerun()
        return

    head_l, head_r = st.columns([5, 1])
    with head_l:
        st.title(f"📘 {assignment['name']}")
        if assignment.get("lesson_tag"):
            st.caption(assignment["lesson_tag"])
    with head_r:
        if st.button("← Back to list", use_container_width=True):
            st.session_state.a_view = "list"
            st.session_state.a_current_id = None
            st.session_state.a_current_problem_id = None
            st.session_state.a_pack_bytes = None
            st.session_state.a_pack_filename = None
            st.rerun()

    problems = db.list_problems(aid)
    if not problems:
        st.warning(
            "No problems were extracted from the uploaded materials. "
            "Delete this assignment and re-create it with different files."
        )
        return

    if st.session_state.a_current_problem_id not in [p["id"] for p in problems]:
        st.session_state.a_current_problem_id = problems[0]["id"]

    sel_l, sel_r = st.columns([4, 1])
    with sel_l:
        problem_labels = [_problem_label(p) for p in problems]
        current_idx = next(
            i for i, p in enumerate(problems)
            if p["id"] == st.session_state.a_current_problem_id
        )
        chosen = st.radio(
            "Problems",
            problem_labels,
            index=current_idx,
            horizontal=True,
            label_visibility="collapsed",
        )
        new_pid = problems[problem_labels.index(chosen)]["id"]
        if new_pid != st.session_state.a_current_problem_id:
            st.session_state.a_current_problem_id = new_pid
            st.session_state.a_pack_bytes = None
            st.rerun()
    with sel_r:
        completed_count = sum(1 for p in problems if p["status"] == "completed")
        can_pack = completed_count > 0
        if st.button(
            f"📦 Pack ({completed_count}/{len(problems)})",
            type="primary" if completed_count == len(problems) else "secondary",
            use_container_width=True,
            disabled=not can_pack,
        ):
            _generate_pack(assignment, problems)

    if st.session_state.a_pack_bytes:
        st.success(f"PDF pack ready ({len(st.session_state.a_pack_bytes) // 1024} KB)")
        st.download_button(
            "⬇ Download PDF",
            data=st.session_state.a_pack_bytes,
            file_name=st.session_state.a_pack_filename,
            mime="application/pdf",
            use_container_width=True,
        )

    st.divider()

    active = next(
        p for p in problems
        if p["id"] == st.session_state.a_current_problem_id
    )

    with st.container(border=True):
        st.subheader(f"Problem {active['problem_number']}")
        st.markdown(active["problem_text"])

    act_l, act_r = st.columns([1, 1])
    with act_l:
        if active["status"] != "completed":
            disabled = not active.get("solution_code")
            help_text = ("Available after generating a solution"
                         if disabled else None)
            if st.button(
                "✓ Mark problem complete",
                use_container_width=True,
                disabled=disabled,
                help=help_text,
            ):
                db.mark_problem_complete(active["id"])
                st.rerun()
        else:
            st.success("✓ This problem is marked complete")
            if st.button("Reopen problem", use_container_width=True):
                db.reopen_problem(active["id"])
                st.rerun()
    with act_r:
        if active.get("solution_code"):
            with st.popover("📋 Code only (for VS Code)", use_container_width=True):
                st.code(active["solution_code"], language="python")

    st.divider()

    has_solution = bool(active.get("solution_explanation"))

    if has_solution:
        with st.chat_message("assistant"):
            st.markdown(active["solution_explanation"])
        for entry in db.list_qa(active["id"]):
            with st.chat_message(entry["role"]):
                st.markdown(entry["content"])

        chat_value = st.chat_input(
            "Ask a question about this problem… (paperclip to attach files)",
            accept_file="multiple",
            file_type=[
                ext.lstrip(".") for ext in sorted(parsers.ALL_SUPPORTED_EXTS)
            ],
        )
        if chat_value:
            text = (chat_value.text or "").strip()
            files = chat_value.files or []
            if text or files:
                _stream_followup(active, text or "(no text)", files)
                st.rerun()
    else:
        st.info(
            "Click **Generate Solution** below and I'll write the code with a "
            "thorough line-by-line explanation."
        )
        if st.button(
            "🧠 Generate Solution",
            type="primary",
            use_container_width=True,
        ):
            _stream_initial_solution(active)
            st.rerun()


def render() -> None:
    _init_state()
    if st.session_state.a_view == "list":
        _render_list()
    elif st.session_state.a_view == "solve":
        _render_solve()
