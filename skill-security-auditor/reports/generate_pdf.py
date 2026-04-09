#!/usr/bin/env python3
"""
generate_pdf.py — Convert skill-security-auditor development report markdown to PDF
Uses reportlab for PDF generation and markdown for parsing.
"""

import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Preformatted, KeepTogether
)
from reportlab.platypus.flowables import Flowable

# ── Page layout ───────────────────────────────────────────────────────────────

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm

# ── Color palette ─────────────────────────────────────────────────────────────

COLOR_TITLE      = colors.HexColor("#1a1a2e")
COLOR_H2         = colors.HexColor("#16213e")
COLOR_H3         = colors.HexColor("#0f3460")
COLOR_H4         = colors.HexColor("#2c3e50")
COLOR_CODE_BG    = colors.HexColor("#f4f4f4")
COLOR_CODE_BORDER= colors.HexColor("#cccccc")
COLOR_TABLE_HEAD = colors.HexColor("#0f3460")
COLOR_TABLE_ALT  = colors.HexColor("#f0f4f8")
COLOR_RULE       = colors.HexColor("#dddddd")
COLOR_LINK       = colors.HexColor("#0066cc")
COLOR_WARN       = colors.HexColor("#e74c3c")
COLOR_OK         = colors.HexColor("#27ae60")
COLOR_INLINE_BG  = colors.HexColor("#eeeeee")

# ── Styles ────────────────────────────────────────────────────────────────────

def build_styles():
    base = getSampleStyleSheet()

    styles = {
        "title": ParagraphStyle("title",
            fontSize=22, leading=28, textColor=COLOR_TITLE,
            fontName="Helvetica-Bold", spaceAfter=6, alignment=TA_CENTER),

        "subtitle": ParagraphStyle("subtitle",
            fontSize=11, leading=14, textColor=colors.HexColor("#555555"),
            fontName="Helvetica", spaceAfter=4, alignment=TA_CENTER),

        "h2": ParagraphStyle("h2",
            fontSize=15, leading=20, textColor=COLOR_H2,
            fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6,
            borderPad=(0, 0, 2, 0)),

        "h3": ParagraphStyle("h3",
            fontSize=12, leading=16, textColor=COLOR_H3,
            fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4),

        "h4": ParagraphStyle("h4",
            fontSize=11, leading=14, textColor=COLOR_H4,
            fontName="Helvetica-BoldOblique", spaceBefore=8, spaceAfter=3),

        "body": ParagraphStyle("body",
            fontSize=9.5, leading=14, textColor=colors.HexColor("#222222"),
            fontName="Helvetica", spaceAfter=5, alignment=TA_JUSTIFY),

        "bullet": ParagraphStyle("bullet",
            fontSize=9.5, leading=13, textColor=colors.HexColor("#222222"),
            fontName="Helvetica", spaceAfter=2, leftIndent=12,
            bulletIndent=2, bulletFontName="Helvetica", bulletFontSize=9.5),

        "bullet2": ParagraphStyle("bullet2",
            fontSize=9, leading=13, textColor=colors.HexColor("#333333"),
            fontName="Helvetica", spaceAfter=2, leftIndent=24,
            bulletIndent=14),

        "code": ParagraphStyle("code",
            fontSize=7.5, leading=11, fontName="Courier",
            textColor=colors.HexColor("#2c2c2c"),
            backColor=COLOR_CODE_BG, borderColor=COLOR_CODE_BORDER,
            borderWidth=0.5, borderPad=4, spaceAfter=6),

        "toc_title": ParagraphStyle("toc_title",
            fontSize=14, leading=18, textColor=COLOR_H2,
            fontName="Helvetica-Bold", spaceAfter=8),

        "toc_item": ParagraphStyle("toc_item",
            fontSize=9.5, leading=14, textColor=colors.HexColor("#333333"),
            fontName="Helvetica", leftIndent=0, spaceAfter=2),
    }
    return styles


# ── Helper: escape XML special chars ─────────────────────────────────────────

