import json
import os
import sys
import tempfile
from io import StringIO

import pytest

from ramose import APIManager


@pytest.fixture(scope="session")
def api_manager():
    """
    Initialize the API manager once for all tests.
    """
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    original_config = os.path.join(current_dir, "..", "src", "api", "meta_v1.hf")
    
    with open(original_config, 'r', encoding='utf8') as f:
        config_content = f.read()
    
    config_content = config_content.replace(
        '#base https://api.opencitations.net/meta',
        '#base http://127.0.0.1:8891'
    )
    config_content = config_content.replace(
        '#endpoint http://virtuoso-service.default.svc.cluster.local:8890/sparql',
        '#endpoint http://127.0.0.1:8891/sparql'
    )
    config_content = config_content.replace(
        '#addon metaapi',
        '#addon ../src/api/metaapi'
    )
    
    tmp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.hf', delete=False, dir=current_dir)
    tmp_file.write(config_content)
    tmp_file.close()
    tmp_config_file = tmp_file.name
    
    try:
        return APIManager([tmp_config_file])
    finally:
        os.unlink(tmp_config_file)


def execute_operation(api_manager, operation_url):
    """
    Execute an API operation and return the output.
    """
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    op = api_manager.get_op(operation_url)
    if isinstance(op, tuple):
        print(f"Error: {op[1]}")
    else:
        status, result, _ = op.exec(method="get", content_type="application/json")
        print(result)
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout
    return output


def normalize_string(s):
    """
    Normalize Unicode characters in a string.
    """
    return s.replace('‘', "'").replace('’', "'").replace('"', '"')


def normalize_json(json_data):
    """
    Recursively normalize Unicode characters in JSON data and sort lists of objects by ID.
    """
    if isinstance(json_data, dict):
        return {k: normalize_json(v) for k, v in json_data.items()}
    elif isinstance(json_data, list):
        normalized_list = [normalize_json(item) for item in json_data]
        return sorted(normalized_list, key=lambda x: x.get('id', ''))
    elif isinstance(json_data, str):
        return normalize_string(json_data)
    else:
        return json_data


def test_metadata_retrieval(api_manager):
    """
    Test metadata retrieval for a specific DOI.
    """
    output = execute_operation(api_manager, "/v1/metadata/doi:10.1002/(sici)1096-9926(199910)60:4<177::aid-tera1>3.0.co;2-z")
    expected_output = [
        {
            "id": "doi:10.1002/(sici)1096-9926(199910)60:4<177::aid-tera1>3.0.co;2-z omid:br/0601",
            "title": "Response To The Letter Of Hanley Et Al. ([1999] Teratology 59:323-324), Concerning The Article By Roy Et Al. ([1998] Teratology 58:62-68)",
            "author": "Slotkin, Theodore A. [omid:ra/0601]; Andrews, James E. [omid:ra/0602]",
            "pub_date": "1999-10",
            "issue": "4",
            "volume": "60",
            "venue": "Teratology [doi:10.1002/(issn)1096-9926 issn:0040-3709 issn:1096-9926 omid:br/06101018]",
            "type": "journal article",
            "page": "177-178",
            "publisher": "Wiley [crossref:311 omid:ra/0610116001]",
            "editor": ""
        }
    ]
    try:
        output_json = json.loads(output)
    except json.JSONDecodeError:
        assert False, "L'output non è un JSON valido"
    normalized_output = normalize_json(output_json)
    normalized_expected = normalize_json(expected_output)
    assert normalized_output == normalized_expected


