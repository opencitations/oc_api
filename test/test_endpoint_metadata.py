# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from collections.abc import Callable
from pathlib import Path
from unittest.mock import call, patch

import pytest
import requests
from rdflib import Graph, Literal, Node, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, RDF, XSD

from src.endpoint_metadata import (
    FORMATS,
    INPUT_FORMAT_PROBES,
    RESULT_FORMAT_PROBES,
    SD,
    SERVICE_DESCRIPTION_SERIALIZATIONS,
    SERVICE_QUERY_PROBE,
    SPDX_TURTLE_HEADER,
    SPARQL_11_QUERY_PROBE,
    DISTINCT_STATISTIC_QUERIES,
    VOID,
    DatasetMetadata,
    Partition,
    ScopeMetadata,
    ServiceCapabilities,
    build_service_description,
    collect_distinct_statistics,
    collect_scope_metadata,
    detect_features,
    detect_input_formats,
    detect_result_formats,
    detect_service_capabilities,
    detect_supported_languages,
    execute_sparql,
    input_format_query,
    write_service_descriptions,
)

QUERY_ENDPOINT = "http://127.0.0.1:8890/sparql?token=private"
PUBLIC_ENDPOINT = "https://example.org/sparql"
META_BR_GRAPH = "https://w3id.org/oc/meta/br/"
EXAMPLE_PROPERTY_A = URIRef("http://example.org/p-a")
EXAMPLE_PROPERTY_B = URIRef("http://example.org/p-b")
EXAMPLE_CLASS = URIRef("http://example.org/Class")


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        content_type: str,
        body: dict[str, object],
    ) -> None:
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.body = body

    def json(self) -> dict[str, object]:
        return self.body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def _sparql_count(value: int) -> dict[str, dict[str, list[dict[str, dict[str, str]]]]]:
    return {"results": {"bindings": [{"value": {"value": str(value)}}]}}


def _sparql_partitions(
    *partitions: Partition,
) -> dict[str, dict[str, list[dict[str, dict[str, str]]]]]:
    return {
        "results": {
            "bindings": [
                {
                    "resource": {"value": str(partition.resource)},
                    "count": {"value": str(partition.count)},
                }
                for partition in partitions
            ]
        }
    }


def _scope_metadata(triples: int) -> ScopeMetadata:
    return ScopeMetadata(
        statistics={
            VOID.triples: triples,
            VOID.properties: 2,
            VOID.distinctSubjects: 3,
            VOID.distinctObjects: 4,
            VOID.classes: 1,
        },
        property_partitions=[
            Partition(EXAMPLE_PROPERTY_A, 4),
            Partition(EXAMPLE_PROPERTY_B, 5),
        ],
        class_partitions=[Partition(EXAMPLE_CLASS, 6)],
    )


def _dataset_metadata(with_named_graph: bool) -> DatasetMetadata:
    named_graphs = {META_BR_GRAPH: _scope_metadata(3)} if with_named_graph else {}
    return DatasetMetadata(default_scope=_scope_metadata(7), named_graphs=named_graphs)


def _capabilities() -> ServiceCapabilities:
    return ServiceCapabilities(
        supported_languages=[SD.SPARQL11Query],
        result_formats=[FORMATS.SPARQL_Results_JSON, FORMATS.Turtle],
        input_formats=[FORMATS.Turtle],
        features=[SD.BasicFederatedQuery, SD.UnionDefaultGraph],
    )


def _partition_rows(
    graph: Graph,
    subject: Node,
    partition_predicate: URIRef,
    resource_predicate: URIRef,
    count_predicate: URIRef,
) -> list[tuple[Node, Node]]:
    rows: list[tuple[Node, Node]] = []
    for partition in graph.objects(subject, partition_predicate):
        resource = next(graph.objects(partition, resource_predicate))
        count = next(graph.objects(partition, count_predicate))
        rows.append((resource, count))
    return sorted(rows, key=lambda row: str(row[0]))


