import json
from unittest.mock import patch

import pytest
from requests import RequestException

from conftest import create_api_manager, execute_operation, normalize_citations
from src.ramose import APIManager


@pytest.fixture(scope="session")
def api_manager() -> APIManager:
    return create_api_manager("src/api/index_v2.hf", {
        "#base https://api.opencitations.net/index": "#base http://127.0.0.1:7011",
        "#endpoint http://qlever-service.default.svc.cluster.local:7011": "#endpoint http://127.0.0.1:7011",
        "#addon indexapi_v2": "#addon ../src/api/indexapi_v2",
    }, env_vars={
        "SPARQL_ENDPOINT_INDEX": "http://127.0.0.1:7011",
        "SPARQL_ENDPOINT_META": "http://127.0.0.1:8891/sparql",
    })


MAIN_PAPER_OMID = "omid:br/062104388184"
MAIN_PAPER_DOI = "doi:10.1162/qss_a_00292"
MAIN_PAPER_PIDS = f"{MAIN_PAPER_OMID} {MAIN_PAPER_DOI}"

EXPECTED_CITATIONS = [
    {
        "oci": "06011163661-062104388184",
        "citing": "omid:br/06011163661 doi:10.1007/s00799-025-00425-9",
        "cited": MAIN_PAPER_PIDS,
        "creation": "2025-07-27",
        "timespan": "P1Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "0607160655-062104388184",
        "citing": "omid:br/0607160655 doi:10.1145/3677389.3702546",
        "cited": MAIN_PAPER_PIDS,
        "creation": "2024-12-16",
        "timespan": "P0Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "0609955465-062104388184",
        "citing": "omid:br/0609955465 doi:10.1057/s41599-025-05387-6",
        "cited": MAIN_PAPER_PIDS,
        "creation": "2025-07-09",
        "timespan": "P1Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "06290518281-062104388184",
        "citing": "omid:br/06290518281 doi:10.1007/s11192-024-05160-7",
        "cited": MAIN_PAPER_PIDS,
        "creation": "2024-09-28",
        "timespan": "P0Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
]

EXPECTED_REFERENCES = [
    {
        "oci": "062104388184-06103007140",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06103007140 doi:10.3233/sw-210434 openalex:W3175063576",
        "creation": "2024",
        "timespan": "P2Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-0610867930",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/0610867930 doi:10.1007/s41019-020-00118-0 openalex:W3023112361",
        "creation": "2024",
        "timespan": "P3Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-061102015064",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/061102015064 doi:10.5195/jmla.2019.650 openalex:W4236981150",
        "creation": "2024",
        "timespan": "P4Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-061102015169",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/061102015169 doi:10.5195/jmla.2018.280 openalex:W4243798656",
        "creation": "2024",
        "timespan": "P5Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-061201341000",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/061201341000 doi:10.1093/nar/gku1061 openalex:W183866246 pmid:25378340",
        "creation": "2024",
        "timespan": "P9Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-061302130471",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/061302130471 doi:10.1007/s11192-019-03217-6 openalex:W2938946739",
        "creation": "2024",
        "timespan": "P4Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-061501741757",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/061501741757 doi:10.3390/publications9010012 openalex:W3137875885",
        "creation": "2024",
        "timespan": "P2Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-061503029782",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/061503029782 doi:10.1080/00049670.2005.10721710 openalex:W2055380710",
        "creation": "2024",
        "timespan": "P18Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-061503595784",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/061503595784 doi:10.35092/yhjc.c.4586573",
        "creation": "2024",
        "timespan": "",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06150878997",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06150878997 doi:10.5260/chara.18.3.25 openalex:W2799725891",
        "creation": "2024",
        "timespan": "P7Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-061703213020",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/061703213020 doi:10.1109/coinfo.2009.66 openalex:W3122659278",
        "creation": "2024",
        "timespan": "P14Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-061703367432",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/061703367432 doi:10.1145/1060745.1060835 openalex:W2152577585",
        "creation": "2024",
        "timespan": "P19Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-061801986475",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/061801986475 doi:10.6087/kcse.192 openalex:W3006916957",
        "creation": "2024",
        "timespan": "P3Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-061802636786",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/061802636786 doi:10.1007/978-3-319-11955-7_42 openalex:W403298716",
        "creation": "2024",
        "timespan": "P10Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062103573093",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062103573093 doi:10.6084/m9.figshare.3443876.v7",
        "creation": "2024",
        "timespan": "",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062202390183",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062202390183 doi:10.1007/978-3-319-47602-5_18 openalex:W2578379428",
        "creation": "2024",
        "timespan": "P8Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062203843935",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062203843935 doi:10.7287/peerj.preprints.3469v1 doi:10.7717/peerj.4201 pmid:29312824",
        "creation": "2024",
        "timespan": "P6Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062303563887",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062303563887 doi:10.25495/7gxk-rd71",
        "creation": "2024",
        "timespan": "",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062501777134",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062501777134 doi:10.1162/qss_a_00023 openalex:W3106215946",
        "creation": "2024",
        "timespan": "P3Y",
        "journal_sc": "yes",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062501777138",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062501777138 doi:10.1162/qss_a_00022 openalex:W3002281830",
        "creation": "2024",
        "timespan": "P3Y",
        "journal_sc": "yes",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062502075555",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062502075555 doi:10.1108/dta-12-2018-0110 openalex:W2969235873",
        "creation": "2024",
        "timespan": "P4Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062502379711",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062502379711 doi:10.1145/3183558 openalex:W2893990175",
        "creation": "2024",
        "timespan": "P5Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06250648347",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06250648347 doi:10.1016/j.joi.2015.11.008 openalex:W2231201268",
        "creation": "2024",
        "timespan": "P7Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062602030618",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062602030618 doi:10.1038/npre.2010.4595.1 openalex:W618057993",
        "creation": "2024",
        "timespan": "P13Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062604422894",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062604422894 doi:10.23640/07243.12469094.v1",
        "creation": "2024",
        "timespan": "",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062604422895",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062604422895 doi:10.48550/arxiv.1902.02534",
        "creation": "2024",
        "timespan": "",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062604422896",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062604422896 doi:10.5281/zenodo.5557028",
        "creation": "2024",
        "timespan": "",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062604422897",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062604422897 doi:10.48550/arxiv.2210.02534",
        "creation": "2024",
        "timespan": "",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062604422898",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062604422898 doi:10.6084/m9.figshare.21747461.v3",
        "creation": "2024",
        "timespan": "",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-062604422899",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/062604422899 doi:10.6084/m9.figshare.21747536.v3",
        "creation": "2024",
        "timespan": "",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06301298733",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06301298733 doi:10.1087/20120404 openalex:W2041971736",
        "creation": "2024",
        "timespan": "P11Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06302611193",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06302611193 doi:10.1007/978-3-319-68130-6_8 openalex:W2761760240",
        "creation": "2024",
        "timespan": "P7Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-0630685531",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/0630685531 doi:10.1038/sdata.2016.18 openalex:W2302501749 pmid:26978244 pmid:30890711",
        "creation": "2024",
        "timespan": "P7Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06320129129",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06320129129 doi:10.6084/m9.figshare.6741422.v18",
        "creation": "2024",
        "timespan": "",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06401296979",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06401296979 doi:10.1007/978-3-031-06981-9_18 openalex:W4285173206",
        "creation": "2024",
        "timespan": "P2Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06401334370",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06401334370 doi:10.1515/bfp-2020-2042 openalex:W3112005222",
        "creation": "2024",
        "timespan": "P3Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06401935463",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06401935463 doi:10.1145/2872427.2874809 openalex:W2309189658",
        "creation": "2024",
        "timespan": "P7Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06402610446",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06402610446 doi:10.1007/978-3-319-70407-4_36 openalex:W2767995756",
        "creation": "2024",
        "timespan": "P7Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-0641097549",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/0641097549 doi:10.48550/arxiv.2205.01833 openalex:W4229010617",
        "creation": "2024",
        "timespan": "",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-0650312105",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/0650312105 doi:10.2139/ssrn.1639998 openalex:W2104231400",
        "creation": "2024",
        "timespan": "P14Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06603394186",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06603394186 doi:10.1145/2362499.2362502 openalex:W2054509941",
        "creation": "2024",
        "timespan": "P12Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06702573854",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06702573854 doi:10.1007/978-3-319-58068-5_6 openalex:W2616601454",
        "creation": "2024",
        "timespan": "P7Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06804723331",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06804723331 doi:10.18653/v1/2020.sdp-1.2",
        "creation": "2024",
        "timespan": "",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06902362263",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06902362263 doi:10.1109/jcdl52503.2021.00029 openalex:W3136510568",
        "creation": "2024",
        "timespan": "P2Y",
        "journal_sc": "no",
        "author_sc": "no",
    },
    {
        "oci": "062104388184-06903616292",
        "citing": MAIN_PAPER_PIDS,
        "cited": "omid:br/06903616292 doi:10.6084/m9.figshare.6683855.v1 openalex:W3215308037",
        "creation": "2024",
        "timespan": "",
        "journal_sc": "no",
        "author_sc": "no",
    },
]

ZENODO_DMP_OMID = "omid:br/060504627"
ZENODO_DMP_DOI = "doi:10.5281/zenodo.4733919"
ZENODO_DMP_PIDS = f"{ZENODO_DMP_OMID} {ZENODO_DMP_DOI}"

DOI_ERRORS_OMID = "omid:br/061202127149"
DOI_ERRORS_DOI = "doi:10.1007/s11192-022-04367-w"
DOI_ERRORS_OPENALEX = "openalex:W3214893238"
DOI_ERRORS_PIDS = f"{DOI_ERRORS_OMID} {DOI_ERRORS_DOI} {DOI_ERRORS_OPENALEX}"

ZENODO_CLEANING_OMID = "omid:br/060504675"
ZENODO_CLEANING_DOI = "doi:10.5281/zenodo.4734512"
ZENODO_CLEANING_PIDS = f"{ZENODO_CLEANING_OMID} {ZENODO_CLEANING_DOI}"

QSS_ARTICLE_OMID = "omid:br/062501777134"
QSS_ARTICLE_DOI = "doi:10.1162/qss_a_00023"
QSS_ARTICLE_OPENALEX = "openalex:W3106215946"
QSS_ARTICLE_PIDS = f"{QSS_ARTICLE_OMID} {QSS_ARTICLE_DOI} {QSS_ARTICLE_OPENALEX}"

QSS_CITING_OMID = "omid:br/062104388184"
QSS_CITING_DOI = "doi:10.1162/qss_a_00292"
QSS_CITING_PIDS = f"{QSS_CITING_OMID} {QSS_CITING_DOI}"

EXPECTED_ZENODO_DMP_CITATIONS = [
    {
        "oci": "061202127149-060504627",
        "citing": DOI_ERRORS_PIDS,
        "cited": ZENODO_DMP_PIDS,
        "creation": "2022-06",
        "timespan": "P0Y11M",
        "journal_sc": "no",
        "author_sc": "yes",
    },
    {
        "oci": "060504675-060504627",
        "citing": ZENODO_CLEANING_PIDS,
        "cited": ZENODO_DMP_PIDS,
        "creation": "2021-06-08",
        "timespan": "-P0Y0M1D",
        "journal_sc": "yes",
        "author_sc": "yes",
    },
]

EXPECTED_QSS_ARTICLE_CITATIONS = [
    {
        "oci": "062104388184-062501777134",
        "citing": QSS_CITING_PIDS,
        "cited": QSS_ARTICLE_PIDS,
        "creation": "2024",
        "timespan": "P3Y",
        "journal_sc": "yes",
        "author_sc": "no",
    },
    {
        "oci": "061202127149-062501777134",
        "citing": DOI_ERRORS_PIDS,
        "cited": QSS_ARTICLE_PIDS,
        "creation": "2022-06",
        "timespan": "P2Y4M",
        "journal_sc": "no",
        "author_sc": "yes",
    },
]


def test_citation_by_oci_outgoing(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, "/v2/citation/062104388184-06103007140"))
    assert normalize_citations(result) == normalize_citations([EXPECTED_REFERENCES[0]])