def test_metadata_retrieval_editor_inbook(api_manager):
    """
    Test metadata retrieval for a book chapter with editors.
    https://github.com/opencitations/api/issues/16
    """
    output = execute_operation(api_manager, "/v1/metadata/omid:br/061702784433")
    expected_output = [
        {
            "id": "doi:10.1007/978-3-642-30859-8_14 openalex:W1555136325 omid:br/061702784433",
            "title": "Analysing Students' Use Of Recorded Lectures Through Methodological Triangulation",
            "author": "Gorissen, Pierre [omid:ra/061707839728]; Van Bruggen, Jan [omid:ra/061707839729]; Jochems, Wim [omid:ra/061707839730]",
            "pub_date": "2012",
            "issue": "",
            "volume": "",
            "venue": "Advances In Intelligent Systems And Computing [doi:10.1007/978-3-642-30859-8 isbn:9783642308581 isbn:9783642308598 openalex:W2221102889 omid:br/061702785338]",
            "type": "book chapter",
            "page": "145-156",
            "publisher": "Springer Science And Business Media Llc [crossref:297 omid:ra/0610116006]",
            "editor": "Uden, Lorna [omid:ra/062409604521]; Corchado, Juan Manuel [orcid:0000-0002-2829-1829 omid:ra/0619011562087]; De Paz Santana, Juan F. [omid:ra/062409604522]; Prieta, Fernando De La [orcid:0000-0002-8239-5020 omid:ra/0611011366962]"
        }
    ]        

    try:
        output_json = json.loads(output)
    except json.JSONDecodeError:
        assert False, "L'output non è un JSON valido"
    normalized_output = normalize_json(output_json)
    normalized_expected = normalize_json(expected_output)
    assert normalized_output == normalized_expected


def test_author_works_retrieval(api_manager):
    """
    Test retrieval of works by a specific author.
    """
    output = execute_operation(api_manager, "/v1/author/orcid:0000-0002-8420-0696")
    expected_output = [
        {
            "id": "doi:10.5334/johd.178 omid:br/06404693975",
            "title": "The Integration Of The Japan Link Center's Bibliographic Data Into OpenCitations",
            "author": "Moretti, Arianna [orcid:0000-0001-5486-7070 omid:ra/061206532421]; Soricetti, Marta [orcid:0009-0008-1466-7742 omid:ra/064013186641]; Heibi, Ivan [orcid:0000-0001-5366-5194 omid:ra/063011864088]; Massari, Arcangelo [orcid:0000-0002-8420-0696 omid:ra/06250110138]; Peroni, Silvio [orcid:0000-0003-0530-4305 omid:ra/0614010840729]; Rizzetto, Elia [orcid:0009-0003-7161-9310 omid:ra/064013186645]",
            "pub_date": "2024",
            "issue": "",
            "volume": "10",
            "venue": "Journal Of Open Humanities Data [issn:2059-481X openalex:S4210240912 omid:br/06160186133]",
            "type": "journal article",
            "page": "",
            "publisher": "Ubiquity Press, Ltd. [crossref:3285 omid:ra/0610116010]",
            "editor": ""
        },
        {
            "id": "doi:10.1007/s11192-022-04367-w openalex:W3214893238 omid:br/061202127149",
            "title": "Identifying And Correcting Invalid Citations Due To DOI Errors In Crossref Data",
            "author": "Cioffi, Alessia [orcid:0000-0002-9812-4065 omid:ra/061206532419]; Coppini, Sara [orcid:0000-0002-6279-3830 omid:ra/061206532420]; Massari, Arcangelo [orcid:0000-0002-8420-0696 omid:ra/06250110138]; Moretti, Arianna [orcid:0000-0001-5486-7070 omid:ra/061206532421]; Peroni, Silvio [orcid:0000-0003-0530-4305 omid:ra/0614010840729]; Santini, Cristian [orcid:0000-0001-7363-6737 omid:ra/067099715]; Shahidzadeh, Nooshin [orcid:0000-0003-4114-074X omid:ra/06220110984]",
            "pub_date": "2022-06",
            "issue": "6",
            "volume": "127",
            "venue": "Scientometrics [issn:0138-9130 issn:1588-2861 openalex:S148561398 omid:br/0626055628]",
            "type": "journal article",
            "page": "3593-3612",
            "publisher": "Springer Science And Business Media Llc [crossref:297 omid:ra/0610116006]",
            "editor": ""
        },
        {
            "id": "doi:10.32388/x2dx81 openalex:W3153150899 omid:br/062203845802",
            "title": "Review Of: \"Investigating Invalid DOIs In COCI\"",
            "author": "Massari, Arcangelo [orcid:0000-0002-8420-0696 omid:ra/06250110138]",
            "pub_date": "2021-04-19",
            "issue": "",
            "volume": "",
            "venue": "",
            "type": "journal article",
            "page": "",
            "publisher": "Qeios Ltd [crossref:17262 omid:ra/0640115413]",
            "editor": ""
        },
        {
            "id": "doi:10.5281/zenodo.4733920 omid:br/060504628",
            "title": "Classes Of Errors In DOI Names (Data Management Plan)",
            "author": "Boente, Ricarda [orcid:0000-0002-2133-8735 omid:ra/06908359558]; Massari, Arcangelo [orcid:0000-0002-8420-0696 omid:ra/06250110138]; Santini, Cristian [orcid:0000-0001-7363-6737 omid:ra/067099715]; Tural, Deniz [orcid:0000-0002-6391-4198 omid:ra/06908359559]",
            "pub_date": "2021-05-03",
            "issue": "",
            "volume": "",
            "venue": "",
            "type": "",
            "page": "",
            "publisher": "Zenodo [omid:ra/0601747332]",
            "editor": ""
        }
    ]
    try:
        output_json = json.loads(output)
    except json.JSONDecodeError:
        assert False, "L'output non è un JSON valido"
    normalized_output = normalize_json(output_json)
    normalized_expected = normalize_json(expected_output)
    assert normalized_output == normalized_expected