def test_collect_distinct_statistics_queries_endpoint() -> None:
    responses = [
        _sparql_count(7),
        _sparql_count(9),
    ]
    with patch(
        "src.endpoint_metadata.execute_sparql",
        side_effect=responses,
    ) as execute_sparql_mock:
        statistics = collect_distinct_statistics(QUERY_ENDPOINT, timeout=42)

    assert statistics == {
        VOID.distinctSubjects: 7,
        VOID.distinctObjects: 9,
    }
    assert execute_sparql_mock.call_args_list == [
        call(QUERY_ENDPOINT, statistic.query, timeout=42)
        for statistic in DISTINCT_STATISTIC_QUERIES
    ]


def test_execute_sparql_requests_json_results() -> None:
    body: dict[str, object] = {"results": {"bindings": [{"value": {"value": "11"}}]}}
    with patch(
        "src.endpoint_metadata.requests.get",
        return_value=FakeResponse(
            200,
            "application/sparql-results+json",
            body,
        ),
    ) as get:
        result = execute_sparql(QUERY_ENDPOINT, "SELECT * WHERE {}", timeout=42)

    assert result == body
    assert get.call_args_list == [
        call(
            QUERY_ENDPOINT,
            params={"query": "SELECT * WHERE {}"},
            headers={"Accept": "application/sparql-results+json"},
            timeout=42,
        )
    ]


def test_collect_scope_metadata_for_named_graph_derives_statistics() -> None:
    responses = [
        _sparql_partitions(
            Partition(EXAMPLE_PROPERTY_A, 4),
            Partition(EXAMPLE_PROPERTY_B, 5),
        ),
        _sparql_partitions(Partition(EXAMPLE_CLASS, 6)),
    ]
    with patch(
        "src.endpoint_metadata.execute_sparql",
        side_effect=responses,
    ) as execute_sparql:
        metadata = collect_scope_metadata(
            QUERY_ENDPOINT, timeout=42, graph_iri=META_BR_GRAPH
        )

    assert metadata == ScopeMetadata(
        statistics={
            VOID.triples: 9,
            VOID.properties: 2,
            VOID.classes: 1,
        },
        property_partitions=[
            Partition(EXAMPLE_PROPERTY_A, 4),
            Partition(EXAMPLE_PROPERTY_B, 5),
        ],
        class_partitions=[Partition(EXAMPLE_CLASS, 6)],
    )
    assert execute_sparql.call_args_list == [
        call(
            QUERY_ENDPOINT,
            "SELECT ?resource (COUNT(*) AS ?count) WHERE { "
            "GRAPH <https://w3id.org/oc/meta/br/> { ?s ?resource ?o } "
            "} GROUP BY ?resource",
            timeout=42,
        ),
        call(
            QUERY_ENDPOINT,
            "SELECT ?resource (COUNT(*) AS ?count) WHERE { "
            "GRAPH <https://w3id.org/oc/meta/br/> { "
            "?s <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ?resource "
            "} } GROUP BY ?resource",
            timeout=42,
        ),
    ]


def test_collect_scope_metadata_for_default_graph_derives_statistics() -> None:
    responses = [
        _sparql_partitions(
            Partition(EXAMPLE_PROPERTY_A, 4),
            Partition(EXAMPLE_PROPERTY_B, 5),
        ),
        _sparql_partitions(Partition(EXAMPLE_CLASS, 6)),
        _sparql_count(7),
        _sparql_count(9),
    ]
    with patch(
        "src.endpoint_metadata.execute_sparql",
        side_effect=responses,
    ) as execute_sparql:
        metadata = collect_scope_metadata(QUERY_ENDPOINT, timeout=42)

    assert metadata == ScopeMetadata(
        statistics={
            VOID.triples: 9,
            VOID.properties: 2,
            VOID.classes: 1,
            VOID.distinctSubjects: 7,
            VOID.distinctObjects: 9,
        },
        property_partitions=[
            Partition(EXAMPLE_PROPERTY_A, 4),
            Partition(EXAMPLE_PROPERTY_B, 5),
        ],
        class_partitions=[Partition(EXAMPLE_CLASS, 6)],
    )
    assert execute_sparql.call_args_list == [
        call(
            QUERY_ENDPOINT,
            "SELECT ?resource (COUNT(*) AS ?count) WHERE { "
            "?s ?resource ?o } GROUP BY ?resource",
            timeout=42,
        ),
        call(
            QUERY_ENDPOINT,
            "SELECT ?resource (COUNT(*) AS ?count) WHERE { "
            "?s <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ?resource "
            "} GROUP BY ?resource",
            timeout=42,
        ),
        call(
            QUERY_ENDPOINT,
            "SELECT (COUNT(DISTINCT ?s) AS ?value) WHERE { ?s ?p ?o }",
            timeout=42,
        ),
        call(
            QUERY_ENDPOINT,
            "SELECT (COUNT(DISTINCT ?o) AS ?value) WHERE { ?s ?p ?o }",
            timeout=42,
        ),
    ]


