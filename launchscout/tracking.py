"""Stretch goal: re-run the crew weekly and highlight competitor price changes.

Every finished report is stored as a dated snapshot. Section 1 of the report is
a fixed-format table (Competitor | Price | ...), so prices are read from it
directly and compared with the previous snapshot of the same idea and city.
"""
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from launchscout.config import OUTPUT_DIR

HISTORY_DIR = OUTPUT_DIR / "history"
TRACKED_FILE = OUTPUT_DIR / "tracked.json"


# ------------------------------------------------------------------ snapshots
def slug(inputs: dict) -> str:
    text = f"{inputs['business_idea']}-{inputs['city']}".lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:80]


def save_snapshot(inputs: dict, report: str) -> Path:
    folder = HISTORY_DIR / slug(inputs)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now()
    path = folder / f"{stamp:%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps({
        "created": stamp.isoformat(timespec="seconds"),
        "inputs": inputs,
        "prices": extract_prices(report),
        "report": report,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def snapshots(inputs: dict) -> list[dict]:
    """All snapshots for this idea + city, oldest first."""
    folder = HISTORY_DIR / slug(inputs)
    if not folder.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]


# ------------------------------------------------------------------ prices
def extract_prices(report: str) -> dict[str, str]:
    """Read {competitor: price text} from the Section 1 table of the report."""
    section = re.split(r"\n##\s*1\.[^\n]*\n", report, maxsplit=1)
    if len(section) < 2:
        return {}
    body = re.split(r"\n##\s", section[1], maxsplit=1)[0]
    prices: dict[str, str] = {}
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= set("-: ") or cells[0].lower() == "competitor":
            continue
        name = re.sub(r"\*|\[\d+\]", "", cells[0]).strip()
        price = re.sub(r"\s*\[\d+\]", "", cells[1]).strip()
        if name:
            prices[name] = price
    return prices


def _key(name: str) -> str:
    """Loose name key so 'Cake Bee (KK Nagar)' matches 'Cake Bee'."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\(.*?\)", "", name.lower()))


def _numbers(price: str) -> list[float]:
    return [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", price)]


@dataclass
class PriceChange:
    competitor: str
    status: str          # "changed", "new", "gone", "same"
    before: str
    after: str


def compare(old: dict[str, str], new: dict[str, str]) -> list[PriceChange]:
    old_k = {_key(n): (n, p) for n, p in old.items()}
    new_k = {_key(n): (n, p) for n, p in new.items()}
    changes = []
    for k, (name, price) in new_k.items():
        if k not in old_k:
            changes.append(PriceChange(name, "new", "", price))
        else:
            before = old_k[k][1]
            same = _numbers(before) == _numbers(price)
            changes.append(PriceChange(name, "same" if same else "changed", before, price))
    for k, (name, price) in old_k.items():
        if k not in new_k:
            changes.append(PriceChange(name, "gone", price, ""))
    order = {"changed": 0, "new": 1, "gone": 2, "same": 3}
    return sorted(changes, key=lambda c: order[c.status])


def changes_since_last(inputs: dict) -> tuple[str, list[PriceChange]] | None:
    """Compare the latest two snapshots. Returns (previous date, changes)."""
    snaps = snapshots(inputs)
    if len(snaps) < 2:
        return None
    prev, last = snaps[-2], snaps[-1]
    return prev["created"], compare(prev["prices"], last["prices"])


def changes_markdown(prev_date: str, changes: list[PriceChange]) -> str:
    icon = {"changed": "PRICE CHANGED", "new": "NEW", "gone": "NOT FOUND", "same": "same"}
    rows = [f"| {c.competitor} | {icon[c.status]} | {c.before or '-'} | {c.after or '-'} |"
            for c in changes]
    return (f"## Price changes since {prev_date[:10]}\n\n"
            "| Competitor | Status | Before | Now |\n|---|---|---|---|\n" + "\n".join(rows))


# ------------------------------------------------------------------ tracked ideas
def tracked() -> list[dict]:
    if not TRACKED_FILE.exists():
        return []
    return json.loads(TRACKED_FILE.read_text(encoding="utf-8"))


def is_tracked(inputs: dict) -> bool:
    return any(slug(t) == slug(inputs) for t in tracked())


def set_tracked(inputs: dict, on: bool) -> None:
    items = [t for t in tracked() if slug(t) != slug(inputs)]
    if on:
        items.append(inputs)
    TRACKED_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
