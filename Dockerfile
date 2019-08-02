FROM python:3.6

WORKDIR /

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock
COPY .env .env
COPY server.py server.py

RUN pip install pipenv
RUN pipenv install --deploy