def test_detect_supported_languages_keeps_sparql_11_query() -> None:
    with patch(
        "src.endpoint_metadata.requests.get",
        return_value=FakeResponse(
            200, "application/sparql-results+json;charset=utf-8", {}
        ),
    ) as get:
        languages = detect_supported_languages(QUERY_ENDPOINT, timeout=12)

    assert languages == [SD.SPARQL11Query]
    assert get.call_args_list == [
        call(
            QUERY_ENDPOINT,
            params={"query": SPARQL_11_QUERY_PROBE},
            headers={"Accept": "application/sparql-results+json"},
            timeout=12,
        )
    ]


@pytest.mark.parametrize(
    "detector",
    [detect_supported_languages, detect_result_formats],
)
def test_capability_detection_propagates_request_failures(
    detector: Callable[[str, int], list[URIRef]],
) -> None:
    with patch(
        "src.endpoint_metadata.requests.get",
        side_effect=requests.Timeout("endpoint unavailable"),
    ):
        with pytest.raises(requests.Timeout) as exc_info:
            detector(QUERY_ENDPOINT, 12)

    assert str(exc_info.value) == "endpoint unavailable"


def test_detect_result_formats_keeps_confirmed_formats() -> None:
    responses = [
        FakeResponse(200, "application/sparql-results+json;charset=utf-8", {}),
        FakeResponse(200, "application/sparql-results+xml", {}),
        FakeResponse(406, "application/json", {}),
        FakeResponse(200, "text/tab-separated-values", {}),
        FakeResponse(200, "text/turtle", {}),
        FakeResponse(200, "text/turtle", {}),
        FakeResponse(500, "application/n-triples", {}),
        FakeResponse(200, "application/json", {}),
        FakeResponse(200, "application/trig", {}),
        FakeResponse(200, "application/n-quads", {}),
    ]
    with patch(
        "src.endpoint_metadata.requests.get",
        side_effect=responses,
    ) as get:
        result_formats = detect_result_formats(QUERY_ENDPOINT, timeout=12)

    assert result_formats == [
        FORMATS.SPARQL_Results_JSON,
        FORMATS.SPARQL_Results_XML,
        FORMATS.SPARQL_Results_TSV,
        FORMATS.Turtle,
        FORMATS.TriG,
        FORMATS["N-Quads"],
    ]
    assert get.call_args_list == [
        call(
            QUERY_ENDPOINT,
            params={"query": probe.query},
            headers={"Accept": probe.media_type},
            timeout=12,
        )
        for probe in RESULT_FORMAT_PROBES
    ]


def test_detect_input_formats_keeps_successful_ask_probes() -> None:
    with patch(
        "src.endpoint_metadata.ask_probe",
        side_effect=[True, False, True, False],
    ) as ask_probe:
        input_formats = detect_input_formats(QUERY_ENDPOINT, timeout=12)

    assert input_formats == [FORMATS.Turtle, FORMATS.RDF_XML]
    assert ask_probe.call_args_list == [
        call(QUERY_ENDPOINT, input_format_query(probe), 12)
        for probe in INPUT_FORMAT_PROBES
    ]


