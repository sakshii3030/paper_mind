import json

def parse_paper(raw_paper: dict) -> dict:
    """Clean and structure a single raw paper."""
    return {
        "id": raw_paper.get("id", ""),
        "title": raw_paper.get("title", "").strip(),
        "abstract": raw_paper.get("abstract", "").strip().replace("\n", " "),
        "authors": raw_paper.get("authors", [])[:10],
        "year": raw_paper.get("published", "")[:4],
        "published": raw_paper.get("published", "")[:10],
        "url": raw_paper.get("url", ""),
        "pdf_url": raw_paper.get("pdf_url", ""),
        "categories": raw_paper.get("categories", []),
    }

def parse_all(filepath: str = "data/raw/papers.json") -> list:
    """Parse all raw papers."""
    with open(filepath, "r") as f:
        raw_papers = json.load(f)

    parsed = [parse_paper(p) for p in raw_papers]
    print(f"Parsed {len(parsed)} papers.")
    return parsed