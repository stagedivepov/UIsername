import csv
import io
import json
import sqlite3
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import requests
from core.advanced_generator import compile_pattern, generate, presets
from core.storage import Store, StorageError, csv_text
from core.identity import check_one, normalize, safe_urls, suggestions, PlatformGate, GuardedSession
from core.features import Features
from core.session import Session
from core.server import AppServer
from core.platform_base import Platform
from platforms import PLATFORM_BY_NAME

class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        self.temp=Path(__file__).resolve().parent/('.test-data-'+uuid.uuid4().hex);self.temp.mkdir();self.stores=[]
        self.addCleanup(self.cleanup)
    def store(self,name='activity.sqlite3'):
        result=Store(self.temp/name);self.stores.append(result);return result
    def cleanup(self):
        for store in self.stores: store.close()
        import shutil
        self.assertEqual(self.temp.resolve().parent,Path(__file__).resolve().parent)
        shutil.rmtree(self.temp)

class GeneratorTests(unittest.TestCase):
    def test_documented_patterns_and_escape(self):
        for pattern,regex in [('????',r'[A-Za-z]{4}'),('####',r'\d{4}'),('LL##',r'[a-z]{2}\d{2}'),('UU##',r'[A-Z]{2}\d{2}'),('word_###',r'[a-z]+_\d{3}'),('prefix+word',r'neo[a-z]+'),(r'\L\U##',r'LU\d{2}')]:
            with self.subTest(pattern=pattern):
                c=compile_pattern({'pattern':pattern,'prefixes':'neo','amount':10,'max_length':40})
                report=generate(c)
                self.assertEqual(len(report['names']),10)
                for name in report['names']: self.assertRegex(name,'^'+regex+'$')
    def test_exact_fixed_combination_count(self):
        self.assertEqual(compile_pattern({'pattern':'LLLL'}).estimate(),{'kind':'exact','value':'456976'})
    def test_small_filtered_space_is_exact(self):
        c=compile_pattern({'pattern':'LL','allowed':'ab','no_adjacent_repeat':True,'amount':10})
        self.assertEqual(c.estimate()['value'],'2');self.assertEqual(set(generate(c)['names']),{'ab','ba'})
    def test_complex_large_space_is_upper_bound(self):
        self.assertEqual(compile_pattern({'pattern':'LLLLLL','no_adjacent_repeat':True}).estimate()['kind'],'upper_bound')
    def test_prefix_digit_filters_not_mislabelled_exact(self):
        c=compile_pattern({'pattern':'prefix+LLLL','prefixes':'12345,abc','max_consecutive_digits':4})
        self.assertEqual(c.estimate()['kind'],'upper_bound')
        self.assertTrue(all(n.startswith('abc') for n in generate(c)['names']))
    def test_uniqueness_and_exhaustion(self):
        report=generate(compile_pattern({'pattern':'##','amount':150}))
        self.assertEqual(len(report['names']),100);self.assertEqual(len(set(report['names'])),100);self.assertEqual(report['status'],'exhausted')
    def test_attempt_limit_is_bounded(self):
        report=generate(compile_pattern({'pattern':'LLLL','banned_words':'a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t,u,v,w,x,y,z','max_attempts':25}))
        self.assertEqual(report['attempts'],25);self.assertEqual(report['status'],'attempt_limit');self.assertEqual(report['names'],[])
    def test_cancellation(self):
        stop=threading.Event();stop.set();r=generate(compile_pattern({'pattern':'LLLLLLLL'}),stop)
        self.assertEqual(r['status'],'cancelled');self.assertEqual(r['names'],[])
    def test_lengths_and_characters(self):
        c=compile_pattern({'pattern':'word+##','language':'pt','allowed':'abcdefghijklmnopqrstuvwxyz0123456789','forbidden':'x','min_length':5,'max_length':8,'amount':100})
        for name in generate(c)['names']:self.assertTrue(5<=len(name)<=8);self.assertNotIn('x',name)
    def test_independent_filters(self):
        c=compile_pattern({'pattern':'CVCV##','require_vowel':True,'require_consonant':True,'no_adjacent_repeat':True,'no_numeric_sequences':True,'pronounceable':True})
        for name in generate(c)['names']:self.assertTrue(c.accepts(name))
        self.assertFalse(compile_pattern({'pattern':'###','no_numeric_sequences':True}).accepts('123'))
        self.assertFalse(compile_pattern({'pattern':'LLLL','no_repeated_sequences':True}).accepts('abab'))
    def test_banned_words(self):
        c=compile_pattern({'pattern':'prefix+##','prefixes':'bad,good','banned_words':'bad'})
        self.assertTrue(all(n.startswith('good') for n in generate(c)['names']))
    def test_conflicts_rejected(self):
        patches=[{'pattern':'LL','lowercase':False},{'min_length':5,'max_length':2},{'pattern':'####','numbers':False},{'pattern':'####','max_consecutive_digits':2},{'pattern':'L','require_vowel':True,'require_consonant':True},{'pattern':'prefix'},{'pattern':'LL','allowed':'_'},{'pattern':'LL\\'},{'pattern':'{oops}'},{'pattern':'###','require_consonant':True},{'amount':True},{'max_attempts':0}]
        for value in patches:
            with self.subTest(value=value),self.assertRaises(ValueError):compile_pattern(value)
    def test_all_presets_compile(self):
        for preset in presets(): self.assertTrue(generate(compile_pattern({**preset['rules'],'amount':5}))['names'])
    def test_dictionary_language_uses_existing_vocabularies(self):
        from words import VERBS_ES
        c=compile_pattern({'pattern':'{word}','language':'es','amount':10})
        from core.utils import strip_accents
        self.assertTrue(set(generate(c)['names']).issubset({strip_accents(n).lower() for n in VERBS_ES}))

