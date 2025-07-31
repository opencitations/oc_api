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

def split_dois2omids(s):
    l_omids = []
    for d in s.split("__"):
        print("omid of :",d)
        l_omids.extend( __get_omid_of(d, multi = True) )
    return " ".join(l_omids),

def id2omids(s):
    if "omid" in s:
        return s.replace("omid:br/","<https://w3id.org/oc/meta/br/") +">",
    return __get_omid_of(s, multi = True),

def metadata(res, *args):
    header = res[0]
    oci_idx = header.index(args[0]);
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
    rows_to_remove = []

    # org value: <https://w3id.org/oc/meta/br/06NNNNNN>
    for idx, row in enumerate(res[1:]):
        omid_uri = res_entities[idx]["omid"]
        citation = res_entities[idx]["citation"]
        reference = res_entities[idx]["reference"]
        entities = citation.split("; ") + reference.split("; ") + [omid_uri]
        r = __br_meta_metadata(["<"+e+">" for e in entities])
        if r is None or all([i in ("", None) for i in r]):
            row.extend(["","",""])
        else:
            k_omids_uris = r[0]

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

        # Use SPARQL instead of META API
        r = __get_full_metadata_sparql([omid_uri])
        if r is None or omid_uri not in r:
            row.extend(["","","","","","","","",""])
        else:
            metadata = r[omid_uri]
            row.extend([
                metadata["authors_str"],
                metadata["pub_date"],
                metadata["title"],
                metadata["source_title"],
                metadata["volume"],
                metadata["issue"],
                metadata["page"],
                metadata["source_id"],
                ""
            ])

    return res, True

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
                    __get_doi(_citing),
                    # cited
                    __get_doi(_cited),
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

