import json
from unittest.mock import patch

import pytest
from requests import RequestException

from conftest import create_api_manager, execute_operation, normalize_citations
from src.ramose import APIManager


@pytest.fixture(scope="session")
def api_manager() -> APIManager:
    return create_api_manager("src/api/index_v1.hf", {
        "#base https://api.opencitations.net/index": "#base http://127.0.0.1:7011",
        "#endpoint http://qlever-service.default.svc.cluster.local:7011": "#endpoint http://127.0.0.1:7011",
        "#addon indexapi_v1": "#addon ../src/api/indexapi_v1",
    }, env_vars={
        "SPARQL_ENDPOINT_INDEX": "http://127.0.0.1:7011",
        "SPARQL_ENDPOINT_META": "http://127.0.0.1:8891/sparql",
    })


DOI_ERRORS_DOI = "10.1007/s11192-022-04367-w"
QSS_ARTICLE_DOI = "10.1162/qss_a_00023"
ZENODO_DMP_DOI = "10.5281/zenodo.4733919"
MAIN_PAPER_DOI = "10.1162/qss_a_00292"

EXPECTED_DOI_ERRORS_REFERENCES = [
    {
        "oci": "061202127149-060504627",
        "citing": DOI_ERRORS_DOI,
        "cited": ZENODO_DMP_DOI,
        "creation": "2022-06",
        "timespan": "P0Y11M",
        "journal_sc": "no",
        "author_sc": "yes",
    },
    {
        "oci": "061202127149-062501777134",
        "citing": DOI_ERRORS_DOI,
        "cited": QSS_ARTICLE_DOI,
        "creation": "2022-06",
        "timespan": "P2Y4M",
        "journal_sc": "no",
        "author_sc": "yes",
    },
]

EXPECTED_QSS_ARTICLE_CITATIONS = [
    {
        "oci": "061202127149-062501777134",
        "citing": DOI_ERRORS_DOI,
        "cited": QSS_ARTICLE_DOI,
        "creation": "2022-06",
        "timespan": "P2Y4M",
        "journal_sc": "no",
        "author_sc": "yes",
    },
    {
        "oci": "062104388184-062501777134",
        "citing": MAIN_PAPER_DOI,
        "cited": QSS_ARTICLE_DOI,
        "creation": "2024",
        "timespan": "P3Y",
        "journal_sc": "yes",
        "author_sc": "no",
    },
]

EXPECTED_ZENODO_DMP_CITATIONS = [
    {
        "oci": "060504675-060504627",
        "citing": "10.5281/zenodo.4734512",
        "cited": ZENODO_DMP_DOI,
        "creation": "2021-06-08",
        "timespan": "-P0Y0M1D",
        "journal_sc": "yes",
        "author_sc": "yes",
    },
    {
        "oci": "061202127149-060504627",
        "citing": DOI_ERRORS_DOI,
        "cited": ZENODO_DMP_DOI,
        "creation": "2022-06",
        "timespan": "P0Y11M",
        "journal_sc": "no",
        "author_sc": "yes",
    },
]


def test_citation_by_oci(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, "/v1/citation/062104388184-062501777134"))
    assert normalize_citations(result) == normalize_citations([EXPECTED_QSS_ARTICLE_CITATIONS[1]])


def test_citations_by_doi(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, f"/v1/citations/{QSS_ARTICLE_DOI}"))
    assert normalize_citations(result) == normalize_citations(EXPECTED_QSS_ARTICLE_CITATIONS)


def test_citations_negative_timespan(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, f"/v1/citations/{ZENODO_DMP_DOI}"))
    assert normalize_citations(result) == normalize_citations(EXPECTED_ZENODO_DMP_CITATIONS)


def test_citations_no_incoming(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, "/v1/citations/10.5281/zenodo.4734512"))
    assert result == []


def test_citation_count(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, f"/v1/citation-count/{QSS_ARTICLE_DOI}"))
    assert result == [{"count": "2"}]


def test_citation_count_zenodo(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, f"/v1/citation-count/{ZENODO_DMP_DOI}"))
    assert result == [{"count": "2"}]


def test_citation_count_zero(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, f"/v1/citation-count/{DOI_ERRORS_DOI}"))
    assert result == [{"count": "0"}]


def test_citation_count_nonexistent(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, "/v1/citation-count/10.9999/nonexistent"))
    assert result == [{"count": "0"}]


def test_references(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, f"/v1/references/{DOI_ERRORS_DOI}"))
    assert normalize_citations(result) == normalize_citations(EXPECTED_DOI_ERRORS_REFERENCES)


def test_references_no_outgoing(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, "/v1/references/10.3233/sw-210434"))
    assert result == []


def test_reference_count(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, f"/v1/reference-count/{DOI_ERRORS_DOI}"))
    assert result == [{"count": "2"}]


def test_reference_count_zero(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, "/v1/reference-count/10.3233/sw-210434"))
    assert result == [{"count": "0"}]


def test_citation_count_meta_sparql_failure(api_manager: APIManager) -> None:
    with patch("indexapi_v1.post", side_effect=RequestException), \
         patch("indexapi_common.post", side_effect=RequestException):
        result = json.loads(
            execute_operation(api_manager, f"/v1/citation-count/{QSS_ARTICLE_DOI}")
        )
    assert result == [{"count": "0"}]


def test_citations_meta_sparql_failure(api_manager: APIManager) -> None:
    with patch("indexapi_v1.post", side_effect=RequestException), \
         patch("indexapi_common.post", side_effect=RequestException):
        result = json.loads(
            execute_operation(api_manager, f"/v1/citations/{QSS_ARTICLE_DOI}")
        )
    assert result == []
