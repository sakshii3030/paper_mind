import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

SIMILARITY_THRESHOLD = 0.60
CO_OCCUR_THRESHOLD = 2


def get_driver():
    return GraphDatabase.driver(URI, auth=(USER, PASSWORD))


# ── 1. SIMILAR_TO ──────────────────────────────────────────
def add_similarity_edges(processed_path: str = "data/processed/papers.json"):
    """
    Compute semantic similarity between paper summaries.
    Add SIMILAR_TO edges where score > threshold.
    """
    print("\n[1/4] Adding SIMILAR_TO edges...")

    with open(processed_path, "r") as f:
        papers = json.load(f)

    papers = [p for p in papers if p.get("processed") and p.get("summary")]
    print(f"  Loading sentence-transformers model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    texts = [f"{p['title']}. {p['summary']}" for p in papers]
    print(f"  Computing embeddings for {len(papers)} papers...")
    embeddings = model.encode(texts, show_progress_bar=False)

    print(f"  Computing similarity matrix...")
    sim_matrix = cosine_similarity(embeddings)

    driver = get_driver()
    edge_count = 0

    with driver.session() as session:
        # clear old similarity edges first
        session.run("MATCH ()-[r:SIMILAR_TO]->() DELETE r")

        for i in range(len(papers)):
            for j in range(i + 1, len(papers)):
                score = float(sim_matrix[i][j])
                if score >= SIMILARITY_THRESHOLD:
                    session.run("""
                        MATCH (p1:Paper {id: $id1})
                        MATCH (p2:Paper {id: $id2})
                        MERGE (p1)-[:SIMILAR_TO {score: $score}]->(p2)
                        MERGE (p2)-[:SIMILAR_TO {score: $score}]->(p1)
                    """, {
                        "id1": papers[i]["id"],
                        "id2": papers[j]["id"],
                        "score": round(score, 4)
                    })
                    edge_count += 1

    driver.close()
    print(f"  ✓ Added {edge_count} SIMILAR_TO edges "
          f"(threshold: {SIMILARITY_THRESHOLD})")
    return edge_count


# ── 2. CO_OCCURS_WITH ──────────────────────────────────────
def add_co_occurrence_edges(processed_path: str = "data/processed/papers.json"):
    """
    Find concepts that appear together in multiple papers.
    Add CO_OCCURS_WITH edges with a count.
    """
    print("\n[2/4] Adding CO_OCCURS_WITH edges...")

    with open(processed_path, "r") as f:
        papers = json.load(f)

    # count concept co-occurrences
    from collections import defaultdict
    co_occur = defaultdict(int)

    for paper in papers:
        concepts = [c.strip().lower() for c in paper.get("concepts", [])]
        for i in range(len(concepts)):
            for j in range(i + 1, len(concepts)):
                pair = tuple(sorted([concepts[i], concepts[j]]))
                co_occur[pair] += 1

    driver = get_driver()
    edge_count = 0

    with driver.session() as session:
        session.run("MATCH ()-[r:CO_OCCURS_WITH]->() DELETE r")

        for (c1, c2), count in co_occur.items():
            if count >= CO_OCCUR_THRESHOLD:
                session.run("""
                    MATCH (c1:Concept {name: $name1})
                    MATCH (c2:Concept {name: $name2})
                    MERGE (c1)-[:CO_OCCURS_WITH {count: $count}]->(c2)
                    MERGE (c2)-[:CO_OCCURS_WITH {count: $count}]->(c1)
                """, {
                    "name1": c1,
                    "name2": c2,
                    "count": count
                })
                edge_count += 1

    driver.close()
    print(f"  ✓ Added {edge_count} CO_OCCURS_WITH edges "
          f"(threshold: {CO_OCCUR_THRESHOLD}+ papers)")
    return edge_count


# ── 3. SAME_AUTHOR ─────────────────────────────────────────
def add_same_author_edges():
    """
    Connect papers written by the same author.
    """
    print("\n[3/4] Adding SAME_AUTHOR edges...")

    driver = get_driver()
    edge_count = 0

    with driver.session() as session:
        session.run("MATCH ()-[r:SAME_AUTHOR]->() DELETE r")

        result = session.run("""
            MATCH (a:Author)-[:AUTHORED]->(p1:Paper)
            MATCH (a)-[:AUTHORED]->(p2:Paper)
            WHERE p1 <> p2
            RETURN a.name AS author, p1.id AS id1, p2.id AS id2
        """)

        pairs_added = set()
        for record in result:
            pair = tuple(sorted([record["id1"], record["id2"]]))
            if pair not in pairs_added:
                session.run("""
                    MATCH (p1:Paper {id: $id1})
                    MATCH (p2:Paper {id: $id2})
                    MERGE (p1)-[:SAME_AUTHOR]->(p2)
                """, {"id1": pair[0], "id2": pair[1]})
                pairs_added.add(pair)
                edge_count += 1

    driver.close()
    print(f"  ✓ Added {edge_count} SAME_AUTHOR edges")
    return edge_count


# ── 4. CITES ───────────────────────────────────────────────
def add_citation_edges(processed_path: str = "data/processed/papers.json"):
    """
    Add CITES edges between papers that exist in our graph.
    Uses arXiv IDs found in the paper metadata.
    """
    print("\n[4/4] Adding CITES edges...")

    with open(processed_path, "r") as f:
        papers = json.load(f)

    known_ids = {p["id"] for p in papers}
    driver = get_driver()
    edge_count = 0

    with driver.session() as session:
        session.run("MATCH ()-[r:CITES]->() DELETE r")

        for paper in papers:
            # arXiv stores references in categories sometimes
            # we match by finding IDs mentioned in abstracts
            abstract = paper.get("abstract", "")
            for other_id in known_ids:
                if other_id != paper["id"] and other_id in abstract:
                    session.run("""
                        MATCH (p1:Paper {id: $id1})
                        MATCH (p2:Paper {id: $id2})
                        MERGE (p1)-[:CITES]->(p2)
                    """, {"id1": paper["id"], "id2": other_id})
                    edge_count += 1

    driver.close()
    print(f"  ✓ Added {edge_count} CITES edges")
    return edge_count


# ── Run all ────────────────────────────────────────────────
def build_all_relationships():
    """Build all 4 relationship types."""

    print("\n" + "="*50)
    print("Building all relationships...")
    print("="*50)

    r1 = add_similarity_edges()
    r2 = add_co_occurrence_edges()
    r3 = add_same_author_edges()
    r4 = add_citation_edges()

    print("\n" + "="*50)
    print("All relationships built!")
    print(f"  SIMILAR_TO     : {r1} edges")
    print(f"  CO_OCCURS_WITH : {r2} edges")
    print(f"  SAME_AUTHOR    : {r3} edges")
    print(f"  CITES          : {r4} edges")
    print("="*50)


if __name__ == "__main__":
    build_all_relationships()