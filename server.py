# Based on https://tools.ietf.org/html/rfc7168
import os
import time
import weakref
import collections

from japronto import Application
import click


# Configuration
START_NUMBER = int(os.environ['START_NUMBER'])
MIN_REQUESTS_COUNT = int(os.environ['MIN_REQUESTS_COUNT'])
TEA_CONTENT_TYPE = 'message/teapot'
TEA_VARIANTS = [
    'english-breakfast',
    'earl-grey',
]


def create_alternates():
    return ', '.join(
        f'{{"/{variant}" {{type {TEA_CONTENT_TYPE}}}}}'
        for variant in TEA_VARIANTS
    )


TEA_ALTERNATES = create_alternates()

# Runtime variables
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
    endpoint = request.match_dict.get('endpoint', '')

    if request.method != 'BREW':
        return request.Response(code=405, text='asdasdas')

    if request.method == 'BREW':

        if endpoint == '':
            return request.Response(
                code=300,
                headers={'Alternates': TEA_ALTERNATES}
            )

        elif endpoint in TEA_VARIANTS:
            traffic = increase_traffic_by_request(request, endpoint)

            if traffic < MIN_REQUESTS_COUNT:
                # FIXME: uvloop is unable to return status code 424
                #        see https://github.com/squeaky-pl/japronto/issues/131
                return request.Response(
                    code=424,
                    text=f'Traffic too low to brew "{endpoint}" tea: {traffic}/{MIN_REQUESTS_COUNT}'
                )

            else:
                return request.Response(text='UEA')

        else:
            return request.Response(
                code=503,
                text=f'"{endpoint}" is not supported for this pot'
            )


app = Application()
r = app.router

r.add_route('/', slash)
r.add_route('/{endpoint}', slash)


@click.command()
@click.option('--host', default='0.0.0.0')
@click.option('--port', default='8080')
@click.option('--worker_num', default=None)
@click.option('--debug', default=False)
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
