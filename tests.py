import unittest
import subprocess
import time
import threading

import requests
import dotenv


dotenv.load_dotenv('.env.test', override=True)


import server


def sleep_to_next_second():
    time_left_to_next_second = int(time.time() + 1) - time.time()
    time.sleep(time_left_to_next_second)


class TestTrafficCounter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class FakeRequest:
            def __init__(self, remote_addr):
                self.remote_addr = remote_addr

        cls.FakeRequest = FakeRequest

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
        sleep_to_next_second()
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

    def setUp(self):
        self.host = '0.0.0.0'
        self.port = '9999'
        self.base_url = f'http://{self.host}:{self.port}'

        server_process = subprocess.Popen(
            args=[
                'python',
                'server.py',
                f'--host={self.host}',
                f'--port={self.port}',
                '--debug'
            ],
        )
        self.server_process = server_process

        for _ in range(100):
            try:
                self.request('GET', '/')
            except requests.ConnectionError:
                time.sleep(0.05)
                continue
            else:
                break

    def tearDown(self):
        self.server_process.send_signal(15)
        self.server_process.wait()

    def request(self, method, endpoint, **kwargs):
        url = f'{self.base_url}{endpoint}'
        return requests.request(method.upper(), url, timeout=None, **kwargs)

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

    def test_start_brew_unsupported_tea(self):
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

    def test_start_brew_english_breakfast_successfully(self):
        response = self.request(
            'BREW',
            '/english-breakfast',
            data='start',
            headers={'Content-Type': 'message/teapot'}
        )

        self.assertEqual(
            response.status_code,
            202
        )
        self.assertEqual(
            response.content,
            b'Brewing'
        )

    def test_start_brew_english_breakfast_but_its_busy(self):
        for _ in range(2):
            response = self.request(
                'BREW',
                '/english-breakfast',
                data='start',
                headers={'Content-Type': 'message/teapot'}
            )

        self.assertEqual(
            response.status_code,
            503
        )
        self.assertEqual(
            response.content,
            b'Pot is busy'
        )

    def test_stop_brew_english_breakfast_successfully(self):
        self.request(
            'BREW',
            '/english-breakfast',
            data='start',
            headers={'Content-Type': 'message/teapot'}
        )

        response = self.request(
            'BREW',
            '/english-breakfast',
            data='stop',
            headers={'Content-Type': 'message/teapot'}
        )

        self.assertEqual(
            response.status_code,
            201
        )
        self.assertEqual(
            response.content,
            b'Finished'
        )

    def test_stop_brew_english_breakfast_but_its_not_started(self):
        response = self.request(
            'BREW',
            '/english-breakfast',
            data='stop',
            headers={'Content-Type': 'message/teapot'}
        )

        self.assertEqual(
            response.status_code,
            400
        )
        self.assertEqual(
            response.content,
            b'No beverage is being brewed by this pot'
        )

    # Earl-grey
    def test_start_brew_earl_grey_successfully(self):
        responses = []
        start_brew = lambda: responses.append(
            self.request(
                'BREW',
                '/earl-grey',
                data='start',
                headers={'Content-Type': 'message/teapot'}
            )
        )
        threads = [threading.Thread(target=start_brew) for _ in range(server.MIN_REQUESTS_COUNT)]
        sleep_to_next_second()
        [t.start() for t in threads]
        [t.join() for t in threads]

        success_responses = list(filter(lambda r: r.status_code == 202, responses))

        self.assertEqual(
            len(success_responses),
            1
        )

        response = success_responses[0]

        self.assertEqual(
            response.content,
            b'Brewing'
        )

    def test_start_brew_earl_grey_but_its_busy(self):
        responses = []
        start_brew = lambda: responses.append(
            self.request(
                'BREW',
                '/earl-grey',
                data='start',
                headers={'Content-Type': 'message/teapot'}
            )
        )
        threads = [threading.Thread(target=start_brew) for _ in range(server.MIN_REQUESTS_COUNT)]
        sleep_to_next_second()
        [t.start() for t in threads]
        [t.join() for t in threads]

        response = self.request(
            'BREW',
            '/earl-grey',
            data='start',
            headers={'Content-Type': 'message/teapot'}
        )

        self.assertEqual(
            response.status_code,
            503
        )
        self.assertEqual(
            response.content,
            b'Pot is busy'
        )

    def test_start_brew_earl_grey_but_traffic_is_too_low(self):
        responses = []
        start_brew = lambda: responses.append(
            self.request(
                'BREW',
                '/earl-grey',
                data='start',
                headers={'Content-Type': 'message/teapot'}
            )
        )
        threads = [threading.Thread(target=start_brew) for _ in range(server.MIN_REQUESTS_COUNT - 1)]
        sleep_to_next_second()
        [t.start() for t in threads]
        [t.join() for t in threads]

        self.assertEqual(
            len(responses),
            server.MIN_REQUESTS_COUNT - 1
        )

        for response in responses:
            self.assertEqual(
                response.code,
                424
            )
            self.assertIn(
                b'Traffic too low to brew',
                response.content
            )

    def test_stop_brew_earl_grey_successfully(self):
        start_brew = lambda: self.request(
            'BREW',
            '/earl-grey',
            data='start',
            headers={'Content-Type': 'message/teapot'}
        )

        threads = [threading.Thread(target=start_brew) for _ in range(server.MIN_REQUESTS_COUNT)]
        sleep_to_next_second()
        [t.start() for t in threads]
        [t.join() for t in threads]

        response = self.request(
            'BREW',
            '/earl-grey',
            data='stop',
            headers={'Content-Type': 'message/teapot'}
        )

        self.assertEqual(
            response.status_code,
            201
        )
        self.assertEqual(
            response.content,
            b'Finished'
        )

    def test_stop_brew_earl_grey_but_its_not_started(self):
        response = self.request(
            'BREW',
            '/earl-grey',
            data='stop',
            headers={'Content-Type': 'message/teapot'}
        )

        self.assertEqual(
            response.status_code,
            400
        )
        self.assertEqual(
            response.content,
            b'No beverage is being brewed by this pot'
        )
