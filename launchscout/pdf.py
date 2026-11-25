"""Converts the Markdown report into a clean, printable PDF."""
import io
import re
from pathlib import Path

import markdown
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xhtml2pdf import default, pisa

from launchscout.config import OUTPUT_DIR

PDF_PATH = OUTPUT_DIR / "report.pdf"

# A Unicode TTF font (regular, bold) so dashes, quotes and the rupee sign render.
# Registered with ReportLab directly; falls back to Helvetica if none exist.
_FONT_CANDIDATES = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]


def _register_font() -> str | None:
    for regular, bold in _FONT_CANDIDATES:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("ReportFont", regular))
            pdfmetrics.registerFont(TTFont("ReportFontBold", bold))
            addMapping("ReportFont", 0, 0, "ReportFont")
            addMapping("ReportFont", 1, 0, "ReportFontBold")
            addMapping("ReportFont", 0, 1, "ReportFont")
            addMapping("ReportFont", 1, 1, "ReportFontBold")
            default.DEFAULT_FONT["reportfont"] = "ReportFont"
            return "ReportFont"
    return None


_FONT = _register_font()

_CSS = """
@page { size: A4; margin: 1.6cm 1.4cm; }
body { font-family: %(font)s; font-size: 9.5pt; line-height: 1.4; color: #222; }
h1 { font-size: 17pt; color: #7a1018; border-bottom: 2px solid #7a1018; padding-bottom: 4pt; }
h2 { font-size: 12.5pt; color: #7a1018; margin-top: 14pt; }
table { width: 100%%; border: 0.5pt solid #bbb; margin: 6pt 0; }
th { background-color: #7a1018; color: #fff; padding: 4pt; text-align: left; font-size: 8.5pt; }
td { padding: 4pt; border: 0.5pt solid #ddd; vertical-align: top; font-size: 8.5pt; }
a { color: #1a5fb4; text-decoration: none; }
li { margin-bottom: 2pt; }
blockquote { color: #444; border-left: 3pt solid #7a1018; padding-left: 6pt; }
"""


def _clean(md_text: str) -> str:
    if not _FONT:
        md_text = md_text.replace("₹", "Rs ")  # Helvetica has no rupee sign
    # Drop emoji / symbols outside the Basic Multilingual Plane (PDF fonts lack them)
    md_text = re.sub(r"[\U00010000-\U0010FFFF]", "", md_text)
    # Make bare URLs clickable
    md_text = re.sub(r"(?<![(\[<\"'])(https?://[^\s)<>\]]+)", r"<\1>", md_text)
    return _separate_blocks(md_text)


_LIST_ITEM = re.compile(r"^\s*([-*+]|\d+\.)\s")
_SOURCE_LINE = re.compile(r"^\s*\[\d+\]")


def _separate_blocks(md_text: str) -> str:
    """LLM Markdown often omits the blank lines Markdown needs. Add them so that
    lists right after a paragraph render as lists and '[n] url' source lines
    stay on separate lines."""
    out: list[str] = []
    for line in md_text.splitlines():
        prev = out[-1] if out else ""
        starts_list = bool(_LIST_ITEM.match(line))
        if prev.strip() and (
            (starts_list and not _LIST_ITEM.match(prev) and not prev.startswith(" "))
            or _SOURCE_LINE.match(line)
        ):
            out.append("")
        out.append(line)
    return "\n".join(out)


def _shorten_link_text(html: str, limit: int = 70) -> str:
    """Long URLs don't wrap in PDF; keep the full href but shorten what is shown."""
    def repl(m: re.Match) -> str:
        href, text = m.group(1), m.group(2)
        if text.startswith("http") and len(text) > limit:
            text = text[:limit] + "…"
        return f'<a href="{href}">{text}</a>'
    return re.sub(r'<a href="([^"]+)">([^<]+)</a>', repl, html)


def markdown_to_pdf(md_text: str) -> bytes:
    """Return the report rendered as PDF bytes."""
    body = _shorten_link_text(
        markdown.markdown(_clean(md_text), extensions=["tables", "sane_lists"]))
    html = (f"<html><head><meta charset='utf-8'><style>{_CSS % {'font': _FONT or 'Helvetica'}}"
            f"</style></head><body>{body}</body></html>")
    buf = io.BytesIO()
    result = pisa.CreatePDF(html, dest=buf, encoding="utf-8")
    if result.err:
        raise RuntimeError("PDF conversion failed")
    return buf.getvalue()


def save_pdf(md_text: str) -> Path:
    PDF_PATH.write_bytes(markdown_to_pdf(md_text))
    return PDF_PATH