def esc(text: str) -> str:
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;"))

# ── Inline formatting ─────────────────────────────────────────────────────────

def inline_fmt(text: str) -> str:
    """Convert inline markdown to ReportLab XML.
    Process code spans first (protect them), then apply other formatting.
    """
    # Step 1: extract code spans, replace with placeholders
    code_spans = []
    def replace_code(m):
        inner = m.group(1).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        placeholder = f"\x00CODE{len(code_spans)}\x00"
        code_spans.append(f'<font name="Courier" size="8">{inner}</font>')
        return placeholder
    text_proc = re.sub(r"`(.+?)`", replace_code, text)

    # Step 2: escape remaining XML
    t = esc(text_proc)

    # Step 3: apply other inline formatting
    # Bold+italic: ***text***
    t = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", t)
    # Bold: **text**
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    # Italic: *text*
    t = re.sub(r"\*([^*]+?)\*", r"<i>\1</i>", t)
    # Links: [text](url) — keep link text only
    t = re.sub(r"\[(.+?)\]\(https?://[^\)]+\)", r'<u>\1</u>', t)
    # Strikethrough: ~~text~~
    t = re.sub(r"~~(.+?)~~", r"<strike>\1</strike>", t)

    # Step 4: restore code spans (already escaped + wrapped)
    for idx, span in enumerate(code_spans):
        t = t.replace(f"\x00CODE{idx}\x00", span)

    return t


# ── Table rendering ───────────────────────────────────────────────────────────

def render_table(rows: list, styles_map: dict) -> Table:
    """Render a list of row-lists (strings) as a styled ReportLab Table."""
    cell_style = ParagraphStyle("cell",
        fontSize=8.5, leading=12, fontName="Helvetica",
        textColor=colors.HexColor("#222222"), wordWrap="CJK")
    head_style = ParagraphStyle("head",
        fontSize=8.5, leading=12, fontName="Helvetica-Bold",
        textColor=colors.white, wordWrap="CJK")

    data = []
    for i, row in enumerate(rows):
        style = head_style if i == 0 else cell_style
        data.append([Paragraph(inline_fmt(cell.strip()), style) for cell in row])

    col_count = max(len(r) for r in data)
    usable_w = PAGE_W - 2 * MARGIN
    col_w = usable_w / col_count

    t = Table(data, colWidths=[col_w] * col_count, repeatRows=1)
    ts = TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_TABLE_HEAD),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        # Alternating rows
        *[("BACKGROUND", (0, j), (-1, j), COLOR_TABLE_ALT)
          for j in range(2, len(data), 2)],
        # Grid
        ("GRID",        (0, 0), (-1, -1), 0.5, COLOR_RULE),
        ("ROWBACKGROUND", (0, 1), (-1, 1), colors.white),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ])
    t.setStyle(ts)
    return t


# ── Markdown parser → ReportLab story ────────────────────────────────────────

