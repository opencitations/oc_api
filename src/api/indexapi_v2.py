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

__author__ = "Arcangelo Massari & Ivan Heibi"

from indexapi_common import (
    lower,  # noqa: F401 - used by ramose via getattr
    count_unique_cits,  # noqa: F401 - used by ramose via getattr
    count_groups,  # noqa: F401 - used by ramose via getattr
    oci_search,  # noqa: F401 - used by ramose via getattr
    literal_search,
    unique_citations,
    citation_row,
    get_id_val,
)


def cited_search(s):
    return (__br_search(s, "cited_br"),)


def citing_search(s):
    return (__br_search(s, "citing_br"),)


def issn_value(s):
    return (s.removeprefix("issn:"),)


def citations_info(res):
    f_res = [
        ["oci", "citing", "cited", "creation", "timespan", "journal_sc", "author_sc"]
    ]
    for citation in unique_citations(res):
        f_res.append(
            citation_row(
                citation,
                __get_all_pids(citation["citing_br"], citation["citing_ids"]),
                __get_all_pids(citation["cited_br"], citation["cited_ids"]),
            )
        )
    return f_res, True


def venue_count(res):
    header = res[0]
    count = res[1][header.index("count")][1] if len(res) > 1 else "0"
    return [["count"], [count]], True


def __br_search(s, variable):
    scheme, value = s.split(":", 1)
    if scheme == "omid":
        return f"VALUES ?{variable} {{ <https://w3id.org/oc/meta/{value}> }}"
    if scheme == "issn":
        return (
            f'?resolved_identifier literal:hasLiteralValue "{value}" . '
            "?resolved_venue datacite:hasIdentifier ?resolved_identifier . "
            f"?{variable} frbr:partOf+ ?resolved_venue ; a fabio:JournalArticle ."
        )
    return literal_search(value, variable)


def __get_all_pids(br, ids):
    return " ".join(["omid:br/" + get_id_val(br), *ids.split(" __ ")])
