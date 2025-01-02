# setup.py
from setuptools import setup, find_packages

setup(
    name="custom_run_launcher",
    version="0.5.0",
    packages=find_packages(),
    install_requires=[
        "dagster",
        "dagster-k8s",
        "kubernetes",
    ],
)
