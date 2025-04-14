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
api_config = {
    "api_base_url": os.getenv("API_BASE_URL", c["api_base_url"]),
    "sparql_endpoint_index": os.getenv("SPARQL_ENDPOINT_INDEX", c["sparql_endpoint_index"]),
    "sparql_endpoint_meta": os.getenv("SPARQL_ENDPOINT_META", c["sparql_endpoint_meta"]),
    "sync_enabled": os.getenv("SYNC_ENABLED", "false").lower() == "true"
}


def lower(s):
    return s.lower(),

def encode(s):
    return quote(s),

def id2omid(s):
    if "omid" in s:
        return s.replace("omid:br/",""),
    return __get_omid_of(s),

def id2omids(s):
    if "omid" in s:
        return s.replace("omid:br/","<https://w3id.org/oc/meta/br/") +">",
    return __get_omid_of(s, multi = True),

def __get_omid_of(s, multi = False):
    MULTI_VAL_MAX = 9000
    sparql_endpoint = api_config["sparql_endpoint_meta"]

    # SPARQL query
    is_journal = False
    br_pre_l = ["doi","issn","isbn","pmid","pmcid","url","wikidata","wikipedia","jid","arxiv"]
    for br_pre in br_pre_l:
        if s.startswith(br_pre+":"):
            is_journal = br_pre in ["issn"]
            s = s.replace(br_pre+":","")
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
            	?identifier literal:hasLiteralValue '"""+s+"""' .
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

    if multi:
        if len(omid_l) == 0:
            return ""
        else:
            sparql_values = []
            for i in range(0, len(omid_l), MULTI_VAL_MAX):
                sparql_values.append( " ".join(["<https://w3id.org/oc/meta/br/"+e+">" for e in omid_l[i:i + MULTI_VAL_MAX]]) )
            return sparql_values

    if len(omid_l) == 0:
        return ""
    elif len(omid_l) == 1:
        return omid_l[0]
    else:
        # return the citation/reference count of all OMIDs
        return __call_tp_for_citations(omid_l)

def __call_tp_for_citations(omid_l):
    MAX_VALUES = 9900

    part_omid_l = omid_l[:MAX_VALUES]
    rest_omid_l = omid_l[MAX_VALUES:]

    # Check the OMID which has more citations/references
    sparql_values = " ".join(["<https://w3id.org/oc/meta/br/"+e+">" for e in part_omid_l])
    sparql_endpoint = api_config["sparql_endpoint_index"]
    sparql_query = """
    PREFIX cito:<http://purl.org/spar/cito/>
    SELECT ?cited (COUNT(?citation) as ?citation_count) WHERE {
        VALUES ?cited {"""+sparql_values+"""} .
        ?citation cito:hasCitedEntity ?cited .
    } GROUP BY ?cited
    """
    try:
        headers={"Accept": "application/sparql-results+json", "Content-Type": "application/sparql-query"}
        response = post(sparql_endpoint, headers=headers, data=sparql_query, timeout=45)
        if response.status_code == 200:
            r = loads(response.text)
            results = r["results"]["bindings"]
            max_cits = -1
            res_omid = part_omid_l[0]
            if len(results) > 0:
                for elem in results:
                    cits_num = elem["citation_count"]["value"]
                    if int(cits_num) > max_cits:
                        res_omid = elem["cited"]["value"].split("meta/br/")[1]
                        max_cits = int(cits_num)

            if len(rest_omid_l) == 0:
                return res_omid
            else:
                return res_omid + __call_tp_for_citations(rest_omid_l)
    except:
        return omid_l[0]

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


def count_unique_brs(res, *args):
    header = res[0]
    idx_omid_br_uri = header.index(args[0])

    count_brs = 0
    if len(res) > 1:
        l_brs = []
        for idx, row in enumerate(res[1:]):
            l_brs.append(row[idx_omid_br_uri][1])
        l_brs = ["<"+_c+">" for _c in l_brs]
        l_brs_anyids = __get_ids_from_meta(l_brs)
        unique_brs_anyid = []
        for _l in l_brs_anyids:
            s = set(_l)
            # check the unique br anyids
            _c_intersection = 0
            for __unique in unique_brs_anyid:
                _c_intersection += len(__unique.intersection(s))
            # if there is no common anyids with the other br entities
            if _c_intersection == 0:
                unique_brs_anyid.append(s)

        count_brs = len(unique_brs_anyid)

    res = [["count"],[count_brs]]
    return res, True

