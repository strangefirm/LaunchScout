"""Assembles the agents and tasks into a crew (sequential or hierarchical)."""
from typing import Callable, Literal, Optional

from crewai import Crew, Process

from launchscout.agents import all_agents, research_manager
from launchscout.tasks import REPORT_PATH, all_tasks

ProcessName = Literal["sequential", "hierarchical"]


def build_crew(
    process: ProcessName = "sequential",
    step_callback: Optional[Callable] = None,
    task_callback: Optional[Callable] = None,
    verbose: bool = True,
) -> Crew:
    """Create the LaunchScout crew.

    sequential   - each task is pre-assigned and runs in order (core build).
    hierarchical - a Research Manager delegates each task to the specialist it
                   chooses and reviews the result (stretch goal).

    step_callback / task_callback let a UI follow progress.
    """
    agents = all_agents()
    hierarchical = process == "hierarchical"
    extra = {"manager_agent": research_manager()} if hierarchical else {}
    return Crew(
        agents=list(agents.values()),
        tasks=all_tasks(agents, assign_agents=not hierarchical),
        process=Process.hierarchical if hierarchical else Process.sequential,
        step_callback=step_callback,
        task_callback=task_callback,
        verbose=verbose,
        **extra,
    )


def clean_inputs(
    business_idea: str,
    city: str,
    target_customer: str,
    known_competitors: str = "",
) -> dict:
    """Validate and normalise the form inputs into crew inputs."""
    business_idea, city = business_idea.strip(), city.strip()
    if not business_idea or not city:
        raise ValueError("Business idea and city are required.")
    return {
        "business_idea": business_idea,
        "city": city,
        "target_customer": target_customer.strip() or "General consumers",
        "known_competitors": known_competitors.strip() or "none provided",
    }


def run_crew(inputs: dict, process: ProcessName = "sequential", **callbacks) -> str:
    """Run the crew and return the final Markdown report."""
    REPORT_PATH.unlink(missing_ok=True)
    result = build_crew(process=process, **callbacks).kickoff(inputs=inputs)
    if REPORT_PATH.exists():
        return REPORT_PATH.read_text(encoding="utf-8")
    return str(result.raw)
