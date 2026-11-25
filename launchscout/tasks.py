"""The four LaunchScout tasks.

Each task has an expected_output that spells out the exact format required, so
the result can be checked. Tasks run in order and each receives the previous
tasks' output through `context`, like a team passing work along.
"""
from crewai import Agent, Task

from launchscout.config import OUTPUT_DIR

REPORT_PATH = OUTPUT_DIR / "report.md"

SCRAPE_TIP = (
    "If a page cannot be read (timeout, blocked, connection error), do NOT retry "
    "that site again; use the search result snippet and its URL as the source "
    "instead. Justdial and Google Maps pages usually block reading, so rely on "
    "their search snippets."
)


def research_task(agent: Agent | None) -> Task:
    return Task(
        description=(
            "Research the competitive landscape for this business idea.\n\n"
            "Business idea: {business_idea}\n"
            "City: {city}\n"
            "Target customer: {target_customer}\n"
            "Known competitors (may be empty): {known_competitors}\n\n"
            "Steps:\n"
            "1. If known competitors are given, include them first.\n"
            "2. Search the web (Google results, Swiggy, Zomato, Instagram, Justdial, "
            "company websites) for businesses in {city} selling something similar.\n"
            "3. Open the most useful pages with the scraper to read real prices, "
            "plans and offers.\n"
            "4. Keep 3 to 5 competitors that genuinely operate in or deliver to {city}. "
            "Prefer direct competitors; add a close substitute only if fewer than 3 "
            "direct ones exist, and label it 'substitute'.\n\n"
            "Rules: never invent a business, price or URL. If a price is not public, "
            "write 'Not listed'. Each competitor needs at least one working source URL.\n"
            + SCRAPE_TIP
        ),
        expected_output=(
            "A Markdown list with 3 to 5 competitors. For EACH competitor, exactly "
            "these fields:\n"
            "### <Competitor name> (direct | substitute)\n"
            "- Price: <price with unit, e.g. 'Rs 180 per meal' or 'Not listed'>\n"
            "- Offers / plans: <subscriptions, discounts, trial offers, or 'None found'>\n"
            "- Sales channels: <comma-separated, e.g. Own website, Swiggy, WhatsApp>\n"
            "- What they sell: <one line>\n"
            "- Sources: <one or more full URLs where the above was found>"
        ),
        agent=agent,
    )


def review_task(agent: Agent | None, context: list[Task]) -> Task:
    return Task(
        description=(
            "For every competitor in the research above, find out what real customers "
            "in {city} say about them.\n\n"
            "Search for reviews on Google Maps, Zomato, Swiggy, Justdial, Reddit, "
            "Instagram comments, YouTube or blog posts. Use queries like "
            "'<competitor name> {city} reviews' and '<competitor name> complaints'. "
            "Scrape review pages when the search snippet is not enough.\n\n"
            "Then find the complaints that come up across several competitors: these "
            "are the market's shared pain points. If you find no reviews for a "
            "competitor, say so instead of guessing.\n" + SCRAPE_TIP
        ),
        expected_output=(
            "Markdown in two parts.\n\n"
            "PART 1 - per competitor, for each one:\n"
            "### <Competitor name>\n"
            "- Customers like: <2-3 short bullet points, or 'No reviews found'>\n"
            "- Customers complain about: <2-3 short bullet points, or 'No reviews found'>\n"
            "- Sources: <full URLs of the review pages used>\n\n"
            "PART 2 - '## Common complaints across the market': 2 to 5 bullet points, "
            "each naming the complaint and the competitors it applies to in brackets, "
            "e.g. '- Same menu every day, gets boring (GreenBowl, MilletMan)'."
        ),
        agent=agent,
        context=context,
    )


def strategy_task(agent: Agent | None, context: list[Task]) -> Task:
    return Task(
        description=(
            "Using ONLY the competitor research and review analysis above (do not "
            "invent new competitors or prices), work out where '{business_idea}' can "
            "win in {city} with {target_customer}.\n\n"
            "1. Build a comparison matrix of all competitors.\n"
            "2. Identify the ONE clearest market gap: a need customers have that no "
            "competitor serves well, supported by the complaints and the price data.\n"
            "3. Recommend positioning: a one-line offer with a specific price in local "
            "currency, set by comparing to the competitor prices found.\n"
            "4. Explain briefly why this price and positioning can win."
        ),
        expected_output=(
            "Markdown with exactly these four parts:\n\n"
            "## Comparison matrix\n"
            "A Markdown table with columns: Competitor | Price | Channel | Strength | "
            "Weakness. One row per competitor.\n\n"
            "## Market gap\n"
            "2-3 sentences naming the gap and the evidence for it.\n\n"
            "## Recommended positioning\n"
            "One line in quotes with a concrete offer and price, e.g. "
            "\"Fresh millet lunch, new menu every day, Rs 3,999 per month\".\n\n"
            "## Why this works\n"
            "3 bullet points linking the positioning to competitor prices and "
            "customer complaints."
        ),
        agent=agent,
        context=context,
    )


def report_task(agent: Agent | None, context: list[Task]) -> Task:
    return Task(
        description=(
            "Write the final competitor report for a founder planning to launch "
            "'{business_idea}' in {city} for {target_customer}.\n\n"
            "Use only facts from your teammates' work above. Keep every source URL. "
            "Number the sources [1], [2], ... in order of first use, cite them inline "
            "next to the prices and claims they support, and list them all in the "
            "Sources section.\n\n"
            "Write a practical 30-day launch plan, week by week, that follows from the "
            "recommended positioning and targets {target_customer} in {city}.\n\n"
            "Save the complete report with the File Writer tool as 'report.md' "
            "(overwrite = true). Then give the complete report as your final answer."
        ),
        expected_output=(
            "The complete report in Markdown, starting with the title line and "
            "containing exactly these six numbered sections in this order:\n\n"
            "# Competitor Report: {business_idea}, {city}\n\n"
            "## 1. Key Competitors\n"
            "Table: Competitor | Price | Channel | Strength | Weakness, with source "
            "citations like [1] next to each price.\n\n"
            "## 2. What Customers Complain About\n"
            "Bullet points naming each complaint and the competitors it applies to.\n\n"
            "## 3. Market Gap\n"
            "2-3 sentences.\n\n"
            "## 4. Recommended Positioning\n"
            "The one-line offer with price, in quotes.\n\n"
            "## 5. 30-Day Launch Plan\n"
            "Week 1, Week 2, Week 3, Week 4: 2-3 concrete actions each.\n\n"
            "## 6. Sources\n"
            "Numbered list [1] <full URL> - <what it supports>.\n\n"
            "No text before the title and no closing remarks after the Sources."
        ),
        agent=agent,
        context=context,
        output_file=str(REPORT_PATH),  # guarantees the report is saved to disk
    )


def all_tasks(agents: dict[str, Agent], assign_agents: bool = True) -> list[Task]:
    """Build the four tasks in order, each receiving the earlier tasks as context.

    assign_agents=False is used for the hierarchical process: tasks are left
    unassigned so the manager decides which specialist handles each one.
    """
    pick = (lambda key: agents[key]) if assign_agents else (lambda key: None)
    research = research_task(pick("researcher"))
    reviews = review_task(pick("reviewer"), context=[research])
    strategy = strategy_task(pick("strategist"), context=[research, reviews])
    report = report_task(pick("writer"), context=[research, reviews, strategy])
    return [research, reviews, strategy, report]