def parse_markdown(md_text: str, styles: dict) -> list:
    story = []
    lines = md_text.splitlines()
    i = 0
    first_h1_done = False

    while i < len(lines):
        line = lines[i]

        # --- Code block ---
        if line.strip().startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # consume closing ```
            code_text = "\n".join(code_lines)
            # Truncate very long code blocks
            if len(code_lines) > 60:
                code_lines = code_lines[:60]
                code_lines.append("  ... [truncated for brevity]")
                code_text = "\n".join(code_lines)
            # Escape for XML
            code_esc = code_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Preformatted(code_esc, styles["code"]))
            story.append(Spacer(1, 3))
            continue

        # --- Horizontal rule ---
        if re.match(r"^-{3,}$", line.strip()) or re.match(r"^\*{3,}$", line.strip()):
            story.append(HRFlowable(width="100%", thickness=0.5,
                                    color=COLOR_RULE, spaceAfter=6, spaceBefore=6))
            i += 1
            continue

        # --- H1 ---
        if line.startswith("# ") and not line.startswith("## "):
            text = line[2:].strip()
            if not first_h1_done:
                story.append(Spacer(1, 6))
                story.append(Paragraph(esc(text), styles["title"]))
                first_h1_done = True
            else:
                story.append(PageBreak())
                story.append(Paragraph(esc(text), styles["title"]))
            i += 1
            continue

        # --- H2 ---
        if line.startswith("## "):
            text = line[3:].strip()
            story.append(Spacer(1, 4))
            story.append(Paragraph(inline_fmt(text), styles["h2"]))
            story.append(HRFlowable(width="100%", thickness=1,
                                    color=COLOR_H3, spaceAfter=4))
            i += 1
            continue

        # --- H3 ---
        if line.startswith("### "):
            text = line[4:].strip()
            story.append(Paragraph(inline_fmt(text), styles["h3"]))
            i += 1
            continue

        # --- H4 ---
        if line.startswith("#### "):
            text = line[5:].strip()
            story.append(Paragraph(inline_fmt(text), styles["h4"]))
            i += 1
            continue

        # --- Table ---
        if "|" in line and i + 1 < len(lines) and re.match(r"^\|?[\s\-|:]+\|?$", lines[i + 1]):
            table_rows = []
            # Parse header
            header_cells = [c.strip() for c in line.strip().strip("|").split("|")]
            table_rows.append(header_cells)
            i += 2  # skip separator row
            while i < len(lines) and "|" in lines[i]:
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                table_rows.append(cells)
                i += 1
            try:
                story.append(render_table(table_rows, styles))
                story.append(Spacer(1, 6))
            except Exception as e:
                # Fallback: render as text
                for row in table_rows:
                    story.append(Paragraph("  ".join(row), styles["body"]))
            continue

        # --- Bullet list (unordered) ---
        if re.match(r"^[-*+]\s+", line):
            text = re.sub(r"^[-*+]\s+", "", line)
            # Check for sub-bullets on next lines
            bullet_items = [(1, text)]
            i += 1
            while i < len(lines) and re.match(r"^  +[-*+]\s+", lines[i]):
                sub = re.sub(r"^  +[-*+]\s+", "", lines[i])
                bullet_items.append((2, sub))
                i += 1
            for level, btext in bullet_items:
                sty = styles["bullet"] if level == 1 else styles["bullet2"]
                prefix = "•" if level == 1 else "◦"
                story.append(Paragraph(f"{prefix}  {inline_fmt(btext)}", sty))
            continue

        # --- Numbered list ---
        if re.match(r"^\d+\.\s+", line):
            text = re.sub(r"^\d+\.\s+", "", line)
            num = re.match(r"^(\d+)\.", line).group(1)
            story.append(Paragraph(f"{num}.  {inline_fmt(text)}", styles["bullet"]))
            i += 1
            continue

        # --- Blank line ---
        if line.strip() == "":
            story.append(Spacer(1, 4))
            i += 1
            continue

        # --- Normal paragraph ---
        stripped = line.strip()
        if stripped:
            story.append(Paragraph(inline_fmt(stripped), styles["body"]))
        i += 1

    return story


# ── Header/footer ─────────────────────────────────────────────────────────────

