import os
from dotenv import load_dotenv

# load .env before any other imports
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

import json
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from agents.crawler import fetch_papers, save_papers
from agents.parser import parse_all
from agents.summarizer import summarize_all
from graph.writer import write_all_papers
from neo4j import GraphDatabase

URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
TOPICS_FILE = "topics.json"
PROCESSED_PATH = "data/processed/papers.json"


def get_existing_ids() -> set:
    """Get all paper IDs already in the graph."""
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        result = session.run("MATCH (p:Paper) RETURN p.id AS id")
        ids = {record["id"] for record in result}
    driver.close()
    return ids


def load_topics() -> list:
    """Load topics from topics.json."""
    if not os.path.exists(TOPICS_FILE):
        print(f"No {TOPICS_FILE} found. Using default.")
        return ["mechanistic interpretability"]
    with open(TOPICS_FILE, "r") as f:
        topics = json.load(f)
    return topics


def check_topic(query: str, max_results: int = 50) -> dict:
    """Run full pipeline for a single topic."""

    print(f"\n{'─'*50}")
    print(f"Topic: '{query}'")
    print(f"Time : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'─'*50}")

    # fetch
    print("Fetching from arXiv...")
    fresh_papers = fetch_papers(
        query=f'all:"{query}"',
        max_results=max_results
    )
    print(f"Found {len(fresh_papers)} papers on arXiv")

    # filter new ones
    existing_ids = get_existing_ids()
    new_raw = [p for p in fresh_papers if p["id"] not in existing_ids]
    print(f"New papers: {len(new_raw)}")

    if not new_raw:
        print("Graph is up to date for this topic.")
        return {"new_papers": 0, "topic": query,
                "timestamp": datetime.now().isoformat()}

    # save raw
    save_papers(new_raw)

    # parse
    all_parsed = parse_all()
    new_parsed = [p for p in all_parsed
                  if p["id"] in {r["id"] for r in new_raw}]

    # summarize
    print(f"Summarizing {len(new_parsed)} papers...")
    summarized = summarize_all(new_parsed, delay=2.0)

    # save processed
    existing_processed = []
    if os.path.exists(PROCESSED_PATH):
        with open(PROCESSED_PATH, "r") as f:
            existing_processed = json.load(f)

    existing_processed_ids = {p["id"] for p in existing_processed}
    new_processed = [p for p in summarized
                     if p["id"] not in existing_processed_ids]
    all_processed = existing_processed + new_processed

    with open(PROCESSED_PATH, "w") as f:
        json.dump(all_processed, f, indent=2)

    # write to graph
    print("Writing to graph...")
    write_all_papers()

    success = sum(1 for p in new_processed if p.get("processed"))
    print(f"✓ Added {success} new papers for topic '{query}'")

    return {
        "new_papers": success,
        "topic": query,
        "timestamp": datetime.now().isoformat(),
        "titles": [p["title"] for p in new_processed
                   if p.get("processed")]
    }


def _log_run(total_new: int, topics: list) -> None:
    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sentinel_log.json')
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    try:
        existing = []
        if os.path.exists(log_path):
            with open(log_path) as f:
                existing = json.load(f)
        existing.append({
            "timestamp": datetime.now().isoformat(),
            "papers_added": total_new,
            "topics": topics,
        })
        with open(log_path, 'w') as f:
            json.dump(existing[-100:], f, indent=2)
    except Exception as e:
        print(f"  Warning: could not write sentinel log: {e}")


def run_all_topics() -> None:
    """
    Main sentinel function.
    Reads topics.json and runs the pipeline for each topic.
    """

    topics = load_topics()

    print(f"\n{'='*50}")
    print(f"Sentinel started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tracking {len(topics)} topic(s): {topics}")
    print(f"{'='*50}")

    total_new = 0
    for topic in topics:
        result = check_topic(topic)
        total_new += result["new_papers"]

    print(f"\n{'='*50}")
    print(f"Sentinel complete!")
    print(f"Total new papers added: {total_new}")
    print(f"Topics tracked: {topics}")
    print(f"{'='*50}\n")

    _log_run(total_new, topics)


if __name__ == "__main__":
    run_all_topics()