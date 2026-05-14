import re
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, grey
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, XPreformatted,
)

from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import Token


PYGMENTS_COLORS = {
    Token.Keyword: "#0033B3",
    Token.Keyword.Namespace: "#0033B3",
    Token.Keyword.Constant: "#0033B3",
    Token.Name.Builtin: "#1750EB",
    Token.Name.Builtin.Pseudo: "#1750EB",
    Token.Name.Function: "#7A3E9D",
    Token.Name.Class: "#267F99",
    Token.Name.Decorator: "#AF00DB",
    Token.Literal.String: "#067D17",
    Token.Literal.String.Doc: "#067D17",
    Token.Literal.String.Escape: "#067D17",
    Token.Comment: "#6B8E23",
    Token.Comment.Single: "#6B8E23",
    Token.Literal.Number: "#1750EB",
    Token.Operator: "#000000",
    Token.Operator.Word: "#0033B3",
    Token.Punctuation: "#000000",
}


def _color_for_token(ttype) -> str | None:
    current = ttype
    while current is not None:
        if current in PYGMENTS_COLORS:
            return PYGMENTS_COLORS[current]
        current = getattr(current, "parent", None)
    return None


def _xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


def highlight_python(code: str) -> str:
    out = []
    for ttype, value in lex(code, PythonLexer()):
        color = _color_for_token(ttype)
        escaped = _xml_escape(value)
        if color:
            out.append(f'<font color="{color}">{escaped}</font>')
        else:
            out.append(escaped)
    return "".join(out)


def _inline_md(text: str) -> str:
    text = _xml_escape(text)
    text = re.sub(r"`([^`]+)`",
                  r'<font face="Courier" color="#A31515">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", text)
    return text


def markdown_to_flowables(md: str, styles: dict) -> list:
    flow: list = []
    lines = md.split("\n")
    para_buf: list[str] = []

    def flush():
        if para_buf:
            text = " ".join(line.strip() for line in para_buf).strip()
            if text:
                flow.append(Paragraph(_inline_md(text), styles["body"]))
        para_buf.clear()

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.strip().startswith("```"):
            flush()
            lang = line.strip()[3:].strip().lower()
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            code = "\n".join(code_lines)
            if lang in ("", "python", "py"):
                flow.append(XPreformatted(highlight_python(code), styles["code"]))
            else:
                flow.append(XPreformatted(_xml_escape(code), styles["code"]))
            flow.append(Spacer(1, 6))
            continue

        if line.startswith("# "):
            flush()
            flow.append(Paragraph(_inline_md(line[2:]), styles["h1"]))
        elif line.startswith("## "):
            flush()
            flow.append(Paragraph(_inline_md(line[3:]), styles["h2"]))
        elif line.startswith("### "):
            flush()
            flow.append(Paragraph(_inline_md(line[4:]), styles["h3"]))
        elif re.match(r"^\s*[-*]\s+", line):
            flush()
            content = re.sub(r"^\s*[-*]\s+", "", line)
            flow.append(Paragraph("&bull;&nbsp; " + _inline_md(content), styles["bullet"]))
        elif re.match(r"^\s*\d+\.\s+", line):
            flush()
            m = re.match(r"^\s*(\d+)\.\s+(.*)", line)
            flow.append(Paragraph(f"{m.group(1)}.&nbsp; " + _inline_md(m.group(2)), styles["bullet"]))
        elif line.strip() == "":
            flush()
        else:
            para_buf.append(line)
        i += 1

    flush()
    return flow


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"],
                                fontSize=26, leading=32,
                                alignment=TA_CENTER, spaceAfter=24,
                                textColor=HexColor("#1F3A60")),
        "h1": ParagraphStyle("h1", parent=base["Heading1"],
                             fontSize=18, leading=22,
                             spaceBefore=16, spaceAfter=10,
                             textColor=HexColor("#1F3A60")),
        "h2": ParagraphStyle("h2", parent=base["Heading2"],
                             fontSize=14, leading=18,
                             spaceBefore=12, spaceAfter=6,
                             textColor=HexColor("#1F3A60")),
        "h3": ParagraphStyle("h3", parent=base["Heading3"],
                             fontSize=12, leading=15,
                             spaceBefore=10, spaceAfter=4,
                             textColor=HexColor("#1F3A60")),
        "body": ParagraphStyle("body", parent=base["BodyText"],
                               fontSize=10.5, leading=14,
                               alignment=TA_LEFT, spaceAfter=6),
        "bullet": ParagraphStyle("bullet", parent=base["BodyText"],
                                 fontSize=10.5, leading=14,
                                 leftIndent=18, spaceAfter=2),
        "code": ParagraphStyle("code", parent=base["Code"],
                               fontName="Courier", fontSize=9, leading=12,
                               backColor=HexColor("#F7F7F7"),
                               borderColor=HexColor("#DDDDDD"),
                               borderWidth=0.5, borderPadding=8,
                               leftIndent=4, rightIndent=4,
                               spaceBefore=6, spaceAfter=6),
        "qa_q": ParagraphStyle("qa_q", parent=base["BodyText"],
                               fontSize=10.5, leading=14,
                               leftIndent=10,
                               textColor=HexColor("#005A9C"),
                               fontName="Helvetica-Bold",
                               spaceBefore=10, spaceAfter=4),
        "qa_a": ParagraphStyle("qa_a", parent=base["BodyText"],
                               fontSize=10.5, leading=14,
                               leftIndent=10, spaceAfter=6),
        "meta": ParagraphStyle("meta", parent=base["BodyText"],
                               fontSize=10, textColor=grey,
                               alignment=TA_CENTER, spaceAfter=6),
    }


