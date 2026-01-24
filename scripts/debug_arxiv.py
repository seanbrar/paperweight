"""Debug script for inspecting arxiv library and local mirror database."""

import inspect
import sqlite3
from pathlib import Path

import arxiv

# Use same path as populate_mirror.py
DB_PATH = Path("data/local_mirror/index.sqlite3")


def debug_arxiv():
    """Inspect the arxiv.Result class signature."""
    print("--- arxiv.Result Inspection ---")
    print(inspect.signature(arxiv.Result.__init__))

    # Check what fields are actually in the object
    try:
        r = arxiv.Result(entry_id="test", title="test")
        print("Created minimal Result:", r)
    except Exception as e:
        print("Creation failed:", e)


def debug_db():
    """Inspect the local mirror database contents."""
    print("\n--- DB Inspection ---")

    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        print("Run scripts/populate_mirror.py first.")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title FROM papers LIMIT 5")
        rows = cursor.fetchall()
        print("First 5 papers in DB:")
        for r in rows:
            print(r)

        # Check specific ID
        cursor.execute("SELECT * FROM papers WHERE id='1706.03762'")
        print("Check 1706.03762:", cursor.fetchone())
    finally:
        conn.close()


if __name__ == "__main__":
    debug_arxiv()
    debug_db()
