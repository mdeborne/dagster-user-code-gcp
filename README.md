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

    
      # Authenticate Docker to use gcloud
      gcloud auth configure-docker \
      europe-west9-docker.pkg.dev
      
      # Build and push dagster-user-code-example-gcp image with tag 1.6.9
      docker build -t dagster-user-code-example-gcp:1.6.9 .
      docker tag dagster-user-code-example-gcp:1.6.9 europe-west9-docker.pkg.dev/prj-d-orchestrator-z0c8/dagster-user-code-example-gcp/dagster-user-code-example-gcp:1.6.9
      docker push europe-west9-docker.pkg.dev/prj-d-orchestrator-z0c8/dagster-user-code-example-gcp/dagster-user-code-example-gcp:1.6.9
      
      # Create the container registry for dagster-webserver
      gcloud artifacts repositories create dagster-webserver \
          --repository-format=docker \
          --location=europe-west9 \
          --description="Docker repository for dagster-webserver"
      
      # Build and push dagster-webserver image using DockerfileWebserv with tag 1.6.9
      docker build -t dagster-webserver:1.6.9 -f DockerfileWebserv .
      docker tag dagster-webserver:1.6.9 europe-west9-docker.pkg.dev/prj-d-orchestrator-z0c8/dagster-webserver/dagster-webserver:1.6.9
      docker push europe-west9-docker.pkg.dev/prj-d-orchestrator-z0c8/dagster-webserver/dagster-webserver:1.6.9

