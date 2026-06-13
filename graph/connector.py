from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

def get_driver():
    return GraphDatabase.driver(URI, auth=(USER, PASSWORD))

def test_connection():
    try:
        driver = get_driver()
        with driver.session() as session:
            result = session.run("RETURN 'Connected!' AS message")
            record = result.single()
            print(f"Success: {record['message']}")
        driver.close()
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    print("Testing Neo4j connection...")
    test_connection()