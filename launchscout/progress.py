"""Runs the crew in a background thread and streams live progress events.

CrewAI emits events (agent started, tool used, task finished...) on a global
event bus. We listen to the ones that matter, turn them into small plain dicts
and put them on a queue that the Streamlit page reads while the crew works.
"""
import json
import queue
import threading
from typing import Iterator

from crewai.events import (
    AgentExecutionStartedEvent,
    TaskCompletedEvent,
    TaskFailedEvent,
    ToolUsageErrorEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
    crewai_event_bus,
)

from launchscout.agents import MANAGER_ROLE
from launchscout.crew import ProcessName, build_crew
from launchscout.pdf import save_pdf
from launchscout.tasks import REPORT_PATH
from launchscout.tracking import save_snapshot

AGENT_ORDER = ["Market Researcher", "Review Analyst", "Strategy Analyst", "Report Writer"]
KNOWN_ROLES = set(AGENT_ORDER) | {MANAGER_ROLE}


def _short(value, limit: int = 220) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[:limit] + "…"


def _describe_tool_call(tool_name: str, args) -> str:
    """Turn a raw tool call into a friendly one-liner."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return f"{tool_name}: {_short(args, 120)}"
    args = args or {}
    if "coworker" in args and "question" in args:
        return f"Asking {args['coworker']}: {_short(args['question'], 140)}"
    if "coworker" in args:
        return f"Delegating to {args['coworker']}: {_short(args.get('task', ''), 140)}"
    if "search_query" in args:
        return f"Searching: “{args['search_query']}”"
    if "website_url" in args:
        return f"Reading page: {args['website_url']}"
    if "filename" in args:
        return f"Saving file: {args['filename']}"
    return f"{tool_name}: {_short(args, 120)}"


def run_with_progress(inputs: dict, process: ProcessName = "sequential") -> Iterator[dict]:
    """Start the crew and yield progress events until it finishes.

    Event shapes:
      {"kind": "agent",  "agent": role}
      {"kind": "tool",   "agent": role, "text": "..."}
      {"kind": "tool_error", "agent": role, "text": "..."}
      {"kind": "task_done",  "agent": role, "output": "..."}
      {"kind": "done",   "report": "..."}
      {"kind": "error",  "text": "..."}
    """
    events: "queue.Queue[dict]" = queue.Queue()
    crew = build_crew(process=process, verbose=False)
    my_agents = {str(a.id) for a in crew.agents}
    if crew.manager_agent:
        my_agents.add(str(crew.manager_agent.id))

    def mine(event) -> bool:
        agent_id = str(getattr(event, "agent_id", "") or "")
        return not agent_id or agent_id in my_agents

    def on_agent(_, e):
        role = e.agent_role or getattr(getattr(e, "agent", None), "role", None)
        if role in KNOWN_ROLES:
            events.put({"kind": "agent", "agent": role})

    def on_tool_start(_, e):
        if mine(e):
            events.put({"kind": "tool", "agent": e.agent_role,
                        "text": _describe_tool_call(e.tool_name, e.tool_args)})

    def on_tool_done(_, e):
        if mine(e) and "search" in (e.tool_name or "").lower():
            events.put({"kind": "tool_result", "agent": e.agent_role,
                        "text": _short(e.output, 300)})

    def on_tool_error(_, e):
        if mine(e):
            events.put({"kind": "tool_error", "agent": e.agent_role,
                        "text": f"{e.tool_name} failed: {_short(e.error, 150)}"})

    def on_task_done(_, e):
        role = getattr(getattr(e.task, "agent", None), "role", e.agent_role)
        events.put({"kind": "task_done", "agent": role,
                    "output": getattr(e.output, "raw", str(e.output))})

    def on_task_failed(_, e):
        events.put({"kind": "error", "text": f"Task failed: {_short(e.error, 300)}"})

    handlers = [
        (AgentExecutionStartedEvent, on_agent),
        (ToolUsageStartedEvent, on_tool_start),
        (ToolUsageFinishedEvent, on_tool_done),
        (ToolUsageErrorEvent, on_tool_error),
        (TaskCompletedEvent, on_task_done),
        (TaskFailedEvent, on_task_failed),
    ]
    for event_type, fn in handlers:
        crewai_event_bus.on(event_type)(fn)

    def worker():
        try:
            REPORT_PATH.unlink(missing_ok=True)
            result = crew.kickoff(inputs=inputs)
            crewai_event_bus.flush()
            report = (REPORT_PATH.read_text(encoding="utf-8")
                      if REPORT_PATH.exists() else str(result.raw))
            # Save outputs here, in the worker, so they exist even if the
            # browser tab is closed before the page finishes.
            save_snapshot(inputs, report)
            try:
                save_pdf(report)
            except Exception:
                pass  # the page shows PDF errors when it builds the download
            events.put({"kind": "done", "report": report})
        except Exception as exc:  # surface any crash to the UI
            events.put({"kind": "error", "text": str(exc)})

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        while True:
            try:
                event = events.get(timeout=0.5)
            except queue.Empty:
                if not thread.is_alive() and events.empty():
                    break
                continue
            yield event
            if event["kind"] in ("done", "error") and not thread.is_alive():
                break
    finally:
        for event_type, fn in handlers:
            crewai_event_bus.off(event_type, fn)
