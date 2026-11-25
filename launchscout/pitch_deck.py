"""Stretch goal: a Pitch Deck agent that turns the report into 6 slides.

The agent returns structured data (a Pydantic model), and python-pptx renders
it into a real PowerPoint file, so the slide design stays consistent and the
LLM only decides what each slide says.
"""
import io
import json
import re

from crewai import Agent, Crew, Process, Task
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu, Pt
from pydantic import BaseModel, Field

from launchscout.config import OUTPUT_DIR, get_llm

DECK_PATH = OUTPUT_DIR / "pitch_deck.pptx"

SLIDE_PLAN = [
    "The problem: the customer's pain, from the complaints section",
    "The market today: the key competitors, their prices and channels",
    "The gap: what nobody is serving well, with evidence",
    "Our offer: the recommended positioning and price",
    "Why we win: our edge against each competitor weakness",
    "Launch plan: the 30-day plan as four weekly milestones, plus the ask",
]


class Slide(BaseModel):
    title: str = Field(description="Short slide title, max 8 words")
    bullets: list[str] = Field(description="3 to 5 bullets, each max 18 words")
    speaker_notes: str = Field(description="2-3 sentences the founder says aloud")


class PitchDeck(BaseModel):
    deck_title: str = Field(description="Business name or one-line idea")
    tagline: str = Field(description="The one-line positioning with price")
    slides: list[Slide] = Field(description="Exactly 6 slides in the planned order")


def pitch_deck_agent() -> Agent:
    return Agent(
        role="Pitch Deck Designer",
        goal="Turn a competitor report into a crisp 6-slide pitch deck a founder can "
             "present to investors or partners in five minutes.",
        backstory=(
            "You have built pitch decks for over a hundred early-stage startups. You "
            "know investors skim, so every slide makes one point, every bullet is "
            "short, and every number comes from the research, never invented."
        ),
        llm=get_llm(),
        allow_delegation=False,
        verbose=False,
    )


def pitch_deck_task(agent: Agent) -> Task:
    plan = "\n".join(f"{i}. {s}" for i, s in enumerate(SLIDE_PLAN, 1))
    return Task(
        description=(
            "Create a 6-slide pitch deck for '{business_idea}' in {city} from the "
            "competitor report below. Use only facts and numbers from the report; "
            "keep prices exactly as written. Slide plan:\n" + plan +
            "\n\nREPORT:\n{report}"
        ),
        expected_output=(
            "ONLY a JSON object, no other text, in exactly this shape:\n"
            '{"deck_title": "...", "tagline": "the positioning line with price", '
            '"slides": [{"title": "max 8 words", "bullets": ["3 to 5 bullets, '
            'each max 18 words"], "speaker_notes": "2-3 sentences"}]}\n'
            "with exactly 6 slides following the slide plan."
        ),
        agent=agent,
        # Not output_pydantic: DeepSeek does not support the JSON-schema
        # response_format it relies on, so we validate the JSON ourselves.
    )


def _parse_deck(raw: str) -> PitchDeck:
    """Pull the JSON object out of the model's answer and validate it."""
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        raise RuntimeError("The Pitch Deck agent did not return JSON")
    return PitchDeck.model_validate(json.loads(match.group(0)))


def generate_pitch_deck(report: str, inputs: dict) -> PitchDeck:
    """Run the Pitch Deck agent on a finished report."""
    agent = pitch_deck_agent()
    crew = Crew(agents=[agent], tasks=[pitch_deck_task(agent)],
                process=Process.sequential, verbose=False)
    result = crew.kickoff(inputs={**inputs, "report": report})
    deck = _parse_deck(result.raw)
    if len(deck.slides) < 6:
        raise RuntimeError(f"Expected 6 slides, got {len(deck.slides)}")
    deck.slides = deck.slides[:6]
    return deck


# ------------------------------------------------------------------ rendering
MAROON = RGBColor(0x7A, 0x10, 0x18)
DARK = RGBColor(0x22, 0x22, 0x22)
GREY = RGBColor(0x66, 0x66, 0x66)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
W, H = Emu(12192000), Emu(6858000)  # 16:9


def _rect(slide, x, y, w, h, color):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def _text(slide, x, y, w, h, text, size, color, bold=False):
    tf = slide.shapes.add_textbox(x, y, w, h).text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size, p.font.color.rgb, p.font.bold = Pt(size), color, bold
    return tf


def render_pptx(deck: PitchDeck, city: str) -> bytes:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    blank = prs.slide_layouts[6]
    margin = Emu(700000)

    # Title slide
    s = prs.slides.add_slide(blank)
    _rect(s, 0, 0, W, H, MAROON)
    _text(s, margin, Emu(1500000), W - 2 * margin, Emu(1800000), deck.deck_title, 40, WHITE, True)
    _text(s, margin, Emu(3700000), W - 2 * margin, Emu(1500000), deck.tagline, 20, WHITE)
    _text(s, margin, Emu(5800000), W - 2 * margin, Emu(500000),
          f"{city}  ·  Competitor research by LaunchScout", 12, WHITE)

    # Content slides
    for i, sl in enumerate(deck.slides, 1):
        s = prs.slides.add_slide(blank)
        _rect(s, 0, 0, Emu(180000), H, MAROON)
        _text(s, margin, Emu(450000), W - 2 * margin, Emu(500000), f"{i:02d}", 14, MAROON, True)
        _text(s, margin, Emu(800000), W - 2 * margin, Emu(900000), sl.title, 32, DARK, True)
        tf = s.shapes.add_textbox(margin, Emu(2000000), W - 2 * margin, Emu(4300000)).text_frame
        tf.word_wrap = True
        for j, bullet in enumerate(sl.bullets[:5]):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            p.text = "•  " + re.sub(r"\s*\[\d+\]", "", bullet)  # drop source markers
            p.font.size, p.font.color.rgb = Pt(20), DARK
            p.space_after = Pt(14)
        _text(s, margin, H - Emu(550000), W - 2 * margin, Emu(400000),
              deck.deck_title, 10, GREY)
        s.notes_slide.notes_text_frame.text = sl.speaker_notes

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def save_pitch_deck(deck: PitchDeck, city: str) -> bytes:
    data = render_pptx(deck, city)
    DECK_PATH.write_bytes(data)
    return data
