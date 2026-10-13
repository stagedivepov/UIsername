"""Conservative adapter around existing platform checkers; no bypasses or proxies."""
import math
import re
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote
import requests
from core.storage import STATES
from core.utils import rng

ABSENCE_ONLY = {'GitHub','Twitch','TikTok','Instagram','YouTube','Telegram','Steam','GitLab','Bluesky','X (Twitter)','Kick','Minecraft','Chess.com','Lichess'}
PROFILE_BASES = {'GitHub':'https://github.com/','Twitch':'https://www.twitch.tv/','TikTok':'https://www.tiktok.com/@',
                 'Instagram':'https://www.instagram.com/','YouTube':'https://www.youtube.com/@','Telegram':'https://t.me/',
                 'Reddit':'https://www.reddit.com/user/','Steam':'https://steamcommunity.com/id/','GitLab':'https://gitlab.com/',
                 'Bluesky':'https://bsky.app/profile/','X (Twitter)':'https://x.com/','Kick':'https://kick.com/',
                 'Chess.com':'https://www.chess.com/member/','Lichess':'https://lichess.org/@/'}
SIGNUPS = {'Roblox':'https://www.roblox.com/','GitHub':'https://github.com/signup','Discord':'https://discord.com/register',
           'Reddit':'https://www.reddit.com/register/'}

class Signal(Exception):
    def __init__(self,status,detail,wait=0): self.status=status; self.detail=detail; self.wait=wait

