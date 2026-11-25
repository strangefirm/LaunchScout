"""LaunchScout - Streamlit front end.

Run:  streamlit run app.py
"""
import time

import streamlit as st

from launchscout.config import MODEL, check_env
from launchscout.crew import clean_inputs
from launchscout.pdf import save_pdf
from launchscout.pitch_deck import generate_pitch_deck, save_pitch_deck
from launchscout.tracking import changes_since_last, is_tracked, set_tracked
from launchscout.agents import MANAGER_ROLE
from launchscout.progress import AGENT_ORDER, run_with_progress

st.set_page_config(page_title="LaunchScout", page_icon=":material/travel_explore:", layout="wide")

AGENT_ICONS = {
    "Market Researcher": ":material/search:",
    "Review Analyst": ":material/reviews:",
    "Strategy Analyst": ":material/insights:",
    "Report Writer": ":material/edit_note:",
    MANAGER_ROLE: ":material/supervisor_account:",
}
PROCESS_LABELS = {"sequential": "Sequential", "hierarchical": "Hierarchical (manager)"}

if "log" not in st.session_state:
    st.session_state.log = []        # progress events of the last run (for replay)
    st.session_state.report = None   # final markdown report
    st.session_state.inputs = None
    st.session_state.elapsed = None
    st.session_state.process = "sequential"


# ---------------------------------------------------------------- progress UI
class ProgressView:
    """Draws one step per agent and fills it with that agent's activity.

    Sequential: agents work one after another, so a new agent appearing means
    the previous one handed over. Hierarchical: the manager stays open the
    whole run while specialists it delegates to open and close inside it.
    """

    def __init__(self, live: bool, hierarchical: bool = False):
        self.live = live
        self.hierarchical = hierarchical
        self.steps: dict[str, dict] = {}

    def _label(self, role: str, detail: str) -> str:
        return f"{AGENT_ICONS.get(role, ':material/smart_toy:')} **{role}** · {detail}"

    def _step(self, role: str) -> dict:
        if role in self.steps:
            step = self.steps[role]
            if self.live and step["state"] != "running":  # delegated to again
                step["state"] = "running"
                step["box"].update(label=self._label(role, ":shimmer[working]"), state="running")
            return step
        if role not in self.steps:
            if not self.hierarchical:
                for other in self.steps.values():  # previous agent has handed over
                    if other["state"] == "running":
                        self._finish(other)
            box = st.status(
                self._label(role, ":shimmer[working]") if self.live
                else self._label(role, "done"),
                type="step", expanded=self.live,
                state="running" if self.live else "complete",
            )
            self.steps[role] = {"box": box, "role": role, "tools": 0, "state": "running"}
        return self.steps[role]

    def _finish(self, step: dict, state: str = "complete"):
        step["state"] = state
        n = step["tools"]
        detail = f"{n} tool call{'s' if n != 1 else ''}" if n else "reasoned over team findings"
        step["box"].update(label=self._label(step["role"], detail), state=state, expanded=False)

    def apply(self, ev: dict):
        kind = ev["kind"]
        if kind in ("done", "error") or not ev.get("agent"):
            return
        step = self._step(ev["agent"])
        box = step["box"]
        if kind == "tool":
            step["tools"] += 1
            box.markdown(f":material/arrow_right: {ev['text']}")
        elif kind == "tool_result":
            box.caption(ev["text"])
        elif kind == "tool_error":
            box.caption(f":orange[:material/warning:] {ev['text']} — moving on")
        elif kind == "task_done":
            step["tasks"] = step.get("tasks", 0) + 1
            title = (f"Accepted result of task {step['tasks']}" if ev["agent"] == MANAGER_ROLE
                     else "What this agent handed over")
            with box.expander(title, icon=":material/output:"):
                st.markdown(ev["output"])
            if self.hierarchical:  # specialists are done; the manager carries on
                for other in self.steps.values():
                    if other["role"] != MANAGER_ROLE and other["state"] == "running":
                        self._finish(other)
            else:
                self._finish(step)

    def close(self, failed: bool = False):
        for step in self.steps.values():
            if step["state"] == "running":
                self._finish(step, "error" if failed else "complete")


# ---------------------------------------------------------------- page
st.title("LaunchScout", anchor=False)
st.caption(
    "A crew of four AI agents researches the market for your business idea and "
    "delivers a competitor report with prices, gaps and a launch plan."
)

problems = check_env()
for p in problems:
    st.error(p, icon=":material/key_off:")

with st.sidebar:
    st.subheader("The crew", anchor=False)
    for role in AGENT_ORDER:
        st.markdown(f"{AGENT_ICONS[role]} {role}")
    st.markdown(f"{AGENT_ICONS[MANAGER_ROLE]} {MANAGER_ROLE} :gray[(hierarchical only)]")
    st.divider()
    st.caption(f"Model: `{MODEL}`")
    st.caption(
        "**Sequential:** tasks run in a fixed order, each agent receiving the previous "
        "agents' work. **Hierarchical:** a manager delegates each task to the specialist "
        "it picks and reviews the result before moving on.")

with st.form("idea_form"):
    business_idea = st.text_input(
        "Business idea", placeholder="Healthy millet meal boxes delivered for lunch")
    col1, col2 = st.columns(2)
    city = col1.text_input("City", placeholder="Coimbatore")
    target_customer = col2.text_input("Target customer", placeholder="Office workers, age 25 to 40")
    known = st.text_area(
        "Known competitors (optional)", placeholder="Leave blank, or list names separated by commas",
        height=68)
    process = st.segmented_control(
        "Crew process", options=list(PROCESS_LABELS), format_func=PROCESS_LABELS.get,
        default="sequential", required=True)
    submitted = st.form_submit_button(
        "Research my market", type="primary", icon=":material/rocket_launch:",
        disabled=bool(problems))

