# SPDX-FileCopyrightText: NONE
#
# SPDX-License-Identifier: CC0-1.0

import importlib
import json
from typing import Protocol, cast
from unittest.mock import patch

import pytest
import web
import yaml
from ramose import OpenAPIDocumentationHandler, Operation


class ApiModule(Protocol):
    app: web.application
    skgif_openapi_manager: OpenAPIDocumentationHandler


@pytest.fixture(scope="module")
def api_module() -> ApiModule:
    return cast(ApiModule, importlib.import_module("api_oc"))


def test_skgif_success_uses_json_media_type(api_module: ApiModule) -> None:
    body = json.dumps(
        {"@context": [{"@base": "https://api-stg.opencitations.net/"}], "@graph": []}
    )
    with patch.object(
        Operation, "exec", return_value=(200, body, "application/json", {})
    ):
        response = api_module.app.request("/skg-if/v1/products", host="localhost:8080")

    assert response.status == "200 OK"
    assert response.headers["Content-Type"] == "application/json"
    assert json.loads(response.data) == {
        "@context": [{"@base": "https://api-stg.opencitations.net/"}],
        "@graph": [],
    }


def test_skgif_resolves_percent_encoded_product_identifier(
    api_module: ApiModule,
) -> None:
    body = json.dumps(
        {
            "@context": [{"@base": "https://api-stg.opencitations.net/"}],
            "@graph": [
                {
                    "local_identifier": "https://w3id.org/oc/meta/br/0601",
                    "entity_type": "product",
                    "product_type": "literature",
                }
            ],
        }
    )
    with patch.object(
        Operation, "exec", return_value=(200, body, "application/json", {})
    ):
        response = api_module.app.request(
            "/skg-if/v1/products/https%3A%2F%2Fw3id.org%2Foc%2Fmeta%2Fbr%2F0601",
            host="localhost:8080",
        )

    assert response.status == "200 OK"
    assert json.loads(response.data)["@graph"] == [
        {
            "local_identifier": "https://w3id.org/oc/meta/br/0601",
            "entity_type": "product",
            "product_type": "literature",
        }
    ]


def test_skgif_invalid_filter_returns_rfc_7807_problem(api_module: ApiModule) -> None:
    with patch.object(
        Operation,
        "exec",
        return_value=(
            422,
            "HTTP status code 422: invalid filter 'unknown'",
            "text/plain",
            {},
        ),
    ):
        response = api_module.app.request(
            "/skg-if/v1/products?filter=unknown:value", host="localhost:8080"
        )

    assert response.status == "422 Unprocessable Entity"
    assert response.headers["Content-Type"] == "application/json"
    assert json.loads(response.data) == {
        "type": "about:blank",
        "title": "Unprocessable Entity",
        "status": 422,
        "detail": "invalid filter 'unknown'",
        "instance": "/skg-if/v1/products?filter=unknown:value",
    }


def test_skgif_unknown_operation_returns_rfc_7807_problem(
    api_module: ApiModule,
) -> None:
    response = api_module.app.request("/skg-if/v1/missing", host="localhost:8080")

    assert response.status == "404 Not Found"
    assert response.headers["Content-Type"] == "application/json"
    assert json.loads(response.data) == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": "the operation requested does not exist",
        "instance": "/skg-if/v1/missing",
    }


def test_skgif_openapi_documents_json_responses(api_module: ApiModule) -> None:
    _, document = api_module.skgif_openapi_manager.get_documentation("/skg-if/v1")
    spec = yaml.safe_load(document)

    for path in spec["paths"].values():
        responses = path["get"]["responses"]
        assert set(responses["200"]["content"]) == {"application/json"}
        for status, response in responses.items():
            if status != "200":
                assert set(response["content"]) == {"application/json"}
