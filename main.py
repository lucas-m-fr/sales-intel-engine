import argparse
import asyncio
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import extractor, interaction, review_enrichment, validator
from src.discovery import discover_leads, save_leads_to_folder
from src.planner import plan_search_strategy


def summarize(folder):
    for name in ("Pricing", "Uniqueness", "Ambience", "Reviews"):
        path = os.path.join(folder, f"{name}.csv")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        fields = [k for k in rows[0] if k != "lead_id"] if rows else []
        filled = sum(1 for r in rows for k in fields if r.get(k, "").strip())
        total = len(rows) * len(fields) or 1
        print(f"  {name:11} {filled}/{total} filled ({filled * 100 // total}%)")


def run(target, limit=5, skip_reviews=False, folder=None):
    if folder:
        business_folder = folder
    else:
        print("Planning search strategy...")
        strategy = plan_search_strategy(target)
        query = strategy.get("refined_query", target)
        print(f"Refined query: {query}")
        leads = discover_leads(query, limit=limit)
        if not leads:
            print("No leads found.")
            return 1
        business_folder = save_leads_to_folder(leads, target)

    print(f"\nCapturing evidence -> {business_folder}")
    asyncio.run(interaction.main(business_folder))

    if not skip_reviews:
        review_enrichment.main(business_folder)

    print("\nExtracting tables...")
    extractor.run_extraction_pipeline(business_folder)
    for table in extractor.TABLES:
        validator.validate_table(business_folder, table)

    print(f"\nDone. Outputs in: {business_folder}")
    summarize(business_folder)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Sales Intelligence Engine")
    parser.add_argument("target", help="e.g. 'Boutique 4 star hotels in Paris'")
    parser.add_argument("--limit", type=int, default=5, help="Number of leads")
    parser.add_argument("--folder", help="Re-run on an existing archive folder")
    parser.add_argument("--skip-reviews", action="store_true", help="Skip external review lookup")
    args = parser.parse_args()
    sys.exit(run(args.target, args.limit, args.skip_reviews, args.folder))


if __name__ == "__main__":
    main()
