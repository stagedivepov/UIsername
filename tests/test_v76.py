import queue
import threading
import unittest
from unittest.mock import Mock, patch
from core import preferences
from core.session import Session
from core.worker import retry_delay
from platforms import PLATFORMS, PLATFORM_BY_NAME
from platforms.minecraft import Minecraft
from platforms.chesscom import ChessCom
from platforms.lichess import Lichess
from platforms.x import X
from platforms.kick import Kick
from platforms.http_helpers import http_signal


def network(status, body):
    response = Mock(status_code=status, headers={})
    response.json.return_value = body
    session = Mock(); session.get.return_value = response
    return session

class NewIntegrations(unittest.TestCase):
    def test_all_18_platforms_support_direct_and_existing_modes(self):
        self.assertEqual(len(PLATFORMS),18)
        for p in PLATFORMS:
            self.assertFalse(p.needs_proxy, p.name)
            self.assertEqual(set(p.modes), {'random','en','pt','es','name','check'})
        self.assertFalse(preferences.DEFAULTS['use_proxies'])

    def test_direct_mode_ignores_saved_proxies(self):
        session=Session();session.select('Discord')
        with patch.object(session,'load_settings',return_value=dict(preferences.DEFAULTS)), patch.object(session,'save_proxies'), patch('core.session.threading.Thread') as thread:
            reply=session.start({'platform':'Discord','mode':'check','list':'example','proxies':'example.invalid:8080'})
            self.assertTrue(reply['ok'])
            self.assertEqual(thread.call_args.kwargs['args'][-1],[])
        session.stop()

    def test_optional_proxy_mode_is_preserved(self):
        session=Session();session.select('Discord')
        with patch.object(session,'load_settings',return_value={**preferences.DEFAULTS,'use_proxies':True}), patch.object(session,'save_proxies'), patch('core.session.threading.Thread') as thread:
            self.assertTrue(session.start({'platform':'Discord','mode':'check','list':'example','proxies':'example.invalid:8080'})['ok'])
            self.assertEqual(thread.call_args.kwargs['args'][-1],['http://example.invalid:8080'])
        session.stop()

    def test_new_public_profile_results_are_strict(self):
        cases=[(Minecraft(),{'id':'a'*32,'name':'Example'},{'path':'/minecraft/profile/lookup/name/example','errorMessage':"Couldn't find any profile with name example"}),
               (ChessCom(),{'username':'example','player_id':1},{'code':0,'message':'User "example" not found.'}),
               (Lichess(),{'username':'Example','id':'example'},{'error':'Not found'})]
        for p,taken,missing in cases:
            with self.subTest(platform=p.name):
                self.assertEqual(p.check(network(200,taken),'example')[0],'taken')
                self.assertEqual(p.check(network(404,missing),'example')[0],'available')
                for status,body in [(200,{}),(404,{}),(200,{'username':'someoneelse','id':'someoneelse','player_id':1})]:
                    with self.assertRaises(RuntimeError):p.check(network(status,body),'example')
                self.assertEqual(p.check(network(403,{}),'example')[0],'ratelimit')

    def test_kick_requires_auth_and_valid_channel_list(self):
        p=Kick()
        self.assertEqual(p.check(Mock(),'example')[0],'ratelimit')
        self.assertEqual(p.check(network(200,{'data':[]}), 'example','fake-token')[0],'available')
        self.assertEqual(p.check(network(200,{'data':[{'slug':'example'}]}), 'example','fake-token')[0],'taken')
        with self.assertRaises(RuntimeError): p.check(network(200,{'data':[{'slug':'other'}]}),'example','fake-token')
        self.assertEqual(p.check(network(403,{}),'example','fake-token')[0],'ratelimit')

    def test_x_absence_requires_explicit_matching_user_error(self):
        p=X(); key='fake-token'
        self.assertEqual(p.check(network(200,{'data':{'username':'Example','id':'123'}}),'example',key)[0],'taken')
        error={'type':'https://api.x.com/2/problems/resource-not-found','resource_type':'user','parameter':'username','value':'example'}
        self.assertEqual(p.check(network(200,{'errors':[error]}),'example',key)[0],'available')
        for body in [{},{'errors':[{**error,'value':'other'}]},{'errors':[{'type':'invalid-request'}]}]:
            with self.assertRaises(RuntimeError): p.check(network(404,body),'example',key)
        self.assertEqual(p.check(Mock(),'example')[0],'ratelimit')

    def test_retries_never_shorten_server_wait(self):
        response=Mock(status_code=429,headers={'Retry-After':'900'})
        signal=http_signal(response)
        self.assertEqual(signal,('retry','900.0'))
        self.assertGreaterEqual(retry_delay(signal[1],1),900)
        self.assertEqual(retry_delay('nan',1),5)

    def test_blocks_in_direct_mode_do_not_report_availability(self):
        for name in ['Discord','Instagram','TikTok','YouTube','PlayStation']:
            session=network(403,{})
            session.post.return_value=session.get.return_value
            self.assertEqual(PLATFORM_BY_NAME[name].check(session,'example')[0],'ratelimit',name)
            session.get.assert_called() if name in ('Instagram','TikTok','YouTube') else session.post.assert_called()
