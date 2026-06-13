import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")


def get_driver():
    return GraphDatabase.driver(URI, auth=(USER, PASSWORD))


def create_constraints(session):
    """Create uniqueness constraints for clean data."""
    session.run("CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE")
    session.run("CREATE CONSTRAINT author_name IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE")
    session.run("CREATE CONSTRAINT concept_name IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE")
    print("  Constraints created.")


def write_paper(session, paper):
    """Write a single paper node with its authors and concepts."""

    # create paper node
    session.run("""
        MERGE (p:Paper {id: $id})
        SET p.title = $title,
            p.abstract = $abstract,
            p.summary = $summary,
            p.contribution = $contribution,
            p.published = $published,
            p.year = $year,
            p.url = $url,
            p.pdf_url = $pdf_url
    """, {
        "id": paper.get("id", ""),
        "title": paper.get("title", ""),
        "abstract": paper.get("abstract", ""),
        "summary": paper.get("summary", ""),
        "contribution": paper.get("contribution", ""),
        "published": paper.get("published", ""),
        "year": paper.get("year", ""),
        "url": paper.get("url", ""),
        "pdf_url": paper.get("pdf_url", "")
    })

    # create author nodes and relationships
    for author in paper.get("authors", []):
        session.run("""
            MERGE (a:Author {name: $name})
            WITH a
            MATCH (p:Paper {id: $paper_id})
            MERGE (a)-[:AUTHORED]->(p)
        """, {"name": author, "paper_id": paper.get("id", "")})

    # create concept nodes and relationships
    for concept in paper.get("concepts", []):
        concept_clean = concept.strip().lower()
        if concept_clean:
            session.run("""
                MERGE (c:Concept {name: $name})
                WITH c
                MATCH (p:Paper {id: $paper_id})
                MERGE (p)-[:HAS_CONCEPT]->(c)
            """, {"name": concept_clean, "paper_id": paper.get("id", "")})


def write_all_papers(filepath: str = "data/processed/papers.json"):
    """Write all processed papers to Neo4j."""

    with open(filepath, "r") as f:
        papers = json.load(f)

    processed = [p for p in papers if p.get("processed")]
    print(f"Writing {len(processed)} papers to Neo4j...\n")

    driver = get_driver()
    with driver.session() as session:
        print("Setting up constraints...")
        create_constraints(session)

        for i, paper in enumerate(processed):
            write_paper(session, paper)
            if (i + 1) % 10 == 0:
                print(f"  Written {i+1}/{len(processed)} papers...")

    driver.close()
    print(f"\n✓ Done! {len(processed)} papers written to graph.")
    print("Open Neo4j browser and run: MATCH (n) RETURN n LIMIT 50")


def write_papers_to_graph(papers: list):
    """Write a list of processed paper dicts to Neo4j."""
    driver = get_driver()
    with driver.session() as session:
        create_constraints(session)
        for paper in papers:
            write_paper(session, paper)
    driver.close()


if __name__ == "__main__":
    write_all_papers()