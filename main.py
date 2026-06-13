import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.sentinel import run_all_topics

def main():
    """Run one full pipeline cycle: fetch → parse → summarize → write to graph."""
    print("Running knowledge graph pipeline...\n")
    run_all_topics()
    print("\nDone. Start the app with: streamlit run app.py")

if __name__ == "__main__":
    main()
