#!/usr/bin/env python3
"""Generate docs/ARCHITECTURE.pdf as-it-is from docs/ARCHITECTURE.md.

Usage:
    python3 scripts/generate_architecture_pdf.py
    python3 scripts/generate_architecture_pdf.py --in docs/ARCHITECTURE.md --out docs/ARCHITECTURE.pdf

What it does:
  - Reads the markdown file verbatim (no content edits).
  - Renders headings, paragraphs, bullets, tables, blockquotes to PDF.
  - Renders every ```mermaid block TWICE so nothing is lost:
      1. a visual diagram image (matplotlib) with the SAME boxes/arrows/labels,
      2. the EXACT mermaid source as monospaced text below it.
  - Output is a single self-contained PDF with header/footer + page numbers.

Requires: reportlab, matplotlib (pip install reportlab matplotlib).
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
import tempfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# ---------------------------------------------------------------- files
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_IN = os.path.join(ROOT, "docs", "ARCHITECTURE.md")
DEFAULT_OUT = os.path.join(ROOT, "docs", "ARCHITECTURE.pdf")

BRAND = "#1E6FF5"
INK = "#0F172A"
MUTED = "#475569"
CODE_BG = "#F1F5F9"
BOX_BG = "#EFF6FF"
BOX_EDGE = "#1E6FF5"

# ---------------------------------------------------------------- matplotlib helpers
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["font.size"] = 8


def _box(ax, xy, w, h, text, fontsize=8, bg=BOX_BG, edge=BOX_EDGE):
    x, y = xy
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.05",
        facecolor=bg, edgecolor=edge, linewidth=1.2,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color="#0F172A", wrap=True)


def _arrow(ax, x1, y1, x2, y2, label=""):
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle="->", color="#334155", lw=1.2,
                        shrinkA=2, shrinkB=4),
    )
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.03, label,
                ha="center", va="bottom", fontsize=7, color="#334155",
                bbox=dict(facecolor="white", edgecolor="none", pad=1.0))


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def diagram_layers(path):
    """flowchart LR layers: browser -> frontend -> backend -> AI -> services -> EHR + DB branch."""
    fig, ax = plt.subplots(figsize=(8.5, 1.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 2)
    ax.axis("off")
    nodes = ["Patient\nbrowser", "Frontend", "Backend API",
             "AI:\nLangGraph+MCP", "App services", "Mock EHR"]
    n = len(nodes)
    w, h, gap = 1.35, 0.8, 0.18
    x0 = (10 - (n * w + (n - 1) * gap)) / 2
    y = 0.9
    xs = []
    for i, t in enumerate(nodes):
        x = x0 + i * (w + gap)
        xs.append(x)
        _box(ax, (x, y), w, h, t)
        if i:
            _arrow(ax, xs[i - 1] + w, y + h / 2, x, y + h / 2)
    # DB branch below backend
    _box(ax, (xs[2], 0.05), w, 0.55, "Postgres", fontsize=8, bg="#F8FAFC", edge="#64748B")
    _arrow(ax, xs[2] + w / 2, y, xs[2] + w / 2, 0.6)
    ax.set_title("Layers — same boxes as mermaid block §1", fontsize=9, color=MUTED)
    return _save(fig, path)


def diagram_sequence(path, title, participants, messages):
    """Generic sequence diagram: participants top, dashed lifelines, labeled arrows."""
    fig, ax = plt.subplots(figsize=(8.5, 1.2 + 0.45 * len(messages)))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 1.2 + 0.45 * len(messages) + 0.8)
    ax.axis("off")
    n = len(participants)
    xs = [1 + i * (8 / max(n - 1, 1)) for i in range(n)]
    top = ax.get_ylim()[1] - 0.5
    for x, p in zip(xs, participants):
        _box(ax, (x - 0.8, top - 0.5), 1.6, 0.5, p, fontsize=8)
        ax.plot([x, x], [0.3, top - 0.5], color="#94A3B8",
                linestyle=(0, (4, 3)), linewidth=1)
    idx = {p: x for p, x in zip(participants, xs)}
    y = top - 1.0
    for src, dst, label, dashed in messages:
        x1, x2 = idx[src], idx[dst]
        ls = (0, (4, 3)) if dashed else "-"
        if x1 == x2:  # self arrow: small loop
            ax.annotate("", xy=(x1 + 0.5, y - 0.12), xytext=(x1 + 0.5, y + 0.12),
                        arrowprops=dict(arrowstyle="->", color="#334155",
                                        linestyle=ls, lw=1.2))
            ax.text(x1 + 0.6, y, label, va="center", fontsize=7.5, color="#334155")
        else:
            ax.annotate("", xy=(x2, y), xytext=(x1, y),
                        arrowprops=dict(arrowstyle="->", color="#334155",
                                        linestyle=ls, lw=1.2))
            ax.text((x1 + x2) / 2, y + 0.08, label, ha="center",
                    fontsize=7.5, color="#334155",
                    bbox=dict(facecolor="white", edgecolor="none", pad=1.0))
        y -= 0.45
    ax.set_title(title, fontsize=9, color=MUTED)
    return _save(fig, path)


def diagram_ai(path):
    fig, ax = plt.subplots(figsize=(5.5, 4.2))
    ax.set_xlim(0, 6)
    ax.set_ylim(0, 6)
    ax.axis("off")
    steps = ["Understand\n+ safety", "Plan with tools",
             "Use 3 tools:\nfind doctors,\ncheck slots, book",
             "Reply + cards", "Remember"]
    w, h, x = 3.0, 0.7, 1.5
    ys = [4.8, 3.8, 2.8, 1.8, 0.8]
    for i, (t, y) in enumerate(zip(steps, ys)):
        _box(ax, (x, y), w, h, t)
        if i:
            _arrow(ax, x + w / 2, ys[i - 1], x + w / 2, y + h)
    ax.set_title("AI LangGraph+MCP — same 5 boxes as mermaid block §5",
                 fontsize=9, color=MUTED)
    return _save(fig, path)


def diagram_small_lr(path, title, nodes, fontsize=8):
    n = len(nodes)
    # auto-fit: keep all boxes inside 0..10 axis
    gap = 0.3 if n <= 4 else 0.2
    w = min(2.2, (10 - 1.0 - (n - 1) * gap) / n)
    h = 0.8
    fig, ax = plt.subplots(figsize=(8.5, 1.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 2)
    ax.axis("off")
    x0 = (10 - (n * w + (n - 1) * gap)) / 2
    y = 0.7
    xs = []
    for i, t in enumerate(nodes):
        x = x0 + i * (w + gap)
        xs.append(x)
        _box(ax, (x, y), w, h, t, fontsize=fontsize)
        if i:
            _arrow(ax, xs[i - 1] + w, y + h / 2, x, y + h / 2)
    ax.set_title(title, fontsize=9, color=MUTED)
    return _save(fig, path)


def diagram_state(path):
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6.4)
    ax.axis("off")
    # spread out to avoid arrow soup; reconciliation on its own row
    pos = {
        "pending": (0.5, 4.9),
        "confirmed": (3.9, 4.9),
        "completed": (7.3, 4.9),
        "rescheduled": (3.9, 3.6),
        "failed": (0.5, 3.6),
        "cancelled": (7.3, 3.6),
        "reconciliation_required": (0.5, 2.0),
    }
    w, h = 2.0, 0.6
    for s, (x, y) in pos.items():
        label = s.replace("reconciliation_required", "reconciliation\nrequired")
        _box(ax, (x, y), w, h, label, fontsize=7.5,
             bg="#FFF7ED" if s == "reconciliation_required" else BOX_BG,
             edge="#EA580C" if s == "reconciliation_required" else BOX_EDGE)
    cx = lambda s: pos[s][0] + w / 2
    cy = lambda s: pos[s][1] + h / 2
    edges = [
        ("pending", "confirmed", "verified"),
        ("pending", "failed", "EHR failed"),
        ("confirmed", "rescheduled", "revalidated"),
        ("rescheduled", "confirmed", "verified"),
        ("confirmed", "cancelled", ""),
        ("confirmed", "completed", ""),
        ("pending", "reconciliation_required", "unknown"),
        ("reconciliation_required", "confirmed", "recovered"),
        ("reconciliation_required", "cancelled", ""),
        ("reconciliation_required", "failed", ""),
    ]
    for a, b, lab in edges:
        _arrow(ax, cx(a), cy(a), cx(b), cy(b), lab)
    ax.set_title("Appointment states — same transitions as mermaid block §8",
                 fontsize=9, color=MUTED)
    return _save(fig, path)


def diagram_docker(path):
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    ax.set_xlim(0, 6)
    ax.set_ylim(0, 5)
    ax.axis("off")
    _box(ax, (1.7, 4.0), 2.6, 0.6, "bridge network", fontsize=8,
         bg="#F8FAFC", edge="#64748B")
    _box(ax, (0.4, 2.8), 2.2, 0.7, "Frontend :80", fontsize=8)
    _box(ax, (3.4, 2.8), 2.2, 0.7, "Backend :8000", fontsize=8)
    _box(ax, (0.4, 1.4), 2.2, 0.7, "Postgres :5432", fontsize=8,
         bg="#F8FAFC", edge="#64748B")
    _box(ax, (3.4, 1.4), 2.2, 0.7, "Mock EHR :8001", fontsize=8)
    _arrow(ax, 2.6, 3.15, 4.0, 3.15)
    _arrow(ax, 4.5, 2.8, 4.5, 2.1)
    _arrow(ax, 2.5, 2.8, 1.5, 2.1)
    ax.set_title("Docker topology — same 4 services as mermaid block §12",
                 fontsize=9, color=MUTED)
    return _save(fig, path)


# ---------------------------------------------------------------- markdown -> reportlab
def md_inline(text):
    """Convert a small markdown subset to reportlab paragraph markup."""
    t = html.escape(text, quote=False)
    t = t.replace("&#x27;", "'").replace("&quot;", '"')
    # inline code `x` first (protect inner stars)
    t = re.sub(r"`([^`]+?)`",
               r'<font face="DejaVuSansMono" size="8" backColor="#F1F5F9">\1</font>', t)
    # bold **x**
    t = re.sub(r"\*\*([^*]+?)\*\*", r"<b>\1</b>", t)
    # arrows etc render fine with DejaVu Sans; keep as-is
    return t


def build_pdf(md_path, pdf_path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (HRFlowable, Image, PageBreak, Paragraph,
                                    Preformatted, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)

    # Unicode-capable fonts (arrows like → render correctly)
    for name, file in [
        ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("DejaVuSans-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("DejaVuSansMono", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    ]:
        try:
            pdfmetrics.registerFont(TTFont(name, file))
        except Exception as e:
            print(f"warn: font {name} not registered: {e}", file=sys.stderr)

    with open(md_path, encoding="utf-8") as f:
        md = f.read()

    # Split markdown into blocks, keeping mermaid fences + tables together
    lines = md.splitlines()
    blocks: list[tuple[str, object]] = []  # (kind, payload)
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```mermaid"):
            j = i + 1
            src = []
            while j < len(lines) and lines[j].strip() != "```":
                src.append(lines[j])
                j += 1
            blocks.append(("mermaid", "\n".join(src)))
            i = j + 1
            continue
        if ln.strip().startswith("```"):
            j = i + 1
            src = []
            while j < len(lines) and lines[j].strip() != "```":
                src.append(lines[j])
                j += 1
            blocks.append(("code", "\n".join(src)))
            i = j + 1
            continue
        if re.match(r"^\s*\|.*\|\s*$", ln):
            tbl = []
            while i < len(lines) and re.match(r"^\s*\|.*\|\s*$", lines[i]):
                tbl.append(lines[i])
                i += 1
            blocks.append(("table", tbl))
            continue
        if ln.startswith("# "):
            blocks.append(("h1", ln[2:].strip()))
        elif ln.startswith("## "):
            blocks.append(("h2", ln[3:].strip()))
        elif ln.startswith("### "):
            blocks.append(("h3", ln[4:].strip()))
        elif ln.strip().startswith("> "):
            blocks.append(("quote", ln.strip()[2:]))
        elif re.match(r"^\s*-\s+", ln):
            items = []
            while i < len(lines) and re.match(r"^\s*-\s+", lines[i]):
                items.append(re.sub(r"^\s*-\s+", "", lines[i]))
                i += 1
            blocks.append(("bullets", items))
            continue
        elif ln.strip() == "":
            blocks.append(("blank", ""))
        else:
            # numbered list item like "1. x" -> treat as bullet
            m = re.match(r"^\s*\d+\.\s+(.*)", ln)
            if m:
                blocks.append(("bullets", [ln.strip()]))
            else:
                blocks.append(("para", ln.strip()))
        i += 1

    styles = getSampleStyleSheet()
    s_title = ParagraphStyle("Title2", parent=styles["Title"],
                             fontName="DejaVuSans-Bold", fontSize=20,
                             textColor=colors.HexColor(BRAND), spaceAfter=4)
    s_h2 = ParagraphStyle("H2", parent=styles["Heading2"],
                          fontName="DejaVuSans-Bold", fontSize=13,
                          textColor=colors.HexColor(BRAND),
                          spaceBefore=14, spaceAfter=6,
                          keepWithNext=True)
    s_h3 = ParagraphStyle("H3", parent=styles["Heading3"],
                          fontName="DejaVuSans-Bold", fontSize=11,
                          textColor=colors.HexColor(INK),
                          spaceBefore=8, spaceAfter=4, keepWithNext=True)
    s_body = ParagraphStyle("Body", parent=styles["Normal"],
                            fontName="DejaVuSans", fontSize=9.2,
                            leading=13.5, textColor=colors.HexColor(INK),
                            spaceAfter=5)
    s_bullet = ParagraphStyle("Bullet", parent=s_body, leftIndent=14,
                              firstLineIndent=0, bulletIndent=6, spaceAfter=3)
    s_quote = ParagraphStyle("Quote", parent=s_body, leftIndent=12,
                             textColor=colors.HexColor(MUTED),
                             borderPadding=(6, 6, 6),
                             spaceAfter=6)
    s_code = ParagraphStyle("Code", parent=styles["Code"],
                            fontName="DejaVuSansMono", fontSize=7.2,
                            leading=10, textColor=colors.HexColor(INK))
    s_caption = ParagraphStyle("Caption", parent=styles["Normal"],
                               fontName="DejaVuSans", fontSize=7.5,
                               textColor=colors.HexColor(MUTED),
                               spaceBefore=2, spaceAfter=8)

    FIG_TITLES = [
        "Layers (browser to Mock EHR)",
        "Request flow (role-scoped queries)",
        "Booking verify-before-confirm",
        "Failure recovery (probe, no duplicates)",
        "AI LangGraph + MCP",
        "Scheduling engine",
        "Appointment states",
        "Observability (one correlation ID)",
        "Voice v1",
        "Docker topology",
    ]
    tmpdir = tempfile.mkdtemp(prefix="arch_pdf_")
    story = []
    mermaid_idx = 0
    img_paths: list[str] = []

    def add_diagram(kind_key):
        nonlocal mermaid_idx
        mermaid_idx += 1
        out = os.path.join(tmpdir, f"diagram_{mermaid_idx:02d}.png")
        box_w, box_h = 170 * mm, 62 * mm
        if kind_key == 1:
            diagram_layers(out)
            box_w, box_h = 170 * mm, 48 * mm
        elif kind_key == 2:
            diagram_sequence(
                out, "Request flow — same 5 messages as mermaid block §2",
                ["User", "Frontend", "Backend API", "Database"],
                [("User", "Frontend", "login / click / chat", False),
                 ("Frontend", "Backend API", "API call with token", False),
                 ("Backend API", "Database", "scoped query by role", False),
                 ("Database", "Backend API", "only allowed rows", True),
                 ("Backend API", "Frontend", "JSON + cards", False)])
            box_w, box_h = 170 * mm, 78 * mm
        elif kind_key == 3:
            diagram_sequence(
                out, "Booking verify-before-confirm — same 4 steps as mermaid block §3",
                ["App", "EHR"],
                [("App", "EHR", "create appointment", False),
                 ("App", "EHR", "read it back (verify)", False),
                 ("EHR", "App", "matched", True),
                 ("App", "App", "sync + confirm + notify", False)])
            box_w, box_h = 170 * mm, 70 * mm
        elif kind_key == 4:
            diagram_sequence(
                out, "Failure recovery — same probe branch as mermaid block §4",
                ["App", "EHR"],
                [("App", "EHR", "create (timeout!)", False),
                 ("App", "EHR", "probe by idempotency key", False),
                 ("EHR", "App", "found → sync, no new write", True),
                  ("EHR", "App", "not found → reconcile + escalate", True)])
            box_w, box_h = 170 * mm, 70 * mm
        elif kind_key == 5:
            diagram_ai(out)
            box_w, box_h = 100 * mm, 105 * mm
        elif kind_key == 6:
            diagram_small_lr(out, "Scheduling — same 3 boxes as mermaid block §7",
                             ["Calendar + rules", "Engine", "Free slots"])
            box_w, box_h = 170 * mm, 42 * mm
        elif kind_key == 7:
            diagram_state(out)
            box_w, box_h = 170 * mm, 100 * mm
        elif kind_key == 8:
            diagram_small_lr(out, "Observability — same chain as mermaid block §10",
                             ["Chat", "Booking", "EHR\nop+verify",
                              "Workflow\n+notify", "Dashboards"],
                             fontsize=7)
            box_w, box_h = 170 * mm, 42 * mm
        elif kind_key == 9:
            diagram_small_lr(out, "Voice — same 4 boxes as mermaid block §11",
                             ["Tap orb+speak", "Hear as text",
                              "Same AI graph", "Speak + cards"])
            box_w, box_h = 170 * mm, 42 * mm
        elif kind_key == 10:
            diagram_docker(out)
            box_w, box_h = 120 * mm, 68 * mm
        img_paths.append(out)
        story.append(Image(out, width=box_w, height=box_h,
                           kind="proportional"))
        title = FIG_TITLES[mermaid_idx - 1] if mermaid_idx <= len(FIG_TITLES) else f"diagram {mermaid_idx}"
        story.append(Paragraph(f"Figure {mermaid_idx} ({title}).", s_caption))

    mermaid_counter = 0
    for kind, payload in blocks:
        if kind == "h1":
            story.append(Paragraph(md_inline(payload), s_title))
            story.append(HRFlowable(width="100%", thickness=1,
                                    color=colors.HexColor(BRAND),
                                    spaceAfter=6))
        elif kind == "h2":
            story.append(Paragraph(md_inline(payload), s_h2))
        elif kind == "h3":
            story.append(Paragraph(md_inline(payload), s_h3))
        elif kind == "para":
            story.append(Paragraph(md_inline(payload), s_body))
        elif kind == "quote":
            story.append(Paragraph(md_inline(payload), s_quote))
        elif kind == "bullets":
            for it in payload:
                story.append(Paragraph(md_inline("•  " + it), s_bullet,
                                       bulletText=""))
        elif kind == "table":
            rows = []
            for r_i, r in enumerate(payload):
                cells = [c.strip() for c in r.strip().strip("|").split("|")]
                if re.match(r"^\s*:?-{2,}:?\s*$", cells[0]):
                    continue  # separator row
                rows.append([Paragraph(md_inline(c), s_body) for c in cells])
            if rows:
                col_w = [(170 * mm) / len(rows[0])] * len(rows[0])
                t = Table(rows, colWidths=col_w, repeatRows=1)
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [colors.white, colors.HexColor("#F8FAFC")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]))
                story.append(t)
                story.append(Spacer(1, 6))
        elif kind == "code":
            story.append(Preformatted(payload, s_code,
                                      maxLineLength=100))
            story.append(Spacer(1, 6))
        elif kind == "mermaid":
            # Rendered diagram image only — no mermaid code in the PDF.
            mermaid_counter += 1
            add_diagram(mermaid_counter)
            story.append(Spacer(1, 8))
        elif kind == "blank":
            pass

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("DejaVuSans", 7)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(15 * mm, 282 * mm,
                          "MediConnect — Architecture (generated from docs/ARCHITECTURE.md)")
        canvas.drawRightString(195 * mm, 282 * mm,
                               os.path.basename(md_path))
        canvas.drawCentredString(105 * mm, 12 * mm,
                                 f"Page {doc.page}")
        canvas.setStrokeColor(colors.HexColor("#E2E8F0"))
        canvas.setLineWidth(0.5)
        canvas.line(15 * mm, 280 * mm, 195 * mm, 280 * mm)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=22 * mm, bottomMargin=16 * mm,
        title="MediConnect Architecture",
        author="MediConnect",
        subject="Generated as-is from docs/ARCHITECTURE.md (markdown + mermaid)",
    )
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"wrote {pdf_path} ({mermaid_counter} mermaid blocks, "
          f"{len(img_paths)} diagrams)")
    return pdf_path


def main():
    ap = argparse.ArgumentParser(
        description="Generate ARCHITECTURE.pdf as-is from ARCHITECTURE.md")
    ap.add_argument("--in", dest="inp", default=DEFAULT_IN)
    ap.add_argument("--out", dest="out", default=DEFAULT_OUT)
    args = ap.parse_args()
    if not os.path.exists(args.inp):
        print(f"input not found: {args.inp}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    build_pdf(args.inp, args.out)


if __name__ == "__main__":
    main()