def test_citation_by_oci_incoming(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, "/v2/citation/06290518281-062104388184"))
    assert normalize_citations(result) == normalize_citations([EXPECTED_CITATIONS[3]])


def test_citations_incoming(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, f"/v2/citations/{MAIN_PAPER_OMID}"))
    assert normalize_citations(result) == normalize_citations(EXPECTED_CITATIONS)


def test_citations_no_incoming(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, "/v2/citations/omid:br/06011163661"))
    assert result == []


def test_citation_count(api_manager: APIManager) -> None:
    result = json.loads(
        execute_operation(api_manager, f"/v2/citation-count/{MAIN_PAPER_OMID}")
    )
    assert result == [{"count": "4"}]


def test_citation_count_zero(api_manager: APIManager) -> None:
    result = json.loads(
        execute_operation(api_manager, "/v2/citation-count/omid:br/06011163661")
    )
    assert result == [{"count": "0"}]


def test_reference_count(api_manager: APIManager) -> None:
    result = json.loads(
        execute_operation(api_manager, f"/v2/reference-count/{MAIN_PAPER_OMID}")
    )
    assert result == [{"count": "45"}]


def test_reference_count_zero(api_manager: APIManager) -> None:
    result = json.loads(
        execute_operation(api_manager, "/v2/reference-count/omid:br/06103007140")
    )
    assert result == [{"count": "0"}]