def test_detect_features_uses_successful_probes_and_graph_counts() -> None:
    metadata = DatasetMetadata(
        default_scope=_scope_metadata(7),
        named_graphs={
            "https://w3id.org/oc/meta/br/": _scope_metadata(3),
            "https://w3id.org/oc/meta/id/": _scope_metadata(4),
        },
    )
    with patch("src.endpoint_metadata.ask_probe", return_value=True) as ask:
        features = detect_features(
            QUERY_ENDPOINT,
            "meta",
            metadata,
            input_formats=[FORMATS.Turtle],
            timeout=12,
        )

    assert features == [
        SD.DereferencesURIs,
        SD.BasicFederatedQuery,
        SD.UnionDefaultGraph,
    ]
    assert ask.call_args_list == [
        call(QUERY_ENDPOINT, SERVICE_QUERY_PROBE.format(endpoint=QUERY_ENDPOINT), 12)
    ]


def test_detect_service_capabilities_combines_probe_results() -> None:
    metadata = _dataset_metadata(with_named_graph=False)
    with patch(
        "src.endpoint_metadata.detect_input_formats",
        return_value=[FORMATS.Turtle],
    ) as detect_input:
        with patch(
            "src.endpoint_metadata.detect_supported_languages",
            return_value=[SD.SPARQL11Query],
        ) as detect_languages:
            with patch(
                "src.endpoint_metadata.detect_result_formats",
                return_value=[FORMATS.SPARQL_Results_JSON],
            ) as detect_results:
                with patch(
                    "src.endpoint_metadata.detect_features",
                    return_value=[SD.DereferencesURIs],
                ) as detect_features_mock:
                    capabilities = detect_service_capabilities(
                        QUERY_ENDPOINT, "index", 12, metadata
                    )

    assert capabilities == ServiceCapabilities(
        supported_languages=[SD.SPARQL11Query],
        result_formats=[FORMATS.SPARQL_Results_JSON],
        input_formats=[FORMATS.Turtle],
        features=[SD.DereferencesURIs],
    )
    assert detect_input.call_args_list == [call(QUERY_ENDPOINT, 12)]
    assert detect_languages.call_args_list == [call(QUERY_ENDPOINT, 12)]
    assert detect_results.call_args_list == [call(QUERY_ENDPOINT, 12)]
    assert detect_features_mock.call_args_list == [
        call(QUERY_ENDPOINT, "index", metadata, [FORMATS.Turtle], 12)
    ]