def test_editor_works_retrieval(api_manager):
    """
    Test retrieval of works edited by a specific person.
    """
    output = execute_operation(api_manager, "/v1/editor/orcid:0000-0003-2098-4759")
    expected_output = [
        {
            "id": "doi:10.1007/978-1-4020-9632-7 isbn:9781402096327 isbn:9789048127108 openalex:W4249829199 omid:br/0612058700",
            "title": "Adaptive Environmental Management",
            "author": "",
            "pub_date": "2009",
            "issue": "",
            "volume": "",
            "venue": "",
            "type": "book",
            "page": "",
            "publisher": "Springer Science And Business Media Llc [crossref:297 omid:ra/0610116006]",
            "editor": "Allan, Catherine [orcid:0000-0003-2098-4759 omid:ra/069012996]; Stankey, George H. [omid:ra/061808486861]"
        }
    ]

    try:
        output_json = json.loads(output)
    except json.JSONDecodeError:
        assert False, "L'output non è un JSON valido"
    normalized_output = normalize_json(output_json)
    normalized_expected = normalize_json(expected_output)        
    assert normalized_output == normalized_expected


def test_venue_without_external_id(api_manager):
    """
    Test venue handling when external ID is missing.
    https://github.com/opencitations/api/issues/15
    """
    output = execute_operation(api_manager, "/v1/metadata/omid:br/061903571196")
    expected_output = [
        {
            "id": "doi:10.36106/gjra/9300981 openalex:W4306682982 omid:br/061903571196",
            "title": "Lung Cavitation: An Unwanted Complication Of Covid-19 Lung Disease",
            "author": "A Dosi, Ravi [omid:ra/061909585847]; Shivhare, Shailendra [omid:ra/061909585848]; Agrawal, Ankur [omid:ra/061909585849]; Jaiswal, Neha [omid:ra/061909585850]; Patidar, Ravindra [omid:ra/061909585851]",
            "pub_date": "2022-09-15",
            "issue": "",
            "volume": "",
            "venue": "Global Journal For Research Analysis [omid:br/061903571793]",
            "type": "journal article",
            "page": "31-33",
            "publisher": "World Wide Journals [crossref:21849 omid:ra/0640115418]",
            "editor": ""
        }
    ]
    try:
        output_json = json.loads(output)
    except json.JSONDecodeError:
        assert False, "The output is not valid JSON"
    normalized_output = normalize_json(output_json)
    normalized_expected = normalize_json(expected_output)
    assert normalized_output == normalized_expected
    assert "omid:" in normalized_output[0]["venue"], "The venue field should contain an OMID"


