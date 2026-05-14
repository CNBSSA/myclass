import os
import base64
import json
from pathlib import Path
from typing import Iterator
import anthropic

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7")

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file locally, "
                "or to the Railway environment variables in production."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


TUTOR_SYSTEM = """You are an expert AI Engineering tutor teaching a focused course covering:
NumPy, Pandas, Data Visualization, Math & Statistics, Probability Distributions,
Advanced Statistics, Data Wrangling, Feature Engineering, and applied data science with Python.

Your teaching philosophy:
- Every solution must include a thorough, line-by-line explanation
- Explain the WHY behind every choice, not just WHAT the code does
- Connect new concepts to prior knowledge the student should have
- Anticipate confusion points and address them before they are asked
- Use realistic, runnable Python code (Python 3.11+, standard data-science stack:
  numpy, pandas, matplotlib, seaborn, scipy, scikit-learn)
- Prefer clear code over clever code
- When the student asks questions, answer with depth and patience
- Never skip steps; never assume prior knowledge that has not been established

Your output format for solutions:
1. Brief restatement of the problem (1-2 sentences)
2. The approach (high-level strategy)
3. The code (single fenced ```python block, complete and runnable)
4. Line-by-line explanation in clear prose
5. Caveats, alternative approaches, or follow-up exercises when useful

When the student asks a follow-up question, answer it directly and thoroughly,
referring back to the code you wrote and using concrete examples.
"""

MCQ_SYSTEM = """You are an expert AI Engineering instructor creating multiple-choice
questions to assess and reinforce a student's understanding.

Guidelines:
- Questions must test conceptual understanding, not trivia
- Exactly 4 options per question, exactly one correct
- Distractors should reflect common misconceptions, not obvious wrong answers
- Vary difficulty across easy, medium, and hard
- Explanations must teach: explain WHY the correct answer is correct AND WHY each
  incorrect option is wrong

Output must strictly match the JSON schema provided.
"""

CODE_REVIEW_SYSTEM = """You are an expert AI Engineering instructor reviewing a
student's Python code.

Review criteria:
- Correctness: does the code solve the problem as specified?
- Style: is the code clear, readable, and idiomatic Python?
- Efficiency: is the approach reasonable for the data sizes implied?
- Robustness: are edge cases handled appropriately?

For each review provide:
1. An integer score from 0-100 (correct & idiomatic = 85+; correct but messy = 65-84;
   partial = 40-64; incorrect = 0-39)
2. Concrete strengths the student demonstrated
3. Specific improvements (actionable, not vague)
4. A clear explanation of any errors and the corrected code

Be encouraging but honest. The student is here to learn.
"""

PROBLEM_EXTRACTION_SYSTEM = """You are an expert at parsing educational assignment
materials. Identify every distinct problem the student must solve. Preserve the
original problem text faithfully. If multiple problems share context (a shared
dataset description, common setup code, etc.), include that context in each
problem's text so it can stand alone.
"""


def _file_to_image_block(file_path: str) -> dict:
    p = Path(file_path)
    ext = p.suffix.lower().lstrip(".")
    media_type = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif", "webp": "image/webp",
    }.get(ext, "image/png")
    data = base64.standard_b64encode(p.read_bytes()).decode("ascii")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def stream_chat(
    messages: list[dict],
    system: str = TUTOR_SYSTEM,
    image_paths: list[str] | None = None,
    max_tokens: int = 16000,
) -> Iterator[str]:
    if image_paths:
        messages = [dict(m) for m in messages]
        last = messages[-1]
        if last["role"] != "user":
            raise ValueError("Images can only be attached to the last user message.")
        original = last["content"]
        last["content"] = [_file_to_image_block(p) for p in image_paths]
        if isinstance(original, str):
            last["content"].append({"type": "text", "text": original})
        elif isinstance(original, list):
            last["content"].extend(original)

    client = get_client()
    with client.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        system=[{
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},
        }],
        thinking={"type": "adaptive"},
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


MCQ_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "correct_answer": {
                        "type": "string",
                        "enum": ["A", "B", "C", "D"],
                    },
                    "difficulty": {
                        "type": "string",
                        "enum": ["easy", "medium", "hard"],
                    },
                    "explanation": {"type": "string"},
                },
                "required": ["question", "options", "correct_answer", "difficulty", "explanation"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["questions"],
    "additionalProperties": False,
}