def generate_assignment_pdf(
    assignment: dict,
    problems: list[dict],
    qa_logs: dict[int, list[dict]],
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        leftMargin=0.8 * inch, rightMargin=0.8 * inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
        title=assignment["name"],
        author="myclass — AI Engineering Platform",
    )
    styles = _styles()
    flow: list = []

    flow.append(Spacer(1, 1.5 * inch))
    flow.append(Paragraph(assignment["name"], styles["title"]))
    if assignment.get("lesson_tag"):
        flow.append(Paragraph(f"Lesson: {assignment['lesson_tag']}", styles["meta"]))
    flow.append(Paragraph(
        f"Generated {datetime.now().strftime('%B %d, %Y')}",
        styles["meta"],
    ))
    flow.append(PageBreak())

    flow.append(Paragraph("Contents", styles["h1"]))
    for p in problems:
        first_line = p["problem_text"].split("\n", 1)[0]
        preview = first_line[:90] + ("..." if len(first_line) > 90 else "")
        flow.append(Paragraph(
            f"Problem {p['problem_number']}: {_inline_md(preview)}",
            styles["body"],
        ))
    flow.append(PageBreak())

    for p in problems:
        flow.append(Paragraph(f"Problem {p['problem_number']}", styles["h1"]))

        flow.append(Paragraph("Statement", styles["h3"]))
        flow.extend(markdown_to_flowables(p["problem_text"], styles))

        if p.get("solution_code"):
            flow.append(Paragraph("Solution", styles["h3"]))
            flow.append(XPreformatted(highlight_python(p["solution_code"]), styles["code"]))

        if p.get("solution_explanation"):
            flow.append(Paragraph("Explanation", styles["h3"]))
            flow.extend(markdown_to_flowables(p["solution_explanation"], styles))

        qa = qa_logs.get(p["id"], [])
        if qa:
            flow.append(Paragraph("Discussion", styles["h3"]))
            for entry in qa:
                if entry["role"] == "user":
                    flow.append(Paragraph(
                        "Q: " + _inline_md(entry["content"]),
                        styles["qa_q"],
                    ))
                else:
                    flow.extend(markdown_to_flowables(entry["content"], styles))

        flow.append(PageBreak())

    doc.build(flow)
    return output_path