def test_metadata_retrieval_with_different_ids(api_manager):
    """
    Test metadata retrieval using different types of identifiers.
    https://github.com/opencitations/api/issues/14
    """
    output_omid = execute_operation(api_manager, "/v1/metadata/omid:br/06603870331")
    json_omid = json.loads(output_omid)
    
    output_isbn = execute_operation(api_manager, "/v1/metadata/isbn:9789264960114")
    json_isbn = json.loads(output_isbn)
    
    output_doi = execute_operation(api_manager, "/v1/metadata/doi:10.1787/b0e499cf-en")
    json_doi = json.loads(output_doi)
    
    normalized_omid = normalize_json(json_omid)
    normalized_isbn = normalize_json(json_isbn)
    normalized_doi = normalize_json(json_doi)
    
    assert len(normalized_omid) == 1
    assert len(normalized_isbn) == 1
    assert len(normalized_doi) == 1
    
    expected_ids = [
        'doi:10.1787/b0e499cf-en',
        'isbn:9789264597587',
        'isbn:9789264759596',
        'isbn:9789264799318',
        'isbn:9789264960114',
        'openalex:W4221051054',
        'omid:br/06603870331'
    ]
    
    omid_ids = normalized_omid[0]['id'].split()
    for expected_id in expected_ids:
        assert expected_id in omid_ids
    
    isbn_ids = normalized_isbn[0]['id'].split()
    for expected_id in expected_ids:
        assert expected_id in isbn_ids

    doi_ids = normalized_doi[0]['id'].split()
    for expected_id in expected_ids:
        assert expected_id in doi_ids
    
    assert len(omid_ids) == len(expected_ids)
    assert len(isbn_ids) == len(expected_ids)
    assert len(doi_ids) == len(expected_ids)
    
    fields_to_check = ['title', 'author', 'pub_date', 'venue', 'publisher', 'type', 'issue', 'volume', 'page', 'editor']
    for field in fields_to_check:
        assert normalized_omid[0][field] == normalized_isbn[0][field]
        assert normalized_omid[0][field] == normalized_doi[0][field]

    assert normalized_omid[0]['title'] == "OECD Economic Surveys: China 2022"
    assert normalized_omid[0]['author'] == "Oecd [omid:ra/066010636485]"
    assert normalized_omid[0]['pub_date'] == "2022-03-18"
    assert normalized_omid[0]['venue'] == "OECD Economic Surveys: China [issn:2072-5027 openalex:S4210223649 omid:br/061402215286]"
    assert normalized_omid[0]['type'] == "book"
    assert normalized_omid[0]['publisher'] == "Organisation For Economic Co-Operation And Development (Oecd) [crossref:1963 omid:ra/0610116167]"


def test_author_order_in_metadata(api_manager):
    """
    Test that author order is preserved in metadata.
    https://github.com/opencitations/api/issues/13
    """
    output = execute_operation(api_manager, "/v1/metadata/omid:br/0680773548")
    expected_output = [
        {
            "author": "Bilgin, Hülya [orcid:0000-0001-6639-5533 omid:ra/0622032021]; Bozkurt, Merlin [omid:ra/06802276621]; Yilmazlar, Selçuk [omid:ra/06802276622]; Korfali, Gülsen [omid:ra/06802276623]",
            "issue": "3",
            "editor": "",
            "pub_date": "2006-05",
            "title": "Sudden Asystole Without Any Alerting Signs During Cerebellopontine Angle Surgery",
            "volume": "18",
            "page": "243-244",
            "id": "doi:10.1016/j.jclinane.2005.12.014 openalex:W2127410217 pmid:16731339 omid:br/0680773548",
            "publisher": "Elsevier Bv [crossref:78 omid:ra/0610116009]",
            "type": "journal article",
            "venue": "Journal Of Clinical Anesthesia [issn:0952-8180 openalex:S155967237 omid:br/0621013884]"
        }
    ]

    try:
        output_json = json.loads(output)
    except json.JSONDecodeError:
        assert False, "The output is not valid JSON"

    normalized_output = normalize_json(output_json)
    normalized_expected = normalize_json(expected_output)

    assert normalized_output == normalized_expected

    authors = normalized_output[0]['author'].split('; ')
    expected_author_order = [
        "Bilgin, Hülya [orcid:0000-0001-6639-5533 omid:ra/0622032021]",
        "Bozkurt, Merlin [omid:ra/06802276621]",
        "Yilmazlar, Selçuk [omid:ra/06802276622]",
        "Korfali, Gülsen [omid:ra/06802276623]"
    ]
    assert authors == expected_author_order


