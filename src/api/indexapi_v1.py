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

__author__ = 'essepuntato'
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

def lower(s):
    return s.lower(),


def encode(s):
    return quote(s),


def decode_doi(res, *args):
    header = res[0]
    field_idx = []

    for field in args:
        field_idx.append(header.index(field))

    for row in res[1:]:
        for idx in field_idx:
            t, v = row[idx]
            row[idx] = t, unquote(v)

    return res, True


def decode_pmid(res, *args):
    header = res[0]
    field_idx = []

    for field in args:
        field_idx.append(header.index(field))

    for row in res[1:]:
        for idx in field_idx:
            t, v = row[idx]
            row[idx] = t, unquote(v)

    return res, True


def merge(res, *args):
    final_result = []
    header = res[0]
    final_result.append(header)
    prefix_idx = header.index(args[0])
    citing_idx = header.index(args[1])
    cited_idx = header.index(args[2])

    citations = {}
    row_idx = 0
    for row in res[1:]:
        source = row[prefix_idx][1]
        citation = row[citing_idx][1], row[cited_idx][1]

        for idx in range(len(header)):
            t, v = row[idx]
            row[idx] = t, source.replace("/", " => ") + v
        if citation in citations:
            processed_row = citations[citation]
            for idx in range(len(header)):
                t, v = final_result[processed_row][idx]
                final_result[processed_row][idx] = t, v + "; " + row[idx][1]
        else:
            row_idx += 1
            citations[citation] = row_idx
            final_result.append(list(row))

    for row in final_result:
        row.pop(prefix_idx)

    return final_result, False


def split_dois(s):
    return "\"%s\"" % "\" \"".join(s.split("__")),

def split_dois2omids(s):
    #return "\"%s\"" % "\" \"".join([__get_omid_of(d) for d in s.split("__")]),
    return " ".join(["<https://w3id.org/oc/meta/br/"+str(__get_omid_of("doi:"+d))+">" for d in s.split("__")]),



def doi2omid(s):
    return __get_omid_of("doi:"+s),

def pmid2omid(s):
    return __get_omid_of("pmid:"+s),

def doi2omids(s):
    return __get_omid_of("doi:"+s, multi = True),