def test_references(api_manager: APIManager) -> None:
    result = json.loads(
        execute_operation(api_manager, f"/v2/references/{MAIN_PAPER_OMID}")
    )
    assert normalize_citations(result) == normalize_citations(EXPECTED_REFERENCES)


def test_references_no_outgoing(api_manager: APIManager) -> None:
    result = json.loads(
        execute_operation(api_manager, "/v2/references/omid:br/06103007140")
    )
    assert result == []


def test_citations_by_doi(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, f"/v2/citations/{MAIN_PAPER_DOI}"))
    assert normalize_citations(result) == normalize_citations(EXPECTED_CITATIONS)


def test_references_by_doi(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, f"/v2/references/{MAIN_PAPER_DOI}"))
    assert normalize_citations(result) == normalize_citations(EXPECTED_REFERENCES)


def test_citation_count_by_doi(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, f"/v2/citation-count/{MAIN_PAPER_DOI}"))
    assert result == [{"count": "4"}]


def test_reference_count_by_doi(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, f"/v2/reference-count/{MAIN_PAPER_DOI}"))
    assert result == [{"count": "45"}]


def test_citation_count_by_pmid(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, "/v2/citation-count/pmid:25378340"))
    assert result == [{"count": "1"}]


def test_reference_count_by_pmid(api_manager: APIManager) -> None:
    result = json.loads(execute_operation(api_manager, "/v2/reference-count/pmid:25378340"))
    assert result == [{"count": "0"}]


