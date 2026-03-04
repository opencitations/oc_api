import json
import os
from requests import RequestException, post
from json import loads
from datetime import datetime
from dateutil.relativedelta import relativedelta

with open("conf.json") as f:
    c = json.load(f)

env_config = {
    "base_url": os.getenv("BASE_URL", c["base_url"]),
    "sparql_endpoint_index": os.getenv("SPARQL_ENDPOINT_INDEX", c["sparql_endpoint_index"]),
    "sparql_endpoint_meta": os.getenv("SPARQL_ENDPOINT_META", c["sparql_endpoint_meta"]),
    "sync_enabled": os.getenv("SYNC_ENABLED", "false").lower() == "true"
}


def lower(s):
    return s.lower(),


def br_meta_metadata(values):
    sparql_endpoint = env_config["sparql_endpoint_meta"]

    sparql_query = """
    PREFIX pro: <http://purl.org/spar/pro/>
    PREFIX frbr: <http://purl.org/vocab/frbr/core#>
    PREFIX fabio: <http://purl.org/spar/fabio/>
    PREFIX datacite: <http://purl.org/spar/datacite/>
    PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
    PREFIX prism: <http://prismstandard.org/namespaces/basic/2.0/>
    SELECT DISTINCT ?val ?pubDate (GROUP_CONCAT(DISTINCT ?id; SEPARATOR=' __ ') AS ?ids) (GROUP_CONCAT(?venue; separator="; ") as ?source) (GROUP_CONCAT(?raAuthor; separator="; ") as ?author)
    WHERE {
    	  VALUES ?val { """ + " ".join(values) + """ }
          OPTIONAL { ?val prism:publicationDate ?pubDate. }
          OPTIONAL {
              ?val datacite:hasIdentifier ?identifier.
              ?identifier datacite:usesIdentifierScheme ?scheme;
                  literal:hasLiteralValue ?literalValue.
              BIND(CONCAT(STRAFTER(STR(?scheme), "http://purl.org/spar/datacite/"), ":", ?literalValue) AS ?id)
          }
          OPTIONAL {
              ?val a fabio:JournalArticle;
                    frbr:partOf+ ?venue.
              ?venue a fabio:Journal.
          }
          OPTIONAL {
              ?val frbr:partOf ?venue.
          }
          OPTIONAL {
              ?val pro:isDocumentContextFor ?arAuthor.
                  ?arAuthor pro:withRole pro:author;
                            pro:isHeldBy ?raAuthor.
          }
     } GROUP BY ?val ?pubDate
    """

    headers = {"Accept": "application/sparql-results+json", "Content-Type": "application/sparql-query"}

    try:
        response = post(sparql_endpoint, headers=headers, data=sparql_query)
        response.raise_for_status()
    except RequestException:
        return {}, []
    r = loads(response.text)
    results = r["results"]["bindings"]
    res_json = {elem["val"]["value"]: elem for elem in results}
    return res_json, ["val", "pubDate", "ids", "source", "author"]


def get_unique_brs_metadata(l_url_brs):
    res: list[list[str]] = []
    l_brs = ["<" + _url_br + ">" for _url_br in l_url_brs]

    i = 0
    chunk_size = 3000
    brs_meta: dict[str, dict[str, dict[str, str]]] = {}
    while i < len(l_brs):
        chunk = l_brs[i:i + chunk_size]
        m_br = br_meta_metadata(chunk)
        brs_meta.update(m_br[0])
        if i == 0:
            res.append(m_br[1])
        i += chunk_size

    unique_brs_anyid: list[set[str]] = []
    for k_val in brs_meta.values():
        br_ids = k_val["ids"]["value"]
        if br_ids:
            s = set(br_ids.split(" __ "))
            _c_intersection = 0
            for __unique in unique_brs_anyid:
                _c_intersection += len(__unique.intersection(s))
            if _c_intersection == 0:
                unique_brs_anyid.append(s)
                br_values = [k_val[k]["value"] if k in k_val else "" for k in res[0]]
                res.append(br_values)

    f_res = {}
    for row in res[1:]:
        f_res[row[0]] = {k_val: row[i] for i, k_val in enumerate(res[0])}

    return f_res


def get_pub_date(elem):
    return elem["pubDate"]


def get_source(elem):
    return elem["source"].split("; ")


def get_author(elem):
    return elem["author"].split("; ")


def get_id_val(val):
    return val.replace("https://w3id.org/oc/meta/br/", "")


def cit_journal_sc(citing_source_ids, cited_source_ids):
    if len(set(citing_source_ids).intersection(set(cited_source_ids))) > 0:
        return "yes"
    return "no"


def cit_author_sc(citing_authors, cited_authors):
    if len(set(citing_authors).intersection(set(cited_authors))) > 0:
        return "yes"
    return "no"


def cit_duration(citing_complete_pub_date, cited_complete_pub_date):

    def _contains_years(date):
        return date is not None and len(date) >= 4

    def _contains_months(date):
        return date is not None and len(date) >= 7

    def _contains_days(date):
        return date is not None and len(date) >= 10

    consider_years = _contains_years(citing_complete_pub_date) and _contains_years(cited_complete_pub_date)
    consider_months = _contains_months(citing_complete_pub_date) and _contains_months(cited_complete_pub_date)
    consider_days = _contains_days(citing_complete_pub_date) and _contains_days(cited_complete_pub_date)

    if not consider_years:
        return ""
    citing_pub_datetime = datetime.strptime((citing_complete_pub_date + "-01-01")[:10], "%Y-%m-%d")
    cited_pub_datetime = datetime.strptime((cited_complete_pub_date + "-01-01")[:10], "%Y-%m-%d")

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
