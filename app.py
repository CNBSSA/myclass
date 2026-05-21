import os
from dotenv import load_dotenv

load_dotenv()

import streamlit as st

from core.db import init_db
from modules import assignments, lessons


st.set_page_config(
    page_title="myclass — AI Engineering",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def _bootstrap() -> None:
    init_db()


_bootstrap()


def render_home() -> None:
    st.title("AI Engineering Interactive Learning")
    st.caption("A personal tutor for your data-science course")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📘 Module 1 — Assignments")
        st.markdown(
            "For real assignments from your course.\n\n"
            "1. **Create** a new assignment\n"
            "2. **Upload** materials (PDF, images, Jupyter notebooks, CSV/Excel, markdown)\n"
            "3. **Solve** each problem one at a time, with thorough line-by-line explanations\n"
            "4. **Ask** follow-up questions until every concept is clear\n"
            "5. **Generate** a PDF pack of solutions + explanations + your Q&A"
        )
        st.info("Desktop-only. You'll copy solutions into VS Code to work alongside.")

    with col2:
        st.subheader("🧪 Module 2 — Lessons")
        st.markdown(
            "Self-directed practice for each of the 10 lessons.\n\n"
            "1. **Pick** a lesson\n"
            "2. **Upload** lesson notes/slides (so questions are grounded in your content)\n"
            "3. **MCQ Quiz** — instant scoring with detailed explanations\n"
            "4. **Coding Challenge** — write Python, get sandbox execution + AI review + score\n"
            "5. **Track** your progress over time"
        )
        st.info("Mobile-friendly. Use on phone for MCQs, laptop for coding challenges.")

    st.divider()
    st.markdown(
        "**Powered by Claude Opus 4.7** for nuanced teaching, vision (reads your "
        "uploaded screenshots), and code review."
    )


with st.sidebar:
    st.title("🎓 myclass")
    st.caption("AI Engineering Platform")
    st.divider()

    module = st.radio(
        "Navigate",
        ["Home", "Assignments", "Lessons"],
        label_visibility="collapsed",
    )

    st.divider()

    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error(
            "**ANTHROPIC_API_KEY** is not set.\n\n"
            "Set it in `.env` for local development, or in Railway's environment "
            "variables for production."
        )
    else:
        st.success("Claude API connected")

    st.caption(f"Model: `{os.getenv('ANTHROPIC_MODEL', 'claude-opus-4-7')}`")
    st.caption("build: 2026-05-21 · quiz-lecture v5")


if module == "Home":
    render_home()
elif module == "Assignments":
    assignments.render()
elif module == "Lessons":
    lessons.render()
