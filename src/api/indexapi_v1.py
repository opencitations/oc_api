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

__author__ = "Arcangelo Massari & Ivan Heibi"

from indexapi_common import (
    lower,  # noqa: F401 - used by ramose via getattr
    count_unique_cits,  # noqa: F401 - used by ramose via getattr
    count_groups,  # noqa: F401 - used by ramose via getattr
    oci_search,  # noqa: F401 - used by ramose via getattr
    literal_search,
    unique_citations,
    citation_row,
)


def cited_search(doi):
    return (literal_search(doi, "cited_br"),)


def citing_search(doi):
    return (literal_search(doi, "citing_br"),)


def citations_info(res):
    f_res = [
        ["oci", "citing", "cited", "creation", "timespan", "journal_sc", "author_sc"]
    ]
    for citation in unique_citations(res):
        f_res.append(
            citation_row(
                citation,
                __get_doi(citation["citing_ids"]),
                __get_doi(citation["cited_ids"]),
            )
        )
    return f_res, True


def __get_doi(ids):
    return " ".join(
        id.removeprefix("doi:") for id in ids.split(" __ ") if id.startswith("doi:")
    )
