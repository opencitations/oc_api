# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html import escape as html_escape
from pathlib import Path
from typing import cast
from urllib.parse import quote

import requests
from rdflib import BNode, Graph, Literal, Namespace, Node, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD

SD = Namespace("http://www.w3.org/ns/sparql-service-description#")
VOID = Namespace("http://rdfs.org/ns/void#")
FORMATS = Namespace("http://www.w3.org/ns/formats/")

SparqlSelectResult = dict[str, dict[str, list[dict[str, dict[str, str]]]]]


@dataclass(frozen=True)
class EndpointProfile:
    title: str
    description: str
    uri_space: str
    named_graphs: tuple[str, ...]


@dataclass(frozen=True)
class StatisticQuery:
    predicate: URIRef
    query: str


@dataclass(frozen=True)
class ResultFormatProbe:
    format_iri: URIRef
    media_type: str
    query: str


@dataclass(frozen=True)
class InputFormatProbe:
    format_iri: URIRef
    media_type: str
    payload: str


@dataclass(frozen=True)
class Partition:
    resource: URIRef
    count: int


@dataclass(frozen=True)
class ScopeMetadata:
    statistics: dict[URIRef, int]
    property_partitions: list[Partition]
    class_partitions: list[Partition]


@dataclass(frozen=True)
class DatasetMetadata:
    default_scope: ScopeMetadata
    named_graphs: dict[str, ScopeMetadata]


@dataclass(frozen=True)
class ServiceCapabilities:
    supported_languages: list[URIRef]
    result_formats: list[URIRef]
    input_formats: list[URIRef]
    features: list[URIRef]


@dataclass(frozen=True)
class ServiceDescriptionSerialization:
    suffix: str
    rdflib_format: str


ENDPOINT_PROFILES = {
    "index": EndpointProfile(
        title="OpenCitations Index",
        description="OpenCitations Index data",
        uri_space="https://w3id.org/oc/index/",
        named_graphs=(),
    ),
    "index-provenance": EndpointProfile(
        title="OpenCitations Index provenance",
        description="OpenCitations Index provenance data",
        uri_space="https://w3id.org/oc/index/",
        named_graphs=(),
    ),
    "meta": EndpointProfile(
        title="OpenCitations Meta",
        description="OpenCitations Meta entity data",
        uri_space="https://w3id.org/oc/meta/",
        named_graphs=(
            "https://w3id.org/oc/meta/br/",
            "https://w3id.org/oc/meta/id/",
            "https://w3id.org/oc/meta/ra/",
            "https://w3id.org/oc/meta/ar/",
            "https://w3id.org/oc/meta/re/",
        ),
    ),
    "meta-provenance": EndpointProfile(
        title="OpenCitations Meta provenance",
        description="OpenCitations Meta provenance data",
        uri_space="https://w3id.org/oc/meta/",
        named_graphs=(),
    ),
}

SERVICE_DESCRIPTION_SERIALIZATIONS = (
    ServiceDescriptionSerialization(suffix=".ttl", rdflib_format="turtle"),
    ServiceDescriptionSerialization(suffix=".jsonld", rdflib_format="json-ld"),
    ServiceDescriptionSerialization(suffix=".rdf", rdflib_format="xml"),
    ServiceDescriptionSerialization(suffix=".nt", rdflib_format="nt"),
)

RDFA_PREFIXES = (
    "sd: http://www.w3.org/ns/sparql-service-description# "
    "void: http://rdfs.org/ns/void# "
    "dcterms: http://purl.org/dc/terms/ "
    "xsd: http://www.w3.org/2001/XMLSchema#"
)

_CURIE_NAMESPACES = (
    (str(SD), "sd"),
    (str(VOID), "void"),
    (str(DCTERMS), "dcterms"),
    (str(FORMATS), "formats"),
    (str(XSD), "xsd"),
    (str(RDF), "rdf"),
)