# Get full metadata via SPARQL instead of external META API
def __get_full_metadata_sparql(omid_uris):
    sparql_endpoint = env_config["sparql_endpoint_meta"]
    
    # SPARQL query to get all necessary metadata fields
    sparql_query = """
    PREFIX pro: <http://purl.org/spar/pro/>
    PREFIX frbr: <http://purl.org/vocab/frbr/core#>
    PREFIX fabio: <http://purl.org/spar/fabio/>
    PREFIX datacite: <http://purl.org/spar/datacite/>
    PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
    PREFIX prism: <http://prismstandard.org/namespaces/basic/2.0/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX biro: <http://purl.org/spar/biro/>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    
    SELECT DISTINCT ?br ?title ?pubDate 
           (GROUP_CONCAT(DISTINCT ?startPage; SEPARATOR='-') AS ?page)
           (GROUP_CONCAT(DISTINCT ?id; SEPARATOR=' __ ') AS ?ids)
           (GROUP_CONCAT(DISTINCT ?venue_title; SEPARATOR='; ') AS ?source_title)
           (GROUP_CONCAT(DISTINCT ?venue_id; SEPARATOR=' ') AS ?source_ids)
           (GROUP_CONCAT(DISTINCT CONCAT(COALESCE(?authorFamily, ""), ", ", COALESCE(?authorGiven, ""), 
                         IF(BOUND(?orcid), CONCAT(", ", STR(?orcid)), "")); SEPARATOR='; ') AS ?authors)
           (GROUP_CONCAT(DISTINCT ?volNum; SEPARATOR='') AS ?volume)
           (GROUP_CONCAT(DISTINCT ?issueNum; SEPARATOR='') AS ?issue)
    WHERE {
        VALUES ?br { """ + " ".join(["<"+uri+">" for uri in omid_uris]) + """ }
        
        # Title
        OPTIONAL { ?br dcterms:title ?title. }
        
        # Publication date
        OPTIONAL { ?br prism:publicationDate ?pubDate. }
        
        # Page
        OPTIONAL { 
            ?br frbr:embodiment ?re.
            ?re prism:startingPage ?startPage.
        }
        
        # Identifiers
        OPTIONAL {
            ?br datacite:hasIdentifier ?identifier.
            ?identifier datacite:usesIdentifierScheme ?scheme;
                       literal:hasLiteralValue ?literalValue.
            BIND(CONCAT(STRAFTER(STR(?scheme), "http://purl.org/spar/datacite/"), ":", ?literalValue) AS ?id)
        }
        
        # Venue, volume, issue
        OPTIONAL {
            ?br frbr:partOf ?issue_or_vol.
            OPTIONAL {
                ?issue_or_vol a fabio:JournalIssue;
                             fabio:hasSequenceIdentifier ?issueNum;
                             frbr:partOf ?vol.
                ?vol a fabio:JournalVolume;
                     fabio:hasSequenceIdentifier ?volNum.
            }
            OPTIONAL {
                ?issue_or_vol a fabio:JournalVolume;
                             fabio:hasSequenceIdentifier ?volNum.
            }
            # Get journal info
            {
                ?issue_or_vol frbr:partOf+ ?venue.
                ?venue a fabio:Journal.
            } UNION {
                ?br frbr:partOf+ ?venue.
                ?venue a fabio:Journal.
            }
            ?venue dcterms:title ?venue_title.
            OPTIONAL {
                ?venue datacite:hasIdentifier ?venue_identifier.
                ?venue_identifier datacite:usesIdentifierScheme ?venue_scheme;
                                 literal:hasLiteralValue ?venue_id_value.
                BIND(CONCAT(STRAFTER(STR(?venue_scheme), "http://purl.org/spar/datacite/"), ":", ?venue_id_value) AS ?venue_id)
            }
        }
        
        # Authors with ORCID
        OPTIONAL {
            ?br pro:isDocumentContextFor ?ar.
            ?ar pro:withRole pro:author;
                pro:isHeldBy ?ra.
            OPTIONAL { ?ra foaf:givenName ?authorGiven. }
            OPTIONAL { ?ra foaf:familyName ?authorFamily. }
            OPTIONAL { 
                ?ra datacite:hasIdentifier ?authorId.
                ?authorId datacite:usesIdentifierScheme datacite:orcid;
                         literal:hasLiteralValue ?orcid.
            }
        }
    }
    GROUP BY ?br ?title ?pubDate
    """
    
    headers = {"Accept": "application/sparql-results+json", "Content-Type": "application/sparql-query"}
    
    try:
        response = post(sparql_endpoint, headers=headers, data=sparql_query, timeout=120)
        if response.status_code == 200:
            r = loads(response.text)
            results = r["results"]["bindings"]
            
            # Format results
            formatted_results = {}
            for result in results:
                br_uri = result["br"]["value"]
                
                # Extract DOI from IDs
                doi = ""
                if "ids" in result and result["ids"]["value"]:
                    for id_str in result["ids"]["value"].split(" __ "):
                        if id_str.startswith("doi:"):
                            doi = id_str.replace("doi:", "")
                            break
                
                # Extract source_id (preferably ISSN)
                source_id = ""
                if "source_ids" in result and result["source_ids"]["value"]:
                    for sid in result["source_ids"]["value"].split(" "):
                        if sid.startswith("issn:"):
                            source_id = sid
                            break
                    if not source_id and result["source_ids"]["value"]:
                        source_id = result["source_ids"]["value"].split(" ")[0]
                
                # Get full publication date
                pub_date = result.get("pubDate", {}).get("value", "")
                
                # Clean authors - remove empty entries
                authors = result.get("authors", {}).get("value", "")
                if authors:
                    authors_list = []
                    for author in authors.split("; "):
                        author = author.strip()
                        # Remove entries that are just commas or spaces
                        if author and author not in [", ,", ", ", " ,", ","]:
                            authors_list.append(author)
                    authors = "; ".join(authors_list)
                
                formatted_results[br_uri] = {
                    "doi": doi,
                    "title": result.get("title", {}).get("value", ""),
                    "authors_str": authors,
                    "pub_date": pub_date,
                    "year": pub_date,  # Return full date as year field based on expected output
                    "source_title": result.get("source_title", {}).get("value", ""),
                    "source_id": source_id,
                    "volume": result.get("volume", {}).get("value", ""),
                    "issue": result.get("issue", {}).get("value", ""),
                    "page": result.get("page", {}).get("value", "")
                }
            
            return formatted_results
            
    except Exception as e:
        print(f"SPARQL error: {e}")
        return {}

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

                if omid == None:
                    continue

                authors = []
                l_authors_id = []
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
                all_source_ids = []
                if "venue" in body:
                    if body["venue"] != "":
                        source_title_string = body["venue"]

                        source_issn = findall(r"(issn\:[\d\-^\]]{1,})",source_title_string)
                        source_isbn = findall(r"(isbn\:[\d\-^\]]{1,})",source_title_string)
                        source_ids = findall(r"\[.{1,}\]",source_title_string)
                        if len(source_ids) > 0:
                            all_source_ids = source_ids[0].split(" ")
                            source_title_string = source_title_string.replace(source_ids[0],"").strip()
                        if len(source_issn) > 0:
                            source_id = source_issn[0]
                        elif len(source_isbn) > 0:
                            source_id = source_isbn[0]
                        source_title = source_title_string

                year = ""
                pub_date = ""
                if "pub_date" in body:
                    pub_date = __normalise(body["pub_date"])
                    if len(body["pub_date"]) >= 4:
                        year = __normalise(body["pub_date"][:4])

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
                    "all_source_ids": all_source_ids,
                    "volume": volume,
                    "issue": issue,
                    "page":page
                }

        return f_res

    return f_res

def __convert_cit_v1(l_cits):
    if len(l_cits) > 0:
        for cit in l_cits:
            for k_att in ["citing","cited"]:
                if k_att in cit:
                    doi = ""
                    for anyid in cit[k_att].split():
                        if anyid.startswith("doi:"):
                            doi = anyid.split("doi:")[1]
                    cit[k_att] = doi
    return l_cits


def __get_omid_of(s, multi = False):
    MULTI_VAL_MAX = 9000
    sparql_endpoint = env_config["sparql_endpoint_meta"]

    sparql_query = """
        PREFIX datacite: <http://purl.org/spar/datacite/>
        PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
        SELECT ?br {
            ?identifier literal:hasLiteralValue '"""+s+"""'.
            ?br datacite:hasIdentifier ?identifier
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

def __normalise(o):
    if o is None:
        s = ""
    else:
        s = str(o)
    return sub("\s+", " ", s).strip()

def __get_id_val(val, reverse = False):
    if not reverse:
        return "https://w3id.org/oc/meta/"+val.split("oc/meta/")[1]
    return val.replace("https://w3id.org/oc/meta/br/","")

def __get_omid(elem):
    str_ids = []
    if "ids" in elem:
        for id in elem["ids"].split(" __ "):
            if id.startswith("omid:"):
                str_ids.append(id.split("omid:")[1])

    return " ".join(str_ids)

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