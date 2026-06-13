# query/cypher.py
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from graph.connector import get_driver

def get_top_concepts(limit=10):
    """Most frequently occurring concepts across all papers."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Paper)-[:HAS_CONCEPT]->(c:Concept)
            RETURN c.name AS concept, count(p) AS paper_count
            ORDER BY paper_count DESC
            LIMIT $limit
        """, limit=limit)
        return [{"concept": r["concept"], "count": r["paper_count"]} for r in result]

def get_top_authors(limit=10):
    """Most prolific authors by paper count."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run("""
            MATCH (a:Author)-[:AUTHORED]->(p:Paper)
            RETURN a.name AS author, count(p) AS paper_count
            ORDER BY paper_count DESC
            LIMIT $limit
        """, limit=limit)
        return [{"author": r["author"], "count": r["paper_count"]} for r in result]

# Replace the get_most_similar_papers function in query/cypher.py

def get_most_similar_papers(paper_title_fragment, limit=5):
    """Find papers most similar to a given paper (by SIMILAR_TO edges).
    Searches by title fragment first, then falls back to concept match."""
    driver = get_driver()
    with driver.session() as session:
        # Try title match first
        result = session.run("""
            MATCH (p:Paper)-[s:SIMILAR_TO]->(q:Paper)
            WHERE toLower(p.title) CONTAINS toLower($fragment)
            RETURN p.title AS source, q.title AS title, q.summary AS summary, q.url AS url, s.score AS score
            ORDER BY score DESC
            LIMIT $limit
        """, fragment=paper_title_fragment, limit=limit)
        rows = list(result)

        # Fallback: search via concept name
        if not rows:
            result = session.run("""
                MATCH (p:Paper)-[:HAS_CONCEPT]->(c:Concept)
                WHERE toLower(c.name) CONTAINS toLower($fragment)
                WITH p LIMIT 1
                MATCH (p)-[s:SIMILAR_TO]->(q:Paper)
                RETURN p.title AS source, q.title AS title, q.summary AS summary, q.url AS url, s.score AS score
                ORDER BY score DESC
                LIMIT $limit
            """, fragment=paper_title_fragment, limit=limit)
            rows = list(result)

        if not rows:
            return []
        return [{"source": r["source"], "title": r["title"], "summary": r["summary"],
                 "url": r["url"], "score": round(r["score"], 3)} for r in rows]

def get_papers_by_concept(concept_name, limit=10):
    """Find papers that contain a given concept."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Paper)-[:HAS_CONCEPT]->(c:Concept)
            WHERE toLower(c.name) CONTAINS toLower($concept)
            RETURN p.title AS title, p.summary AS summary, p.published AS published, p.url AS url
            ORDER BY p.published DESC
            LIMIT $limit
        """, concept=concept_name, limit=limit)
        return [{"title": r["title"], "summary": r["summary"], "published": r["published"], "url": r["url"]} for r in result]

def get_papers_by_author(author_name, limit=10):
    """Find all papers by an author."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run("""
            MATCH (a:Author)-[:AUTHORED]->(p:Paper)
            WHERE toLower(a.name) CONTAINS toLower($name)
            RETURN p.title AS title, p.summary AS summary, p.published AS published, p.url AS url
            ORDER BY p.published DESC
            LIMIT $limit
        """, name=author_name, limit=limit)
        return [{"title": r["title"], "summary": r["summary"], "published": r["published"], "url": r["url"]} for r in result]

def get_recent_papers(limit=10):
    """Most recently published papers in the graph."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Paper)
            WHERE p.published IS NOT NULL
            RETURN p.title AS title, p.published AS published, p.url AS url
            ORDER BY p.published DESC
            LIMIT $limit
        """, limit=limit)
        return [{"title": r["title"], "published": r["published"], "url": r["url"]} for r in result]

def get_graph_stats():
    """Overall graph statistics."""
    driver = get_driver()
    with driver.session() as session:
        stats = {}
        for label in ["Paper", "Author", "Concept"]:
            r = session.run(f"MATCH (n:{label}) RETURN count(n) AS count").single()
            stats[label.lower() + "s"] = r["count"]
        for rel in ["AUTHORED", "HAS_CONCEPT", "SIMILAR_TO", "CO_OCCURS_WITH", "SAME_AUTHOR"]:
            r = session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS count").single()
            stats[rel.lower()] = r["count"]
        return stats

def get_co_occurring_concepts(concept_name, limit=10):
    """Find concepts that frequently co-occur with a given concept."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run("""
            MATCH (c1:Concept)-[r:CO_OCCURS_WITH]->(c2:Concept)
            WHERE toLower(c1.name) CONTAINS toLower($concept)
            RETURN c2.name AS related_concept, r.count AS count
            ORDER BY count DESC
            LIMIT $limit
        """, concept=concept_name, limit=limit)
        return [{"concept": r["related_concept"], "count": r["count"]} for r in result]