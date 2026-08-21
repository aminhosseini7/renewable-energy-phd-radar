import sqlite3
from pathlib import Path

DB=Path('data/opportunities.db')

def init():
    DB.parent.mkdir(exist_ok=True)
    con=sqlite3.connect(DB)

    con.execute('''
    CREATE TABLE IF NOT EXISTS opportunities(
        url TEXT PRIMARY KEY,
        source TEXT,
        score INTEGER,
        funding TEXT,
        deadline TEXT,
        discovered TEXT
    )
    ''')

    con.commit()
    con.close()


def exists(url):
    con=sqlite3.connect(DB)
    cur=con.execute(
        'SELECT url FROM opportunities WHERE url=?',
        (url,)
    )
    result=cur.fetchone()
    con.close()
    return result is not None
