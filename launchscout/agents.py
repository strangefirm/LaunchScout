"""The four LaunchScout agents.

Each agent has a clearly different job, so their roles, goals and backstories
do not overlap. Placeholders like {business_idea} and {city} are filled in by
CrewAI from the form inputs when the crew is kicked off, which is why the same
code works for any idea in any city.
"""
from crewai import Agent

from launchscout.config import get_llm, is_local_model
from launchscout.tools import file_writer_tool, scrape_tool, search_tool

# Local models need more room to recover from a bad tool call.
MAX_ITER = 25 if is_local_model() else 15


def market_researcher() -> Agent:
    return Agent(
        role="Market Researcher",
        goal=(
            "Find 3 to 5 REAL competitors for '{business_idea}' operating in {city}, "
            "and record for each one: its price, current offers, and the sales "
            "channels it uses (own website, app, Swiggy, Zomato, WhatsApp, Instagram, "
            "etc.). Every price must come with the URL of the page it was found on."
        ),
        backstory=(
            "You spent eight years as a field researcher for a retail consultancy, "
            "mapping local markets across Indian cities before a client spends a rupee. "
            "You trust only what you can link to: menus, listing pages, delivery-app "
            "pages and official websites. You never invent a business or a price; if "
            "a price is not public you write 'Not listed' and say where you looked."
        ),
        tools=[search_tool(), scrape_tool()],
        llm=get_llm(),
        allow_delegation=False,
        max_iter=MAX_ITER,
        verbose=True,
    )


def review_analyst() -> Agent:
    return Agent(
        role="Review Analyst",
        goal=(
            "For each competitor the Market Researcher found, discover what customers "
            "in {city} like and what they complain about, using public reviews on "
            "Google Maps, Zomato, Swiggy, Justdial, Reddit, Instagram or blogs. "
            "Group complaints into recurring themes and link every claim to its source."
        ),
        backstory=(
            "You are a customer-experience analyst who has read tens of thousands of "
            "reviews. You know a single angry review is noise and the same complaint "
            "from five people is a signal. You quote customers briefly, you separate "
            "praise from pain points, and you always note which competitor and which "
            "page each piece of feedback came from."
        ),
        tools=[search_tool(), scrape_tool()],
        llm=get_llm(),
        allow_delegation=False,
        max_iter=MAX_ITER,
        verbose=True,
    )


def strategy_analyst() -> Agent:
    return Agent(
        role="Strategy Analyst",
        goal=(
            "Using only the research and reviews gathered by your teammates, build a "
            "competitor comparison matrix, identify the single clearest market gap for "
            "'{business_idea}' in {city} aimed at {target_customer}, and recommend a "
            "one-line positioning with a specific price."
        ),
        backstory=(
            "You are a former startup strategist who has helped dozens of first-time "
            "founders find their wedge. You do not browse the web; you reason over the "
            "evidence in front of you. You look for the pain point that every competitor "
            "shares and nobody solves, then price the offer against real competitor "
            "prices so the founder can defend the number."
        ),
        tools=[],  # reasons over the first two agents' work only
        llm=get_llm(),
        allow_delegation=False,
        max_iter=MAX_ITER,
        verbose=True,
    )


def report_writer() -> Agent:
    return Agent(
        role="Report Writer",
        goal=(
            "Turn the team's findings into a clean, founder-friendly Markdown "
            "competitor report for '{business_idea}' in {city} with exactly six "
            "sections, including a practical 30-day launch plan and a numbered source "
            "list, and save it to report.md."
        ),
        backstory=(
            "You write for busy founders, not analysts. Short sentences, clear tables, "
            "no filler. You never add a fact your teammates did not find, and every "
            "price or claim in your report keeps its source link so the founder can "
            "verify it."
        ),
        tools=[file_writer_tool()],
        llm=get_llm(),
        allow_delegation=False,
        max_iter=MAX_ITER,
        verbose=True,
    )


MANAGER_ROLE = "Research Manager"


def research_manager() -> Agent:
    """Stretch goal: manager for Process.hierarchical. Has no tools of its own;
    CrewAI gives it 'delegate work' and 'ask question' tools for the team."""
    return Agent(
        role=MANAGER_ROLE,
        goal=(
            "Deliver a complete, fully sourced competitor report for "
            "'{business_idea}' in {city} by delegating each piece of work to the "
            "right specialist and checking their output before accepting it."
        ),
        backstory=(
            "You run a small market-research agency. You never do the research "
            "yourself: you brief specialists precisely, pass them the context they "
            "need from earlier work, and send work back when it is missing prices, "
            "source links or required sections. Your team: a Market Researcher "
            "(finds competitors and prices on the web), a Review Analyst (finds "
            "customer reviews), a Strategy Analyst (comparison, gap, positioning; "
            "no web access) and a Report Writer (writes and saves the final report).\n"
            "Working rules: handle ONLY the current task. Delegate it to the one "
            "specialist it belongs to and never start later steps early (no report "
            "writing during research). Send work back at most once, and only if "
            "required fields, prices or source links are missing. Pass instructions "
            "through exactly as written, including file names such as 'report.md'."
        ),
        llm=get_llm(),
        allow_delegation=True,
        max_iter=MAX_ITER,
        verbose=True,
    )


def all_agents() -> dict[str, Agent]:
    return {
        "researcher": market_researcher(),
        "reviewer": review_analyst(),
        "strategist": strategy_analyst(),
        "writer": report_writer(),
    }
