import logging
import sys
from typing import Mapping, Optional, Sequence

import kubernetes
from dagster import _check as check
from dagster._core.events import EngineEventData
from dagster._core.storage.dagster_run import DagsterRun
from dagster._core.storage.tags import DOCKER_IMAGE_TAG
from dagster._utils.error import serializable_error_info_from_exc_info
from dagster._utils.merger import merge_dicts

from dagster_k8s.client import DagsterKubernetesClient
from dagster_k8s.job import DagsterK8sJobConfig, construct_dagster_k8s_job, get_job_name_from_run_id
from dagster_k8s.launcher import K8sRunLauncher


class MultiClusterK8sRunLauncher(K8sRunLauncher):
    """RunLauncher that starts a Kubernetes Job for each Dagster job run in a specified Kubernetes cluster."""

    def __init__(
        self,
        clusters: Mapping[str, dict],
        default_cluster: str,
        **kwargs,
    ):
        """Initialize with multiple cluster configurations.

        Args:
            clusters (Mapping[str, dict]): Mapping of cluster names to configurations.
                Each config must contain `kubeconfig_file` or `context` if not using in-cluster config.
            default_cluster (str): Name of the default cluster to use if none is specified for a run.
        """
        super().__init__(**kwargs)
        self.clusters = check.dict_param(clusters, "clusters", key_type=str, value_type=dict)
        self.default_cluster = check.str_param(default_cluster, "default_cluster")
        self._clients = {}

        for cluster_name, cluster_config in self.clusters.items():
            self._initialize_client(cluster_name, cluster_config)

    @classmethod
    def config_schema(cls):
        """Define the configuration schema."""
        return merge_dicts(
            super().config_schema(),
            {
                "clusters": {
                    "type": dict,
                    "description": "Mapping of cluster names to Kubernetes configurations. Each cluster can define `kubeconfig_file` or `context`.",
                },
                "default_cluster": {
                    "type": str,
                    "description": "The default cluster to use if none is specified for a run.",
                },
            },
        )

    @classmethod
    def from_config_value(cls, inst_data, config_value):
        """Initialize from configuration."""
        clusters = config_value.pop("clusters")
        default_cluster = config_value.pop("default_cluster")
        return cls(inst_data=inst_data, clusters=clusters, default_cluster=default_cluster, **config_value)

    def _initialize_client(self, cluster_name: str, cluster_config: dict) -> None:
        """Initialize Kubernetes client for a given cluster."""
        load_incluster_config = cluster_config.get("load_incluster_config", True)
        kubeconfig_file = cluster_config.get("kubeconfig_file")
        context = cluster_config.get("context")

        if load_incluster_config:
            kubernetes.config.load_incluster_config()
        elif kubeconfig_file:
            kubernetes.config.load_kube_config(kubeconfig_file, context=context)
        else:
            raise ValueError(f"Cluster {cluster_name} missing valid kubeconfig or in-cluster config.")

        self._clients[cluster_name] = DagsterKubernetesClient.production_client()

    def _get_client_for_run(self, dagster_run: DagsterRun) -> DagsterKubernetesClient:
        """Determine the appropriate Kubernetes client for the run."""
        container_context = self.get_container_context_for_run(dagster_run)
        cluster_name = container_context.additional_env_vars.get("DAGSTER_CLUSTER", self.default_cluster)
        if cluster_name not in self._clients:
            raise ValueError(f"Cluster '{cluster_name}' is not configured in this launcher.")
        return self._clients[cluster_name]

    def _launch_k8s_job_with_args(
        self, job_name: str, args: Optional[Sequence[str]], run: DagsterRun
    ) -> None:
        container_context = self.get_container_context_for_run(run)
        client = self._get_client_for_run(run)

        pod_name = job_name
        job_origin = check.not_none(run.job_code_origin)
        user_defined_k8s_config = container_context.run_k8s_config
        repository_origin = job_origin.repository_origin

        job_config = container_context.get_k8s_job_config(
            job_image=repository_origin.container_image, run_launcher=self
        )

        labels = {
            "dagster/job": job_origin.job_name,
            "dagster/run-id": run.run_id,
        }
        if run.remote_job_origin:
            labels["dagster/code-location"] = (
                run.remote_job_origin.repository_origin.code_location_origin.location_name
            )

        job = construct_dagster_k8s_job(
            job_config=job_config,
            args=args,
            job_name=job_name,
            pod_name=pod_name,
            component="run_worker",
            user_defined_k8s_config=user_defined_k8s_config,
            labels=labels,
            env_vars=[
                {
                    "name": "DAGSTER_RUN_JOB_NAME",
                    "value": job_origin.job_name,
                },
            ],
        )

        self._instance.add_run_tags(
            run.run_id,
            {DOCKER_IMAGE_TAG: job.spec.template.spec.containers[0].image},
        )

        namespace = check.not_none(container_context.namespace)

        self._instance.report_engine_event(
            f"Creating Kubernetes run worker job in cluster '{client.cluster_name}'",
            run,
            EngineEventData(
                {
                    "Kubernetes Job name": job_name,
                    "Kubernetes Namespace": namespace,
                    "Run ID": run.run_id,
                }
            ),
            cls=self.__class__,
        )

        client.create_namespaced_job_with_retries(body=job, namespace=namespace)
        self._instance.report_engine_event(
            f"Kubernetes run worker job created in cluster '{client.cluster_name}'",
            run,
            cls=self.__class__,
        )

    def terminate(self, run_id):
        """Terminate a job across clusters."""
        check.str_param(run_id, "run_id")
        run = self._instance.get_run_by_id(run_id)

        if not run or run.is_finished:
            return False

        self._instance.report_run_canceling(run)

        container_context = self.get_container_context_for_run(run)
        client = self._get_client_for_run(run)

        job_name = get_job_name_from_run_id(
            run_id, resume_attempt_number=self._get_resume_attempt_number(run)
        )

        try:
            termination_result = client.delete_job(
                job_name=job_name, namespace=container_context.namespace
            )
            if termination_result:
                self._instance.report_engine_event(
                    f"Run was terminated successfully in cluster '{client.cluster_name}'.",
                    dagster_run=run,
                    cls=self.__class__,
                )
            else:
                self._instance.report_engine_event(
                    f"Run was not terminated successfully; delete_job returned {termination_result} in cluster '{client.cluster_name}'",
                    dagster_run=run,
                    cls=self.__class__,
                )
            return termination_result
        except Exception:
            self._instance.report_engine_event(
                f"Run was not terminated successfully; encountered error in delete_job in cluster '{client.cluster_name}'",
                dagster_run=run,
                engine_event_data=EngineEventData.engine_error(
                    serializable_error_info_from_exc_info(sys.exc_info())
                ),
                cls=self.__class__,
            )