def generate_mcqs(lesson_title: str, materials_text: str, count: int = 5) -> list[dict]:
    client = get_client()
    user_msg = (
        f"Lesson: {lesson_title}\n\n"
        f"--- Course materials ---\n{materials_text}\n--- End materials ---\n\n"
        f"Generate exactly {count} multiple-choice questions grounded in these "
        f"materials. Cover the most important concepts. Vary difficulty across "
        f"easy, medium, and hard."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=[{
            "type": "text",
            "text": MCQ_SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_msg}],
        output_config={
            "format": {"type": "json_schema", "schema": MCQ_SCHEMA},
            "effort": "medium",
        },
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["questions"]


CHALLENGE_SCHEMA = {
    "type": "object",
    "properties": {
        "problem": {"type": "string"},
        "expected_behavior": {"type": "string"},
        "starter_code": {"type": "string"},
        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
        "hints": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["problem", "expected_behavior", "starter_code", "difficulty", "hints"],
    "additionalProperties": False,
}


def generate_coding_challenge(
    lesson_title: str,
    materials_text: str,
    difficulty: str = "medium",
) -> dict:
    client = get_client()
    user_msg = (
        f"Lesson: {lesson_title}\nTarget difficulty: {difficulty}\n\n"
        f"--- Course materials ---\n{materials_text}\n--- End materials ---\n\n"
        "Create one practical Python coding challenge tied to this lesson. "
        "The problem should be solvable in 5-30 lines of code. Provide clear "
        "expected behavior so the student knows what success looks like. "
        "Include 2-3 progressive hints (each more revealing than the last). "
        "Starter code may be an empty stub or minimal scaffolding."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=[{
            "type": "text",
            "text": TUTOR_SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_msg}],
        output_config={
            "format": {"type": "json_schema", "schema": CHALLENGE_SCHEMA},
            "effort": "medium",
        },
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "verdict": {"type": "string", "enum": ["correct", "mostly_correct", "incorrect"]},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
        "explanation": {"type": "string"},
        "corrected_code": {"type": "string"},
    },
    "required": ["score", "verdict", "strengths", "improvements", "explanation", "corrected_code"],
    "additionalProperties": False,
}


def review_code(
    problem: str,
    expected_behavior: str,
    user_code: str,
    stdout: str,
    stderr: str,
    success: bool,
) -> dict:
    client = get_client()
    user_msg = (
        f"--- Problem ---\n{problem}\n\n"
        f"--- Expected behavior ---\n{expected_behavior}\n\n"
        f"--- Student's code ---\n```python\n{user_code}\n```\n\n"
        f"--- Sandbox execution ---\n"
        f"Success: {success}\nstdout:\n{stdout or '(empty)'}\n\n"
        f"stderr:\n{stderr or '(empty)'}\n\n"
        "Review the code per your guidelines. Provide an honest score and detailed "
        "feedback. If the code has bugs, return the corrected code in `corrected_code`. "
        "If the code is correct, return a cleaner or more efficient alternative in "
        "`corrected_code` (with an explanation of why it is better)."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=[{
            "type": "text",
            "text": CODE_REVIEW_SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_msg}],
        output_config={
            "format": {"type": "json_schema", "schema": REVIEW_SCHEMA},
            "effort": "high",
        },
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "problems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "problem_number": {"type": "integer"},
                    "problem_text": {"type": "string"},
                },
                "required": ["problem_number", "problem_text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["problems"],
    "additionalProperties": False,
}


def extract_problems(
    materials_text: str,
    image_paths: list[str] | None = None,
) -> list[dict]:
    client = get_client()
    content: list = []
    if image_paths:
        content.extend(_file_to_image_block(p) for p in image_paths)
    content.append({
        "type": "text",
        "text": (
            f"--- Assignment materials (text) ---\n{materials_text or '(no text content)'}\n"
            "--- End materials ---\n\n"
            "Identify every distinct problem in this assignment. Number them sequentially "
            "starting from 1. Preserve original problem wording faithfully. Include any "
            "shared context (dataset descriptions, setup code, definitions) in each "
            "problem's text so it stands alone."
        ),
    })

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=PROBLEM_EXTRACTION_SYSTEM,
        messages=[{"role": "user", "content": content}],
        output_config={
            "format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA},
            "effort": "medium",
        },
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["problems"]
