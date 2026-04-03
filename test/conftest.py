import os
import subprocess
import tempfile
import time

import pytest
import requests

from src.ramose import APIManager

# v0.5.45
QLEVER_IMAGE = "adfreiburg/qlever@sha256:4672a53f0ff4e55ac921d25832a21ec0bb3ca08f54d7c1950d04ebf6af7b8c21"
QLEVER_CONTAINER = "oc-api-test-qlever"
QLEVER_PORT = 7011
INDEX_NAME = "oc-index-test"
DOCKER_USER = f"{os.getuid()}:{os.getgid()}"

# v7.2.16
VIRTUOSO_IMAGE = "openlink/virtuoso-opensource-7@sha256:e7a5cd1915569d70d8363503dc62f6bf818b485f1501b230c7608cde8528c72d"
VIRTUOSO_CONTAINER = "oc-api-test-virtuoso"
VIRTUOSO_HTTP_PORT = 8891
VIRTUOSO_ISQL_PORT = 1112

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
QLEVER_DATA_DIR = os.path.join(TEST_DIR, "qlever-index-data")
VIRTUOSO_DATA_DIR = os.path.join(TEST_DIR, "virtuoso-meta-data")


def _wait_for_http(port: int, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"http://127.0.0.1:{port}", timeout=2)
            if r.status_code in range(200, 500):
                return
        except requests.ConnectionError:
            pass
        time.sleep(1)
    raise TimeoutError(f"Service did not become ready on port {port} within {timeout}s")


def _wait_for_virtuoso(container: str, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["docker", "exec", container, "isql", "1111", "dba", "dba", "exec=SELECT 1;"],
            capture_output=True,
        )
        if result.returncode == 0:
            return
        time.sleep(1)
    raise TimeoutError(f"Virtuoso did not become ready within {timeout}s")


@pytest.fixture(scope="session")
def qlever_endpoint():
    subprocess.run(["docker", "rm", "-f", QLEVER_CONTAINER], capture_output=True)
    subprocess.run(
        [
            "docker", "run", "-d",
            "--name", QLEVER_CONTAINER,
            "--entrypoint", "bash",
            "-u", DOCKER_USER,
            "-v", f"{QLEVER_DATA_DIR}:/index:ro",
            "-w", "/index",
            "-p", f"{QLEVER_PORT}:{QLEVER_PORT}",
            "--init",
            QLEVER_IMAGE,
            "-c",
            f"qlever-server -i {INDEX_NAME} -j 4 -p {QLEVER_PORT} -m 1G -c 500M -e 500M -k 50 -s 30s",
        ],
        check=True,
        capture_output=True,
    )
    _wait_for_http(QLEVER_PORT)
    yield f"http://127.0.0.1:{QLEVER_PORT}"
    subprocess.run(["docker", "stop", QLEVER_CONTAINER], capture_output=True)
    subprocess.run(["docker", "rm", "-f", QLEVER_CONTAINER], capture_output=True)


@pytest.fixture(scope="session")
def virtuoso_endpoint():
    subprocess.run(["docker", "rm", "-f", VIRTUOSO_CONTAINER], capture_output=True)
    subprocess.run(
        [
            "docker", "run", "-d",
            "--name", VIRTUOSO_CONTAINER,
            "-p", f"{VIRTUOSO_HTTP_PORT}:8890",
            "-p", f"{VIRTUOSO_ISQL_PORT}:1111",
            "-e", "DBA_PASSWORD=dba",
            "-e", "VIRT_Parameters_DirsAllowed=/",
            "-v", f"{VIRTUOSO_DATA_DIR}:/data",
            VIRTUOSO_IMAGE,
        ],
        check=True,
        capture_output=True,
    )
    _wait_for_virtuoso(VIRTUOSO_CONTAINER)
    subprocess.run(
        [
            "docker", "exec", VIRTUOSO_CONTAINER,
            "isql", "1111", "dba", "dba",
            "exec=ld_dir('/data', 'meta_subset.nq', ''); rdf_loader_run(); checkpoint;",
        ],
        check=True,
        capture_output=True,
    )
    yield f"http://127.0.0.1:{VIRTUOSO_HTTP_PORT}/sparql"
    subprocess.run(["docker", "stop", VIRTUOSO_CONTAINER], capture_output=True)
    subprocess.run(["docker", "rm", "-f", VIRTUOSO_CONTAINER], capture_output=True)


def normalize_citation(citation: dict[str, str]) -> dict[str, str]:
    return {k: " ".join(sorted(v.split())) if k in ("citing", "cited") else v for k, v in citation.items()}


def normalize_citations(citations: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted([normalize_citation(c) for c in citations], key=lambda x: x["oci"])


def execute_operation(api_manager: APIManager, operation_url: str) -> str:
    op = api_manager.get_op(operation_url)
    if isinstance(op, tuple):
        raise ValueError(f"Operation not found: {operation_url}")
    status, result, _ = op.exec(method="get", content_type="application/json")
    if status != 200:
        raise RuntimeError(f"API returned status {status}: {result}")
    return result


def create_api_manager(
    config_path: str,
    replacements: dict[str, str],
    env_vars: dict[str, str] | None = None,
) -> APIManager:
    full_config_path = os.path.join(TEST_DIR, "..", config_path)

    with open(full_config_path, "r", encoding="utf8") as f:
        config_content = f.read()

    for old, new in replacements.items():
        config_content = config_content.replace(old, new)

    if env_vars:
        for key, value in env_vars.items():
            os.environ[key] = value

    tmp_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".hf", delete=False, dir=TEST_DIR
    )
    tmp_file.write(config_content)
    tmp_file.close()

    try:
        return APIManager([tmp_file.name])
    finally:
        os.unlink(tmp_file.name)
