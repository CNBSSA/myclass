import streamlit as st


def render() -> None:
    st.title("📘 Assignments")
    st.caption("Tutor-mode: I write solutions with thorough explanations; you copy to VS Code")

    st.info(
        "**Phase 2 — coming next.** This module will let you create assignments, "
        "upload materials, work through problems one at a time with full Q&A, "
        "and generate a PDF assignment pack.\n\n"
        "The data model and AI plumbing are already wired up. Building the UI flow next."
    )
