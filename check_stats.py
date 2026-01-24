import sys
sys.path.append('.')
from backend.storage import DataStorage

def check():
    db = DataStorage()
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT count(*) FROM news_articles')
        print('Articles:', cur.fetchone()[0])
        cur.execute('SELECT count(*) FROM skipped_events')
        print('Skipped:', cur.fetchone()[0])
        cur.execute('SELECT count(*) FROM error_events')
        print('Errors:', cur.fetchone()[0])

if __name__ == "__main__":
    check()