def test_venue_citation_count(api_manager: APIManager) -> None:
    result = json.loads(
        execute_operation(api_manager, "/v2/venue-citation-count/issn:2641-3337")
    )
    assert result == [{"count": "6"}]


def test_citations_negative_timespan(api_manager: APIManager) -> None:
    result = json.loads(
        execute_operation(api_manager, f"/v2/citations/{ZENODO_DMP_OMID}")
    )
    assert normalize_citations(result) == normalize_citations(
        EXPECTED_ZENODO_DMP_CITATIONS
    )


def test_citation_count_zenodo_dmp(api_manager: APIManager) -> None:
    result = json.loads(
        execute_operation(api_manager, f"/v2/citation-count/{ZENODO_DMP_OMID}")
    )
    assert result == [{"count": "2"}]


def test_citation_count_nonexistent_doi(api_manager: APIManager) -> None:
    result = json.loads(
        execute_operation(api_manager, "/v2/citation-count/doi:10.9999/nonexistent")
    )
    assert result == [{"count": "0"}]


def test_citations_with_author_sc(api_manager: APIManager) -> None:
    result = json.loads(
        execute_operation(api_manager, f"/v2/citations/{QSS_ARTICLE_OMID}")
    )
    assert normalize_citations(result) == normalize_citations(
        EXPECTED_QSS_ARTICLE_CITATIONS
    )


def test_citation_count_meta_sparql_failure(api_manager: APIManager) -> None:
    with patch("indexapi_v2.post", side_effect=RequestException), \
         patch("indexapi_common.post", side_effect=RequestException):
        result = json.loads(
            execute_operation(api_manager, f"/v2/citation-count/{MAIN_PAPER_DOI}")
        )
    assert result == [{"count": "0"}]


def test_citations_meta_sparql_failure(api_manager: APIManager) -> None:
    with patch("indexapi_v2.post", side_effect=RequestException), \
         patch("indexapi_common.post", side_effect=RequestException):
        result = json.loads(
            execute_operation(api_manager, f"/v2/citations/{MAIN_PAPER_OMID}")
        )
    assert result == []