def make_header_footer(canvas, doc):
    canvas.saveState()
    w, h = doc.pagesize

    # Header bar
    canvas.setFillColor(COLOR_TITLE)
    canvas.rect(MARGIN, h - 12*mm, w - 2*MARGIN, 7*mm, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(colors.white)
    canvas.drawString(MARGIN + 3*mm, h - 8*mm,
                      "skill-security-auditor — Development Report 2026-04-09")
    canvas.drawRightString(w - MARGIN - 3*mm, h - 8*mm,
                           "github.com/WilliamHE-cyber/claude-skills")

    # Footer
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawCentredString(w / 2, 8*mm, f"Page {doc.page}")
    canvas.drawString(MARGIN, 8*mm, "Confidential — Internal Development Record")
    canvas.drawRightString(w - MARGIN, 8*mm, "© WilliamHE-cyber 2026")

    # Footer line
    canvas.setStrokeColor(COLOR_RULE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 12*mm, w - MARGIN, 12*mm)

    canvas.restoreState()


# ── Cover page ────────────────────────────────────────────────────────────────

def make_cover(styles: dict) -> list:
    elements = []
    elements.append(Spacer(1, 40*mm))

    # Title block
    title_style = ParagraphStyle("cover_title",
        fontSize=28, leading=34, textColor=COLOR_TITLE,
        fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=8)
    subtitle_style = ParagraphStyle("cover_sub",
        fontSize=14, leading=18, textColor=COLOR_H3,
        fontName="Helvetica", alignment=TA_CENTER, spaceAfter=6)
    meta_style = ParagraphStyle("cover_meta",
        fontSize=10, leading=14, textColor=colors.HexColor("#555555"),
        fontName="Helvetica", alignment=TA_CENTER, spaceAfter=4)

    elements.append(Paragraph("skill-security-auditor", title_style))
    elements.append(Paragraph("Full Development Report", subtitle_style))
    elements.append(Spacer(1, 8*mm))
    elements.append(HRFlowable(width="60%", thickness=2, color=COLOR_H3,
                                hAlign="CENTER", spaceAfter=8*mm))

    metrics = [
        ("Report Date", "2026-04-09"),
        ("Report Version", "1.0"),
        ("Author", "WilliamHE-cyber"),
        ("Repository", "github.com/WilliamHE-cyber/claude-skills"),
        ("Skill Version", "0.2.3"),
        ("Benchmark Accuracy", "97.8%  (89 skills)"),
        ("False Positive Rate", "0.0%"),
        ("Gate-level F1", "1.00"),
        ("Pull Requests Merged", "7"),
    ]

    meta_data = [[Paragraph(f"<b>{k}</b>", meta_style),
                  Paragraph(v, meta_style)] for k, v in metrics]
    meta_table = Table(meta_data, colWidths=[60*mm, 80*mm])
    meta_table.setStyle(TableStyle([
        ("ALIGN",    (0, 0), (0, -1), "RIGHT"),
        ("ALIGN",    (1, 0), (1, -1), "LEFT"),
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 20*mm))

    # Abstract
    abstract_style = ParagraphStyle("abstract",
        fontSize=9.5, leading=14, textColor=colors.HexColor("#333333"),
        fontName="Helvetica-Oblique", alignment=TA_JUSTIFY,
        borderPad=8, borderColor=COLOR_RULE, borderWidth=0.5,
        backColor=COLOR_TABLE_ALT, leftIndent=10, rightIndent=10)
    elements.append(Paragraph(
        "This report documents the complete development lifecycle of skill-security-auditor, "
        "a self-iterating security analysis system for Claude Code skills. Across seven merged "
        "pull requests and four self-improvement cycles, the project evolved from a passive static "
        "scanner into a four-layer active security gatekeeper achieving 97.8% classification "
        "accuracy, 0.0% false positive rate, and gate-level F1 of 1.00 across 89 skills.",
        abstract_style))

    elements.append(PageBreak())
    return elements


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    src = Path("/Users/net2global/claude-skills-repo/skill-security-auditor/reports/development-report-2026-04-09.md")
    out = src.with_suffix(".pdf")

    print(f"Reading {src} ...")
    md_text = src.read_text(encoding="utf-8")

    print("Building PDF story ...")
    styles = build_styles()

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=18*mm,
        bottomMargin=18*mm,
        title="skill-security-auditor Development Report",
        author="WilliamHE-cyber",
        subject="Security audit system development documentation",
        creator="Claude Code + reportlab",
    )

    story = []
    story += make_cover(styles)
    story += parse_markdown(md_text, styles)

    print(f"Writing {out} ...")
    doc.build(story, onFirstPage=make_header_footer, onLaterPages=make_header_footer)
    print(f"✅  PDF generated: {out}")
    print(f"    Size: {out.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
