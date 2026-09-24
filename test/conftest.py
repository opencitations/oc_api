import os
import subprocess
import tempfile
import time

import pytest
import requests

from ramose import APIManager, Operation

# v0.6.0
QLEVER_IMAGE = "adfreiburg/qlever@sha256:37d5ede193f1bffb6aebf734d15d2a4c2a3228ee102858b0c6c2e65c149a78ec"
QLEVER_CONTAINER = "oc-api-test-qlever"
QLEVER_PORT = 7011
INDEX_NAME = "oc-test"
DOCKER_USER = f"{os.getuid()}:{os.getgid()}"

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
QLEVER_DATA_DIR = os.path.join(TEST_DIR, "qlever-data")


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


@pytest.fixture(scope="session")
def qlever_endpoint():
    subprocess.run(["docker", "rm", "-f", QLEVER_CONTAINER], capture_output=True)
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            QLEVER_CONTAINER,
            "--entrypoint",
            "bash",
            "-u",
            DOCKER_USER,
            "-v",
            f"{QLEVER_DATA_DIR}:/index:ro",
            "-w",
            "/index",
            "-p",
            f"{QLEVER_PORT}:{QLEVER_PORT}",
            "--init",
            QLEVER_IMAGE,
            "-c",
            f"qlever-server -i {INDEX_NAME} -j 4 -p {QLEVER_PORT} -m 1G -c 500M -e 500M -k 50 -s 30s --no-metrics-log --no-resource-usage-log",
        ],
        check=True,
        capture_output=True,
    )
    _wait_for_http(QLEVER_PORT)
    yield f"http://127.0.0.1:{QLEVER_PORT}"
    subprocess.run(["docker", "stop", QLEVER_CONTAINER], capture_output=True)
    subprocess.run(["docker", "rm", "-f", QLEVER_CONTAINER], capture_output=True)


@pytest.fixture(scope="session")
def skgif_api_manager(qlever_endpoint):
    manager = APIManager(
        [os.path.join(TEST_DIR, "..", "src", "api", "skgif_v1.hf")],
        endpoint_override=qlever_endpoint,
    )
    for config in manager.all_conf.values():
        config["sources_map"] = {"meta": qlever_endpoint, "index": qlever_endpoint}
    return manager


def normalize_citation(citation: dict[str, str]) -> dict[str, str]:
    return {
        k: " ".join(sorted(v.split())) if k in ("citing", "cited") else v
        for k, v in citation.items()
    }


def normalize_citations(citations: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted([normalize_citation(c) for c in citations], key=lambda x: x["oci"])


def execute_operation(api_manager: APIManager, operation_url: str) -> str:
    op = api_manager.get_op(operation_url)
    if not isinstance(op, Operation):
        raise ValueError(f"Operation not found: {operation_url}")
    response = op.exec(method="get", content_type="application/json")
    if response.status_code != 200:
        raise RuntimeError(
            f"API returned status {response.status_code}: {response.body}"
        )
    return response.body


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