URI_LABELS: dict[str, str] = {
    str(SD.SPARQL10Query): "SPARQL 1.0 Query",
    str(SD.SPARQL11Query): "SPARQL 1.1 Query",
    str(SD.SPARQL11Update): "SPARQL 1.1 Update",
    str(SD.BasicFederatedQuery): "Basic Federated Query",
    str(SD.UnionDefaultGraph): "Union Default Graph",
    str(SD.DereferencesURIs): "Dereferences URIs",
    str(FORMATS.SPARQL_Results_JSON): "SPARQL Results JSON",
    str(FORMATS.SPARQL_Results_XML): "SPARQL Results XML",
    str(FORMATS.SPARQL_Results_CSV): "SPARQL Results CSV",
    str(FORMATS.SPARQL_Results_TSV): "SPARQL Results TSV",
    str(FORMATS.Turtle): "Turtle",
    str(FORMATS.RDF_XML): "RDF/XML",
    str(FORMATS["N-Triples"]): "N-Triples",
    str(FORMATS["JSON-LD"]): "JSON-LD",
    str(FORMATS.TriG): "TriG",
    str(FORMATS["N-Quads"]): "N-Quads",
}

DISTINCT_STATISTIC_QUERIES = (
    StatisticQuery(
        predicate=VOID.distinctSubjects,
        query="SELECT (COUNT(DISTINCT ?s) AS ?value) WHERE { ?s ?p ?o }",
    ),
    StatisticQuery(
        predicate=VOID.distinctObjects,
        query="SELECT (COUNT(DISTINCT ?o) AS ?value) WHERE { ?s ?p ?o }",
    ),
)

SELECT_QUERY = "SELECT * WHERE { ?s ?p ?o } LIMIT 1"
CONSTRUCT_QUERY = "CONSTRUCT WHERE { ?s ?p ?o } LIMIT 1"
SPARQL_11_QUERY_PROBE = "SELECT * WHERE { VALUES ?s { <urn:oc-meta-probe:s> } } LIMIT 1"
SERVICE_QUERY_PROBE = "ASK {{ SERVICE <{endpoint}> {{ ?s ?p ?o }} }}"

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

PROPERTY_PARTITION_QUERY_TEMPLATE = (
    "SELECT ?resource (COUNT(*) AS ?count) WHERE {{ {pattern} }} GROUP BY ?resource"
)
CLASS_PARTITION_QUERY_TEMPLATE = (
    "SELECT ?resource (COUNT(*) AS ?count) WHERE {{ {pattern} }} GROUP BY ?resource"
)

RESULT_FORMAT_PROBES = (
    ResultFormatProbe(
        format_iri=FORMATS.SPARQL_Results_JSON,
        media_type="application/sparql-results+json",
        query=SELECT_QUERY,
    ),
    ResultFormatProbe(
        format_iri=FORMATS.SPARQL_Results_XML,
        media_type="application/sparql-results+xml",
        query=SELECT_QUERY,
    ),
    ResultFormatProbe(
        format_iri=FORMATS.SPARQL_Results_CSV,
        media_type="text/csv",
        query=SELECT_QUERY,
    ),
    ResultFormatProbe(
        format_iri=FORMATS.SPARQL_Results_TSV,
        media_type="text/tab-separated-values",
        query=SELECT_QUERY,
    ),
    ResultFormatProbe(
        format_iri=FORMATS.Turtle,
        media_type="text/turtle",
        query=CONSTRUCT_QUERY,
    ),
    ResultFormatProbe(
        format_iri=FORMATS.RDF_XML,
        media_type="application/rdf+xml",
        query=CONSTRUCT_QUERY,
    ),
    ResultFormatProbe(
        format_iri=FORMATS["N-Triples"],
        media_type="application/n-triples",
        query=CONSTRUCT_QUERY,
    ),
    ResultFormatProbe(
        format_iri=FORMATS["JSON-LD"],
        media_type="application/ld+json",
        query=CONSTRUCT_QUERY,
    ),
    ResultFormatProbe(
        format_iri=FORMATS.TriG,
        media_type="application/trig",
        query=CONSTRUCT_QUERY,
    ),
    ResultFormatProbe(
        format_iri=FORMATS["N-Quads"],
        media_type="application/n-quads",
        query=CONSTRUCT_QUERY,
    ),
)

