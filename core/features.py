"""Feature orchestration; jobs never run on the HTTP or UI event loop."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from core.config import DATA_DIR
from core import advanced_generator as generator
from core.identity import PlatformGate, check_one, normalize, suggestions, safe_urls
from core.storage import Store, StorageError, csv_text
from platforms import PLATFORM_BY_NAME

class LedgerObserver:
    def __init__(self,store,sid,p): self.store=store; self.sid=sid; self.p=p; self.captured={}
    def generated(self,index):
        try: self.store.event(self.sid,'generated:'+str(index),self.p.name,'GENERATED')
        except StorageError: pass
    def capture(self,username,status,response):
        self.captured[username] = normalize(self.p,status,username,response)[0]
    def result(self,index,status,username='',elapsed=0,response=None):
        normalized,_=normalize(self.p,status,username,response)
        if status in ('available','taken') and username in self.captured: normalized=self.captured.pop(username)
        if status=='error': normalized='ERROR'
        if response is not None and response.status_code==429: normalized='RATE_LIMITED'
        if response is not None and response.status_code in (401,402,403): normalized='AUTH_REQUIRED'
        try: self.store.event(self.sid,'check:'+str(index),self.p.name,normalized,elapsed=elapsed,verified=True)
        except StorageError: pass
    def finish(self,status):
        try: self.store.finish(self.sid,status)
        except StorageError: pass

class Features:
    def __init__(self,session,path=None):
        self.session=session; self.store=Store(path or Path(DATA_DIR)/'activity.sqlite3'); self.lock=threading.RLock()
        self.jobs={}; self.current={}; self.gate=PlatformGate(); self.closed=False
        session.features=self
    @property
    def identity_running(self):
        with self.lock: return any(job['kind']=='identity' and job['status']=='running' for job in self.jobs.values())
    def legacy_observer(self,p,mode):
        try: return LedgerObserver(self.store,self.store.begin('legacy',p.name,mode),p)
        except StorageError: return None
    def _new(self,kind,platform,method,total):
        if self.closed: raise ValueError('O aplicativo está encerrando.')
        if any(j['kind']==kind and j['status']=='running' for j in self.jobs.values()): raise ValueError('Já existe uma operação deste tipo em execução.')
        sid=self.store.begin(kind,platform,method)
        job=dict(id=sid,kind=kind,status='running',total=total,done=0,results=[],names=[],error='',stop=threading.Event(),started=time.time())
        self.jobs[sid]=job; self.current[kind]=sid
        old=[key for key,value in self.jobs.items() if value['status']!='running']
        for key in old[:-6]: self.jobs.pop(key,None)
        return job
    def _finish(self,job,status,error=''):
        try: self.store.finish(job['id'],status)
        except StorageError as exc: error=str(exc)
        with self.lock: job['status']=status; job['error']=error
    def start_generator(self,rules):
        compiled=generator.compile_pattern(rules)
        interval=self.session.load_settings()['username_interval']
        with self.lock: job=self._new('generator','local',compiled.rules['pattern'],compiled.rules['amount'])
        def work():
            try:
                def update(count,attempts):
                    with self.lock: job['done']=count; job['attempts']=attempts
                report=generator.generate(compiled,job['stop'],update,interval=interval)
                with self.lock: job.update({k:v for k,v in report.items() if k!='status'}); job['done']=len(report['names'])
                if report['names']: self.store.event(job['id'],'generated','local','GENERATED',quantity=len(report['names']))
                self._finish(job,report['status'])
            except Exception as exc: self._finish(job,'failed','Falha na geração: '+type(exc).__name__)
        threading.Thread(target=work,daemon=True,name='advanced-generator').start()
        return {'ok':True,'id':job['id']}
    def start_identity(self,data):
        names=data.get('names',[]); platforms=data.get('platforms',[]); credentials=data.get('credentials',{})
        if not isinstance(names,list) or not 1<=len(names)<=100 or any(not isinstance(n,str) or not 1<=len(n.strip())<=255 or any(ord(c)<32 for c in n) for n in names): raise ValueError('Informe de 1 a 100 usernames válidos.')
        names=list(dict.fromkeys(n.strip() for n in names))
        if not isinstance(platforms,list) or not platforms or len(platforms)>18 or any(not isinstance(p,str) or p not in PLATFORM_BY_NAME for p in platforms): raise ValueError('Escolha plataformas válidas.')
        platforms=list(dict.fromkeys(platforms))
        if not isinstance(credentials,dict) or any(p not in PLATFORM_BY_NAME or not isinstance(t,str) or len(t)>4096 for p,t in credentials.items()): raise ValueError('Credenciais inválidas.')
        timeout=data.get('timeout',10); concurrency=data.get('concurrency',4); retries=data.get('retries',1)
        if type(timeout) not in (int,float) or not 2<=timeout<=30 or type(concurrency) is not int or not 1<=concurrency<=8 or type(retries) is not int or not 0<=retries<=2: raise ValueError('Limites de consulta inválidos.')
        auto=data.get('auto_suggestions',False)
        if type(auto) is not bool: raise ValueError('Opção inválida.')
        with self.session.lock, self.lock:
            if self.session.running: raise ValueError('Pare a verificação de plataforma antes de iniciar o Identity Checker.')
            queries={}
            for platform in platforms:
                seen=set(); queries[platform]=[]
                for username in names:
                    normalized=PLATFORM_BY_NAME[platform].normalize(username)
                    if normalized not in seen: seen.add(normalized); queries[platform].append(username)
            job=self._new('identity','multi','identity',sum(map(len,queries.values())))
            # Config contains usernames and platform names only, never credentials.
            job['query']={'names':names,'platforms':platforms}
        username_interval=self.session.load_settings()['username_interval']
        def record(result,key,suggestion=False):
            result['suggestion']=suggestion; result['session_id']=job['id']; result['result_key']=key
            try: self.store.event(job['id'],key,result['platform'],result['status'],elapsed=result['elapsed'],verified=result['verified'],result=result)
            except StorageError as exc:
                with self.lock: job['error']=str(exc)
            with self.lock: job['results'].append(result); job['done']+=1
        def platform_work(name):
            original=PLATFORM_BY_NAME[name]; p=type(original)(); p.delay=max(p.delay,username_interval); token=credentials.get(name,'')
            originals={p.normalize(n) for n in queries[name]}
            checked=set()
            for index,username in enumerate(queries[name]):
                result=check_one(p,username,token,timeout,job['stop'],self.gate,retries)
                checked.add(result['username'])
                options=[n for n in suggestions(p,result['username']) if n not in originals and n not in checked] if result['status']=='TAKEN' else []
                result['suggestions']=options
                result['input_username']=username
                record(result,f'{name}:{index}')
                if auto and options and not job['stop'].is_set():
                    with self.lock: job['total']+=len(options)
                    for j,option in enumerate(options):
                        record(check_one(p,option,token,timeout,job['stop'],self.gate,retries),f'{name}:{index}:suggestion:{j}',True)
                        checked.add(option)
        def work():
            try:
                with ThreadPoolExecutor(max_workers=concurrency,thread_name_prefix='identity') as pool:
                    futures=[pool.submit(platform_work,name) for name in platforms]
                    for future in as_completed(futures): future.result()
                self._finish(job,'cancelled' if job['stop'].is_set() else 'completed',job['error'])
            except Exception as exc: self._finish(job,'failed','Falha na consulta: '+type(exc).__name__)
            finally: credentials.clear()
        threading.Thread(target=work,daemon=True,name='identity-coordinator').start()
        return {'ok':True,'id':job['id']}
    def snapshot(self):
        with self.lock:
            data={}
            for kind,sid in self.current.items():
                if sid in self.jobs:
                    job=self.jobs[sid]; data[kind]={k:v for k,v in job.items() if k not in ('stop','started')}
            return {'ok':True,'jobs':data,'warning':self.store.warning}
    def cancel(self,sid):
        with self.lock:
            job=self.jobs.get(sid)
            if job and job['status']=='running': job['stop'].set()
        return {'ok':True}
    def dispatch(self,route,data):
        if route=='features/state': return self.snapshot()
        if route=='generator/start': return self.start_generator(data.get('rules',{}))
        if route=='generator/estimate': return {'ok':True,'estimate':generator.compile_pattern(data.get('rules',{})).estimate()}
        if route=='identity/start': return self.start_identity(data)
        if route=='features/cancel': return self.cancel(data.get('id'))
        if route=='analytics/session':
            self.store.manage_session(data.get('id'), data.get('action'))
            if data.get('action') == 'delete':
                with self.lock:
                    self.jobs.pop(data.get('id'), None)
                    for kind, sid in list(self.current.items()):
                        if sid == data.get('id'): self.current.pop(kind, None)
            return {'ok':True}
        if route=='analytics/query': return {'ok':True,'data':self.store.analytics(**self._filters(data))}
        if route=='analytics/export': return {'ok':True,'text':self.store.export_analytics(data.get('format','json'),**self._filters(data))}
        if route=='identity/history':
            rows=self.store.identity_history(data.get('id'))
            if data.get('id'):
                for row in rows:
                    p=PLATFORM_BY_NAME.get(row['platform'])
                    if p:
                        row.update(safe_urls(p,row['username'],row['status']))
                        row['suggestions']=suggestions(p,row['username']) if row['status']=='TAKEN' and not row['suggestion'] else []
            return {'ok':True,'rows':rows}
        if route=='identity/export':
            from core.storage import re_uuid
            if not re_uuid(data.get('id')): raise ValueError('Sessão inválida.')
            rows=self.store.identity_history(data.get('id'))
            if data.get('available_only'): rows=[r for r in rows if r['status']=='AVAILABLE']
            fmt=data.get('format','json')
            if fmt=='json': text=json.dumps(rows,ensure_ascii=False,indent=2)
            elif fmt=='csv': text=csv_text(rows,['session_id','result_key','platform','username','status','detail','verified','elapsed','profile_url','signup_url','suggestion'])
            else: raise ValueError('Formato inválido.')
            return {'ok':True,'text':text}
        if route=='generator/presets': return {'ok':True,'rows':generator.presets()+self.store.saved_presets(),'favorites':self.store.favorites()}
        if route=='generator/preset-save':
            compiled=generator.compile_pattern(data.get('rules',{})); rules={k:compiled.rules[k] for k in generator.DEFAULT_RULES}
            return {'ok':True,'id':self.store.save_preset(data.get('name'),rules,data.get('id'))}
        if route=='generator/preset-delete': self.store.delete_preset(data.get('id')); return {'ok':True}
        if route=='generator/favorite': self.store.favorite(data.get('username'),data.get('active')); return {'ok':True}
        return None
    @staticmethod
    def _filters(data):
        platform=data.get('platform',''); period=data.get('period','all'); search=data.get('search','')
        if platform and platform not in PLATFORM_BY_NAME and platform!='local': raise ValueError('Plataforma inválida.')
        if not isinstance(search,str) or len(search)>200: raise ValueError('Busca inválida.')
        return dict(platform=platform,period=period,search=search)
    def close(self):
        with self.lock:
            self.closed=True
            for job in self.jobs.values(): job['stop'].set()
        self.session.stop()
        def cleanup():
            for _ in range(650):
                with self.lock: active=any(j['status']=='running' for j in self.jobs.values())
                if not active and not self.session.running: break
                time.sleep(.05)
            self.store.close()
        threading.Thread(target=cleanup,daemon=True,name='feature-storage-cleanup').start()