def __get_omid_of(s, multi = False):
    sparql_endpoint = api_config["sparql_endpoint_meta"]

    # SPARQL query
    br_pre_l = ["doi","issn","isbn","pmid","pmcid","url","wikidata","wikipedia","jid","arxiv"]
    for br_pre in br_pre_l:
        if s.startswith(br_pre+":"):
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
        return " ".join(["<https://w3id.org/oc/meta/br/"+e+">" for e in omid_l])

    if len(omid_l) == 0:
        return ""
    elif len(omid_l) == 1:
        return omid_l[0]
    else:
        # Check the OMID which has more citations/references
        sparql_values = " ".join(["<https://w3id.org/oc/meta/br/"+e+">" for e in omid_l])
        sparql_endpoint = api_config["sparql_endpoint_index"]
        sparql_query = """
        PREFIX cito:<http://purl.org/spar/cito/>
        SELECT ?cited (COUNT(?citation) as ?citation_count) WHERE {
          	VALUES ?cited {"""+sparql_values+"""} .
        	?citation cito:hasCitedEntity ?cited .
        } GROUP BY ?cited
        """
        try:
            response = post(sparql_endpoint, headers=headers, data=sparql_query, timeout=45)
            if response.status_code == 200:
                r = loads(response.text)
                results = r["results"]["bindings"]
                max_cits = -1
                res_omid = omid_l[0]
                if len(results) > 0:
                    for elem in results:
                        cits_num = elem["citation_count"]["value"]
                        if int(cits_num) > max_cits:
                            res_omid = elem["cited"]["value"].split("meta/br/")[1]
                            max_cits = int(cits_num)
                return res_omid
        except:
            return omid_l[0]

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

            citation_ids = []
            for e in citation.split("; "):
                if e in r:
                    citation_ids.append(__get_identifier(r[e]))

            reference_ids = []
            for e in reference.split("; "):
                if e in r:
                    reference_ids.append(__get_identifier(r[e]))

            row.extend([
                __get_identifier(r[omid_uri],["doi"]),
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

# args must contain the [[citing]] and [[cited]]
def citations_info(res, *args):

    header = res[0]
    oci_idx = header.index(args[0]);
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
                citing_id = __get_identifier(r[citing_entity], all_ids)
                citing_pubdate = __get_pub_date(r[citing_entity])

            cited_id = ""
            duration = ""
            journal_sc = ""
            author_sc = ""
            if citing_entity in r and cited_entity in r:
                cited_id = __get_identifier(r[cited_entity], all_ids)
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

def __get_identifier(elem, ids = ["doi","pmid"]):
    if "ids" in elem:
        for pre in ids:
            for id in elem["ids"]["value"].split(" __ "):
                if id.startswith(pre+":"):
                    return id.replace(pre+":","")
    return ""

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

def __get_issn(body):
    cur_id = ""
    if "ISSN" in body and len(body["ISSN"]):
        cur_id = "; ".join("issn:" + cur_issn for cur_issn in body["ISSN"])
    return __normalise(cur_id)

def __get_isbn(body):
    cur_id = ""
    if "ISBN" in body and len(body["ISBN"]):
        cur_id = "; ".join("isbn:" + cur_issn for cur_issn in body["ISBN"])
    return __normalise(cur_id)

def __get_id(body, f_list):
    cur_id = ""
    for f in f_list:
        if cur_id == "":
            cur_id = f(body)
    return __normalise(cur_id)

def __create_title_from_list(title_list):
    cur_title = ""

    for title in title_list:
        strip_title = title.strip()
        if strip_title != "":
            if cur_title == "":
                cur_title = strip_title
            else:
                cur_title += " - " + strip_title

    return __create_title(cur_title)


def __create_title(cur_title):
    return __normalise(cur_title.title())


def __normalise(o):
    if o is None:
        s = ""
    else:
        s = str(o)
    return sub(r"\s+", " ", s).strip()

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

def __ocmeta_parser(ids, pre="doi"):
    api = "http://127.0.0.1/meta/api/v1/metadata/"

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

def __crossref_parser(doi):
    api = "https://api.crossref.org/works/%s"

    try:
        r = get(api % doi,
                headers={"User-Agent": "COCI REST API (via OpenCitations - http://opencitations.net; mailto:contact@opencitations.net)"}, timeout=30)
        if r.status_code == 200:
            json_res = loads(r.text)
            if "message" in json_res:
                body = json_res["message"]

                authors = []
                if "author" in body:
                    for author in body["author"]:
                        author_string = None
                        if "family" in author:
                            author_string = author["family"].title()
                            if "given" in author:
                                author_string += ", " + author["given"].title()
                                if "ORCID" in author:
                                    author_string += ", " + \
                                        author["ORCID"].replace(
                                            "http://orcid.org/", "")
                        if author_string is not None:
                            authors.append(__normalise(author_string))

                year = ""
                if "issued" in body and "date-parts" in body["issued"] and len(body["issued"]["date-parts"]) and \
                        len(body["issued"]["date-parts"][0]):
                    year = __normalise(body["issued"]["date-parts"][0][0])

                title = ""
                if "title" in body:
                    title = __create_title_from_list(body["title"])

                source_title = ""
                if "container-title" in body:
                    source_title = __create_title_from_list(
                        body["container-title"])

                volume = ""
                if "volume" in body:
                    volume = __normalise(body["volume"])

                issue = ""
                if "issue" in body:
                    issue = __normalise(body["issue"])

                page = ""
                if "page" in body:
                    page = __normalise(body["page"])

                source_id = ""
                if "type" in body:
                    if body["type"] == "book-chapter":
                        source_id = __get_isbn(body)
                    else:
                        source_id = __get_issn(body)
                else:
                    source_id = __get_id(body, [__get_issn, __get_isbn])

                return ["; ".join(authors), year, title, source_title, volume, issue, page, source_id]

    except Exception as e:
        return ["", "", "", "", "", "", "", ""]


def __datacite_parser(doi):
    api = "https://api.datacite.org/works/%s"

    try:
        r = get(api % doi,
                headers={"User-Agent": "COCI REST API (via OpenCitations - "
                                       "http://opencitations.net; mailto:contact@opencitations.net)"}, timeout=30)
        if r.status_code == 200:
            json_res = loads(r.text)
            if "data" in json_res and "attributes" in json_res["data"]:
                body = json_res["data"]["attributes"]

                authors = []
                if "author" in body:
                    for author in body["author"]:
                        author_string = None
                        if "family" in author:
                            author_string = author["family"].title()
                            if "given" in author:
                                author_string += ", " + author["given"].title()
                                if "ORCID" in author:
                                    author_string += ", " + \
                                        author["ORCID"].replace(
                                            "http://orcid.org/", "")
                        if author_string is not None:
                            authors.append(__normalise(author_string))

                year = ""
                if "published" in body:
                    year = __normalise(body["published"])

                title = ""
                if "title" in body:
                    title = __create_title(body["title"])

                source_title = ""
                if "container-title" in body:
                    source_title = __create_title(body["container-title"])

                volume = ""
                issue = ""
                page = ""
                source_id = ""
                return ["; ".join(authors), year, title, source_title, volume, issue, page, source_id]

    except Exception as e:
        return ["", "", "", "", "", "", "", ""]


def oalink(res, *args):
    base_api_url = "https://api.unpaywall.org/v2/%s?email=contact@opencitations.net"

    # doi, reference, citation_count
    header = res[0]
    doi_field = header.index("doi")
    additional_fields = ["oa_link"]

    header.extend(additional_fields)

    for row in res[1:]:
        row.append("")  # empty element
        # citing_doi = row[doi_field][1]
        #
        # try:
        #     r = get(base_api_url % citing_doi,
        #             headers={"User-Agent": "COCI REST API (via OpenCitations - "
        #                                    "http://opencitations.net; mailto:contact@opencitations.net)"}, timeout=30)
        #     if r.status_code == 200:
        #         res_json = loads(r.text)
        #         if "best_oa_location" in res_json and res_json["best_oa_location"] is not None and \
        #                 "url" in res_json["best_oa_location"]:
        #             row.append(res_json["best_oa_location"]["url"])
        #         else:
        #             row.append("")  # empty element
        #     else:
        #         row.append("")  # empty element
        # except Exception as e:
        #     row.append("")  # empty element

    return res, True

def oc_coci_references(res, *args):
    api = "http://127.0.0.1/index/coci/api/v1/references/%s"

    header = res[0]
    doi_field = header.index("doi")
    additional_fields = ["reference"]

    header.extend(additional_fields)

    for row in res[1:]:
        citing_doi = row[doi_field][1]

        try:
            r = get(api % citing_doi, headers={"User-Agent": "COCI REST API (via OpenCitations - http://opencitations.net; mailto:contact@opencitations.net)"}, timeout=30)
            if r.status_code == 200:
                cited_dois = []
                res_json = loads(r.text)
                if len(res_json) > 0:
                    for item in res_json:
                        cited_dois.append(item["cited"])
                    row.append("; ".join(cited_dois))  # list of dois
                else:
                    row.append("")  # empty element
            else:
                row.append("")  # empty element
        except Exception as e:
            row.append("")  # empty element

    return res, True
