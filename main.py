"""Run LaunchScout from the command line.

Examples:
  python main.py
  python main.py --idea "Pet grooming at home" --city "Chennai" --customer "Pet owners"
"""
import argparse
import time

from launchscout.config import MODEL, check_env
from launchscout.crew import clean_inputs, run_crew
from launchscout.pdf import save_pdf
from launchscout.tasks import REPORT_PATH


def main() -> None:
    p = argparse.ArgumentParser(description="LaunchScout competitor research crew")
    p.add_argument("--idea", default="Healthy millet meal boxes delivered for lunch")
    p.add_argument("--city", default="Coimbatore")
    p.add_argument("--customer", default="Office workers, age 25 to 40")
    p.add_argument("--competitors", default="")
    p.add_argument("--process", choices=["sequential", "hierarchical"], default="sequential")
    args = p.parse_args()

    problems = check_env()
    if problems:
        raise SystemExit("\n".join(problems))

    inputs = clean_inputs(args.idea, args.city, args.customer, args.competitors)
    print(f"Model: {MODEL}\nInputs: {inputs}\n")

    start = time.time()
    report = run_crew(inputs, process=args.process)
    print("\n" + "=" * 70 + "\nFINAL REPORT\n" + "=" * 70)
    print(report)
    pdf_path = save_pdf(report)
    print(f"\nSaved to {REPORT_PATH} and {pdf_path}  ({time.time() - start:.0f}s)")


if __name__ == "__main__":
    main()