def test_build_service_description_for_meta_returns_parsable_rdf() -> None:
    metadata = _dataset_metadata(with_named_graph=True)
    graph = build_service_description(
        "meta", PUBLIC_ENDPOINT, metadata, _capabilities()
    )

    parsed_graph = Graph()
    parsed_graph.parse(data=graph.serialize(format="turtle"), format="turtle")

    service = next(parsed_graph.subjects(RDF.type, SD.Service))
    dataset = next(parsed_graph.objects(service, SD.defaultDataset))
    default_graph = next(parsed_graph.objects(dataset, SD.defaultGraph))
    named_graph = next(parsed_graph.objects(dataset, SD.namedGraph))
    graph_description = next(parsed_graph.objects(named_graph, SD.graph))
    statistic_predicates = (
        VOID.triples,
        VOID.properties,
        VOID.distinctSubjects,
        VOID.distinctObjects,
        VOID.classes,
    )

    assert len(parsed_graph) == 51
    assert set(parsed_graph.objects(service, SD.endpoint)) == {URIRef(PUBLIC_ENDPOINT)}
    assert set(parsed_graph.objects(service, SD.supportedLanguage)) == {
        SD.SPARQL11Query
    }
    assert set(parsed_graph.objects(service, SD.resultFormat)) == {
        FORMATS.SPARQL_Results_JSON,
        FORMATS.Turtle,
    }
    assert set(parsed_graph.objects(service, SD.inputFormat)) == {FORMATS.Turtle}
    assert set(parsed_graph.objects(service, SD.feature)) == {
        SD.BasicFederatedQuery,
        SD.UnionDefaultGraph,
    }
    assert set(parsed_graph.objects(dataset, RDF.type)) == {SD.Dataset, VOID.Dataset}
    assert set(parsed_graph.objects(dataset, DCTERMS.title)) == {
        Literal("OpenCitations Meta", lang="en")
    }
    assert set(parsed_graph.objects(dataset, DCTERMS.description)) == {
        Literal("OpenCitations Meta entity data", lang="en")
    }
    assert set(parsed_graph.objects(dataset, VOID.uriSpace)) == {
        Literal("https://w3id.org/oc/meta/")
    }
    assert set(parsed_graph.objects(dataset, VOID.sparqlEndpoint)) == {
        URIRef(PUBLIC_ENDPOINT)
    }
    assert {
        predicate: list(parsed_graph.objects(dataset, predicate))
        for predicate in statistic_predicates
    } == {
        VOID.triples: [],
        VOID.properties: [],
        VOID.distinctSubjects: [],
        VOID.distinctObjects: [],
        VOID.classes: [],
    }
    assert list(parsed_graph.objects(dataset, VOID.propertyPartition)) == []
    assert list(parsed_graph.objects(dataset, VOID.classPartition)) == []
    assert set(parsed_graph.objects(default_graph, RDF.type)) == {SD.Graph}
    assert list(parsed_graph.objects(default_graph, SD.name)) == []
    assert {
        predicate: set(parsed_graph.objects(default_graph, predicate))
        for predicate in statistic_predicates
    } == {
        VOID.triples: {Literal(7, datatype=XSD.integer)},
        VOID.properties: {Literal(2, datatype=XSD.integer)},
        VOID.distinctSubjects: {Literal(3, datatype=XSD.integer)},
        VOID.distinctObjects: {Literal(4, datatype=XSD.integer)},
        VOID.classes: {Literal(1, datatype=XSD.integer)},
    }
    assert _partition_rows(
        parsed_graph,
        default_graph,
        VOID.propertyPartition,
        VOID.property,
        VOID.triples,
    ) == [
        (EXAMPLE_PROPERTY_A, Literal(4, datatype=XSD.integer)),
        (EXAMPLE_PROPERTY_B, Literal(5, datatype=XSD.integer)),
    ]
    assert _partition_rows(
        parsed_graph,
        default_graph,
        VOID.classPartition,
        VOID["class"],
        VOID.entities,
    ) == [(EXAMPLE_CLASS, Literal(6, datatype=XSD.integer))]
    assert set(parsed_graph.objects(named_graph, RDF.type)) == {SD.NamedGraph}
    assert set(parsed_graph.objects(named_graph, SD.name)) == {URIRef(META_BR_GRAPH)}
    assert set(parsed_graph.objects(graph_description, RDF.type)) == {SD.Graph}
    assert set(parsed_graph.objects(graph_description, VOID.uriSpace)) == {
        Literal(META_BR_GRAPH)
    }
    assert set(parsed_graph.objects(graph_description, VOID.triples)) == {
        Literal(3, datatype=XSD.integer)
    }
    assert _partition_rows(
        parsed_graph,
        graph_description,
        VOID.propertyPartition,
        VOID.property,
        VOID.triples,
    ) == [
        (EXAMPLE_PROPERTY_A, Literal(4, datatype=XSD.integer)),
        (EXAMPLE_PROPERTY_B, Literal(5, datatype=XSD.integer)),
    ]
    assert _partition_rows(
        parsed_graph,
        graph_description,
        VOID.classPartition,
        VOID["class"],
        VOID.entities,
    ) == [(EXAMPLE_CLASS, Literal(6, datatype=XSD.integer))]
    assert set(parsed_graph.objects(dataset, SD.defaultGraph)) == {default_graph}


