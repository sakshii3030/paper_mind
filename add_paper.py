import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

import sys
import json
import re
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


import arxiv
from agents.parser import parse_paper
from agents.summarizer import summarize_paper
from graph.writer import write_all_papers
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

TOPICS_FILE = "topics.json"
PROCESSED_PATH = "data/processed/papers.json"


def load_topics() -> list:
    if not os.path.exists(TOPICS_FILE):
        return ["mechanistic interpretability"]
    with open(TOPICS_FILE, "r") as f:
        return json.load(f)


def save_topics(topics: list) -> None:
    with open(TOPICS_FILE, "w") as f:
        json.dump(topics, f, indent=2)
    print(f"  topics.json updated: {topics}")


def add_topic_if_new(topic: str) -> bool:
    """Add topic to topics.json if not already there. Returns True if added."""
    topic = topic.strip().lower()
    topics = load_topics()
    if topic not in [t.lower() for t in topics]:
        topics.append(topic)
        save_topics(topics)
        print(f"  New topic '{topic}' added to topics.json")
        print(f"  Sentinel will now track this topic every 24 hours.")
        return True
    else:
        print(f"  Topic '{topic}' already being tracked.")
        return False


def extract_arxiv_id(url_or_id: str) -> str:
    """Extract arXiv ID from URL or return as-is if already an ID."""
    match = re.search(r'arxiv\.org/abs/([^\s/]+)', url_or_id)
    if match:
        return match.group(1)
    if re.match(r'^\d{4}\.\d{4,5}', url_or_id):
        return url_or_id
    return None


def fetch_by_id(arxiv_id: str) -> dict:
    """Fetch a single paper by arXiv ID."""
    client = arxiv.Client()
    search = arxiv.Search(id_list=[arxiv_id])
    results = list(client.results(search))
    if not results:
        return None
    result = results[0]
    return {
        "id": result.entry_id.split("/")[-1],
        "title": result.title,
        "abstract": result.summary,
        "authors": [a.name for a in result.authors][:10],
        "published": result.published.isoformat(),
        "updated": result.updated.isoformat(),
        "url": result.entry_id,
        "pdf_url": result.pdf_url,
        "categories": result.categories,
        "fetched_at": __import__('datetime').datetime.now().isoformat()
    }


def fetch_by_name(title: str) -> dict:
    """Search arXiv by paper title and return best match."""
    client = arxiv.Client()
    search = arxiv.Search(
        query=f'ti:"{title}"',
        max_results=3,
        sort_by=arxiv.SortCriterion.Relevance
    )
    results = list(client.results(search))
    if not results:
        return None
    result = results[0]
    print(f"\nBest match found: {result.title}")
    confirm = input("Is this the right paper? (y/n): ").strip().lower()
    if confirm != 'y':
        return None
    return {
        "id": result.entry_id.split("/")[-1],
        "title": result.title,
        "abstract": result.summary,
        "authors": [a.name for a in result.authors][:10],
        "published": result.published.isoformat(),
        "updated": result.updated.isoformat(),
        "url": result.entry_id,
        "pdf_url": result.pdf_url,
        "categories": result.categories,
        "fetched_at": __import__('datetime').datetime.now().isoformat()
    }


def get_existing_ids() -> set:
    """Get all paper IDs already in the graph."""
    from graph.connector import get_driver
    driver = get_driver()
    with driver.session() as session:
        result = session.run("MATCH (p:Paper) RETURN p.id AS id")
        ids = {record["id"] for record in result}
    driver.close()
    return ids


def process_and_add_paper(raw_paper: dict) -> dict:
    """Parse, summarize and write a paper to the graph."""

    # parse
    print("\nParsing paper...")
    parsed = parse_paper(raw_paper)
    parsed["year"] = parsed["published"][:4]

    # summarize
    print("Summarizing with LLM...")
    processed = summarize_paper(parsed)

    if not processed.get("processed"):
        print("Summarization failed.")
        return None

    print(f"\nTitle       : {processed['title']}")
    print(f"Summary     : {processed['summary'][:120]}...")
    print(f"Concepts    : {', '.join(processed['concepts'])}")
    print(f"Contribution: {processed['contribution']}")

    # save to processed file
    os.makedirs("data/processed", exist_ok=True)
    existing = []
    if os.path.exists(PROCESSED_PATH):
        with open(PROCESSED_PATH, "r") as f:
            existing = json.load(f)

    existing_ids = {p["id"] for p in existing}
    if processed["id"] not in existing_ids:
        existing.append(processed)
        with open(PROCESSED_PATH, "w") as f:
            json.dump(existing, f, indent=2)

    # write to graph
    print("\nWriting to knowledge graph...")
    write_all_papers()

    return processed


def add_paper(input_str: str) -> None:
    """
    Add a paper by URL, arXiv ID, or title.
    Also asks if the user wants to track that topic going forward.
    """

    print(f"\nAdding paper: '{input_str}'\n")

    existing_ids = get_existing_ids()
    arxiv_id = extract_arxiv_id(input_str)

    # fetch the paper
    if arxiv_id:
        print(f"Detected arXiv ID: {arxiv_id}")
        if arxiv_id in existing_ids:
            print("This paper is already in your graph!")
        else:
            raw_paper = fetch_by_id(arxiv_id)
            if not raw_paper:
                print("Paper not found on arXiv.")
                return
            processed = process_and_add_paper(raw_paper)
            if processed:
                print(f"\n✓ Paper added to graph!")
    else:
        print("Searching arXiv by title...")
        raw_paper = fetch_by_name(input_str)
        if not raw_paper:
            print("Paper not found or cancelled.")
            return
        if raw_paper["id"] in existing_ids:
            print("This paper is already in your graph!")
        else:
            processed = process_and_add_paper(raw_paper)
            if processed:
                print(f"\n✓ Paper added to graph!")
            else:
                return

    # always ask about topic tracking
    print(f"\n{'─'*50}")
    print("Do you want to track a related topic?")
    print("This will add a search query to topics.json")
    print("and the Sentinel will fetch papers on it every 24hrs.")
    print(f"{'─'*50}")
    track = input("\nEnter a topic to track (or press Enter to skip): ").strip()

    if track:
        add_topic_if_new(track)
        print(f"\n  The Sentinel will now search for '{track}' every 24 hours.")
        print(f"  Current topics being tracked:")
        for t in load_topics():
            print(f"    - {t}")


def add_topic_only(topic: str) -> None:
    """Just add a topic to tracking without adding a specific paper."""
    print(f"\nAdding topic: '{topic}' to tracking...")
    added = add_topic_if_new(topic)
    if added:
        print(f"\n✓ Done! Sentinel will now search for '{topic}' every 24 hours.")
        print(f"\nCurrent topics being tracked:")
        for t in load_topics():
            print(f"  - {t}")
    else:
        print(f"\nAlready tracking '{topic}'.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Add paper by URL  : python add_paper.py https://arxiv.org/abs/2406.04093")
        print("  Add paper by ID   : python add_paper.py 2406.04093")
        print('  Add paper by name : python add_paper.py "Attention is All You Need"')
        print('  Add topic only    : python add_paper.py --topic "sparse autoencoders"')
        sys.exit(1)

    if sys.argv[1] == "--topic":
        if len(sys.argv) < 3:
            print("Please provide a topic name.")
            sys.exit(1)
        add_topic_only(" ".join(sys.argv[2:]))
    else:
        input_str = " ".join(sys.argv[1:])
        add_paper(input_str)