INPUT_FORMAT_PROBES = (
    InputFormatProbe(
        format_iri=FORMATS.Turtle,
        media_type="text/turtle",
        payload="<urn:oc-meta-probe:s> <urn:oc-meta-probe:p> <urn:oc-meta-probe:o> .",
    ),
    InputFormatProbe(
        format_iri=FORMATS["N-Triples"],
        media_type="application/n-triples",
        payload="<urn:oc-meta-probe:s> <urn:oc-meta-probe:p> <urn:oc-meta-probe:o> .",
    ),
    InputFormatProbe(
        format_iri=FORMATS.RDF_XML,
        media_type="application/rdf+xml",
        payload=(
            '<?xml version="1.0"?>'
            '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
            'xmlns:probe="urn:oc-meta-probe:">'
            '<rdf:Description rdf:about="urn:oc-meta-probe:s">'
            '<probe:p rdf:resource="urn:oc-meta-probe:o"/>'
            "</rdf:Description>"
            "</rdf:RDF>"
        ),
    ),
    InputFormatProbe(
        format_iri=FORMATS["JSON-LD"],
        media_type="application/ld+json",
        payload=(
            '[{"@id":"urn:oc-meta-probe:s",'
            '"urn:oc-meta-probe:p":{"@id":"urn:oc-meta-probe:o"}}]'
        ),
    ),
)


def property_partition_pattern(graph_iri: str | None) -> str:
    if graph_iri is None:
        return "?s ?resource ?o"
    return f"GRAPH <{graph_iri}> {{ ?s ?resource ?o }}"


def class_partition_pattern(graph_iri: str | None) -> str:
    if graph_iri is None:
        return f"?s <{RDF_TYPE}> ?resource"
    return f"GRAPH <{graph_iri}> {{ ?s <{RDF_TYPE}> ?resource }}"


