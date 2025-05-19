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
import json
import os
from urllib.parse import quote, unquote
from requests import get,post
from rdflib import Graph, URIRef
from re import sub,findall
from json import loads
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from collections import defaultdict

# Load the configuration file
with open("conf.json") as f:
    c = json.load(f)
    

# Docker ENV variables
env_config = {
    "base_url": os.getenv("BASE_URL", c["base_url"]),
    "sparql_endpoint_index": os.getenv("SPARQL_ENDPOINT_INDEX", c["sparql_endpoint_index"]),
    "sparql_endpoint_meta": os.getenv("SPARQL_ENDPOINT_META", c["sparql_endpoint_meta"]),
    "sync_enabled": os.getenv("SYNC_ENABLED", "false").lower() == "true"
}

def lower(s):
    return s.lower(),

def encode(s):
    return quote(s),

def id2omids(s):
    if "omid" in s:
        return s.replace("omid:br/","<https://w3id.org/oc/meta/br/") +">",
    return __get_omid_of(s, multi = True),

def count_unique_cits(res, *args):
    header = res[0]
    oci_idx = header.index(args[0])
    citing_idx = header.index(args[1])
    cited_idx = header.index(args[2])
    set_oci = set()

    # build
    if len(res) > 1:
        citing_to_dedup = []
        cited_to_dedup = []
        for idx, row in enumerate(res[1:]):
            citing_val = row[citing_idx]
            cited_val = row[cited_idx]
            if isinstance(citing_val, tuple):
                citing_to_dedup.extend(citing_val)
                cited_to_dedup.extend(cited_val)
            else:
                citing_to_dedup.append(citing_val)
                cited_to_dedup.append(cited_val)

        citing_to_dedup_meta = __get_unique_brs_metadata( list(set(citing_to_dedup)) )
        cited_to_dedup_meta = __get_unique_brs_metadata( list(set(cited_to_dedup)) )
        for _k_citing in citing_to_dedup_meta.keys():
            for _k_cited in cited_to_dedup_meta.keys():
                set_oci.add( (_k_citing,_k_cited) )

    return [["count"],[ len( set_oci ) ]], True

# args must contain the <citing> and <cited>
def citations_info(res, *args):

    header = res[0]
    oci_idx = header.index(args[0])
    citing_idx = header.index(args[1])
    cited_idx = header.index(args[2])

    # build
    f_res = [
        ["oci", "citing", "cited", "creation", "timespan", "journal_sc", "author_sc"]
    ]

    if len(res) > 1:
        citing_to_dedup = []
        cited_to_dedup = []
        for idx, row in enumerate(res[1:]):
            citing_val = row[citing_idx]
            cited_val = row[cited_idx]
            if isinstance(citing_val, tuple):
                citing_to_dedup.extend(citing_val)
                cited_to_dedup.extend(cited_val)
            else:
                citing_to_dedup.append(citing_val)
                cited_to_dedup.append(cited_val)

        citing_to_dedup_meta = __get_unique_brs_metadata( list(set(citing_to_dedup)) )
        cited_to_dedup_meta = __get_unique_brs_metadata( list(set(cited_to_dedup)) )

        for citing_entity in citing_to_dedup_meta:
            for cited_entity in cited_to_dedup_meta:

                _citing = citing_to_dedup_meta[citing_entity]
                _cited = cited_to_dedup_meta[cited_entity]

                res_row = [
                    # oci value
                    __get_id_val(citing_entity,True)+"-"+__get_id_val(cited_entity,True),
                    # citing
                    __get_all_pids(_citing,citing_entity),
                    # cited
                    __get_all_pids(_cited,cited_entity),
                    # creation = citing[pub_date]
                    __get_pub_date(_citing),
                    # timespan = citing[pub_date] - cited[pub_date]
                    __cit_duration(__get_pub_date(_citing),__get_pub_date(_cited)),
                    # journal_sc = compare citing[source_id] and cited[source_id]
                    __cit_journal_sc(__get_source(_citing),__get_source(_cited)),
                    # author_sc = compare citing[source_id] and cited[source_id]
                    __cit_author_sc(__get_author(_citing),__get_author(_cited))
                ]
                f_res.append(res_row)

    return f_res, True

