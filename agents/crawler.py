import arxiv
import json
import os
from datetime import datetime

def fetch_papers(query: str, max_results: int = 100) -> list:
    """Fetch papers from arXiv based on a search query."""
    
    client = arxiv.Client()
    
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    
    papers = []
    for result in client.results(search):
        paper = {
            "id": result.entry_id.split("/")[-1],
            "title": result.title,
            "abstract": result.summary,
            "authors": [author.name for author in result.authors],
            "published": result.published.isoformat(),
            "updated": result.updated.isoformat(),
            "url": result.entry_id,
            "pdf_url": result.pdf_url,
            "categories": result.categories,
            "fetched_at": datetime.now().isoformat()
        }
        papers.append(paper)
        print(f"  Fetched: {result.title[:60]}...")
    
    return papers


def save_papers(papers: list, filepath: str = "data/raw/papers.json"):
    """Save papers to JSON, skipping duplicates."""
    
    existing_papers = []
    existing_ids = set()
    
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            existing_papers = json.load(f)
            existing_ids = {p["id"] for p in existing_papers}
    
    new_papers = [p for p in papers if p["id"] not in existing_ids]
    all_papers = existing_papers + new_papers
    
    with open(filepath, "w") as f:
        json.dump(all_papers, f, indent=2)
    
    return len(new_papers), len(all_papers)


if __name__ == "__main__":
    print("Fetching MI papers from arXiv...\n")
    
    papers = fetch_papers(
        query='all:"mechanistic interpretability"',
        max_results=100
    )
    new_count, total_count = save_papers(papers)
    
    print(f"\nDone!")
    print(f"New papers added : {new_count}")
    print(f"Total in database: {total_count}")
    
    if papers:
        print(f"\nSample paper:")
        print(f"  Title    : {papers[0]['title']}")
        print(f"  Authors  : {', '.join(papers[0]['authors'][:3])}")
        print(f"  Published: {papers[0]['published'][:10]}")
        print(f"  Abstract : {papers[0]['abstract'][:150]}...")