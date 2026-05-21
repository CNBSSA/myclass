from pathlib import Path

import streamlit as st

from core import ai, parsers, sandbox
from core.db import DATA_DIR
from modules import lessons_db as db


def _unlink_quietly(file_path: str | None) -> None:
    if not file_path:
        return
    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception:
        pass


def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("l_view", "picker")
    ss.setdefault("l_current_lesson_id", None)
    ss.setdefault("l_section", "materials")
    ss.setdefault("l_quiz", None)
    ss.setdefault("l_challenge", None)
    ss.setdefault("l_user_code", "")
    ss.setdefault("l_last_review", None)
    ss.setdefault("l_confirm_delete_all", False)


def _aggregate_materials_text(materials: list[dict]) -> str:
    return parsers.aggregate_text(materials)


def _render_picker() -> None:
    st.title("🧪 Lessons")
    st.caption(
        "Pick a lesson to upload materials, take MCQ quizzes, and solve "
        "coding challenges. Works on phone and desktop."
    )

    lessons = db.list_lessons()
    cols = st.columns(2)
    for i, lesson in enumerate(lessons):
        col = cols[i % 2]
        with col:
            with st.container(border=True):
                progress = db.get_progress(lesson["id"])
                st.markdown(
                    f"### Lesson {lesson['lesson_number']:02d}"
                )
                st.markdown(f"**{lesson['title']}**")

                mcq_total = progress["mcq_total"]
                code_total = progress["code_total"]
                if mcq_total or code_total:
                    mcq_pct = (
                        int(100 * progress["mcq_correct"] / mcq_total)
                        if mcq_total else 0
                    )
                    pieces = []
                    if mcq_total:
                        pieces.append(f"MCQ: {progress['mcq_correct']}/{mcq_total} ({mcq_pct}%)")
                    if code_total:
                        pieces.append(f"Coding: {code_total} runs · avg {progress['code_avg']}/100")
                    st.caption(" · ".join(pieces))
                else:
                    st.caption("No activity yet")

                if st.button(
                    "Open ▸",
                    key=f"open_lesson_{lesson['id']}",
                    use_container_width=True,
                ):
                    st.session_state.l_view = "lesson"
                    st.session_state.l_current_lesson_id = lesson["id"]
                    st.session_state.l_section = "materials"
                    st.session_state.l_quiz = None
                    st.session_state.l_challenge = None
                    st.session_state.l_last_review = None
                    st.rerun()


def _render_lesson() -> None:
    lid = st.session_state.l_current_lesson_id
    lesson = db.get_lesson(lid)
    if not lesson:
        st.error("Lesson not found.")
        st.session_state.l_view = "picker"
        st.rerun()
        return

    head_l, head_r = st.columns([5, 1])
    with head_l:
        st.title(f"🧪 Lesson {lesson['lesson_number']:02d} — {lesson['title']}")
    with head_r:
        if st.button("← All lessons", use_container_width=True):
            st.session_state.l_view = "picker"
            st.session_state.l_current_lesson_id = None
            st.rerun()

    tabs = st.tabs(["📄 Materials", "❓ MCQ Quiz", "💻 Coding Challenge"])

    with tabs[0]:
        _render_materials_tab(lesson)
    with tabs[1]:
        _render_quiz_tab(lesson)
    with tabs[2]:
        _render_coding_tab(lesson)


