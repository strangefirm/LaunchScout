"""Stretch goal: re-run the crew for every tracked idea and report price changes.

Track an idea from the app (toggle "Re-run weekly"), then schedule this script.
Windows, every Monday at 9:00:
  schtasks /Create /SC WEEKLY /D MON /ST 09:00 /TN LaunchScoutWeekly ^
    /TR "\"<project>\\.venv\\Scripts\\python.exe\" \"<project>\\weekly.py\""

Run by hand:  python weekly.py
"""
from datetime import datetime

from launchscout.config import check_env
from launchscout.crew import run_crew
from launchscout.pdf import save_pdf
from launchscout.tracking import (
    HISTORY_DIR, slug, changes_markdown, changes_since_last, save_snapshot, tracked,
)


def main() -> None:
    problems = check_env()
    if problems:
        raise SystemExit("\n".join(problems))
    ideas = tracked()
    if not ideas:
        print("No tracked ideas. Turn on 'Re-run weekly' for a report in the app.")
        return

    for inputs in ideas:
        print(f"\n=== {inputs['business_idea']} · {inputs['city']} ===")
        try:
            report = run_crew(inputs, process=inputs.get("process", "sequential"))
        except Exception as e:
            print(f"  failed: {e}")
            continue
        save_snapshot(inputs, report)
        save_pdf(report)
        diff = changes_since_last(inputs)
        if not diff:
            print("  first snapshot saved; changes will show from next week")
            continue
        prev_date, changes = diff
        md = changes_markdown(prev_date, changes)
        out = HISTORY_DIR / slug(inputs) / f"changes-{datetime.now():%Y%m%d}.md"
        out.write_text(md, encoding="utf-8")
        moved = [c for c in changes if c.status != "same"]
        print(f"  {len(moved)} change(s) since {prev_date[:10]} -> {out}")
        for c in moved:
            print(f"   - {c.competitor}: {c.status} ({c.before or '-'} -> {c.after or '-'})")


if __name__ == "__main__":
    main()