class StorageTests(WorkspaceCase):
    def test_availability_denominator_and_separate_generation(self):
        s=self.store();sid=s.begin('identity','multi','identity')
        for i,state in enumerate(('AVAILABLE','TAKEN','UNKNOWN','ERROR','RATE_LIMITED','AUTH_REQUIRED','UNSUPPORTED')):s.event(sid,str(i),'Roblox',state,verified=i<5)
        s.event(sid,'g','local','GENERATED',quantity=40);s.finish(sid,'completed');a=s.analytics()
        self.assertEqual(a['generated'],40);self.assertEqual(a['verified'],5);self.assertEqual(a['availability_rate'],.5);self.assertEqual(a['unknown'],4);self.assertEqual(a['errors'],1)
    def test_event_replay_is_idempotent(self):
        s=self.store();sid=s.begin('generator','local','LL');s.event(sid,'g','local','GENERATED',quantity=3);s.event(sid,'g','local','GENERATED',quantity=3)
        self.assertEqual(s.analytics()['generated'],3)
    def test_persistence_and_interrupted_recovery(self):
        s=self.store();sid=s.begin('identity','multi','identity');s.event(sid,'1','GitHub','TAKEN',verified=True);s.close();reopened=self.store()
        a=reopened.analytics();self.assertEqual(a['taken'],1);self.assertEqual(a['sessions'][0]['status'],'interrupted');self.assertEqual(a['sessions'][0]['id'],sid)
    def test_foreign_key_and_invalid_state(self):
        s=self.store()
        with self.assertRaises(StorageError):s.event('unknown','1','Roblox','TAKEN')
        sid=s.begin('identity','multi','identity')
        with self.assertRaises(ValueError):s.event(sid,'1','Roblox','invented')
    def test_concurrent_writes(self):
        s=self.store();sid=s.begin('identity','multi','identity')
        threads=[threading.Thread(target=lambda k=i:[s.event(sid,f'{k}:{j}','Roblox','TAKEN',verified=True) for j in range(20)]) for i in range(8)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(s.analytics()['verified'],160)
    def test_migration_preserves_existing_identity_results(self):
        s=self.store();sid=s.begin('identity','multi','identity')
        s.event(sid,'1','GitHub','TAKEN',verified=True,result=dict(username='alpha',detail='confirmed'))
        s.finish(sid,'completed');s.close()
        db=sqlite3.connect(self.temp/'activity.sqlite3')
        db.execute('ALTER TABLE identity_results DROP COLUMN input_username');db.execute('PRAGMA user_version=1');db.commit();db.close()
        s=self.store();self.assertEqual(s.identity_history(sid)[0]['username'],'alpha')
        self.assertEqual(s.db.execute('PRAGMA user_version').fetchone()[0],2)

    def test_daily_chart_buckets_use_local_midnight(self):
        from datetime import datetime
        s=self.store();sid=s.begin('identity','multi','identity');s.event(sid,'1','GitHub','TAKEN',verified=True)
        stamp=s.analytics()['timeline'][0]['at'];self.assertEqual(datetime.fromtimestamp(stamp).hour,0)

    def test_exports_have_consistent_ids(self):
        s=self.store();sid=s.begin('identity','multi','identity');s.event(sid,'1','Roblox','AVAILABLE',verified=True)
        j=json.loads(s.export_analytics('json'));self.assertEqual(j['sessions'][0]['id'],sid)
        rows=list(csv.DictReader(io.StringIO(s.export_analytics('csv'))));self.assertEqual(rows[0]['session_id'],sid);self.assertEqual(rows[0]['status'],'AVAILABLE')
    def test_corrupt_database_preserved(self):
        (self.temp/'activity.sqlite3').write_bytes(b'not a sqlite database');s=self.store();self.assertTrue(s.db);self.assertIn('corrompido',s.warning);self.assertTrue(list(self.temp.glob('*.corrupt-*')))
    def test_future_schema_not_overwritten(self):
        path=self.temp/'activity.sqlite3'
        with sqlite3.connect(path) as db:db.execute('PRAGMA user_version=99')
        db.close()
        s=self.store();self.assertIsNone(s.db)
        with sqlite3.connect(path) as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],99)
        db.close()
    def test_period_platform_and_search(self):
        s=self.store();sid=s.begin('identity','multi','identity');s.event(sid,'1','Roblox','AVAILABLE',verified=True);s.event(sid,'2','GitHub','TAKEN',verified=True)
        self.assertEqual(s.analytics(platform='GitHub',period='hour',search=sid)['taken'],1);self.assertEqual(s.analytics(platform='GitHub')['available'],0);self.assertEqual(s.analytics(search='missing')['sessions'],[])
    def test_presets_and_favorites_reload(self):
        s=self.store();pid=s.save_preset('My pattern',{'pattern':'LLLL'});s.save_preset('Renamed',{'pattern':'LL##'},pid);s.favorite('alpha',True);s.close();s=self.store()
        self.assertEqual(s.saved_presets()[0]['name'],'Renamed');self.assertEqual(s.favorites(),['alpha']);s.favorite('alpha',False);s.delete_preset(pid);self.assertEqual(s.favorites(),[]);self.assertEqual(s.saved_presets(),[])
    def test_export_spreadsheet_formula_safety(self):
        self.assertIn("'=SUM",csv_text([{'username':'=SUM(A1)'}],['username']))