def _render_materials_tab(lesson: dict) -> None:
    materials = db.list_lesson_materials(lesson["id"])

    uploaded = st.file_uploader(
        "Upload notes, slides, or any reference for this lesson",
        accept_multiple_files=True,
        type=[ext.lstrip(".") for ext in sorted(parsers.ALL_SUPPORTED_EXTS)],
        key=f"mat_uploader_{lesson['id']}",
    )

    if uploaded and st.button(
        "Save uploaded files",
        type="primary",
        use_container_width=True,
        key=f"save_mats_{lesson['id']}",
    ):
        dest = DATA_DIR / "uploads" / f"lesson_{lesson['id']}"
        with st.spinner("Parsing and saving..."):
            for uf in uploaded:
                pf = parsers.save_and_parse(uf.name, uf.getvalue(), dest)
                db.add_lesson_material(lesson["id"], pf)
        st.success(f"Saved {len(uploaded)} file(s).")
        st.rerun()

    st.divider()

    if not materials:
        st.info(
            "No materials uploaded yet. Upload at least one file so that "
            "quizzes and coding challenges can be grounded in your content."
        )
        return

    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.subheader(f"Materials ({len(materials)})")
    with head_r:
        if st.button("🗑 Remove ALL", use_container_width=True,
                     key=f"ask_del_all_{lesson['id']}"):
            st.session_state.l_confirm_delete_all = True
            st.rerun()

    if st.session_state.l_confirm_delete_all:
        st.warning(
            f"Permanently delete **all {len(materials)} files** for this "
            f"lesson? This removes the DB records and the saved files on disk. "
            f"This cannot be undone."
        )
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button(
                "✓ Yes, delete everything",
                type="primary",
                use_container_width=True,
                key=f"do_del_all_{lesson['id']}",
            ):
                paths = db.delete_all_lesson_materials(lesson["id"])
                for p in paths:
                    _unlink_quietly(p)
                st.session_state.l_confirm_delete_all = False
                st.rerun()
        with cc2:
            if st.button(
                "Cancel",
                use_container_width=True,
                key=f"cancel_del_all_{lesson['id']}",
            ):
                st.session_state.l_confirm_delete_all = False
                st.rerun()
        return

    MAX_SHOWN = 30
    shown = materials[:MAX_SHOWN]
    if len(materials) > MAX_SHOWN:
        st.caption(
            f"Showing {MAX_SHOWN} of {len(materials)} files. "
            f"Use **Remove ALL** above to clear them all at once."
        )

    for m in shown:
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"**{m['filename']}**")
                st.caption(
                    f"{m['file_type']} · added {m['created_at'].strftime('%b %d, %Y')}"
                )
                if m["extracted_text"]:
                    with st.expander("Preview extracted text", expanded=False):
                        st.text(m["extracted_text"][:2000])
                        if len(m["extracted_text"]) > 2000:
                            st.caption(
                                f"(showing first 2000 of "
                                f"{len(m['extracted_text'])} characters)"
                            )
            with c2:
                if st.button("Remove", key=f"rm_mat_{m['id']}",
                             use_container_width=True):
                    removed_path = db.delete_lesson_material(m["id"])
                    _unlink_quietly(removed_path)
                    st.rerun()


