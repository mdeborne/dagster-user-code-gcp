# Base image arguments
ARG ROOT_IMAGE=580698825394.dkr.ecr.eu-central-1.amazonaws.com/python
ARG BASE_VERSION=3.9.5-bullseye-20241209_220357@sha256:2bb7b1c4c9b6b7d883f0ee4c92297e20bb9cb8dd00a9eb948cc0a21196f1d30b

# Builder stage
FROM ${ROOT_IMAGE}:${BASE_VERSION} as builder

ARG POETRY_VERSION=1.8.2

RUN pip install poetry==$POETRY_VERSION poetry-plugin-export

WORKDIR /opt/dagster/app

COPY pyproject.toml poetry.lock ./
RUN touch README.md

RUN poetry export --without-hashes --format=requirements.txt --without dev > requirements.txt

# Runtime stage
FROM ${ROOT_IMAGE}:${BASE_VERSION} as runtime

WORKDIR /opt/dagster/app

COPY --from=builder /opt/dagster/app/requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY dagster_user_code_example/ /opt/dagster/app/

RUN ls -al

CMD ["dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "3000","--python-file","/opt/dagster/app/example_repo/repo.py"]
#CMD ["sleep","600"]