def test_author_works_retrieval_with_omid(api_manager):
    """
    Test retrieval of works by a specific author using OMID identifier.
    This tests the OMID scheme handling in generate_ra_search function.
    """
    output = execute_operation(api_manager, "/v1/author/omid:ra/06250110138")
    expected_output = [
        {
            "id": "doi:10.5334/johd.178 omid:br/06404693975",
            "title": "The Integration Of The Japan Link Center's Bibliographic Data Into OpenCitations",
            "author": "Moretti, Arianna [orcid:0000-0001-5486-7070 omid:ra/061206532421]; Soricetti, Marta [orcid:0009-0008-1466-7742 omid:ra/064013186641]; Heibi, Ivan [orcid:0000-0001-5366-5194 omid:ra/063011864088]; Massari, Arcangelo [orcid:0000-0002-8420-0696 omid:ra/06250110138]; Peroni, Silvio [orcid:0000-0003-0530-4305 omid:ra/0614010840729]; Rizzetto, Elia [orcid:0009-0003-7161-9310 omid:ra/064013186645]",
            "pub_date": "2024",
            "issue": "",
            "volume": "10",
            "venue": "Journal Of Open Humanities Data [issn:2059-481X openalex:S4210240912 omid:br/06160186133]",
            "type": "journal article",
            "page": "",
            "publisher": "Ubiquity Press, Ltd. [crossref:3285 omid:ra/0610116010]",
            "editor": ""
        },
        {
            "id": "doi:10.1007/s11192-022-04367-w openalex:W3214893238 omid:br/061202127149",
            "title": "Identifying And Correcting Invalid Citations Due To DOI Errors In Crossref Data",
            "author": "Cioffi, Alessia [orcid:0000-0002-9812-4065 omid:ra/061206532419]; Coppini, Sara [orcid:0000-0002-6279-3830 omid:ra/061206532420]; Massari, Arcangelo [orcid:0000-0002-8420-0696 omid:ra/06250110138]; Moretti, Arianna [orcid:0000-0001-5486-7070 omid:ra/061206532421]; Peroni, Silvio [orcid:0000-0003-0530-4305 omid:ra/0614010840729]; Santini, Cristian [orcid:0000-0001-7363-6737 omid:ra/067099715]; Shahidzadeh, Nooshin [orcid:0000-0003-4114-074X omid:ra/06220110984]",
            "pub_date": "2022-06",
            "issue": "6",
            "volume": "127",
            "venue": "Scientometrics [issn:0138-9130 issn:1588-2861 openalex:S148561398 omid:br/0626055628]",
            "type": "journal article",
            "page": "3593-3612",
            "publisher": "Springer Science And Business Media Llc [crossref:297 omid:ra/0610116006]",
            "editor": ""
        },
        {
            "id": "doi:10.32388/x2dx81 openalex:W3153150899 omid:br/062203845802",
            "title": "Review Of: \"Investigating Invalid DOIs In COCI\"",
            "author": "Massari, Arcangelo [orcid:0000-0002-8420-0696 omid:ra/06250110138]",
            "pub_date": "2021-04-19",
            "issue": "",
            "volume": "",
            "venue": "",
            "type": "journal article",
            "page": "",
            "publisher": "Qeios Ltd [crossref:17262 omid:ra/0640115413]",
            "editor": ""
        },
        {
            "id": "doi:10.5281/zenodo.4733920 omid:br/060504628",
            "title": "Classes Of Errors In DOI Names (Data Management Plan)",
            "author": "Boente, Ricarda [orcid:0000-0002-2133-8735 omid:ra/06908359558]; Massari, Arcangelo [orcid:0000-0002-8420-0696 omid:ra/06250110138]; Santini, Cristian [orcid:0000-0001-7363-6737 omid:ra/067099715]; Tural, Deniz [orcid:0000-0002-6391-4198 omid:ra/06908359559]",
            "pub_date": "2021-05-03",
            "issue": "",
            "volume": "",
            "venue": "",
            "type": "",
            "page": "",
            "publisher": "Zenodo [omid:ra/0601747332]",
            "editor": ""
        }
    ]
    try:
        output_json = json.loads(output)
    except json.JSONDecodeError:
        assert False, "The output is not valid JSON"
    normalized_output = normalize_json(output_json)
    normalized_expected = normalize_json(expected_output)
    assert normalized_output == normalized_expected


