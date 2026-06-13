import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from agents.sentinel import run_all_topics
from datetime import datetime

def run_sentinel():
    try:
        run_all_topics()
        print(f"[{datetime.now()}] Sentinel cycle complete.")
    except Exception as e:
        print(f"[{datetime.now()}] Sentinel error: {e}")

if __name__ == "__main__":
    print("Knowledge Graph Scheduler starting...")
    print("Topics are loaded from topics.json")
    print("Add new topics with: python add_paper.py --topic 'your topic'")
    print("Running first check now...\n")

    run_sentinel()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_sentinel,
        trigger=IntervalTrigger(hours=24),
        id="sentinel",
        name="Knowledge Graph Sentinel",
        replace_existing=True
    )

    print(f"\nNext check in 24 hours. Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\nScheduler stopped.")
        scheduler.shutdown()