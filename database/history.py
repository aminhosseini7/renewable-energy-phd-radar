import sqlite3
from pathlib import Path

DB=Path("data/history.db")

def init():
    DB.parent.mkdir(exist_ok=True)
    con=sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS opportunities(url TEXT PRIMARY KEY)")
    con.commit()
    con.close()
