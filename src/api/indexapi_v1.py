#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2018, Silvio Peroni <essepuntato@gmail.com>
#
# Permission to use, copy, modify, and/or distribute this software for any purpose
# with or without fee is hereby granted, provided that the above copyright notice
# and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT,
# OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE,
# DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS
# ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS
# SOFTWARE.

__author__ = 'Arcangelo Massari & Ivan Heibi'

from requests import RequestException, get, post
from json import loads
from re import sub, findall
from indexapi_common import (
    lower,  # noqa: F401 - used by ramose via getattr
    env_config,
    br_meta_metadata,
    get_unique_brs_metadata,
    get_pub_date,
    get_source,
    get_author,
    get_id_val,
    cit_journal_sc,
    cit_author_sc,
    cit_duration,
)


def split_dois2omids(s):
    l_omids = []
    for d in s.split("__"):
        l_omids.extend(__get_omid_of(d))
    return " ".join(l_omids),

def id2omids(s):
    if "omid" in s:
        return s.replace("omid:br/","<https://w3id.org/oc/meta/br/") +">",
    return __get_omid_of(s),

def metadata(res, *args):
    header = res[0]
    oci_idx = header.index(args[0])
    citation_idx = header.index(args[1])
    reference_idx = header.index(args[2])

    res_entities = {}
    if len(res) > 1:
        for idx, row in enumerate(res[1:]):
            res_entities[idx] = {
                "omid": row[oci_idx][1],
                "citation": row[citation_idx][1],
                "reference": row[reference_idx][1]
            }

    # delete the item + citing + cited columns
    res = [[elem for idx, elem in enumerate(row) if idx != oci_idx and idx != citation_idx and idx != reference_idx] for row in res]

    header = res[0]
    additional_fields = ["doi" , "citation_count", "citation", "reference", "author", "year", "title", "source_title", "volume", "issue", "page", "source_id", "oa_link"]
    header.extend(additional_fields)

    # org value: <https://w3id.org/oc/meta/br/06NNNNNN>
    for idx, row in enumerate(res[1:]):
        omid_uri = res_entities[idx]["omid"]
        citation = res_entities[idx]["citation"]
        reference = res_entities[idx]["reference"]
        entities = citation.split("; ") + reference.split("; ") + [omid_uri]
        br_meta, _ = br_meta_metadata(["<"+e+">" for e in entities])
        if not br_meta:
            row.extend(["","",""])
        else:
            k_omids_uris = br_meta

            citation_ids = []
            for e in citation.split("; "):
                if e in k_omids_uris:
                    citation_ids.append(__get_doi(k_omids_uris[e],True))

            reference_ids = []
            for e in reference.split("; "):
                if e in k_omids_uris:
                    reference_ids.append(__get_doi(k_omids_uris[e],True))

            row.extend([
                __get_doi(k_omids_uris[omid_uri],True),
                str(len(citation_ids)),
                "; ".join(citation_ids),
                "; ".join(reference_ids)
            ])


        entity = "omid:"+omid_uri.split("oc/meta/")[1]
        r = __ocmeta_parser([entity],"omid")
        if r is None or all([i in ("", None) for i in r]):
            row.extend(["","","","","","","","",""])
        else:
            if entity in r:
                r = r[entity]
                row.extend([
                    r["authors_str"],
                    r["pub_date"],
                    r["title"],
                    r["source_title"],
                    r["volume"],
                    r["issue"],
                    r["page"],
                    r["source_id"],
                    ""
                ])

    return res, True

def count_unique_cits(res, *args):
    header = res[0]
    citing_idx = header.index(args[1])
    cited_idx = header.index(args[2])
    set_oci = set()

    # build
    if len(res) > 1:
        citing_to_dedup = []
        cited_to_dedup = []
        for row in res[1:]:
            citing_val = row[citing_idx]
            cited_val = row[cited_idx]
            if isinstance(citing_val, tuple):
                citing_to_dedup.extend(citing_val)
                cited_to_dedup.extend(cited_val)
            else:
                citing_to_dedup.append(citing_val)
                cited_to_dedup.append(cited_val)

        citing_to_dedup_meta = get_unique_brs_metadata( list(set(citing_to_dedup)) )
        cited_to_dedup_meta = get_unique_brs_metadata( list(set(cited_to_dedup)) )
        for _k_citing in citing_to_dedup_meta.keys():
            for _k_cited in cited_to_dedup_meta.keys():
                set_oci.add( (_k_citing,_k_cited) )
    return [["count"],[ len( set_oci ) ]], True

# args must contain the <citing> and <cited>
def citations_info(res, *args):

    header = res[0]
    citing_idx = header.index(args[1])
    cited_idx = header.index(args[2])

    # build
    f_res = [
        ["oci", "citing", "cited", "creation", "timespan", "journal_sc", "author_sc"]
    ]

    if len(res) > 1:
        citing_to_dedup = []
        cited_to_dedup = []
        for row in res[1:]:
            citing_val = row[citing_idx]
            cited_val = row[cited_idx]
            if isinstance(citing_val, tuple):
                citing_to_dedup.extend(citing_val)
                cited_to_dedup.extend(cited_val)
            else:
                citing_to_dedup.append(citing_val)
                cited_to_dedup.append(cited_val)

        citing_to_dedup_meta = get_unique_brs_metadata( list(set(citing_to_dedup)) )
        cited_to_dedup_meta = get_unique_brs_metadata( list(set(cited_to_dedup)) )

        for citing_entity in citing_to_dedup_meta:
            for cited_entity in cited_to_dedup_meta:

                _citing = citing_to_dedup_meta[citing_entity]
                _cited = cited_to_dedup_meta[cited_entity]

                res_row = [
                    # oci value
                    get_id_val(citing_entity)+"-"+get_id_val(cited_entity),
                    # citing
                    __get_doi(_citing),
                    # cited
                    __get_doi(_cited),
                    # creation = citing[pub_date]
                    get_pub_date(_citing),
                    # timespan = citing[pub_date] - cited[pub_date]
                    cit_duration(get_pub_date(_citing),get_pub_date(_cited)),
                    # journal_sc = compare citing[source_id] and cited[source_id]
                    cit_journal_sc(get_source(_citing),get_source(_cited)),
                    # author_sc = compare citing[source_id] and cited[source_id]
                    cit_author_sc(get_author(_citing),get_author(_cited))
                ]
                f_res.append(res_row)

    return f_res, True


