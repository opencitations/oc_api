from datetime import datetime
from dateutil.relativedelta import relativedelta


def lower(s):
    return (s.lower(),)


def oci_search(oci):
    citing, cited = oci.split("-")
    return (
        f"VALUES ?citation {{ <https://w3id.org/oc/index/ci/{oci}> }} "
        f"VALUES ?citing_br {{ <https://w3id.org/oc/meta/br/{citing}> }} "
        f"VALUES ?cited_br {{ <https://w3id.org/oc/meta/br/{cited}> }}",
    )


def literal_search(value, variable):
    return (
        f'?resolved_identifier literal:hasLiteralValue "{value}" . '
        f"?{variable} datacite:hasIdentifier ?resolved_identifier ."
    )


def unique_citations(res):
    citing_groups: dict[str, str] = {}
    cited_groups: dict[str, str] = {}
    citations: dict[tuple[str, str], dict[str, str]] = {}
    for row in sorted(__rows(res), key=lambda row: (row["citing_br"], row["cited_br"])):
        key = (
            __group(row["citing_br"], row["citing_ids"], citing_groups),
            __group(row["cited_br"], row["cited_ids"], cited_groups),
        )
        citations.setdefault(key, row)
    return list(citations.values())


def count_unique_cits(res):
    return [["count"], [len(unique_citations(res))]], True


def count_groups(res, side):
    entities = sorted({(row[f"{side}_br"], row[f"{side}_ids"]) for row in __rows(res)})
    groups: dict[str, str] = {}
    return [["count"], [len({__group(*entity, groups) for entity in entities})]], True


def citation_row(citation, citing, cited):
    return [
        citation["oci"],
        citing,
        cited,
        citation["citing_date"],
        cit_duration(citation["citing_date"], citation["cited_date"]),
        __yes_no(citation, "same_journal"),
        __yes_no(citation, "same_author"),
    ]


def get_id_val(val):
    return val.replace("https://w3id.org/oc/meta/br/", "")


def cit_duration(citing_complete_pub_date, cited_complete_pub_date):

    def _contains_years(date):
        return date is not None and len(date) >= 4

    def _contains_months(date):
        return date is not None and len(date) >= 7

    def _contains_days(date):
        return date is not None and len(date) >= 10

    consider_years = _contains_years(citing_complete_pub_date) and _contains_years(
        cited_complete_pub_date
    )
    consider_months = _contains_months(citing_complete_pub_date) and _contains_months(
        cited_complete_pub_date
    )
    consider_days = _contains_days(citing_complete_pub_date) and _contains_days(
        cited_complete_pub_date
    )

    if not consider_years:
        return ""
    citing_pub_datetime = datetime.strptime(
        (citing_complete_pub_date + "-01-01")[:10], "%Y-%m-%d"
    )
    cited_pub_datetime = datetime.strptime(
        (cited_complete_pub_date + "-01-01")[:10], "%Y-%m-%d"
    )

    delta = relativedelta(citing_pub_datetime, cited_pub_datetime)

    result = ""
    if (
        delta.years < 0
        or (delta.years == 0 and delta.months < 0 and consider_months)
        or (delta.years == 0 and delta.months == 0 and delta.days < 0 and consider_days)
    ):
        result += "-"
    result += "P%sY" % abs(delta.years)

    if consider_months:
        result += "%sM" % abs(delta.months)

    if consider_days:
        result += "%sD" % abs(delta.days)

    return result


def __rows(res):
    header = res[0]
    return [
        {field: value for field, (_, value) in zip(header, typed_row)}
        for typed_row in res[1:]
    ]


def __group(br, ids, groups):
    identifiers = ids.split(" __ ")
    for identifier in identifiers:
        if identifier in groups:
            return groups[identifier]
    for identifier in identifiers:
        groups[identifier] = br
    return br


def __yes_no(citation, column):
    return "yes" if citation.get(column) == "yes" else "no"
