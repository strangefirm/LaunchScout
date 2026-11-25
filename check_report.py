"""Checks a report against the brief's 'Done checklist'.

Run:  python check_report.py [path/to/report.md]
"""
import re
import sys
from pathlib import Path

from launchscout.tasks import REPORT_PATH
from launchscout.tracking import extract_prices

SECTIONS = ["Key Competitors", "What Customers Complain About", "Market Gap",
            "Recommended Positioning", "30-Day Launch Plan", "Sources"]


def check(report: str) -> list[tuple[bool, str]]:
    results = []

    headings = re.findall(r"^##\s*\d\.\s*(.+?)\s*$", report, re.M)
    missing = [s for s in SECTIONS if not any(s.lower() in h.lower() for h in headings)]
    results.append((not missing, f"All 6 sections present (missing: {missing or 'none'})"))

    table = re.split(r"\n##\s*1\.[^\n]*\n", report, maxsplit=1)[-1].split("\n## ")[0]
    rows = [l for l in table.splitlines() if l.strip().startswith("|")][2:]
    priced = extract_prices(report)
    with_price = [n for n, p in priced.items() if re.search(r"\d", p)]
    cited = [r for r in rows if re.search(r"\[\d+\]", r)]
    results.append((len(with_price) >= 3, f"At least 3 competitors with a price ({len(with_price)} found)"))
    results.append((len(cited) >= 3 and len(cited) == len(rows),
                    f"Every competitor row cites a source ({len(cited)}/{len(rows)})"))

    sources = re.split(r"\n##\s*6\.[^\n]*\n", report, maxsplit=1)[-1]
    urls = re.findall(r"https?://\S+", sources)
    cites = {int(n) for n in re.findall(r"\[(\d+)\]", report.split("## 6.")[0])}
    results.append((len(urls) >= len(cites) > 0,
                    f"Sources list has a URL for every citation ({len(urls)} URLs, "
                    f"{len(cites)} distinct citations)"))

    weeks = re.findall(r"Week\s*[1-4]", report.split("## 5.")[-1].split("## 6.")[0])
    results.append((len(set(weeks)) == 4, "30-day plan covers Week 1 to Week 4"))
    return results


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPORT_PATH
    ok_all = True
    for ok, msg in check(path.read_text(encoding="utf-8")):
        ok_all &= ok
        print(f"[{'ok' if ok else 'x '}] {msg}")
    print("\nPASS" if ok_all else "\nFAIL")
    sys.exit(0 if ok_all else 1)
