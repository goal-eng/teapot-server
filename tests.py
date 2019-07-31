import unittest
import subprocess
import time
import threading

import requests
import dotenv


dotenv.load_dotenv('.env.test', override=True)


import server


class TestTrafficCounter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class FakeRequest:
            def __init__(self, remote_addr):
                self.remote_addr = remote_addr

        cls.FakeRequest = FakeRequest

    def sleep_to_next_second(self):
        time_left_to_next_second = int(time.time() + 1) - time.time()
        time.sleep(time_left_to_next_second)

    def create_threads_to_increase_traffic(self, threads_count, request_ip, tea_variant, results_list):
        return [
            threading.Thread(
                target=lambda: results_list.append(
                    server.increase_traffic_by_request(self.FakeRequest(request_ip), tea_variant)
                )
            )
            for _ in range(threads_count)
        ]

    def run_threads_with_next_second(self, threads):
        self.sleep_to_next_second()
        [t.start() for t in threads]
        [t.join() for t in threads]

    def test_increase_by_single_client_single_variant(self):
        threads_count = 10
        results = []

        threads = self.create_threads_to_increase_traffic(threads_count, '127.0.0.1', 'earl-gray', results)
        self.run_threads_with_next_second(threads)

        self.assertEqual(
            len(results),
            threads_count
        )
        self.assertEqual(
            results,
            list(range(1, threads_count + 1))
        )
        self.assertEqual(
            len(server.TRAFFIC),
            1
        )

    def test_increase_by_single_client_many_variants(self):
        threads_count = 10
        results = []

        threads = [
            *self.create_threads_to_increase_traffic(threads_count, '127.0.0.1', 'earl-gray', results),
            *self.create_threads_to_increase_traffic(threads_count, '127.0.0.1', 'english-breakfast', results)
        ]

        self.run_threads_with_next_second(threads)

        self.assertEqual(
            len(results),
            threads_count*2
        )
        self.assertEqual(
            set(results),
            set(range(1, threads_count + 1))
        )
        self.assertEqual(
            len(server.TRAFFIC),
            1
        )

    def test_increase_by_many_clients_single_variant(self):
        threads_count = 10
        results = []

        threads = [
            *self.create_threads_to_increase_traffic(threads_count, '127.0.0.1', 'earl-gray', results),
            *self.create_threads_to_increase_traffic(threads_count, '127.0.0.2', 'earl-gray', results)
        ]

        self.run_threads_with_next_second(threads)

        self.assertEqual(
            len(results),
            threads_count*2
        )
        self.assertEqual(
            set(results),
            set(range(1, threads_count + 1))
        )
        self.assertEqual(
            len(server.TRAFFIC),
            1
        )


class TestServer(unittest.TestCase):
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
