# Based on https://tools.ietf.org/html/rfc7168
import os
import time

from japronto import Application
import click


# Configuration
START_NUMBER = os.environ.get('START_NUMBER', 0)
MIN_REQUESTS_COUNT = os.environ.get('MIN_REQUEST_COUNT', 20)
TEA_CONTENT_TYPE = 'message/teapot'
TEA_VARIANTS = [
    'english-breakfast',
    'earl-grey',
]


def create_alternates():
    items = []
    for variant in TEA_VARIANTS:
        items.append(
            f'{{"/{variant}" {{type {TEA_CONTENT_TYPE}}}}}'
        )
    return ', '.join(items)


TEA_ALTERNATES = create_alternates()

# Runtime variables
CURRENT_SECOND = 0
CURRENT_REQUESTS_COUNT = 0
TRAFFIC = {}


def increase_traffic_by_request(request, tea_variant):
    ip_data = TRAFFIC.get(request.remote_addr, None)

    if ip_data is None:
        ip_data = {}
        TRAFFIC[request.remote_addr] = ip_data

    tea_data = ip_data.get(tea_variant, None)

    if tea_data is None:
        tea_data = {}
        ip_data[tea_variant] = tea_data

    last_recorded_second = tea_data.get('last_recorded_second', 0)
    requests_count = tea_data.get('requests_count', 0)

    cur_second = int(time.time())
    if cur_second > last_recorded_second:
        requests_count = 1
    else:
        requests_count += 1

    tea_data['request_count'] = requests_count
    tea_data['last_recorded_second'] = cur_second
    return requests_count


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
