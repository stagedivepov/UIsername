"""Offline regression checks. Run: python -m unittest discover -s tests -v."""
import queue
import threading
import time
import unittest
from unittest.mock import Mock, patch

import requests
from core.worker import run_worker, run_worker_batch
from core.session import Session
from core.server import AppServer
from core.platform_base import Platform
from platforms.discord import Discord
from platforms.roblox import Roblox
from platforms.github import GitHub
from platforms.instagram import Instagram
from platforms.twitch import Twitch
from platforms.youtube import YouTube
from platforms import PLATFORMS


class FakePlatform(Platform):
    name = 'Fake'
    delay = 0
    def local_ok(self, name):
        return name != 'bad!'
    def check(self, *args):
        return 'taken', ''
    def check_batch(self, *args):
        return {'alpha': 'taken'}, None


CFG = {'mode': 'check', 'names': ['alpha', 'beta']}


class Regressions(unittest.TestCase):
    def test_all_platforms_and_modes_preserved(self):
        self.assertEqual(len(PLATFORMS), 18)
        for p in PLATFORMS:
            self.assertEqual(set(p.modes), {'random', 'en', 'pt', 'es', 'name', 'check'})

    def test_missing_batch_results_are_errors(self):
        events = queue.Queue()
        run_worker_batch(FakePlatform(), 2, CFG, events, threading.Event())
        result = list(events.queue)
        self.assertEqual([e[0] for e in result], ['invalid', 'error', 'done'])

    def test_unknown_status_is_not_taken(self):
        p = FakePlatform()
        p.check = Mock(return_value=('unknown', ''))
        events = queue.Queue()
        run_worker(p, 2, CFG, events, threading.Event())
        self.assertEqual([e[0] for e in events.queue], ['error', 'error', 'done'])

    def test_failure_outside_check_always_finishes(self):
        events = queue.Queue()
        p = FakePlatform()
        p.local_ok = Mock(side_effect=RuntimeError('broken generator'))
        run_worker(p, 2, CFG, events, threading.Event())
        self.assertEqual(list(events.queue)[-1], ('done', 0, 'failed'))

    def test_cancellation_interrupts_long_pause(self):
        p = FakePlatform()
        p.direct_delay = 60
        stop, events = threading.Event(), queue.Queue()
        thread = threading.Thread(target=run_worker, args=(p, 2, CFG, events, stop))
        thread.start()
        self.assertEqual(events.get(timeout=2)[0], 'invalid')
        stop.set()
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(list(events.queue)[-1], ('done', 0, 'stopped'))

    def test_progress_counts_results_not_out_of_order_indexes(self):
        session = Session()
        session.total = 10
        session._handle('badformat', 10, 'bad!')
        self.assertEqual(session.progress, .1)
        session._handle('invalid', 1, 'alpha')
        self.assertEqual(session.progress, .2)

    def test_save_failure_counted_once(self):
        p = FakePlatform()
        p.batch_size = 2
        p.check_batch = Mock(return_value=({'alpha': 'available', 'beta': 'taken'}, None))
        p.save = Mock(side_effect=OSError('read only'))
        events = queue.Queue()
        run_worker_batch(p, 2, CFG, events, threading.Event())
        self.assertEqual([e[0] for e in events.queue], ['error', 'error', 'done'])

    def test_request_errors_do_not_leak_api_keys(self):
        p = FakePlatform()
        p.check = Mock(side_effect=requests.ConnectionError('https://api/?key=SECRET'))
        events = queue.Queue()
        run_worker(p, 2, CFG, events, threading.Event())
        self.assertNotIn('SECRET', str(list(events.queue)))

    def test_required_fields_not_assumed_available(self):
        response = Mock(status_code=200, headers={})
        response.json.return_value = {}
        network = Mock()
        network.get.return_value = response
        network.post.return_value = response
        with patch('requests.get', return_value=response), patch('requests.post', return_value=response):
            for p in (Roblox(), Discord(), Instagram(), YouTube()):
                with self.subTest(platform=p.name), self.assertRaises(RuntimeError):
                    p.check(network, 'alpha', 'fake-key' if p.name == 'YouTube' else '')
            twitch = Twitch()
            twitch._get_token = Mock(return_value='fake')
            with self.assertRaises(RuntimeError):
                twitch.check_batch(network, ['alpha'], 'client:secret')

    def test_graphql_partial_errors_do_not_become_available(self):
        response = Mock(status_code=200, headers={})
        response.json.return_value = {
            'data': {'u0': None, 'u1': None},
            'errors': [{'type': 'FORBIDDEN', 'path': ['u0']}, {'type': 'NOT_FOUND', 'path': ['u1']}],
        }
        network = Mock()
        network.post.return_value = response
        results, signal = GitHub().check_batch(network, ['alpha', 'beta'], 'fake')
        self.assertEqual(results, {'beta': 'available'})

    def test_http_validation_and_authentication(self):
        server = AppServer(Session())
        server.start()
        base = f'http://127.0.0.1:{server.port}'
        headers = {'X-App-Token': server.token}
        try:
            self.assertEqual(requests.get(base + '/api/state', timeout=3).status_code, 401)
            self.assertEqual(requests.post(base + '/api/start', headers=headers, data='{', timeout=3).status_code, 400)
            self.assertEqual(requests.post(base + '/api/start', headers=headers, json=[], timeout=3).status_code, 400)
            meta = requests.get(base + '/api/state', headers=headers, timeout=3).json()
            self.assertEqual(len(meta['platforms']), 18)
            requests.post(base + '/api/select', headers=headers, json={'platform': 'Roblox'}, timeout=3)
            reply = requests.post(base + '/api/start', headers=headers, json={'platform': 'Roblox', 'mode': 'random', 'amount': '0'}, timeout=3).json()
            self.assertEqual(reply['field'], 'amount')
        finally:
            server.stop()


if __name__ == '__main__':
    unittest.main()