def test_build_service_description_without_named_graphs() -> None:
    graph = build_service_description(
        "meta-provenance",
        PUBLIC_ENDPOINT,
        _dataset_metadata(with_named_graph=False),
        _capabilities(),
    )

    parsed_graph = Graph()
    parsed_graph.parse(data=graph.serialize(format="turtle"), format="turtle")
    service = next(parsed_graph.subjects(RDF.type, SD.Service))
    dataset = next(parsed_graph.objects(service, SD.defaultDataset))
    default_graph = next(parsed_graph.objects(dataset, SD.defaultGraph))

    assert list(parsed_graph.objects(dataset, SD.namedGraph)) == []
    assert set(parsed_graph.objects(dataset, SD.defaultGraph)) == {default_graph}
    assert set(parsed_graph.objects(default_graph, RDF.type)) == {SD.Graph}
    assert set(parsed_graph.objects(default_graph, VOID.triples)) == {
        Literal(7, datatype=XSD.integer)
    }
    assert list(parsed_graph.objects(dataset, VOID.triples)) == []


def test_write_service_descriptions_use_public_endpoint(tmp_path: Path) -> None:
    output = tmp_path / "description.ttl"
    metadata = _dataset_metadata(with_named_graph=False)
    capabilities = _capabilities()
    with patch(
        "src.endpoint_metadata.collect_dataset_metadata",
        return_value=metadata,
    ) as collect_metadata:
        with patch(
            "src.endpoint_metadata.detect_service_capabilities",
            return_value=capabilities,
        ) as detect:
            output_paths = write_service_descriptions(
                "index",
                QUERY_ENDPOINT,
                PUBLIC_ENDPOINT,
                output,
                timeout=10,
            )

    expected_graph = build_service_description(
        "index", PUBLIC_ENDPOINT, metadata, capabilities
    )
    assert output_paths == (
        tmp_path / "description.ttl",
        tmp_path / "description.jsonld",
        tmp_path / "description.rdf",
        tmp_path / "description.nt",
    )
    for serialization, output_path in zip(
        SERVICE_DESCRIPTION_SERIALIZATIONS, output_paths, strict=True
    ):
        parsed_graph = Graph()
        parsed_graph.parse(output_path, format=serialization.rdflib_format)
        assert isomorphic(parsed_graph, expected_graph) is True
        content = output_path.read_text(encoding="utf-8")
        assert content.endswith("\n") is True
        assert content.endswith("\n\n") is False

    graph = Graph()
    graph.parse(output, format="turtle")
    service = next(graph.subjects(RDF.type, SD.Service))
    dataset = next(graph.objects(service, SD.defaultDataset))
    default_graph = next(graph.objects(dataset, SD.defaultGraph))

    assert collect_metadata.call_args_list == [call("index", QUERY_ENDPOINT, 10)]
    assert detect.call_args_list == [call(QUERY_ENDPOINT, "index", 10, metadata)]
    assert output.read_text(encoding="utf-8").startswith(SPDX_TURTLE_HEADER)
    assert set(graph.objects(service, SD.endpoint)) == {URIRef(PUBLIC_ENDPOINT)}
    assert set(graph.objects(default_graph, RDF.type)) == {SD.Graph}
    assert set(graph.objects(default_graph, VOID.triples)) == {
        Literal(7, datatype=XSD.integer)
    }
    assert list(graph.objects(dataset, VOID.triples)) == []


def test_write_service_descriptions_do_not_write_after_query_failure(
    tmp_path: Path,
) -> None:
    output = tmp_path / "description.ttl"
    with patch(
        "src.endpoint_metadata.execute_sparql",
        side_effect=RuntimeError("endpoint unavailable"),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            write_service_descriptions(
                "meta",
                QUERY_ENDPOINT,
                PUBLIC_ENDPOINT,
                output,
                timeout=10,
            )

    assert str(exc_info.value) == "endpoint unavailable"
    assert [
        output.with_suffix(serialization.suffix).exists()
        for serialization in SERVICE_DESCRIPTION_SERIALIZATIONS
    ] == [False, False, False, False]