def _render_quiz_tab(lesson: dict) -> None:
    materials = db.list_lesson_materials(lesson["id"])
    if not materials:
        st.warning("Upload lesson materials in the Materials tab first.")
        return

    quiz = st.session_state.l_quiz

    if quiz is None:
        st.subheader("MCQ Quiz")
        progress = db.get_progress(lesson["id"])
        if progress["mcq_total"]:
            pct = int(100 * progress["mcq_correct"] / progress["mcq_total"])
            st.caption(
                f"Lifetime: {progress['mcq_correct']}/{progress['mcq_total']} "
                f"correct ({pct}%)"
            )

        count = st.slider("Number of questions", 3, 10, 5)
        if st.button(
            "🧠 Start new quiz",
            type="primary",
            use_container_width=True,
        ):
            text_blob = _aggregate_materials_text(materials)
            with st.spinner("Generating quiz..."):
                try:
                    questions = ai.generate_mcqs(
                        lesson["title"], text_blob, count=count,
                    )
                except Exception as e:
                    st.error(f"Failed to generate quiz: {e}")
                    return
            st.session_state.l_quiz = {
                "questions": questions,
                "current": 0,
                "answers": [None] * len(questions),
                "submitted": [False] * len(questions),
                "lectures": {},
            }
            st.rerun()
        return

    questions = quiz["questions"]
    idx = quiz["current"]

    if idx >= len(questions):
        _render_quiz_summary(lesson, quiz)
        return

    q = questions[idx]
    st.subheader(f"Question {idx + 1} of {len(questions)}")
    st.caption(f"Difficulty: {q['difficulty']}")
    st.markdown(f"**{q['question']}**")

    option_keys = ["A", "B", "C", "D"]
    labels = [f"**{k}.** {opt}" for k, opt in zip(option_keys, q["options"])]

    if not quiz["submitted"][idx]:
        choice_label = st.radio(
            "Your answer",
            labels,
            index=None,
            key=f"mcq_radio_{lesson['id']}_{idx}",
        )
        if st.button(
            "Submit answer",
            type="primary",
            use_container_width=True,
            disabled=choice_label is None,
        ):
            user_letter = option_keys[labels.index(choice_label)]
            is_correct = (user_letter == q["correct_answer"])
            quiz["answers"][idx] = user_letter
            quiz["submitted"][idx] = True
            db.add_mcq_attempt(
                lesson_id=lesson["id"],
                question=q["question"],
                options=q["options"],
                correct_answer=q["correct_answer"],
                user_answer=user_letter,
                is_correct=is_correct,
                explanation=q["explanation"],
            )
            st.rerun()
    else:
        user_letter = quiz["answers"][idx]
        correct_letter = q["correct_answer"]
        for k, label in zip(option_keys, labels):
            if k == correct_letter and k == user_letter:
                st.success(f"✓ {label} (your answer — correct)")
            elif k == correct_letter:
                st.success(f"✓ {label} (correct answer)")
            elif k == user_letter:
                st.error(f"✗ {label} (your answer)")
            else:
                st.markdown(f"&nbsp;&nbsp; {label}")
        st.markdown("**Quick answer**")
        st.info(q["explanation"])

        st.markdown("**📚 In-depth explanation**")
        lectures = quiz.setdefault("lectures", {})
        if idx not in lectures:
            chunks: list[str] = []
            ph = st.empty()
            try:
                for chunk in ai.stream_mcq_lecture(
                    lesson_title=lesson["title"],
                    question=q["question"],
                    options=q["options"],
                    correct_answer=correct_letter,
                    user_answer=user_letter,
                    is_correct=(user_letter == correct_letter),
                ):
                    chunks.append(chunk)
                    ph.markdown("".join(chunks) + "▌")
                ph.markdown("".join(chunks))
                lectures[idx] = "".join(chunks)
            except Exception as e:
                ph.error(f"Could not generate the in-depth explanation: {e}")
        else:
            st.markdown(lectures[idx])

        c1, c2 = st.columns([3, 1])
        with c1:
            if st.button(
                "Next question" if idx < len(questions) - 1 else "See summary",
                type="primary",
                use_container_width=True,
            ):
                quiz["current"] = idx + 1
                st.rerun()
        with c2:
            if st.button("End quiz", use_container_width=True):
                st.session_state.l_quiz = None
                st.rerun()


