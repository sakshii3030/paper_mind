import json
import os
import sys

# make sure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.parser import parse_all, parse_paper
from agents.summarizer import summarize_all, summarize_paper

def process_paper(raw_paper: dict) -> dict | None:
    """Parse and summarize a single raw paper. Returns None on failure."""
    if "id" not in raw_paper:
        raw_paper = {**raw_paper, "id": raw_paper.get("arxiv_id", "")}
    parsed = parse_paper(raw_paper)
    result = summarize_paper(parsed)
    return result if result.get("processed") else None


def run_pipeline(
    raw_filepath: str = "data/raw/papers.json",
    output_filepath: str = "data/processed/papers.json"
):
    """Run full pipeline: parse → summarize → save."""

    os.makedirs("data/processed", exist_ok=True)

    # load already processed papers so we don't redo them
    existing_ids = set()
    existing_papers = []
    if os.path.exists(output_filepath):
        with open(output_filepath, "r") as f:
            existing_papers = json.load(f)
            existing_ids = {p["id"] for p in existing_papers if p.get("processed")}
        print(f"Already processed: {len(existing_ids)} papers — skipping them.\n")

    # step 1: parse
    print("Step 1: Parsing raw papers...")
    all_papers = parse_all(raw_filepath)

    # step 2: filter to only new papers
    to_process = [p for p in all_papers if p["id"] not in existing_ids]
    print(f"Step 2: Summarizing {len(to_process)} new papers...\n")

    if not to_process:
        print("Nothing new to process!")
        return existing_papers

    # step 3: summarize
    processed_new = summarize_all(to_process)

    # step 4: merge and save
    all_processed = existing_papers + processed_new
    with open(output_filepath, "w") as f:
        json.dump(all_processed, f, indent=2)

    success = sum(1 for p in processed_new if p.get("processed"))
    print(f"\n✓ Done!")
    print(f"  Successfully processed : {success}/{len(to_process)}")
    print(f"  Failed                 : {len(to_process) - success}")
    print(f"  Total in database      : {len(all_processed)}")

    # show a sample
    good = [p for p in processed_new if p.get("processed")]
    if good:
        p = good[0]
        print(f"\nSample output:")
        print(f"  Title      : {p['title']}")
        print(f"  Summary    : {p['summary'][:150]}...")
        print(f"  Concepts   : {', '.join(p['concepts'])}")
        print(f"  Contribution: {p['contribution']}")

    return all_processed


if __name__ == "__main__":
    run_pipeline()