class IdentityTests(unittest.TestCase):
    def result(self,name='Roblox',response=None,raw=None,timeout=10,stop=None):
        p=type(PLATFORM_BY_NAME[name])();gate=PlatformGate();stop=stop or threading.Event()
        if raw:p.check=Mock(return_value=raw)
        with patch('requests.Session.request',return_value=response):return check_one(p,'example','fake-token' if p.has_token else '',timeout,stop,gate,0)
    def test_profile_absence_is_unknown(self):
        for name in ['GitHub','Twitch','Instagram','TikTok','YouTube','Steam','GitLab','Bluesky','X (Twitter)','Kick','Minecraft','Chess.com','Lichess']:
            self.assertEqual(normalize(PLATFORM_BY_NAME[name],'available')[0],'UNKNOWN',name)
    def test_confirmed_available(self):
        r=Mock(status_code=200,headers={});r.json.return_value={'code':0}
        self.assertEqual(self.result(response=r)['status'],'AVAILABLE')
    def test_network_http_states(self):
        for code,state in [(429,'RATE_LIMITED'),(401,'AUTH_REQUIRED'),(403,'AUTH_REQUIRED'),(503,'ERROR'),(302,'UNKNOWN')]:
            self.assertEqual(self.result(response=Mock(status_code=code,headers={'Retry-After':'600'}))['status'],state)
    def test_http400_not_taken(self):
        r=Mock(status_code=400,headers={});r.json.return_value={}
        self.assertEqual(self.result('Discord',r)['status'],'UNKNOWN')
    def test_rejected_roblox_name_not_taken(self):
        r=Mock(status_code=200,headers={});r.json.return_value={'code':2}
        self.assertEqual(self.result(response=r)['status'],'UNKNOWN')
    def test_missing_credentials_without_network(self):
        p=PLATFORM_BY_NAME['Kick'];pcheck=Mock()
        with patch.object(p,'check',pcheck):result=check_one(p,'example','',10,threading.Event(),PlatformGate())
        self.assertEqual(result['status'],'AUTH_REQUIRED');self.assertFalse(result['verified']);pcheck.assert_not_called()
    def test_unsupported_and_bad_format_without_network(self):
        for p,name in [(PLATFORM_BY_NAME['PlayStation'],'example'),(PLATFORM_BY_NAME['Roblox'],'bad/')]:
            self.assertEqual(check_one(p,name,'',10,threading.Event(),PlatformGate())['status'],'UNSUPPORTED')
    def test_timeout_is_error_and_no_secret_leak(self):
        with patch('requests.Session.request',side_effect=requests.Timeout('secret-key')):
            r=check_one(PLATFORM_BY_NAME['Roblox'],'example','',2,threading.Event(),PlatformGate())
        self.assertEqual(r['status'],'ERROR');self.assertNotIn('secret-key',str(r))
    def test_cancelled_check_makes_no_requests(self):
        stop=threading.Event();stop.set();p=type(PLATFORM_BY_NAME['Roblox'])();p.check=Mock()
        r=check_one(p,'example','',10,stop,PlatformGate());p.check.assert_not_called();self.assertEqual(r['status'],'UNKNOWN')
    def test_cancel_interrupts_gate_wait(self):
        gate=PlatformGate();gate.cooldown('Roblox',10);stop=threading.Event();thread=threading.Thread(target=lambda:check_one(PLATFORM_BY_NAME['Roblox'],'example','',10,stop,gate));thread.start();stop.set();thread.join(1);self.assertFalse(thread.is_alive())
    def test_user_interval_is_waited_and_can_be_cancelled(self):
        gate=PlatformGate();gate.next['Roblox']=time.monotonic()+60;stop=threading.Event();results=[]
        thread=threading.Thread(target=lambda:results.append(check_one(PLATFORM_BY_NAME['Roblox'],'example','',10,stop,gate)))
        thread.start();time.sleep(.02);stop.set();thread.join(1)
        self.assertFalse(thread.is_alive());self.assertEqual(results[0]['status'],'UNKNOWN');self.assertFalse(results[0]['verified'])

    def test_request_timeout_override_and_explicit_direct_mode(self):
        response=Mock(status_code=200,headers={})
        with patch('requests.Session.request',return_value=response) as request:
            with GuardedSession(3,threading.Event()) as session:session.get('https://example.org',timeout=50)
        self.assertLessEqual(request.call_args.kwargs['timeout'],3);self.assertFalse(request.call_args.kwargs['allow_redirects']);self.assertEqual(request.call_args.kwargs['proxies'],{})
    def test_cooldown_does_not_issue_early_requests(self):
        gate=PlatformGate();gate.cooldown('Roblox',900);p=type(PLATFORM_BY_NAME['Roblox'])();p.check=Mock()
        result=check_one(p,'example','',10,threading.Event(),gate)
        self.assertEqual(result['status'],'RATE_LIMITED');self.assertFalse(result['verified']);p.check.assert_not_called()

    def test_quota_error_is_rate_limited(self):
        response=Mock(status_code=403,headers={});response.json.return_value={'error':{'errors':[{'reason':'quotaExceeded'}]}}
        self.assertEqual(self.result(response=response)['status'],'RATE_LIMITED')

    def test_safe_urls(self):
        p=PLATFORM_BY_NAME['GitHub'];self.assertEqual(safe_urls(p,'alice','TAKEN')['profile_url'],'https://github.com/alice');self.assertIsNone(safe_urls(p,'../../bad','TAKEN')['profile_url']);self.assertIsNone(safe_urls(p,'alice','UNKNOWN')['signup_url'])
        p=PLATFORM_BY_NAME['Bluesky'];self.assertEqual(safe_urls(p,'alice','TAKEN')['profile_url'],'https://bsky.app/profile/alice.bsky.social')
    def test_suggestions_follow_all_platform_rules(self):
        for p in PLATFORM_BY_NAME.values():
            values=suggestions(p,'example')
            self.assertEqual(len(values),len(set(values)))
            self.assertTrue(all(p.local_ok(n) and n!=p.normalize('example') for n in values),p.name)
    def test_malformed_success_is_not_confirmed(self):
        r=Mock(status_code=200,headers={});r.json.return_value={}
        self.assertEqual(self.result(response=r)['status'],'UNKNOWN')