def _render_quiz_summary(lesson: dict, quiz: dict) -> None:
    questions = quiz["questions"]
    answers = quiz["answers"]
    correct = sum(
        1 for q, a in zip(questions, answers)
        if a == q["correct_answer"]
    )
    total = len(questions)
    pct = int(100 * correct / total) if total else 0

    st.subheader("Quiz complete!")
    st.metric("Score", f"{correct} / {total}", f"{pct}%")

    if pct == 100:
        st.balloons()
        st.success("Perfect score!")
    elif pct >= 80:
        st.success("Strong understanding.")
    elif pct >= 60:
        st.info("Solid grasp. Review the misses below.")
    else:
        st.warning("Some gaps to address. Review the explanations carefully.")

    with st.expander("Review every question", expanded=False):
        for i, q in enumerate(questions):
            ua = answers[i]
            ok = ua == q["correct_answer"]
            icon = "✓" if ok else "✗"
            st.markdown(f"**{icon} Q{i+1}.** {q['question']}")
            st.caption(
                f"Your answer: {ua} · Correct: {q['correct_answer']}"
            )
            st.markdown(q["explanation"])
            st.divider()

    if st.button(
        "Take another quiz",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.l_quiz = None
        st.rerun()


def _render_coding_tab(lesson: dict) -> None:
    materials = db.list_lesson_materials(lesson["id"])
    if not materials:
        st.warning("Upload lesson materials in the Materials tab first.")
        return

    challenge = st.session_state.l_challenge

    if challenge is None:
        st.subheader("Coding Challenge")
        progress = db.get_progress(lesson["id"])
        if progress["code_total"]:
            st.caption(
                f"Lifetime: {progress['code_total']} runs · "
                f"average {progress['code_avg']}/100"
            )

        difficulty = st.select_slider(
            "Difficulty",
            options=["easy", "medium", "hard"],
            value="medium",
        )
        if st.button(
            "💻 Generate challenge",
            type="primary",
            use_container_width=True,
        ):
            text_blob = _aggregate_materials_text(materials)
            with st.spinner("Generating challenge..."):
                try:
                    ch = ai.generate_coding_challenge(
                        lesson["title"], text_blob, difficulty=difficulty,
                    )
                except Exception as e:
                    st.error(f"Failed to generate challenge: {e}")
                    return
            st.session_state.l_challenge = ch
            st.session_state.l_user_code = ch.get("starter_code", "")
            st.session_state.l_last_review = None
            st.rerun()
        return

    st.subheader("Coding Challenge")
    st.caption(f"Difficulty: {challenge['difficulty']}")
    st.markdown("**Problem**")
    st.markdown(challenge["problem"])
    st.markdown("**Expected behavior**")
    st.info(challenge["expected_behavior"])

    if challenge.get("hints"):
        with st.expander("Hints (open only if stuck)", expanded=False):
            for i, hint in enumerate(challenge["hints"], start=1):
                st.markdown(f"**Hint {i}:** {hint}")

    st.markdown("**Your code**")
    user_code = st.text_area(
        "Write your solution here",
        value=st.session_state.l_user_code,
        height=300,
        label_visibility="collapsed",
        key=f"code_input_{lesson['id']}",
    )
    st.session_state.l_user_code = user_code

    c1, c2 = st.columns([3, 1])
    with c1:
        run_clicked = st.button(
            "▶ Run & Review",
            type="primary",
            use_container_width=True,
            disabled=not user_code.strip(),
        )
    with c2:
        if st.button("✕ New challenge", use_container_width=True):
            st.session_state.l_challenge = None
            st.session_state.l_user_code = ""
            st.session_state.l_last_review = None
            st.rerun()

    if run_clicked:
        with st.spinner("Running in sandbox..."):
            result = sandbox.execute_python(user_code)
        with st.spinner("Reviewing your code with Claude..."):
            try:
                review = ai.review_code(
                    problem=challenge["problem"],
                    expected_behavior=challenge["expected_behavior"],
                    user_code=user_code,
                    stdout=result["stdout"],
                    stderr=result["stderr"],
                    success=result["success"],
                )
            except Exception as e:
                st.error(f"Review failed: {e}")
                return
        db.add_coding_attempt(
            lesson_id=lesson["id"],
            problem=challenge["problem"],
            expected_behavior=challenge["expected_behavior"],
            user_code=user_code,
            stdout=result["stdout"],
            stderr=result["stderr"],
            success=result["success"],
            ai_review=review["explanation"],
            score=review["score"],
        )
        st.session_state.l_last_review = {
            "execution": result,
            "review": review,
        }
        st.rerun()

    if st.session_state.l_last_review:
        _render_review(st.session_state.l_last_review)


def _render_review(payload: dict) -> None:
    exe = payload["execution"]
    rev = payload["review"]

    st.divider()
    st.subheader("Sandbox execution")
    if exe["success"]:
        st.success("Ran successfully (exit code 0)")
    elif exe["timed_out"]:
        st.warning("Timed out — your code took too long to finish")
    else:
        st.error(f"Failed with exit code {exe['return_code']}")
    if exe["stdout"]:
        st.markdown("**stdout**")
        st.code(exe["stdout"], language="text")
    if exe["stderr"]:
        st.markdown("**stderr**")
        st.code(exe["stderr"], language="text")

    st.subheader("Claude's review")
    verdict = rev["verdict"]
    score = rev["score"]
    verdict_color = {
        "correct": "success",
        "mostly_correct": "info",
        "incorrect": "error",
    }[verdict]
    getattr(st, verdict_color)(
        f"**Verdict: {verdict.replace('_', ' ').title()} · "
        f"Score: {score}/100**"
    )

    if rev.get("strengths"):
        st.markdown("**Strengths**")
        for s in rev["strengths"]:
            st.markdown(f"- {s}")

    if rev.get("improvements"):
        st.markdown("**Improvements**")
        for imp in rev["improvements"]:
            st.markdown(f"- {imp}")

    if rev.get("explanation"):
        st.markdown("**Detailed explanation**")
        st.markdown(rev["explanation"])

    if rev.get("corrected_code"):
        st.markdown("**Suggested version**")
        st.code(rev["corrected_code"], language="python")


def render() -> None:
    _init_state()
    if st.session_state.l_view == "picker":
        _render_picker()
    elif st.session_state.l_view == "lesson":
        _render_lesson()
