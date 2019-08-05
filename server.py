# Based on https://tools.ietf.org/html/rfc7168
import os
import time
import weakref
import collections
import multiprocessing

from japronto import Application
import click


# Configuration (load .env file if variables aren't present)
for _ in range(2):
    try:
        START_NUMBER = int(os.environ['START_NUMBER'])
        MIN_REQUESTS_COUNT = int(os.environ['MIN_REQUESTS_COUNT'])
        SERVER_HOST = os.environ['SERVER_HOST']
        SERVER_PORT = os.environ['SERVER_PORT']
        SERVER_WORKER_NUM = int(os.environ['SERVER_WORKER_NUM'])
    except KeyError:
        import dotenv
        dotenv.load_dotenv('.env', override=True)
    else:
        break


TEA_CONTENT_TYPE = 'message/teapot'
TEA_VARIANTS = [
    'english-breakfast',
    'earl-grey',
]
HIGH_TRAFFIC_VARIANT = 'disabled-for-now'

with open('home.html') as home_html_file:
    HOME_HTML_CONTENT = home_html_file.read()


def create_alternates():
    return ', '.join(
        f'{{"/{variant}" {{type {TEA_CONTENT_TYPE}}}}}'
        for variant in TEA_VARIANTS
    )


TEA_ALTERNATES = create_alternates()

# Runtime variables
multiprocessing_manager = multiprocessing.Manager()

POTS_BREWING = multiprocessing_manager.dict({variant: False for variant in TEA_VARIANTS})

TRAFFIC = weakref.WeakValueDictionary()
CUR_SECOND_COUNTER = None  # used to keep reference


def increase_traffic_by_request(request, tea_variant):
    global CUR_SECOND_COUNTER

    cur_second_int = int(time.time())
    request_key = f'{request.remote_addr}/{tea_variant}'

    if cur_second_int not in TRAFFIC:
        cur_second_counter = collections.Counter()
        TRAFFIC[cur_second_int] = cur_second_counter
    else:
        cur_second_counter = TRAFFIC[cur_second_int]

    CUR_SECOND_COUNTER = cur_second_counter

    cur_second_counter[request_key] += 1
    return cur_second_counter[request_key]


def slash(request):
    """
    :type request:
    """

    endpoint = request.match_dict.get('endpoint', '')

    if request.method == 'GET':
        return request.Response(
            code=200,
            text=HOME_HTML_CONTENT,
            headers={'Content-Type': 'text/html'}
        )

    if request.method == 'BREW':

        if endpoint == '':
            return request.Response(
                code=300,
                headers={'Alternates': TEA_ALTERNATES}
            )

        # Some pot
        elif endpoint in TEA_VARIANTS:

            # Wrong Content-Type
            if request.headers.get('Content-Type', '') != TEA_CONTENT_TYPE:
                return request.Response(
                    code=400,
                    headers={'Alternates': TEA_ALTERNATES}
                )

            brewing_key = f'{endpoint}/{request.remote_addr}'
            is_brewing = POTS_BREWING.get(brewing_key, False)

            # Start brewing
            if request.body == b'start':

                # Pot is busy - already brewing
                if is_brewing:
                    return request.Response(
                        code=503,
                        text='Pot is busy'
                    )

                # Make sure there is enough traffic for high traffic pot
                if endpoint == HIGH_TRAFFIC_VARIANT:
                    traffic = increase_traffic_by_request(request, tea_variant=endpoint)

                    if traffic < MIN_REQUESTS_COUNT:
                        # FIXME: uvloop is unable to return status code 424
                        #        see https://github.com/squeaky-pl/japronto/issues/131
                        return request.Response(
                            code=424,
                            text=f'Traffic too low to brew "{endpoint}" tea: {traffic}/{MIN_REQUESTS_COUNT}'
                        )

                # Successfully start brewing
                POTS_BREWING[brewing_key] = True

                return request.Response(
                    code=202,
                    text='Brewing'
                )

            # Stop brewing
            if request.body == b'stop':

                if not is_brewing:
                    return request.Response(
                        code=400,
                        text='No beverage is being brewed by this pot',
                    )

                # Successfully stop brewing
                POTS_BREWING[endpoint] = False

                return request.Response(
                    code=201,
                    text='Finished',
                )

            return request.Response(
                code=400
            )

        # Unknown pot
        else:
            return request.Response(
                code=503,
                text=f'"{endpoint}" is not supported for this pot'
            )

    else:
        return request.Response(code=405)


app = Application()
r = app.router

r.add_route('/', slash)
r.add_route('/{endpoint}', slash)


@click.command()
@click.option('--host', default=SERVER_HOST)
@click.option('--port', default=SERVER_PORT)
@click.option('--worker-num', default=SERVER_WORKER_NUM)
@click.option('--debug', default=False, is_flag=True)
def cli(host, port, worker_num, debug):
    click.echo('Starting server with following configuration:')
    click.echo('Host: %r' % host)
    click.echo('Port: %r' % port)
    click.echo('Worker number: %r' % worker_num)
    click.echo('Debug: %r' % debug)

    app.run(
        host=host,
        port=int(port),
        worker_num=int(worker_num) if worker_num else None,
        debug=debug
    )


if __name__ == '__main__':
    cli()
