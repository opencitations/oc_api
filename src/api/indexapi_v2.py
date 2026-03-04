#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2023, Silvio Peroni <essepuntato@gmail.com>
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

from requests import RequestException, post
from json import loads
from indexapi_common import (
    lower,  # noqa: F401 - used by ramose via getattr
    env_config,
    get_unique_brs_metadata,
    get_pub_date,
    get_source,
    get_author,
    get_id_val,
    cit_journal_sc,
    cit_author_sc,
    cit_duration,
)


def id2omids(s):
    if "omid" in s:
        return s.replace("omid:br/","<https://w3id.org/oc/meta/br/") +">",
    return __get_omid_of(s),

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
            citing_to_dedup.extend(row[citing_idx])
            cited_to_dedup.extend(row[cited_idx])

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
            citing_to_dedup.extend(row[citing_idx])
            cited_to_dedup.extend(row[cited_idx])

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
                    __get_all_pids(_citing,citing_entity),
                    # cited
                    __get_all_pids(_cited,cited_entity),
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

# args must contain the <count>
def sum_all(res, *args):

    header = res[0]
    count_idx = header.index(args[0])

    tot_count = 0
    for row in res[1:]:
        tot_count += int(row[count_idx][1])

    res = [header, [str(tot_count)]]
    return res, True


# ---
# Local methods
# ---

def __get_omid_of(s):
    MULTI_VAL_MAX = 9000
    sparql_endpoint = env_config["sparql_endpoint_meta"]

    # SPARQL query
    is_journal = False
    br_pre_l = ["doi","issn","isbn","pmid","pmcid","url","wikidata","wikipedia","jid","arxiv"]
    for br_pre in br_pre_l:
        if s.startswith(br_pre+":"):
            s = s.replace(br_pre+":","")
            # check if is journal
            is_journal = br_pre in ["issn"]
            break

    sparql_query = """
        PREFIX datacite: <http://purl.org/spar/datacite/>
        PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
        SELECT ?br {
            { ?identifier literal:hasLiteralValue '"""+s+"""'^^<http://www.w3.org/2001/XMLSchema#string>. }
            UNION
            {?identifier literal:hasLiteralValue '"""+s+"""'.}
            ?br datacite:hasIdentifier ?identifier
        }
    """

    # in case is a journal the SAPRQL query retrieves all associated BRs
    if is_journal:
        sparql_query = """
            PREFIX datacite: <http://purl.org/spar/datacite/>
            PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
            PREFIX ns1: <http://purl.org/vocab/frbr/core#>
            PREFIX fabio: <http://purl.org/spar/fabio/>
            SELECT ?br {
            	{ ?identifier literal:hasLiteralValue '"""+s+"""'^^<http://www.w3.org/2001/XMLSchema#string>. }
                UNION
                {?identifier literal:hasLiteralValue '"""+s+"""'.}
            	?venue datacite:hasIdentifier ?identifier .
              	{?br ns1:partOf ?venue .}
              	UNION { ?br ns1:partOf/ns1:partOf ?venue . }
              	UNION { ?br ns1:partOf/ns1:partOf/ns1:partOf ?venue . }
              	UNION { ?br ns1:partOf/ns1:partOf/ns1:partOf/ns1:partOf ?venue .}
              	?br a fabio:JournalArticle .
            }
        """

    headers = {"Accept": "application/sparql-results+json", "Content-Type": "application/sparql-query"}
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

def __get_all_pids(elem, uri_omid):
    str_omid = "omid:br/"+get_id_val(uri_omid)
    str_ids = [str_omid]
    if "ids" in elem:
        for id in elem["ids"].split(" __ "):
            str_ids.append(id)

    return " ".join(str_ids)
