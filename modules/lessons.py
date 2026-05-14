import streamlit as st


def render() -> None:
    st.title("🧪 Lessons")
    st.caption("Interactive practice for the 10 course lessons")

    st.info(
        "**Phase 3 — coming after Module 1.** This module will let you upload "
        "lesson materials, take MCQ quizzes with instant scoring, and solve "
        "coding challenges that execute in a sandbox and get reviewed by Claude.\n\n"
        "The data model, AI plumbing, and code sandbox are already wired up. "
        "Building the UI flow next."
    )