def test_editor_works_retrieval_with_omid(api_manager):
    """
    Test retrieval of works edited by a specific person using OMID identifier.
    This tests the OMID scheme handling in generate_ra_search function for editors.
    """
    output = execute_operation(api_manager, "/v1/editor/omid:ra/069012996")
    expected_output = [
        {
            "id": "doi:10.1007/978-1-4020-9632-7 isbn:9781402096327 isbn:9789048127108 openalex:W4249829199 omid:br/0612058700",
            "title": "Adaptive Environmental Management",
            "author": "",
            "pub_date": "2009",
            "issue": "",
            "volume": "",
            "venue": "",
            "type": "book",
            "page": "",
            "publisher": "Springer Science And Business Media Llc [crossref:297 omid:ra/0610116006]",
            "editor": "Allan, Catherine [orcid:0000-0003-2098-4759 omid:ra/069012996]; Stankey, George H. [omid:ra/061808486861]"
        }
    ]

    try:
        output_json = json.loads(output)
    except json.JSONDecodeError:
        assert False, "The output is not valid JSON"
    normalized_output = normalize_json(output_json)
    normalized_expected = normalize_json(expected_output)        
    assert normalized_output == normalized_expected


def test_author_works_retrieval_without_scheme_prefix(api_manager):
    """
    Test retrieval of works by a specific author using identifier without scheme prefix.
    This tests the default ORCID scheme fallback in generate_ra_search function.
    """
    output = execute_operation(api_manager, "/v1/author/0000-0002-8420-0696")
    expected_output = [
        {
            "id": "doi:10.5334/johd.178 omid:br/06404693975",
            "title": "The Integration Of The Japan Link Center's Bibliographic Data Into OpenCitations",
            "author": "Moretti, Arianna [orcid:0000-0001-5486-7070 omid:ra/061206532421]; Soricetti, Marta [orcid:0009-0008-1466-7742 omid:ra/064013186641]; Heibi, Ivan [orcid:0000-0001-5366-5194 omid:ra/063011864088]; Massari, Arcangelo [orcid:0000-0002-8420-0696 omid:ra/06250110138]; Peroni, Silvio [orcid:0000-0003-0530-4305 omid:ra/0614010840729]; Rizzetto, Elia [orcid:0009-0003-7161-9310 omid:ra/064013186645]",
            "pub_date": "2024",
            "issue": "",
            "volume": "10",
            "venue": "Journal Of Open Humanities Data [issn:2059-481X openalex:S4210240912 omid:br/06160186133]",
            "type": "journal article",
            "page": "",
            "publisher": "Ubiquity Press, Ltd. [crossref:3285 omid:ra/0610116010]",
            "editor": ""
        },
        {
            "id": "doi:10.1007/s11192-022-04367-w openalex:W3214893238 omid:br/061202127149",
            "title": "Identifying And Correcting Invalid Citations Due To DOI Errors In Crossref Data",
            "author": "Cioffi, Alessia [orcid:0000-0002-9812-4065 omid:ra/061206532419]; Coppini, Sara [orcid:0000-0002-6279-3830 omid:ra/061206532420]; Massari, Arcangelo [orcid:0000-0002-8420-0696 omid:ra/06250110138]; Moretti, Arianna [orcid:0000-0001-5486-7070 omid:ra/061206532421]; Peroni, Silvio [orcid:0000-0003-0530-4305 omid:ra/0614010840729]; Santini, Cristian [orcid:0000-0001-7363-6737 omid:ra/067099715]; Shahidzadeh, Nooshin [orcid:0000-0003-4114-074X omid:ra/06220110984]",
            "pub_date": "2022-06",
            "issue": "6",
            "volume": "127",
            "venue": "Scientometrics [issn:0138-9130 issn:1588-2861 openalex:S148561398 omid:br/0626055628]",
            "type": "journal article",
            "page": "3593-3612",
            "publisher": "Springer Science And Business Media Llc [crossref:297 omid:ra/0610116006]",
            "editor": ""
        },
        {
            "id": "doi:10.32388/x2dx81 openalex:W3153150899 omid:br/062203845802",
            "title": "Review Of: \"Investigating Invalid DOIs In COCI\"",
            "author": "Massari, Arcangelo [orcid:0000-0002-8420-0696 omid:ra/06250110138]",
            "pub_date": "2021-04-19",
            "issue": "",
            "volume": "",
            "venue": "",
            "type": "journal article",
            "page": "",
            "publisher": "Qeios Ltd [crossref:17262 omid:ra/0640115413]",
            "editor": ""
        },
        {
            "id": "doi:10.5281/zenodo.4733920 omid:br/060504628",
            "title": "Classes Of Errors In DOI Names (Data Management Plan)",
            "author": "Boente, Ricarda [orcid:0000-0002-2133-8735 omid:ra/06908359558]; Massari, Arcangelo [orcid:0000-0002-8420-0696 omid:ra/06250110138]; Santini, Cristian [orcid:0000-0001-7363-6737 omid:ra/067099715]; Tural, Deniz [orcid:0000-0002-6391-4198 omid:ra/06908359559]",
            "pub_date": "2021-05-03",
            "issue": "",
            "volume": "",
            "venue": "",
            "type": "",
            "page": "",
            "publisher": "Zenodo [omid:ra/0601747332]",
            "editor": ""
        }
    ]
    try:
        output_json = json.loads(output)
    except json.JSONDecodeError:
        assert False, "The output is not valid JSON"
    normalized_output = normalize_json(output_json)
    normalized_expected = normalize_json(expected_output)
    assert normalized_output == normalized_expected


def test_editor_works_retrieval_without_scheme_prefix(api_manager):
    """
    Test retrieval of works edited by a specific person using identifier without scheme prefix.
    This tests the default ORCID scheme fallback in generate_ra_search function for editors.
    """
    output = execute_operation(api_manager, "/v1/editor/0000-0003-2098-4759")
    expected_output = [
        {
            "id": "doi:10.1007/978-1-4020-9632-7 isbn:9781402096327 isbn:9789048127108 openalex:W4249829199 omid:br/0612058700",
            "title": "Adaptive Environmental Management",
            "author": "",
            "pub_date": "2009",
            "issue": "",
            "volume": "",
            "venue": "",
            "type": "book",
            "page": "",
            "publisher": "Springer Science And Business Media Llc [crossref:297 omid:ra/0610116006]",
            "editor": "Allan, Catherine [orcid:0000-0003-2098-4759 omid:ra/069012996]; Stankey, George H. [omid:ra/061808486861]"
        }
    ]

    try:
        output_json = json.loads(output)
    except json.JSONDecodeError:
        assert False, "The output is not valid JSON"
    normalized_output = normalize_json(output_json)
    normalized_expected = normalize_json(expected_output)        
    assert normalized_output == normalized_expected