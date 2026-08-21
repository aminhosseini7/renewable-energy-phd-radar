import sqlite3
from pathlib import Path

DB = Path("data/radar.db")

def init():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)

    con.execute('''
    CREATE TABLE IF NOT EXISTS opportunities(
        url TEXT PRIMARY KEY,
        title TEXT,
        source TEXT,
        score INTEGER,
        funding TEXT,
        deadline TEXT
    )
    ''')

    con.commit()
    con.close()
