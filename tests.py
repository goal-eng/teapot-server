import unittest
import subprocess
import time

import requests


class TestFirst(unittest.TestCase):
    SERVER_EXE_PATH = 'server.py'

    @classmethod
    def setUpClass(cls):
        cls.host = '0.0.0.0'
        cls.port = '9999'
        cls.base_url = f'http://{cls.host}:{cls.port}'

        server_process = subprocess.Popen([
            'python',
            'server.py',
            f'--host={cls.host}',
            f'--port={cls.port}',
        ])
        cls.server_process = server_process
        time.sleep(1)
        assert server_process.poll() is None

    @classmethod
    def tearDownClass(cls):
        cls.server_process.send_signal(15)
        cls.server_process.wait()

    def request(self, method, endpoint, **kwargs):
        url = f'{self.base_url}{endpoint}'
        print('url =', url)
        return requests.request(method.upper(), url, timeout=3, **kwargs)

    def test_invalid_method(self):
        bad_requests = [
            # GET, PUT, HEAD, DELETE, OPTIONS, PATCH, and TRACE
            # methods are not acceptable HTCPCP verbs
            self.request('GET', '/'),
            self.request('PUT', '/'),
            self.request('HEAD', '/'),
            self.request('DELETE', '/'),
            self.request('OPTIONS', '/'),
            self.request('PATCH', '/'),
            self.request('TRACE', '/'),
            # Missing body
            # self.request('POST', '/'),
            # self.request('BREW', '/'),
            # self.request('WHEN', '/'),
        ]
        for response in bad_requests:
            self.assertEqual(
                response.status_code,
                405
            )

    def test_brew_no_pot(self):
        response = self.request(
            'BREW',
            '/',
            data='start'
        )

        self.assertEqual(
            response.status_code,
            300
        )

        self.assertEqual(
            response.headers['Alternates'],
            '{"/english-breakfast" {type message/teapot}}, '
            '{"/earl-grey" {type message/teapot}}'
        )

    def test_brew_tea_start_unsupported_tea(self):
        response = self.request(
            'BREW',
            '/unsupported-tea',
            data='start',
            headers={'Content-Type': 'message/teapot'}
        )

        self.assertEqual(
            response.status_code,
            503
        )
        self.assertEqual(
            response.content,
            b'"unsupported-tea" is not supported for this pot'
        )

    def test_brew_tea_start_too_little_traffic(self):
        response = self.request(
            'BREW',
            '/earl-grey',
            data='start',
            headers={'Content-Type': 'message/teapot'}
        )

        self.assertEqual(
            response.status_code,
            424
        )
        self.assertEqual(
            response.content,
            b'Traffic too low to brew "earl-grey" tea: 1/20'
        )