if submitted:
    try:
        inputs = clean_inputs(business_idea, city, target_customer, known)
    except ValueError as e:
        st.warning(str(e), icon=":material/edit:")
        st.stop()

    st.session_state.update(log=[], report=None, inputs=inputs, elapsed=None, process=process)
    st.subheader("Live progress", anchor=False)
    view = ProgressView(live=True, hierarchical=process == "hierarchical")
    start = time.time()
    failed = None
    with st.spinner("The crew is working. This usually takes 3 to 5 minutes…"):
        for ev in run_with_progress(inputs, process=process):
            st.session_state.log.append(ev)
            view.apply(ev)
            if ev["kind"] == "done":
                st.session_state.report = ev["report"]  # snapshot saved by the worker
            elif ev["kind"] == "error":
                failed = ev["text"]
    view.close(failed=bool(failed and not st.session_state.report))
    st.session_state.elapsed = time.time() - start
    if failed and not st.session_state.report:
        st.error(failed, title="The crew stopped", icon=":material/error:")

elif st.session_state.log:
    # Replay the last run's log so it stays visible after any rerun.
    st.subheader("Crew activity", anchor=False)
    replay = ProgressView(live=False, hierarchical=st.session_state.process == "hierarchical")
    for ev in st.session_state.log:
        replay.apply(ev)
    replay.close()

# ---------------------------------------------------------------- report
report = st.session_state.report
if report:
    inputs = st.session_state.inputs
    st.success(
        f"Report ready in {st.session_state.elapsed:.0f} seconds "
        f"({PROCESS_LABELS[st.session_state.process].lower()} process).",
        title=f"{inputs['business_idea']} · {inputs['city']}", icon=":material/task_alt:")
    if st.session_state.get("pdf_for") != report:  # build the PDF once per report
        try:
            st.session_state.pdf = save_pdf(report).read_bytes()
        except Exception as e:
            st.session_state.pdf = None
            st.warning(f"PDF could not be created: {e}", icon=":material/picture_as_pdf:")
        st.session_state.pdf_for = report
    with st.container(horizontal=True):
        st.download_button(
            "Download Markdown", data=report, file_name="report.md", mime="text/markdown",
            icon=":material/download:")
        if st.session_state.pdf:
            st.download_button(
                "Download PDF", data=st.session_state.pdf, file_name="report.pdf",
                mime="application/pdf", icon=":material/picture_as_pdf:")
    # Stretch goal: price changes versus the previous run of this idea + city
    diff = changes_since_last(inputs)
    if diff:
        prev_date, changes = diff
        moved = [c for c in changes if c.status != "same"]
        status_txt = {"changed": ":orange-badge[Price changed]", "new": ":blue-badge[New]",
                      "gone": ":gray-badge[Not found]", "same": ":green-badge[Same]"}
        with st.expander(
                f"Price changes since {prev_date[:10]}: {len(moved)} change"
                f"{'s' if len(moved) != 1 else ''}", icon=":material/trending_up:",
                expanded=bool(moved)):
            rows = [f"| {c.competitor} | {status_txt[c.status]} | {c.before or '-'} | "
                    f"{c.after or '-'} |" for c in changes]
            st.markdown("\n".join(
                ["| Competitor | Status | Before | Now |", "|---|---|---|---|", *rows]))
    track = st.toggle(
        "Re-run weekly and highlight price changes", value=is_tracked(inputs),
        help="Adds this idea to outputs/tracked.json. Schedule weekly.py to re-run "
             "every tracked idea (see README).")
    if track != is_tracked(inputs):
        set_tracked({**inputs, "process": st.session_state.process}, track)
        st.toast("Tracking on: weekly.py will re-run this idea." if track
                 else "Tracking off.", icon=":material/event_repeat:")

    report_tab, deck_tab = st.tabs(
        [":material/description: Report", ":material/slideshow: Pitch deck"],
        key="result_tabs")  # keyed so the open tab survives reruns
    with report_tab:
        with st.container(border=True):
            st.markdown(report)

    with deck_tab:  # stretch goal: Pitch Deck agent
        deck_state = st.session_state.get("deck")
        if not deck_state or deck_state["for"] != report:
            st.caption("A fifth agent, the Pitch Deck Designer, turns this report into "
                       "6 slides with speaker notes. Takes about 30 seconds.")
            if st.button("Make pitch deck", icon=":material/auto_awesome:", type="primary"):
                with st.spinner("Pitch Deck Designer is building your slides…"):
                    try:
                        deck = generate_pitch_deck(report, inputs)
                        pptx = save_pitch_deck(deck, inputs["city"])
                        st.session_state.deck = {"for": report, "deck": deck, "pptx": pptx}
                        st.rerun()
                    except Exception as e:
                        st.error(str(e), title="Could not build the deck", icon=":material/error:")
        else:
            deck = deck_state["deck"]
            st.download_button(
                "Download PowerPoint", data=deck_state["pptx"], file_name="pitch_deck.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                icon=":material/download:")
            with st.container(border=True):
                st.subheader(deck.deck_title, anchor=False)
                st.markdown(f"*{deck.tagline}*")
            for i, slide in enumerate(deck.slides, 1):
                with st.container(border=True):
                    st.markdown(f"**{i:02d} · {slide.title}**")
                    st.markdown("\n".join(f"- {b}" for b in slide.bullets))
                    st.caption(f":material/record_voice_over: {slide.speaker_notes}")