def retry_after(value):
    try:
        wait=float(value)
        return max(1,wait) if math.isfinite(wait) else 60
    except (ValueError,TypeError):
        try: return max(1,(parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds())
        except (TypeError,ValueError,OverflowError): return 60

class GuardedSession(requests.Session):
    def __init__(self, timeout, stop):
        super().__init__(); self.trust_env=False; self.timeout=timeout; self.stop=stop; self.last_response=None; self.deadline=time.monotonic()+timeout
    def request(self,method,url,**kwargs):
        if self.stop.is_set(): raise Signal('UNKNOWN','Consulta cancelada.')
        remaining=self.deadline-time.monotonic()
        if remaining<=0: raise requests.Timeout()
        kwargs.update(timeout=min(self.timeout,remaining),allow_redirects=False,proxies={})
        response=super().request(method,url,**kwargs); self.last_response=response
        code=response.status_code
        if code==429 or (code==403 and response.headers.get('X-RateLimit-Remaining')=='0'):
            reset=response.headers.get('X-RateLimit-Reset') or response.headers.get('Ratelimit-Reset')
            wait=retry_after(response.headers.get('Retry-After','60'))
            if reset and str(reset).isdigit(): wait=max(wait,float(reset)-time.time())
            raise Signal('RATE_LIMITED','Limite de requisições. Tente mais tarde.',wait)
        if code==403:
            try:
                reasons=[e.get('reason') for e in response.json().get('error',{}).get('errors',[])]
            except (ValueError,TypeError,AttributeError): reasons=[]
            if any(r in ('quotaExceeded','dailyLimitExceeded','rateLimitExceeded','userRateLimitExceeded') for r in reasons):
                raise Signal('RATE_LIMITED','Limite de requisições. Tente mais tarde.',86400 if any(r in ('quotaExceeded','dailyLimitExceeded') for r in reasons) else 60)
        if code in (401,402,403): raise Signal('AUTH_REQUIRED','Acesso recusado. Confira as credenciais e permissões.')
        if 300<=code<400: raise Signal('UNKNOWN','Redirecionamento ou página de login; resultado inconclusivo.')
        if code>=500 or code==407: raise Signal('ERROR','Falha HTTP '+str(code)+'.')
        return response

class PlatformGate:
    def __init__(self): self.lock=threading.Lock(); self.next={}; self.limits={}
    def wait(self,name,pause,stop):
        while not stop.is_set():
            with self.lock:
                seconds=self.next.get(name,0)-time.monotonic()
                if seconds<=0: self.next[name]=time.monotonic()+pause; return True
            if stop.wait(min(seconds,.2)): break
        return False
    def cooldown(self,name,wait):
        with self.lock:
            until=time.monotonic()+wait
            self.next[name]=max(self.next.get(name,0),until); self.limits[name]=max(self.limits.get(name,0),until)
    def cooldown_remaining(self,name):
        with self.lock: return max(0,self.limits.get(name,0)-time.monotonic())
    def remaining(self,name):
        with self.lock: return max(0,self.next.get(name,0)-time.monotonic())


def safe_urls(p,name,status):
    normalized=p.normalize(name)
    if not p.local_ok(normalized): return {'profile_url':None,'signup_url':None}
    profile=PROFILE_BASES.get(p.name)
    value=p.format_username(normalized) if p.name=='Bluesky' else normalized
    return {'profile_url':profile+quote(value,safe='') if profile and status=='TAKEN' else None,
            'signup_url':SIGNUPS.get(p.name) if status=='AVAILABLE' else None}


def normalize(p,raw,detail='',response=None):
    if raw=='available':
        if p.name in ABSENCE_ONLY or p.lookup_only: return 'UNKNOWN','Perfil não encontrado; disponibilidade de cadastro não confirmada.'
        if p.name in ('Roblox','Discord','Reddit') or getattr(p,'confirms_availability',False): return 'AVAILABLE','Disponibilidade confirmada pelo verificador.'
        return 'UNKNOWN','A plataforma não confirmou a disponibilidade.'
    if raw=='taken':
        if p.name=='Reddit': return 'UNKNOWN','Nome indisponível para cadastro; ocupação não confirmada.'
        if response is not None:
            code=response.status_code
            if code!=200: return 'UNKNOWN','Resposta não confirma que o nome está ocupado.'
            try: body=response.json()
            except ValueError: body=None
            name=p.name
            if name=='Roblox' and (not isinstance(body,dict) or body.get('code')!=1): return 'UNKNOWN','Nome rejeitado pelo serviço; ocupação não confirmada.'
            if name=='GitHub' and (not isinstance(body,dict) or str(body.get('login','')).lower()!=detail.lower() or type(body.get('id')) is not int or body['id']<=0): return 'UNKNOWN','Resposta de perfil inesperada.'
            if name=='Instagram':
                user=(body.get('data') or {}).get('user') if isinstance(body,dict) and isinstance(body.get('data'),dict) else None
                if not isinstance(user,dict) or str(user.get('username','')).lower()!=detail.lower() or not user.get('id'): return 'UNKNOWN','Resposta de perfil inesperada.'
            if name=='Twitch' and (not isinstance(body,dict) or not any(isinstance(u,dict) and str(u.get('login','')).lower()==detail.lower() and str(u.get('id','')).isdigit() for u in body.get('data',[]))): return 'UNKNOWN','Resposta de perfil inesperada.'
            if name=='YouTube' and body is not None:
                if not isinstance(body,dict) or not any(isinstance(item,dict) and re.fullmatch(r'UC[A-Za-z0-9_-]{22}',str(item.get('id',''))) for item in body.get('items',[])): return 'UNKNOWN','Resposta de perfil inesperada.'
            if name=='YouTube' and body is None:
                if not re.search(r'"channelId"\s*:\s*"UC[A-Za-z0-9_-]+"',response.text) or ('/@'+detail.lower()) not in response.text.lower(): return 'UNKNOWN','Página sem identidade de canal confirmada.'
            if name=='Telegram' and 'tgme_page_title' not in response.text: return 'UNKNOWN','Página sem identidade de perfil confirmada.'
            if name=='TikTok':
                import json
                try:
                    script=re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',response.text,re.S)
                    scope=json.loads(script.group(1))['__DEFAULT_SCOPE__']['webapp.user-detail']
                    user=scope['userInfo']['user']
                    valid=scope.get('statusCode')==0 and str(user.get('uniqueId','')).lower()==detail.lower() and str(user.get('id','')).isdigit()
                except (ValueError,KeyError,TypeError,AttributeError): valid=False
                if not valid: return 'UNKNOWN','Página sem identidade de perfil confirmada.'
        return 'TAKEN','Nome ocupado confirmado pelo verificador.'
    if raw in ('retry','ratelimit'): return 'UNKNOWN','O serviço não confirmou o resultado. Tente mais tarde.'
    if raw=='badproxy': return 'ERROR','Falha de conexão com o serviço.'
    return 'UNKNOWN','Resposta de disponibilidade desconhecida.'


def check_one(p,name,token,timeout,stop,gate,max_retries=1):
    username=p.normalize(name); started=time.monotonic(); verified=False
    status,detail='UNKNOWN','Consulta cancelada.'
    if p.name=='PlayStation': status,detail='UNSUPPORTED','Endpoint experimental sem confirmação confiável para consultas unificadas.'
    elif not p.local_ok(username): status,detail='UNSUPPORTED','Username incompatível com as regras desta plataforma.'
    elif p.token_required and (not token or not p.token_ok(token)): status,detail='AUTH_REQUIRED',p.token_error
    else:
        pause=max(p.delay,p.direct_pause(token) or 0)
        for attempt in range(max_retries+1):
            if stop.is_set(): break
            if gate.cooldown_remaining(p.name)>30: status,detail='RATE_LIMITED','Plataforma em espera após limite de requisições.'; break
            if not gate.wait(p.name,pause,stop): break
            try:
                with GuardedSession(timeout,stop) as network:
                    verified=True; raw,message=p.check(network,username,token)
                    status,detail=normalize(p,raw,username,network.last_response)
                    if raw=='ratelimit' and p.token_required and re.search('credenc|token|chave',str(message),re.I): status,detail='AUTH_REQUIRED','Credenciais recusadas pelo serviço.'
                break
            except Signal as signal:
                status,detail=signal.status,signal.detail
                if status=='RATE_LIMITED':
                    gate.cooldown(p.name,signal.wait)
                    if attempt<max_retries and signal.wait<=30 and not stop.is_set(): continue
                break
            except requests.Timeout: status,detail='ERROR','Tempo limite da consulta atingido.'; break
            except requests.RequestException: status,detail='ERROR','Falha de rede durante a consulta.'; break
            except NotImplementedError: status,detail='UNSUPPORTED','Consulta não suportada pela plataforma.'; break
            except (ValueError,RuntimeError,TypeError,KeyError): status,detail='UNKNOWN','Resposta inesperada; não foi possível confirmar.'; break
            except Exception: status,detail='ERROR','Falha técnica durante a consulta.'; break
    if stop.is_set(): status,detail='UNKNOWN','Consulta cancelada.'
    return dict(username=username,platform=p.name,status=status,detail=detail,
                verified=verified,elapsed=max(0,time.monotonic()-started),**safe_urls(p,username,status))


def suggestions(p,name,limit=4):
    base=p.normalize(name); choices=[]
    variants=[base+'_',base+'7',base+'x',base[:-1],base[:-1]+base[-1:]*2]
    if len(base)>1: variants.append(base[:-2]+base[-1]+base[-2])
    variants += [base[:max(0,p.max_len-2)]+str(rng.randrange(10,99)) for _ in range(12)]
    for value in variants:
        value=p.normalize(value)
        if value!=base and value not in choices and p.local_ok(value): choices.append(value)
        if len(choices)==limit: break
    return choices
