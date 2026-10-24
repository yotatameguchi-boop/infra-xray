"""Compatibility shim for older pip/setuptools bundled with Python 3.9."""
from setuptools import find_packages, setup

setup(
    name="infra-xray",
    version="0.1.0",
    description="Local, evidence-based Terraform plan explorer",
    packages=find_packages(include=["infra_xray", "infra_xray.*"]),
    package_data={"infra_xray": ["static/*", "static/assets/*"]},
    entry_points={"console_scripts": ["infra-xray=infra_xray.cli:main"]},
    python_requires=">=3.9",
    license="MIT",
)