# args must contain the <citing> and <cited>
def citations_info(res, *args):

    header = res[0]
    oci_idx = header.index(args[0])
    citing_idx = header.index(args[1])
    cited_idx = header.index(args[2])
    # ids managed – ordered by relevance
    all_ids = ["doi","pmid"]
    if len(args) > 3:
        all_ids = args[3].split("__")

    index_meta = {}

    #all_entities = ["omid:br/06101068294","omid:br/0610123167","omid:br/06101494166"]
    res_entities = {}
    all_entities = []
    if len(res) > 1:
        for idx, row in enumerate(res[1:]):
            res_entities[idx] = []
            res_entities[idx] += [__get_omid_str(row[citing_idx][1]), __get_omid_str(row[cited_idx][1])]
            all_entities += [__get_omid_str(row[citing_idx][1]), __get_omid_str(row[cited_idx][1])]

    # delete the item + citing + cited columns
    res = [[elem for idx, elem in enumerate(row) if idx != oci_idx and idx != citing_idx and idx != cited_idx] for row in res]

    additional_fields = ["oci", "citing", "cited", "creation", "timespan", "journal_sc","author_sc"]
    header = res[0]
    header.extend(additional_fields)

    # call __ocmeta_parser for each STEP entities each time
    r = {}
    STEP = 8
    all_entities = list(set(all_entities))
    all_entities = ["<"+e+">" for e in all_entities]
    r = __br_meta_metadata(all_entities)

    # process and elaborate additional fields
    #creation = entities_data["citing"][1]
    if len(res) > 1:
        for idx, row in enumerate(res[1:]):

            citing_entity = res_entities[idx][0]
            cited_entity = res_entities[idx][1]

            oci_val = __get_omid_str(citing_entity,True)+"-"+__get_omid_str(cited_entity,True)

            citing_id = ""
            citing_pubdate = ""
            if citing_entity in r:
                citing_id = __get_all_pids(r[citing_entity], citing_entity)
                citing_pubdate = __get_pub_date(r[citing_entity])

            cited_id = ""
            duration = ""
            journal_sc = ""
            author_sc = ""
            if citing_entity in r and cited_entity in r:
                cited_id = __get_all_pids(r[cited_entity], cited_entity)
                duration = __cit_duration(__get_pub_date(r[citing_entity]),__get_pub_date(r[cited_entity]))
                journal_sc = __cit_journal_sc(__get_source(r[citing_entity]),__get_source(r[cited_entity]))
                author_sc = __cit_author_sc(__get_author(r[citing_entity]),__get_author(r[cited_entity]))

            # in case its the API of POCI add the prefix
            if len(all_ids) == 1 and "pmid" in all_ids:
                if oci_val != "":
                    oci_val = "oci:"+oci_val
                if citing_id != "":
                    citing_id = "pmid:"+citing_id
                if cited_id != "":
                    cited_id = "pmid:"+cited_id

            # pre_source = ""
            # if len(all_ids) > 1:
            #     if citing_id.startswith("10."):
            #         pre_source = "coci => "
            #     else:
            #         pre_source = "poci => "

            row.extend([
                # oci value
                oci_val,
                # citing
                citing_id,
                # cited
                cited_id,
                # creation = citing[pub_date]
                citing_pubdate,
                # timespan = citing[pub_date] - cited[pub_date]
                duration,
                # journal_sc = compare citing[source_id] and cited[source_id]
                journal_sc,
                # author_sc = compare citing[source_id] and cited[source_id]
                author_sc
            ])


    return res, True

def __get_omid_str(val, reverse = False):
    if not reverse:
        return "https://w3id.org/oc/meta/"+val.split("oc/meta/")[1]
    return val.replace("https://w3id.org/oc/meta/br/","")

def __get_all_pids(elem, uri_omid):
    str_omid = "omid:br/"+__get_omid_str(uri_omid,True)
    str_ids = [str_omid]
    if "ids" in elem:
        for id in elem["ids"]["value"].split(" __ "):
            str_ids.append(id)

    return " ".join(str_ids)

def __get_pub_date(elem):
    if "pubDate" in elem:
        return elem["pubDate"]["value"]
    return ""

def __get_source(elem):
    if "source" in elem:
        return elem["source"]["value"].split("; ")
    return ""

def __get_author(elem):
    if "author" in elem:
        return elem["author"]["value"].split("; ")
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

def __get_ids_from_meta(values, finalres = None):

    if finalres == None:
        finalres = []

    MAX_VALUES = 2000

    values_part = values[:MAX_VALUES]
    values_rest = values[MAX_VALUES:]

    sparql_endpoint = api_config["sparql_endpoint_meta"]
    sparql_query = """
    PREFIX datacite: <http://purl.org/spar/datacite/>
    PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
    SELECT ?br_omid ?identifier_val ?scheme {
      	VALUES ?br_omid { """+" ".join(values_part)+""" }
      	?br_omid datacite:hasIdentifier ?identifier .
        ?identifier literal:hasLiteralValue ?identifier_val .
      	?identifier datacite:usesIdentifierScheme ?scheme .
    }
    """
    headers={"Accept": "application/sparql-results+json", "Content-Type": "application/sparql-query"}
    data = {"query": sparql_query}

    res = dict()

    try:
        response = post(sparql_endpoint, headers=headers, data=sparql_query)
        if response.status_code == 200:
            r = loads(response.text)
            results = r["results"]["bindings"]
            if len(results) > 0:
                for elem in results:
                    omid_br = elem["br_omid"]["value"]
                    anyid_pref = elem["scheme"]["value"].split("datacite/")[1]
                    anyid_val = elem["identifier_val"]["value"]

                    if omid_br not in res:
                        res[omid_br] = []
                    res[omid_br].append(anyid_pref+":"+anyid_val)
    except:
        pass

    finalres += [res[k] for k in res]
    res = None
    if len(values_rest) > 0:
        return __get_ids_from_meta(values_rest, finalres)
    else:
        return finalres


def __br_meta_metadata(values):
    sparql_endpoint = api_config["sparql_endpoint_meta"]

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
            return res_json

    except:
        return None
