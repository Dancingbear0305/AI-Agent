"""SQLite compatibility and MySQL 8 adapter. Credentials never enter source control."""
import os, re
from contextlib import contextmanager
from pathlib import Path

def load_env(path):
    if not path.exists(): return
    for line in path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        key,sep,value=line.partition('=')
        if not sep or not re.fullmatch(r'[A-Z][A-Z0-9_]*',key): raise RuntimeError('Invalid .env format')
        value=value.strip()
        if len(value)>=2 and value[0]==value[-1] and value[0] in "\"'": value=value[1:-1]
        os.environ.setdefault(key,value)

class MySQL:
    def __init__(self, conn): self.conn=conn
    def execute(self, sql, args=()):
        if sql=='BEGIN IMMEDIATE':
            # Reads use autocommit. Explicit revision transactions serialize on a singleton row.
            self.conn.begin()
            cur=self.conn.cursor();cur.execute('SELECT id FROM lab_lock WHERE id=1 FOR UPDATE');return cur
        cur=self.conn.cursor();cur.execute(sql.replace('?','%s'),args);return cur
    def executescript(self, script):
        for sql in script.split(';'):
            if not sql.strip():continue
            sql=sql.replace('INTEGER PRIMARY KEY','BIGINT PRIMARY KEY AUTO_INCREMENT')
            sql=re.sub(r'\bINTEGER\b','BIGINT',sql)
            sql=re.sub(r'\bTEXT\b','LONGTEXT',sql)
            # Expand inline references into actual foreign keys on MySQL.
            refs=re.findall(r'(\w+) BIGINT REFERENCES (\w+)\((\w+)\)',sql)
            sql=re.sub(r' REFERENCES \w+\(\w+\)','',sql)
            if refs:
                pos=sql.rfind(')');sql=sql[:pos]+''.join(f', FOREIGN KEY ({a}) REFERENCES {b}({c})' for a,b,c in refs)+sql[pos:]
            self.execute(sql)

@contextmanager
def mysql_connection():
    import pymysql
    password=os.environ.get('DB_PASSWORD')
    if not password: raise RuntimeError('MySQL requires DB_PASSWORD in local .env or environment')
    settings=dict(user=os.environ.get('DB_USER','cindy_app'),password=password,database=os.environ.get('DB_NAME','cindydb'),charset='utf8mb4',autocommit=True,cursorclass=pymysql.cursors.DictCursor,connect_timeout=8)
    socket=os.environ.get('DB_SOCKET','')
    if socket:settings['unix_socket']=socket
    else:settings.update(host=os.environ.get('DB_HOST','127.0.0.1'),port=int(os.environ.get('DB_PORT','3306')))
    conn=pymysql.connect(**settings)
    try:
        yield MySQL(conn)
        conn.commit()
    except Exception:
        conn.rollback();raise
    finally:conn.close()
