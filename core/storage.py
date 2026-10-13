"""Local SQLite ledger. Atomic migrations, serialized writes, idempotent events."""
import csv
import io
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

STATES = ('AVAILABLE','TAKEN','UNKNOWN','RATE_LIMITED','AUTH_REQUIRED','ERROR','UNSUPPORTED')
class StorageError(RuntimeError): pass

def csv_text(rows, fields):
    output = io.StringIO(newline=''); writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore'); writer.writeheader()
    for row in rows:
        clean = {}
        for key in fields:
            value = row.get(key, '')
            if isinstance(value, (dict,list)): value = json.dumps(value,ensure_ascii=False)
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r')): value = "'"+value
            clean[key] = value
        writer.writerow(clean)
    return output.getvalue()

class Store:
    def __init__(self, path):
        self.path = str(path); self.lock = threading.RLock(); self.warning = ''; self.db = None
        try:
            Path(path).parent.mkdir(parents=True,exist_ok=True)
            try: self._open()
            except sqlite3.DatabaseError as exc:
                if getattr(exc,'sqlite_errorcode',None) not in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB): raise
                if self.db: self.db.close(); self.db = None
                backup = str(path)+'.corrupt-'+str(time.time_ns())
                for suffix in ('','-wal','-shm'):
                    if os.path.exists(str(path)+suffix): os.replace(str(path)+suffix,backup+suffix)
                self.warning = 'Banco corrompido preservado para recuperação. Um novo banco foi criado.'
                self._open()
        except (OSError,sqlite3.Error,StorageError) as exc:
            if self.db: self.db.close(); self.db = None
            self.warning = 'Armazenamento indisponível: '+type(exc).__name__

    def _open(self):
        self.db = sqlite3.connect(self.path,timeout=5,check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=5000'); self.db.execute('PRAGMA foreign_keys=ON')
        check = self.db.execute('PRAGMA quick_check').fetchone()[0]
        if check != 'ok':
            exc=sqlite3.DatabaseError('corrupt'); exc.sqlite_errorcode=sqlite3.SQLITE_CORRUPT; raise exc
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        if version > 3: raise StorageError('Unsupported schema version')
        self.db.execute('PRAGMA journal_mode=WAL'); self.db.execute('PRAGMA synchronous=NORMAL')
        if version == 0:
            self.db.executescript('''BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, kind TEXT NOT NULL, platform TEXT NOT NULL,
              method TEXT NOT NULL, started REAL NOT NULL, ended REAL, status TEXT NOT NULL, generated INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events(session_id TEXT NOT NULL REFERENCES sessions(id), event_key TEXT NOT NULL,
              platform TEXT NOT NULL, at REAL NOT NULL, status TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 1,
              elapsed REAL NOT NULL DEFAULT 0, verified INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(session_id,event_key));
            CREATE INDEX IF NOT EXISTS event_period ON events(at,platform,status);
            CREATE INDEX IF NOT EXISTS session_period ON sessions(started,platform);
            CREATE TABLE IF NOT EXISTS identity_results(session_id TEXT NOT NULL REFERENCES sessions(id), result_key TEXT NOT NULL,
              username TEXT NOT NULL, platform TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL,
              elapsed REAL NOT NULL, verified INTEGER NOT NULL, profile_url TEXT, signup_url TEXT, suggestion INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY(session_id,result_key));
            CREATE TABLE IF NOT EXISTS presets(id TEXT PRIMARY KEY, name TEXT NOT NULL, rules TEXT NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS favorites(username TEXT PRIMARY KEY, added REAL NOT NULL);
            PRAGMA user_version=1;
            COMMIT;''')
        if version < 2:
            self.db.executescript('BEGIN IMMEDIATE; ALTER TABLE identity_results ADD COLUMN input_username TEXT; PRAGMA user_version=2; COMMIT;')
        if version < 3:
            self.db.executescript('BEGIN IMMEDIATE; ALTER TABLE sessions ADD COLUMN archived INTEGER NOT NULL DEFAULT 0; PRAGMA user_version=3; COMMIT;')
        with self.db: self.db.execute("UPDATE sessions SET status='interrupted',ended=? WHERE status='running'",(time.time(),))

    def _ready(self):
        if not self.db: raise StorageError(self.warning or 'Armazenamento indisponível.')
    def _run(self, fn):
        with self.lock:
            self._ready()
            try:
                with self.db: return fn(self.db)
            except sqlite3.Error as exc:
                self.warning = 'Falha ao salvar ou consultar estatísticas: '+type(exc).__name__
                raise StorageError(self.warning) from exc
    def begin(self, kind, platform, method, session_id=None):
        sid = session_id or str(uuid.uuid4())
        self._run(lambda db: db.execute('INSERT INTO sessions(id,kind,platform,method,started,status) VALUES(?,?,?,?,?,?)',
                                        (sid,kind,platform,method,time.time(),'running')))
        return sid
    def finish(self, sid, status):
        self._run(lambda db: db.execute("UPDATE sessions SET ended=?,status=? WHERE id=? AND status='running'",(time.time(),status,sid)))
    def event(self,sid,key,platform,status,quantity=1,elapsed=0,verified=False,result=None):
        if status not in STATES+('GENERATED',): raise ValueError('Estado inválido.')
        if type(quantity) is not int or quantity < 1: raise ValueError('Quantidade inválida.')
        def write(db):
            cursor=db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,?)',
                             (sid,str(key),platform,time.time(),status,quantity,max(0,elapsed),int(verified)))
            if cursor.rowcount and status=='GENERATED': db.execute('UPDATE sessions SET generated=generated+? WHERE id=?',(quantity,sid))
            if result and cursor.rowcount:
                db.execute('INSERT INTO identity_results VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                           (sid,str(key),result['username'],platform,status,result['detail'],max(0,elapsed),int(verified),
                            result.get('profile_url'),result.get('signup_url'),int(result.get('suggestion',False)),result.get('input_username',result['username'])))
            return bool(cursor.rowcount)
        return self._run(write)
    def identity_history(self, sid=None):
        def query(db):
            if sid:
                rows = db.execute('SELECT * FROM identity_results WHERE session_id=? ORDER BY rowid',(sid,)).fetchall()
                return [dict(r) for r in rows]
            return [dict(r) for r in db.execute("SELECT s.*,count(r.result_key) AS checked FROM sessions s LEFT JOIN identity_results r ON r.session_id=s.id WHERE s.kind='identity' GROUP BY s.id ORDER BY s.started DESC LIMIT 200")]
        return self._run(query)
    def manage_session(self, sid, action):
        if not re_uuid(sid): raise ValueError('Sessão inválida.')
        if action not in ('archive', 'restore', 'delete'): raise ValueError('Ação inválida.')
        def write(db):
            row = db.execute('SELECT status FROM sessions WHERE id=?', (sid,)).fetchone()
            if not row: raise ValueError('Sessão não encontrada.')
            if row['status'] == 'running': raise ValueError('Aguarde a sessão terminar antes de alterar o histórico.')
            if action == 'delete':
                db.execute('DELETE FROM identity_results WHERE session_id=?', (sid,))
                db.execute('DELETE FROM events WHERE session_id=?', (sid,))
                db.execute('DELETE FROM sessions WHERE id=?', (sid,))
            else:
                db.execute('UPDATE sessions SET archived=? WHERE id=?', (int(action == 'archive'), sid))
        self._run(write)

    def analytics(self, platform='', period='all', search=''):
        days={'hour':1/24,'day':1,'week':7,'month':30,'all':None}
        if period not in days: raise ValueError('Período inválido.')
        since=time.time()-days[period]*86400 if days[period] else 0
        def query(db):
            params=[since]; where='e.at>=?'
            if platform: where+=' AND e.platform=?'; params.append(platform)
            states={k:0 for k in STATES}; generated=verified=0; byplatform={}; buckets={}
            bucket=60 if period=='hour' else 3600 if period in ('day','week') else 86400
            grouped=db.execute('SELECT e.platform,e.status,SUM(e.quantity) AS quantity,SUM(e.verified*e.quantity) AS checked,SUM(e.elapsed) AS elapsed FROM events e WHERE '+where+' GROUP BY e.platform,e.status',params)
            for event in grouped:
                p=byplatform.setdefault(event['platform'],dict(platform=event['platform'],verified=0,available=0,taken=0,unknown=0,errors=0,elapsed=0))
                if event['status']=='GENERATED': generated+=event['quantity']; continue
                states[event['status']]+=event['quantity']; verified+=event['checked']
                p['verified']+=event['checked']; p['elapsed']+=event['elapsed']
                p['available']+=event['quantity'] if event['status']=='AVAILABLE' else 0
                p['taken']+=event['quantity'] if event['status']=='TAKEN' else 0
                p['unknown']+=event['quantity'] if event['status'] in ('UNKNOWN','RATE_LIMITED','AUTH_REQUIRED','UNSUPPORTED') else 0
                p['errors']+=event['quantity'] if event['status']=='ERROR' else 0
            if bucket==86400:
                stamp_sql="CAST(strftime('%s',date(e.at,'unixepoch','localtime'),'utc') AS INTEGER)"
                timeline_params=params
            else:
                stamp_sql='CAST(e.at/? AS INTEGER)*?'; timeline_params=[bucket,bucket]+params
            timeline=db.execute('SELECT '+stamp_sql+' AS stamp,SUM(e.quantity) AS count FROM events e WHERE '+where+' AND e.verified=1 GROUP BY stamp ORDER BY stamp',timeline_params)
            buckets={r['stamp']:r['count'] for r in timeline}
            for p in byplatform.values():
                p['speed']=p['verified']/p['elapsed'] if p['elapsed'] else 0
                p['conclusive_rate']=(p['available']+p['taken'])/p['verified'] if p['verified'] else 0
            # Filter sessions by matching events, so identity sessions can be filtered by their individual platform.
            session_where='(s.started>=? OR EXISTS(SELECT 1 FROM events e WHERE e.session_id=s.id AND e.at>=?))'; session_params=[since,since]
            if platform:
                session_where+=' AND (s.platform=? OR EXISTS(SELECT 1 FROM events e WHERE e.session_id=s.id AND e.platform=? AND e.at>=?))'
                session_params += [platform,platform,since]
            now=time.time()
            duration_sql='MAX(0,COALESCE(s.ended,?)-MAX(s.started,?))'
            totals=db.execute('SELECT COUNT(*),COALESCE(SUM('+duration_sql+'),0),COALESCE(SUM(CASE WHEN s.kind!=\'generator\' THEN '+duration_sql+' ELSE 0 END),0) FROM sessions s WHERE '+session_where,[now,since,now,since]+session_params).fetchone()
            processing,checking=totals[1],totals[2]
            search_sql=" AND INSTR(LOWER(s.id||' '||s.platform||' '||s.method||' '||s.status),?)>0"
            history=[dict(row) for archived in (0,1) for row in db.execute('SELECT s.* FROM sessions s WHERE '+session_where+search_sql+' AND s.archived=? ORDER BY s.started DESC LIMIT 200',session_params+[search.lower(),archived])]
            for session in history:
                stat=db.execute('SELECT SUM(verified*quantity),SUM(CASE WHEN status=\'AVAILABLE\' THEN quantity ELSE 0 END) FROM events WHERE session_id=? AND at>=?'+(' AND platform=?' if platform else ''),[session['id'],since]+([platform] if platform else [])).fetchone()
                session.update(verified=stat[0] or 0,available=stat[1] or 0,duration=max(0,(session['ended'] or now)-max(session['started'],since)))
            denominator=states['AVAILABLE']+states['TAKEN']
            best=max(byplatform.values(),key=lambda p:p['available'],default=None)
            return dict(generated=generated,verified=verified,available=states['AVAILABLE'],taken=states['TAKEN'],
                        unknown=sum(states[k] for k in ('UNKNOWN','RATE_LIMITED','AUTH_REQUIRED','UNSUPPORTED')),errors=states['ERROR'],
                        availability_rate=states['AVAILABLE']/denominator if denominator else None,
                        speed=verified/checking if checking else 0,processing_seconds=processing,
                        best_platform=best['platform'] if best and best['available'] else None,
                        distribution=states,platforms=list(byplatform.values()),
                        timeline=[{'at':at,'verified':n} for at,n in sorted(buckets.items())],bucket_seconds=bucket,
                        sessions=[s for s in history if not s['archived']],archived_sessions=[s for s in history if s['archived']],session_count=totals[0],warning=self.warning)
        return self._run(query)
    def export_analytics(self, fmt, **filters):
        data=self.analytics(**filters)
        if fmt=='json': return json.dumps(data,ensure_ascii=False,indent=2)
        if fmt=='csv':
            def query(db):
                days={'hour':1/24,'day':1,'week':7,'month':30,'all':None}; day=days[filters.get('period','all')]; since=time.time()-day*86400 if day else 0
                where='e.at>=?'; params=[since]
                if filters.get('platform'): where+=' AND e.platform=?'; params.append(filters['platform'])
                rows=[dict(r) for r in db.execute('SELECT e.*,s.kind,s.method,s.started,s.ended,s.status AS session_status FROM events e JOIN sessions s ON s.id=e.session_id WHERE '+where+' ORDER BY e.at',params)]
                return csv_text(rows,['session_id','event_key','platform','kind','method','at','status','quantity','elapsed','verified','started','ended','session_status'])
            return self._run(query)
        raise ValueError('Formato inválido.')
    def saved_presets(self):
        return self._run(lambda db:[dict(r, rules=json.loads(r['rules']), builtin=False) for r in db.execute('SELECT * FROM presets ORDER BY name')])
    def save_preset(self,name,rules,pid=None):
        if not isinstance(name,str) or not name.strip() or len(name)>60: raise ValueError('Nome do preset inválido.')
        if pid and not re_uuid(pid): raise ValueError('Preset inválido.')
        pid=pid or str(uuid.uuid4())
        self._run(lambda db:db.execute('INSERT INTO presets VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,rules=excluded.rules,updated=excluded.updated',
                                       (pid,name.strip(),json.dumps(rules,ensure_ascii=False),time.time())))
        return pid
    def delete_preset(self,pid): self._run(lambda db:db.execute('DELETE FROM presets WHERE id=?',(pid,)))
    def favorites(self): return self._run(lambda db:[r[0] for r in db.execute('SELECT username FROM favorites ORDER BY added DESC LIMIT 10000')])
    def favorite(self,name,active):
        if not isinstance(name,str) or not 1<=len(name)<=255 or any(ord(c)<32 for c in name): raise ValueError('Username inválido.')
        if type(active) is not bool: raise ValueError('Opção inválida.')
        if active: self._run(lambda db:db.execute('INSERT OR IGNORE INTO favorites VALUES(?,?)',(name,time.time())))
        else: self._run(lambda db:db.execute('DELETE FROM favorites WHERE username=?',(name,)))
    def close(self):
        with self.lock:
            if self.db: self.db.close(); self.db=None

def re_uuid(value):
    try: return isinstance(value,str) and str(uuid.UUID(value))==value
    except (ValueError,AttributeError): return False