def execute_sparql(endpoint: str, query: str, timeout: int) -> SparqlSelectResult:
    response = requests.get(
        endpoint,
        params={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=timeout,
    )
    response.raise_for_status()
    return cast(SparqlSelectResult, response.json())


def collect_distinct_statistics(endpoint: str, timeout: int) -> dict[URIRef, int]:
    statistics: dict[URIRef, int] = {}
    for statistic in DISTINCT_STATISTIC_QUERIES:
        result = execute_sparql(endpoint, statistic.query, timeout=timeout)
        value = result["results"]["bindings"][0]["value"]["value"]
        statistics[statistic.predicate] = int(value)
    return statistics


def collect_partitions(
    endpoint: str,
    query: str,
    timeout: int,
) -> list[Partition]:
    result = execute_sparql(endpoint, query, timeout=timeout)
    partitions: list[Partition] = []
    for binding in result["results"]["bindings"]:
        partitions.append(
            Partition(
                resource=URIRef(binding["resource"]["value"]),
                count=int(binding["count"]["value"]),
            )
        )
    return partitions


def collect_scope_metadata(
    endpoint: str,
    timeout: int,
    graph_iri: str | None = None,
) -> ScopeMetadata:
    property_partitions = collect_partitions(
        endpoint,
        PROPERTY_PARTITION_QUERY_TEMPLATE.format(
            pattern=property_partition_pattern(graph_iri)
        ),
        timeout,
    )
    class_partitions = collect_partitions(
        endpoint,
        CLASS_PARTITION_QUERY_TEMPLATE.format(
            pattern=class_partition_pattern(graph_iri)
        ),
        timeout,
    )
    statistics = {
        VOID.triples: sum(partition.count for partition in property_partitions),
        VOID.properties: len(property_partitions),
        VOID.classes: len(class_partitions),
    }
    if graph_iri is None:
        statistics.update(collect_distinct_statistics(endpoint, timeout))
    return ScopeMetadata(
        statistics=statistics,
        property_partitions=property_partitions,
        class_partitions=class_partitions,
    )


def collect_dataset_metadata(
    dataset_name: str,
    endpoint: str,
    timeout: int,
) -> DatasetMetadata:
    profile = ENDPOINT_PROFILES[dataset_name]
    named_graphs: dict[str, ScopeMetadata] = {}
    for graph_iri in profile.named_graphs:
        named_graphs[graph_iri] = collect_scope_metadata(endpoint, timeout, graph_iri)
    return DatasetMetadata(
        default_scope=collect_scope_metadata(endpoint, timeout),
        named_graphs=named_graphs,
    )


def media_type(response: requests.Response) -> str:
    return response.headers["Content-Type"].split(";", 1)[0].strip()


def json_probe(endpoint: str, query: str, timeout: int) -> requests.Response:
    return requests.get(
        endpoint,
        params={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=timeout,
    )


def ask_probe(endpoint: str, query: str, timeout: int) -> bool:
    response = json_probe(endpoint, query, timeout)
    if not 200 <= response.status_code < 300:
        return False
    if "Content-Type" not in response.headers:
        return False
    if media_type(response) != "application/sparql-results+json":
        return False
    result = cast(dict[str, object], response.json())
    return result["boolean"] is True


def detect_supported_languages(endpoint: str, timeout: int) -> list[URIRef]:
    response = json_probe(endpoint, SPARQL_11_QUERY_PROBE, timeout)
    if not 200 <= response.status_code < 300:
        return []
    if "Content-Type" not in response.headers:
        return []
    if media_type(response) != "application/sparql-results+json":
        return []
    return [SD.SPARQL11Query]


def detect_result_formats(endpoint: str, timeout: int) -> list[URIRef]:
    result_formats: list[URIRef] = []
    for probe in RESULT_FORMAT_PROBES:
        response = requests.get(
            endpoint,
            params={"query": probe.query},
            headers={"Accept": probe.media_type},
            timeout=timeout,
        )
        if "Content-Type" not in response.headers:
            continue
        if (
            200 <= response.status_code < 300
            and media_type(response) == probe.media_type
        ):
            result_formats.append(probe.format_iri)
    return result_formats


def input_format_query(probe: InputFormatProbe) -> str:
    data_iri = f"data:{probe.media_type},{quote(probe.payload, safe='')}"
    return (
        f"ASK FROM <{data_iri}> "
        "WHERE { <urn:oc-meta-probe:s> <urn:oc-meta-probe:p> <urn:oc-meta-probe:o> }"
    )


def detect_input_formats(endpoint: str, timeout: int) -> list[URIRef]:
    input_formats: list[URIRef] = []
    for probe in INPUT_FORMAT_PROBES:
        if ask_probe(endpoint, input_format_query(probe), timeout):
            input_formats.append(probe.format_iri)
    return input_formats


def detect_features(
    endpoint: str,
    dataset_name: str,
    metadata: DatasetMetadata,
    input_formats: list[URIRef],
    timeout: int,
) -> list[URIRef]:
    features: list[URIRef] = []
    if input_formats:
        features.append(SD.DereferencesURIs)
    if ask_probe(endpoint, SERVICE_QUERY_PROBE.format(endpoint=endpoint), timeout):
        features.append(SD.BasicFederatedQuery)
    if dataset_name == "meta":
        named_graph_triples = sum(
            scope.statistics[VOID.triples] for scope in metadata.named_graphs.values()
        )
        if named_graph_triples == metadata.default_scope.statistics[VOID.triples]:
            features.append(SD.UnionDefaultGraph)
    return features


def detect_service_capabilities(
    endpoint: str,
    dataset_name: str,
    timeout: int,
    metadata: DatasetMetadata,
) -> ServiceCapabilities:
    input_formats = detect_input_formats(endpoint, timeout)
    return ServiceCapabilities(
        supported_languages=detect_supported_languages(endpoint, timeout),
        result_formats=detect_result_formats(endpoint, timeout),
        input_formats=input_formats,
        features=detect_features(
            endpoint,
            dataset_name,
            metadata,
            input_formats,
            timeout,
        ),
    )


def add_scope_metadata(
    graph: Graph,
    subject: BNode,
    metadata: ScopeMetadata,
) -> None:
    for predicate, value in metadata.statistics.items():
        graph.add((subject, predicate, Literal(value, datatype=XSD.integer)))
    for partition in metadata.property_partitions:
        partition_node = BNode()
        graph.add((subject, VOID.propertyPartition, partition_node))
        graph.add((partition_node, VOID.property, partition.resource))
        graph.add(
            (
                partition_node,
                VOID.triples,
                Literal(partition.count, datatype=XSD.integer),
            )
        )
    for partition in metadata.class_partitions:
        partition_node = BNode()
        graph.add((subject, VOID.classPartition, partition_node))
        graph.add((partition_node, VOID["class"], partition.resource))
        graph.add(
            (
                partition_node,
                VOID.entities,
                Literal(partition.count, datatype=XSD.integer),
            )
        )


def build_service_description(
    dataset_name: str,
    public_endpoint: str,
    metadata: DatasetMetadata,
    capabilities: ServiceCapabilities,
) -> Graph:
    profile = ENDPOINT_PROFILES[dataset_name]
    service = BNode()
    dataset = BNode()
    default_graph = BNode()

    graph = Graph()
    graph.bind("sd", SD)
    graph.bind("void", VOID)
    graph.bind("dcterms", DCTERMS)
    graph.bind("formats", FORMATS)

    graph.add((service, RDF.type, SD.Service))
    graph.add((service, SD.endpoint, URIRef(public_endpoint)))
    graph.add((service, SD.defaultDataset, dataset))
    for supported_language in capabilities.supported_languages:
        graph.add((service, SD.supportedLanguage, supported_language))
    for result_format in capabilities.result_formats:
        graph.add((service, SD.resultFormat, result_format))
    for input_format in capabilities.input_formats:
        graph.add((service, SD.inputFormat, input_format))
    for feature in capabilities.features:
        graph.add((service, SD.feature, feature))

    graph.add((dataset, RDF.type, SD.Dataset))
    graph.add((dataset, RDF.type, VOID.Dataset))
    graph.add((dataset, DCTERMS.title, Literal(profile.title, lang="en")))
    graph.add((dataset, DCTERMS.description, Literal(profile.description, lang="en")))
    graph.add((dataset, VOID.uriSpace, Literal(profile.uri_space)))
    graph.add((dataset, VOID.sparqlEndpoint, URIRef(public_endpoint)))
    graph.add((dataset, SD.defaultGraph, default_graph))

    graph.add((default_graph, RDF.type, SD.Graph))
    add_scope_metadata(graph, default_graph, metadata.default_scope)
    for graph_iri, graph_metadata in metadata.named_graphs.items():
        named_graph = BNode()
        graph_description = BNode()
        graph.add((dataset, SD.namedGraph, named_graph))
        graph.add((named_graph, RDF.type, SD.NamedGraph))
        graph.add((named_graph, SD.name, URIRef(graph_iri)))
        graph.add((named_graph, SD.graph, graph_description))
        graph.add((graph_description, RDF.type, SD.Graph))
        graph.add((graph_description, VOID.uriSpace, Literal(graph_iri)))
        add_scope_metadata(graph, graph_description, graph_metadata)

    return graph


def _curie(uri: str) -> str:
    for ns, prefix in _CURIE_NAMESPACES:
        if uri.startswith(ns):
            return f"{prefix}:{uri[len(ns) :]}"
    return uri


def _uri_label(uri: str) -> str:
    label = URI_LABELS.get(uri)
    if label is not None:
        return label
    fragment = uri.rsplit("#", 1)[-1] if "#" in uri else uri.rsplit("/", 1)[-1]
    return fragment.replace("_", " ")


def _render_scope_html(graph: Graph, scope_node: Node, h_part: int) -> str:
    parts: list[str] = []

    stat_predicates = [
        (VOID.triples, "void:triples", "Triples"),
        (VOID.distinctSubjects, "void:distinctSubjects", "Distinct Subjects"),
        (VOID.distinctObjects, "void:distinctObjects", "Distinct Objects"),
        (VOID.properties, "void:properties", "Properties"),
        (VOID.classes, "void:classes", "Classes"),
    ]

    stats_items: list[str] = []
    uri_spaces = list(graph.objects(scope_node, VOID.uriSpace, unique=True))
    if uri_spaces:
        stats_items.append("<dt>URI Space</dt>")
        stats_items.append(
            f'<dd><span property="void:uriSpace" lang="">'
            f"{html_escape(str(uri_spaces[0]))}</span></dd>"
        )
    for pred, pred_curie, label in stat_predicates:
        values = list(graph.objects(scope_node, pred, unique=True))
        if values:
            value = int(str(values[0]))
            stats_items.append(f"<dt>{label}</dt>")
            stats_items.append(
                f'<dd><span property="{pred_curie}" content="{value}" '
                f'datatype="xsd:integer">{value:,}</span></dd>'
            )
    if stats_items:
        parts.append("<dl>")
        parts.extend(stats_items)
        parts.append("</dl>")

    prop_partitions = list(
        graph.objects(scope_node, VOID.propertyPartition, unique=True)
    )
    if prop_partitions:
        rows: list[tuple[str, int]] = []
        for pp in prop_partitions:
            prop_uri = str(next(graph.objects(pp, VOID.property, unique=True)))
            count = int(str(next(graph.objects(pp, VOID.triples, unique=True))))
            rows.append((prop_uri, count))
        rows.sort(key=lambda r: (-r[1], r[0]))
        parts.append(f"<h{h_part}>Property Partitions</h{h_part}>")
        parts.append(
            "<table><thead><tr><th>Property</th><th>Triples</th></tr></thead><tbody>"
        )
        for prop_uri, count in rows:
            parts.append(
                f'<tr rel="void:propertyPartition" typeof="">'
                f'<td><a rel="void:property" href="{html_escape(prop_uri)}">'
                f"{html_escape(_uri_label(prop_uri))}</a></td>"
                f'<td><span property="void:triples" content="{count}" '
                f'datatype="xsd:integer">{count:,}</span></td></tr>'
            )
        parts.append("</tbody></table>")

    class_partitions = list(graph.objects(scope_node, VOID.classPartition, unique=True))
    if class_partitions:
        class_rows: list[tuple[str, int]] = []
        for cp in class_partitions:
            class_uri = str(next(graph.objects(cp, VOID["class"], unique=True)))
            count = int(str(next(graph.objects(cp, VOID.entities, unique=True))))
            class_rows.append((class_uri, count))
        class_rows.sort(key=lambda r: (-r[1], r[0]))
        parts.append(f"<h{h_part}>Class Partitions</h{h_part}>")
        parts.append(
            "<table><thead><tr><th>Class</th><th>Entities</th></tr></thead><tbody>"
        )
        for class_uri, count in class_rows:
            parts.append(
                f'<tr rel="void:classPartition" typeof="">'
                f'<td><a rel="void:class" href="{html_escape(class_uri)}">'
                f"{html_escape(_uri_label(class_uri))}</a></td>"
                f'<td><span property="void:entities" content="{count}" '
                f'datatype="xsd:integer">{count:,}</span></td></tr>'
            )
        parts.append("</tbody></table>")

    return "\n".join(parts)


def _render_service_html(graph: Graph, service: Node, h_base: int) -> str:
    endpoint_uri = str(next(graph.objects(service, SD.endpoint, unique=True)))
    dataset = next(graph.objects(service, SD.defaultDataset, unique=True))
    title = str(next(graph.objects(dataset, DCTERMS.title, unique=True)))
    description = str(next(graph.objects(dataset, DCTERMS.description, unique=True)))
    uri_space = str(next(graph.objects(dataset, VOID.uriSpace, unique=True)))
    default_graph_node = next(graph.objects(dataset, SD.defaultGraph, unique=True))

    parts: list[str] = []
    parts.append('<article typeof="sd:Service">')

    if h_base == 1:
        parts.append("<h1>SPARQL Service Description</h1>")
    else:
        parts.append(f"<h{h_base}>{html_escape(title)}</h{h_base}>")

    parts.append("<dl>")
    parts.append("<dt>Endpoint</dt>")
    parts.append(
        f'<dd><a rel="sd:endpoint" href="{html_escape(endpoint_uri)}">'
        f"{html_escape(endpoint_uri)}</a></dd>"
    )
    for predicate, rel, label in [
        (SD.supportedLanguage, "sd:supportedLanguage", "Supported Languages"),
        (SD.feature, "sd:feature", "Features"),
        (SD.resultFormat, "sd:resultFormat", "Result Formats"),
        (SD.inputFormat, "sd:inputFormat", "Input Formats"),
    ]:
        uris = sorted(
            str(obj) for obj in graph.objects(service, predicate, unique=True)
        )
        if uris:
            items = "".join(
                f'<li><a rel="{rel}" href="{html_escape(u)}">'
                f"{html_escape(_uri_label(u))}</a></li>"
                for u in uris
            )
            parts.append(f"<dt>{label}</dt>")
            parts.append(f'<dd><ul class="tags">{items}</ul></dd>')
    parts.append("</dl>")

    dataset_types = sorted(
        str(t) for t in graph.objects(dataset, RDF.type, unique=True)
    )
    typeof_attr = " ".join(_curie(t) for t in dataset_types)

    h_ds = h_base + 1
    h_graph = h_base + 2
    h_part = h_base + 3

    parts.append(f'<div rel="sd:defaultDataset" typeof="{typeof_attr}">')
    parts.append(
        f'<h{h_ds}><span property="dcterms:title">{html_escape(title)}</span></h{h_ds}>'
    )
    parts.append(f'<p property="dcterms:description">{html_escape(description)}</p>')
    parts.append("<dl>")
    parts.append("<dt>URI Space</dt>")
    parts.append(
        f'<dd><span property="void:uriSpace" lang="">'
        f"{html_escape(uri_space)}</span></dd>"
    )
    parts.append("<dt>SPARQL Endpoint</dt>")
    parts.append(
        f'<dd><a rel="void:sparqlEndpoint" href="{html_escape(endpoint_uri)}">'
        f"{html_escape(endpoint_uri)}</a></dd>"
    )
    parts.append("</dl>")

    parts.append('<div rel="sd:defaultGraph" typeof="sd:Graph">')
    parts.append(f"<h{h_graph}>Default Graph</h{h_graph}>")
    parts.append(_render_scope_html(graph, default_graph_node, h_part))
    parts.append("</div>")

    named_graphs = list(graph.objects(dataset, SD.namedGraph, unique=True))
    if named_graphs:
        named_graphs_sorted = sorted(
            named_graphs,
            key=lambda ng: str(next(graph.objects(ng, SD.name, unique=True))),
        )
        for ng in named_graphs_sorted:
            ng_name = str(next(graph.objects(ng, SD.name, unique=True)))
            ng_graph = next(graph.objects(ng, SD.graph, unique=True))
            parts.append('<div rel="sd:namedGraph" typeof="sd:NamedGraph">')
            parts.append(
                f"<h{h_graph}>Named Graph: "
                f'<a rel="sd:name" href="{html_escape(ng_name)}">'
                f"{html_escape(ng_name)}</a></h{h_graph}>"
            )
            parts.append('<div rel="sd:graph" typeof="sd:Graph">')
            parts.append(_render_scope_html(graph, ng_graph, h_part))
            parts.append("</div>")
            parts.append("</div>")

    parts.append("</div>")
    parts.append("</article>")
    return "\n".join(parts)


def serialize_html_rdfa(graph: Graph) -> str:
    services = sorted(graph.subjects(RDF.type, SD.Service, unique=True), key=str)
    multi = len(services) > 1

    page_title = "SPARQL Service Description"
    if multi:
        page_title = "VoID Description"
    elif services:
        dataset = next(graph.objects(services[0], SD.defaultDataset, unique=True))
        ds_title = str(next(graph.objects(dataset, DCTERMS.title, unique=True)))
        page_title = f"SPARQL Service Description — {ds_title}"

    body_parts: list[str] = []
    if multi:
        body_parts.append("<h1>VoID Description</h1>")
    for s in services:
        body_parts.append(_render_service_html(graph, s, h_base=2 if multi else 1))

    return (
        "<!DOCTYPE html>\n"
        f'<html lang="en" prefix="{RDFA_PREFIXES}">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{html_escape(page_title)}</title>\n"
        "</head>\n"
        "<body>\n" + "\n".join(body_parts) + "\n</body>\n"
        "</html>\n"
    )


def _serialize_graph_to_files(graph: Graph, output: Path) -> tuple[Path, ...]:
    output_paths: list[Path] = []
    for serialization in SERVICE_DESCRIPTION_SERIALIZATIONS:
        output_path = output.with_suffix(serialization.suffix)
        content = graph.serialize(format=serialization.rdflib_format)
        output_path.write_text(f"{content.rstrip()}\n", encoding="utf-8")
        output_paths.append(output_path)
    html_path = output.with_suffix(".html")
    html_path.write_text(serialize_html_rdfa(graph), encoding="utf-8")
    output_paths.append(html_path)
    return tuple(output_paths)


def write_service_descriptions(
    dataset_name: str,
    endpoint: str,
    public_endpoint: str,
    output: Path,
    timeout: int,
) -> tuple[Path, ...]:
    metadata = collect_dataset_metadata(dataset_name, endpoint, timeout)
    capabilities = detect_service_capabilities(
        endpoint, dataset_name, timeout, metadata
    )
    graph = build_service_description(
        dataset_name, public_endpoint, metadata, capabilities
    )
    return _serialize_graph_to_files(graph, output)


def write_combined_void(source_dir: Path, output: Path) -> tuple[Path, ...]:
    combined = Graph()
    combined.bind("sd", SD)
    combined.bind("void", VOID)
    combined.bind("dcterms", DCTERMS)
    combined.bind("formats", FORMATS)
    for name in ("index", "meta"):
        source = source_dir / f"{name}.ttl"
        g = Graph()
        g.parse(source, format="turtle")
        for s, p, o in g:
            combined.add((s, p, o))
    return _serialize_graph_to_files(combined, output)


def parse_args() -> argparse.Namespace:  # pragma: no cover
    parser = argparse.ArgumentParser(
        description="Generate SPARQL Service Description files for an OpenCitations endpoint.",
    )
    parser.add_argument(
        "dataset",
        choices=sorted(ENDPOINT_PROFILES),
        help="Endpoint profile to describe.",
    )
    parser.add_argument(
        "--endpoint",
        required=True,
        help="SPARQL endpoint URL used to collect statistics.",
    )
    parser.add_argument(
        "--public-endpoint",
        help="SPARQL endpoint URL to write when it differs from --endpoint.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output path whose suffix is replaced for each serialization.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="SPARQL query timeout in seconds (default: 3600).",
    )
    return parser.parse_args()


def main() -> None:  # pragma: no cover
    args = parse_args()
    public_endpoint = args.public_endpoint if args.public_endpoint else args.endpoint
    write_service_descriptions(
        dataset_name=args.dataset,
        endpoint=args.endpoint,
        public_endpoint=public_endpoint,
        output=args.output,
        timeout=args.timeout,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
