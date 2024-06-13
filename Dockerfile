ARG PYTHON_VERSION=3.10

FROM python:$PYTHON_VERSION-buster as builder

ARG POETRY_VERSION=1.8.2

RUN pip install poetry==$POETRY_VERSION poetry-plugin-export

WORKDIR /opt/dagster/app

COPY pyproject.toml poetry.lock ./
RUN touch README.md

RUN poetry export --without-hashes --format=requirements.txt --without dev > requirements.txt

FROM python:$PYTHON_VERSION-slim-buster as runtime

WORKDIR /opt/dagster/app

COPY --from=builder /opt/dagster/app/requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY dagster_user_code_example/ /opt/dagster/app/

CMD ["dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "3000"]