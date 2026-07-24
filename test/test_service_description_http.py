# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

import importlib
from pathlib import Path

import pytest

SERVICE_DESCRIPTIONS = Path("static/service-descriptions")


@pytest.fixture(scope="module")
def application(qlever_endpoint: str, virtuoso_endpoint: str):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("SPARQL_ENDPOINT_INDEX", qlever_endpoint)
        monkeypatch.setenv("SPARQL_ENDPOINT_META", virtuoso_endpoint)
        module = importlib.import_module("api_oc")
        yield module.app


@pytest.mark.parametrize(
    ("path", "accept", "file_name", "content_type"),
    [
        (
            "/sparql/index",
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "index.html",
            "text/html; charset=utf-8",
        ),
        (
            "/sparql/index",
            "application/ld+json;q=0, text/turtle;q=1",
            "index.ttl",
            "text/turtle; charset=utf-8",
        ),
        (
            "/sparql/index",
            "text/turtle;q=0.2, application/ld+json;q=1",
            "index.jsonld",
            "application/ld+json; charset=utf-8",
        ),
        (
            "/.well-known/void",
            "application/rdf+xml",
            "void.rdf",
            "application/rdf+xml; charset=utf-8",
        ),
    ],
)
def test_service_description_negotiates_accept(
    application,
    path: str,
    accept: str,
    file_name: str,
    content_type: str,
) -> None:
    response = application.request(path, headers={"Accept": accept})

    assert response.status == "200 OK"
    assert response.headers == {
        "Content-Type": content_type,
        "Access-Control-Allow-Origin": "*",
        "Vary": "Accept",
    }
    assert response.data == (SERVICE_DESCRIPTIONS / file_name).read_bytes()


def test_service_description_rejects_unavailable_representation(application) -> None:
    response = application.request(
        "/sparql/index", headers={"Accept": "application/pdf"}
    )

    assert response.status == "406 Not Acceptable"
    assert response.headers == {"Content-Type": "text/html"}
    assert response.data == b"not acceptable"