class IntegrationTests(WorkspaceCase):
    def setup_features(self):
        session=Session();feature=Features(session,self.temp/'activity.sqlite3');self.stores.append(feature.store);self.addCleanup(feature.close);return session,feature
    def wait(self,feature,kind):
        for _ in range(500):
            state=feature.snapshot()['jobs'][kind]
            if state['status']!='running':return state
            time.sleep(.01)
        self.fail('Job did not finish')
    def test_generate_check_record_and_export(self):
        session,f=self.setup_features();f.start_generator({'pattern':'LL','amount':10});job=self.wait(f,'generator');self.assertEqual(len(job['names']),10)
        with patch('core.features.check_one',side_effect=lambda p,n,*a:dict(platform=p.name,username=n,status='AVAILABLE',detail='fixture',elapsed=.1,verified=True,profile_url=None,signup_url='https://www.roblox.com/')):
            f.start_identity({'names':job['names'][:3],'platforms':['Roblox']});identity=self.wait(f,'identity')
        self.assertEqual(identity['done'],3);self.assertEqual(f.store.analytics()['generated'],10);self.assertEqual(f.store.analytics()['available'],3)
        rows=json.loads(f.dispatch('identity/export',{'id':identity['id'],'format':'json','available_only':True})['text']);self.assertEqual(len(rows),3);self.assertEqual(rows[0]['session_id'],identity['id'])
    def test_auto_suggestions_are_checked_and_recorded_separately(self):
        _,f=self.setup_features()
        def check(p,n,*args):
            return dict(platform=p.name,username=n,status='TAKEN' if n=='example' else 'AVAILABLE',detail='fixture',elapsed=.01,verified=True)
        with patch('core.features.check_one',side_effect=check):
            f.start_identity({'names':['example'],'platforms':['Roblox'],'auto_suggestions':True});job=self.wait(f,'identity')
        self.assertEqual(job['done'],job['total']);self.assertEqual(len([r for r in job['results'] if r['suggestion']]),4)
        self.assertEqual(f.store.analytics()['verified'],5)

    def test_identity_cancel_and_normalized_duplicates(self):
        _,f=self.setup_features();entered=threading.Event()
        def check(p,n,token,timeout,stop,*args):
            entered.set();stop.wait(1)
            return dict(platform=p.name,username=n,status='UNKNOWN',detail='cancelled',elapsed=.01,verified=False)
        with patch('core.features.check_one',side_effect=check):
            result=f.start_identity({'names':['Example','example'],'platforms':['Minecraft']});entered.wait(1)
            f.cancel(result['id']);job=self.wait(f,'identity')
        self.assertEqual(job['status'],'cancelled');self.assertEqual(job['total'],1);self.assertEqual(job['done'],1)

    def test_configured_username_interval_applies_to_identity(self):
        session,f=self.setup_features();delays=[]
        def check(p,n,*args):
            delays.append(p.delay);return dict(platform=p.name,username=n,status='UNKNOWN',detail='',elapsed=.1,verified=True)
        with patch.object(session,'load_settings',return_value={'username_interval':2.5}),patch('core.features.check_one',side_effect=check):
            f.start_identity({'names':['example'],'platforms':['Roblox']});self.wait(f,'identity')
        self.assertEqual(delays,[2.5])

    def test_mutual_network_exclusion(self):
        session,f=self.setup_features();session.running=True
        with self.assertRaises(ValueError):f.start_identity({'names':['example'],'platforms':['Roblox']})
        session.running=False
        with patch('core.features.check_one',side_effect=lambda *a: (time.sleep(.1) or dict(platform='Roblox',username='example',status='UNKNOWN',detail='',elapsed=.1,verified=False))):
            f.start_identity({'names':['example'],'platforms':['Roblox']});session.select('Roblox');self.assertFalse(session.start({'platform':'Roblox','mode':'check','list':'example'})['ok']);self.wait(f,'identity')
    def test_identity_validation_and_no_tokens_in_storage(self):
        _,f=self.setup_features()
        for patch_value in [{'names':[]},{'names':['example'],'platforms':['invalid']},{'names':['example'],'platforms':['Roblox'],'timeout':float('nan')},{'names':['example'],'platforms':['Roblox'],'concurrency':True}]:
            with self.assertRaises(ValueError):f.start_identity(patch_value)
        with patch('core.features.check_one',side_effect=lambda p,n,*a:dict(platform=p.name,username=n,status='ERROR',detail='safe',elapsed=.1,verified=True)):
            f.start_identity({'names':['example'],'platforms':['Roblox'],'credentials':{'Roblox':'SECRET-DO-NOT-PERSIST'}});self.wait(f,'identity')
        with f.store.lock:f.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        self.assertNotIn(b'SECRET-DO-NOT-PERSIST',(self.temp/'activity.sqlite3').read_bytes())
    def test_native_startup_enables_exports_and_external_links(self):
        import app
        import sys
        import os
        native=MagicMock();native.settings={}
        with patch.dict(sys.modules,{'webview':native}),patch.dict(os.environ,{},clear=True),patch('app.Session'),patch('app.AppServer'),patch('app.os.makedirs'):
            app.main()
        self.assertTrue(native.settings['ALLOW_DOWNLOADS'])
        self.assertTrue(native.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'])
        native.start.assert_called_once()

    def test_http_routes_use_current_token(self):
        session=Session()
        with patch('core.server.Features',side_effect=lambda s:Features(s,self.temp/'activity.sqlite3')):server=AppServer(session)
        self.stores.append(server.features.store);server.start();self.addCleanup(server.stop)
        base=f'http://127.0.0.1:{server.port}/api/';headers={'X-App-Token':server.token}
        self.assertEqual(requests.post(base+'analytics/query',json={},timeout=3).status_code,401)
        self.assertTrue(requests.post(base+'generator/estimate',json={'rules':{'pattern':'##'}},headers=headers,timeout=3).json()['ok'])
        self.assertEqual(requests.post(base+'generator/start',json={'rules':{'pattern':'LL','min_length':9}},headers=headers,timeout=3).status_code,400)
        data=requests.post(base+'analytics/query',json={},headers=headers,timeout=3).json();self.assertEqual(data['data']['verified'],0)
    def test_legacy_collector_is_idempotent_and_conservative(self):
        _,f=self.setup_features();observer=f.legacy_observer(PLATFORM_BY_NAME['GitHub'],'random');observer.generated(1);observer.generated(1);observer.result(1,'available','alpha');observer.finish('completed')
        a=f.store.analytics();self.assertEqual(a['generated'],1);self.assertEqual(a['unknown'],1);self.assertEqual(a['available'],0)