# ---
# Local methods
# ---

def __ocmeta_parser(ids, pre="doi"):
    api = "https://api.opencitations.net/meta/v1/metadata/"

    r = get(api + "__".join(ids), headers={"User-Agent": "INDEX REST API (via OpenCitations - http://opencitations.net; mailto:contact@opencitations.net)"}, timeout=60)

    f_res = {}
    if r.status_code == 200:
        json_res = loads(r.text)
        if len(json_res) > 0:

            for body in json_res:

                id = None
                omid = None
                if "id" in body:
                    for p_id in body["id"].split(" "):
                        if str(p_id).startswith(pre):
                            id = str(p_id)
                        if str(p_id).startswith("omid"):
                            omid = str(p_id)

                if omid is None:
                    continue

                authors = []
                authors_orcid = []
                if "author" in body:
                    if body["author"] != "":
                        for author in body["author"].split(";"):
                            author_string = author
                            author_orcid = findall(r"orcid\:([\d\-^\]]{1,})",author)
                            author_ids = findall(r"\[.{1,}\]",author)
                            if len(author_ids) > 0:
                                author_string = author.replace(author_ids[0],"").strip()
                                if len(author_orcid) > 0:
                                    authors_orcid.append(author_orcid[0].strip())
                                    author_string = author_string+", "+author_orcid[0].strip()
                            if author_string is not None:
                                authors.append(__normalise(author_string))

                source_title = ""
                source_id = ""
                if "venue" in body:
                    if body["venue"] != "":
                        source_title_string = body["venue"]

                        source_issn = findall(r"(issn\:[\d\-^\]]{1,})",source_title_string)
                        source_isbn = findall(r"(isbn\:[\d\-^\]]{1,})",source_title_string)
                        source_ids = findall(r"\[.{1,}\]",source_title_string)
                        if len(source_ids) > 0:
                            source_title_string = source_title_string.replace(source_ids[0],"").strip()
                        if len(source_issn) > 0:
                            source_id = source_issn[0]
                        elif len(source_isbn) > 0:
                            source_id = source_isbn[0]
                        source_title = source_title_string

                pub_date = ""
                if "pub_date" in body:
                    pub_date = __normalise(body["pub_date"])

                title = ""
                if "title" in body:
                    title = body["title"]

                volume = ""
                if "volume" in body:
                    volume = __normalise(body["volume"])

                issue = ""
                if "issue" in body:
                    issue = __normalise(body["issue"])

                page = ""
                if "page" in body:
                    page = __normalise(body["page"])

                f_res[omid] = {
                    "id": id,
                    "authors_str": "; ".join(authors),
                    "authors_orcid": authors_orcid,
                    "pub_date": pub_date,
                    "title": title,
                    "source_title": source_title,
                    "source_id": source_id,
                    "volume": volume,
                    "issue": issue,
                    "page":page
                }

        return f_res

    return f_res

def __get_omid_of(s):
    MULTI_VAL_MAX = 9000
    sparql_endpoint = env_config["sparql_endpoint_meta"]

    sparql_query = """
        PREFIX datacite: <http://purl.org/spar/datacite/>
        PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
        SELECT ?br {
            { ?identifier literal:hasLiteralValue '"""+s+"""'^^<http://www.w3.org/2001/XMLSchema#string>. }
            UNION
            { ?identifier literal:hasLiteralValue '"""+s+"""'. }
            ?br datacite:hasIdentifier ?identifier
        }
    """

    headers={"Accept": "application/sparql-results+json", "Content-Type": "application/sparql-query"}
    try:
        response = post(sparql_endpoint, headers=headers, data=sparql_query, timeout=45)
        response.raise_for_status()
    except RequestException:
        return ""
    r = loads(response.text)
    results = r["results"]["bindings"]
    omid_l = [elem["br"]["value"].split("meta/br/")[1] for elem in results]

    if len(omid_l) == 0:
        return ""

    sparql_values = []
    for i in range(0, len(omid_l), MULTI_VAL_MAX):
        sparql_values.append( " ".join(["<https://w3id.org/oc/meta/br/"+e+">" for e in omid_l[i:i + MULTI_VAL_MAX]]) )
    return sparql_values

def __normalise(o):
    if o is None:
        s = ""
    else:
        s = str(o)
    return sub(r"\s+", " ", s).strip()

def __get_doi(elem, value_key = False):
    str_ids = []
    if "ids" in elem:
        ids = elem["ids"]
        if value_key:
            ids = ids["value"]
        for id in ids.split(" __ "):
            if id.startswith("doi:"):
                str_ids.append(id.split("doi:")[1])

    return " ".join(str_ids)
