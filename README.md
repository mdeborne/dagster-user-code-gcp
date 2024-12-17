# dagster-user-code-example

View this example in the Dagster docs at https://docs.dagster.io/deployment/guides/kubernetes/deploying-with-helm


## Usage

1. Install dependencies

    ```bash
    poetry install
    ```

2. Run Dagster

    ```bash
    cd dagster_user_code_example

    poetry run dagster dev
    ```

## Docker build & push to GCP artifcat registery 

    ```bash
    gcloud auth configure-docker \
    europe-west9-docker.pkg.dev

    docker build -t dagster-user-code-example-gcp:latest .
    docker tag dagster-user-code-example-gcp:latest europe-west9-docker.pkg.dev/prj-d-orchestrator-z0c8/dagster-user-code-example-gcp/dagster-user-code-example-gcp:latest
    docker push europe-west9-docker.pkg.dev/prj-d-orchestrator-z0c8/dagster-user-code-example-gcp/dagster-user-code-example-gcp:latest
    ```