# args must contain the <count>
def sum_all(res, *args):

    header = res[0]
    try:
        count_idx = header.index(args[0])

        tot_count = 0
        for idx, row in enumerate(res[1:]):
            tot_count += int(row[count_idx][1])

        # delete the item + citing + cited columns
        res = [header,[str(tot_count)]]
        return res, True

    except:
        return [], True


# ---
# Local methods
# ---

def __get_omid_of(s, multi = False):
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
            ?identifier literal:hasLiteralValue '"""+s+"""'.
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
            	?identifier literal:hasLiteralValue '"""+s+"""'^^<http://www.w3.org/2001/XMLSchema#string>.
            	?venue datacite:hasIdentifier ?identifier .
              	{?br ns1:partOf ?venue .}
              	UNION { ?br ns1:partOf/ns1:partOf ?venue . }
              	UNION { ?br ns1:partOf/ns1:partOf/ns1:partOf ?venue . }
              	UNION { ?br ns1:partOf/ns1:partOf/ns1:partOf/ns1:partOf ?venue .}
              	?br a fabio:JournalArticle .
            }
        """

    headers={"Accept": "application/sparql-results+json", "Content-Type": "application/sparql-query"}
    data = {"query": sparql_query}
    omid_l = []
    try:
        response = post(sparql_endpoint, headers=headers, data=sparql_query, timeout=45)
        if response.status_code == 200:
            r = loads(response.text)
            results = r["results"]["bindings"]
            if len(results) > 0:
                for elem in results:
                    omid_val = elem["br"]["value"].split("meta/br/")[1]
                    omid_l.append(omid_val)
    except:
        return ""

    if len(omid_l) == 0:
        return ""

    if multi:
        sparql_values = []
        for i in range(0, len(omid_l), MULTI_VAL_MAX):
            sparql_values.append( " ".join(["<https://w3id.org/oc/meta/br/"+e+">" for e in omid_l[i:i + MULTI_VAL_MAX]]) )
        return sparql_values

    # in case multi OMIDs is not handled
    # return the only omid given as result
    return omid_l[0]

def __get_unique_brs_metadata(l_url_brs):

    res = []
    l_brs = ["<"+_url_br+">" for _url_br in l_url_brs]

    i = 0
    chunk_size = 3000
    brs_meta = {}
    while i < len(l_brs):
        chunk = l_brs[i:i + chunk_size]
        m_br = __br_meta_metadata(chunk)
        brs_meta.update( m_br[0] )
        if i == 0:
            res.append(m_br[1])
        i += chunk_size

    unique_brs_anyid = []
    unique_brs = []
    for k_br,k_val in brs_meta.items():
        br_ids = k_val["ids"]["value"]
        if br_ids:
            s = set( [id for id in br_ids.split(" __ ")] )
            # check the unique br anyids
            _c_intersection = 0
            for __unique in unique_brs_anyid:
                _c_intersection += len(__unique.intersection(s))
            # if there is no common anyids with the other br entities
            if _c_intersection == 0:
                unique_brs_anyid.append(s)
                br_values = [k_val[k]['value'] if k in k_val else "" for k in res[0]]
                res.append( br_values )
                #unique_brs.append( br_values )

    f_res = {}
    for row in res[1:]:
        f_res[row[0]] = {k_val: row[i] for i, k_val in enumerate(res[0])}

    return f_res

def __br_meta_metadata(values):
    sparql_endpoint = env_config["sparql_endpoint_meta"]

    # SPARQL query
    sparql_query = """
    PREFIX pro: <http://purl.org/spar/pro/>
    PREFIX frbr: <http://purl.org/vocab/frbr/core#>
    PREFIX fabio: <http://purl.org/spar/fabio/>
    PREFIX datacite: <http://purl.org/spar/datacite/>
    PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
    PREFIX prism: <http://prismstandard.org/namespaces/basic/2.0/>
    SELECT DISTINCT ?val ?pubDate (GROUP_CONCAT(DISTINCT ?id; SEPARATOR=' __ ') AS ?ids) (GROUP_CONCAT(?venue; separator="; ") as ?source) (GROUP_CONCAT(?raAuthor; separator="; ") as ?author)
    WHERE {
    	  VALUES ?val { """+" ".join(values)+""" }
          OPTIONAL { ?val prism:publicationDate ?pubDate. }
          OPTIONAL {
              ?val datacite:hasIdentifier ?identifier.
              ?identifier datacite:usesIdentifierScheme ?scheme;
                  literal:hasLiteralValue ?literalValue.
              BIND(CONCAT(STRAFTER(STR(?scheme), "http://purl.org/spar/datacite/"), ":", ?literalValue) AS ?id)
          }
          OPTIONAL {
              {
                ?val a fabio:JournalArticle;
                      frbr:partOf+ ?venue.
                ?venue a fabio:Journal.
              } UNION {
                ?val frbr:partOf ?venue.
              }
          }
          OPTIONAL {
              ?val pro:isDocumentContextFor ?arAuthor.
                  ?arAuthor pro:withRole pro:author;
                            pro:isHeldBy ?raAuthor.
          }
     } GROUP BY ?val ?pubDate
    """

    headers={"Accept": "application/sparql-results+json", "Content-Type": "application/sparql-query"}
    data = {"query": sparql_query}

    try:
        response = post(sparql_endpoint, headers=headers, data=sparql_query)
        if response.status_code == 200:
            r = loads(response.text)
            results = r["results"]["bindings"]
            res_json = {}
            if len(results) > 0:
                for elem in results:
                    res_json[elem["val"]["value"]] = elem
            return res_json,["val","pubDate","ids","source","author"]

    except:
        return None,None

def __get_id_val(val, reverse = False):
    if not reverse:
        return "https://w3id.org/oc/meta/"+val.split("oc/meta/")[1]
    return val.replace("https://w3id.org/oc/meta/br/","")

def __get_all_pids(elem, uri_omid):
    str_omid = "omid:br/"+__get_id_val(uri_omid,True)
    str_ids = [str_omid]
    if "ids" in elem:
        for id in elem["ids"].split(" __ "):
            str_ids.append(id)

    return " ".join(str_ids)

def __get_pub_date(elem):
    if "pubDate" in elem:
        return elem["pubDate"]
    return ""

def __get_source(elem):
    if "source" in elem:
        return elem["source"].split("; ")
    return ""

def __get_author(elem):
    if "author" in elem:
        return elem["author"].split("; ")
    return ""

def __cit_journal_sc(citing_source_ids, cited_source_ids):
    if len(set(citing_source_ids).intersection(set(cited_source_ids))) > 0:
        return "yes"
    return "no"

def __cit_author_sc(citing_authors, cited_authors):
    if len(set(citing_authors).intersection(set(cited_authors))) > 0:
        return "yes"
    return "no"

def __cit_duration(citing_complete_pub_date, cited_complete_pub_date):

    def ___contains_years(date):
        return date is not None and len(date) >= 4

    def ___contains_months(date):
        return date is not None and len(date) >= 7

    def ___contains_days(date):
        return date is not None and len(date) >= 10

    DEFAULT_DATE = datetime(1970, 1, 1, 0, 0)
    consider_months = ___contains_months(citing_complete_pub_date) and ___contains_months(cited_complete_pub_date)
    consider_days = ___contains_days(citing_complete_pub_date) and ___contains_days(cited_complete_pub_date)

    try:
        if citing_complete_pub_date == "" or citing_complete_pub_date == None:
            return ""
        citing_pub_datetime = parse(
            citing_complete_pub_date, default=DEFAULT_DATE
        )
    except ValueError:  # It is not a leap year
        citing_pub_datetime = parse(
            citing_complete_pub_date[:7] + "-28", default=DEFAULT_DATE
        )
    try:
        if cited_complete_pub_date == "" or cited_complete_pub_date == None:
            return ""
        cited_pub_datetime = parse(
            cited_complete_pub_date, default=DEFAULT_DATE
        )
    except ValueError:  # It is not a leap year
        cited_pub_datetime = parse(
            cited_complete_pub_date[:7] + "-28", default=DEFAULT_DATE
        )

    delta = relativedelta(citing_pub_datetime, cited_pub_datetime)

    result = ""
    if (
        delta.years < 0
        or (delta.years == 0 and delta.months < 0 and consider_months)
        or (
            delta.years == 0
            and delta.months == 0
            and delta.days < 0
            and consider_days
        )
    ):
        result += "-"
    result += "P%sY" % abs(delta.years)

    if consider_months:
        result += "%sM" % abs(delta.months)

    if consider_days:
        result += "%sD" % abs(delta.days)

    return result