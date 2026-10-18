"""Optional SHACL integration remains explicit without installed dependency."""
import importlib.util
import pytest
from rdflib import Graph
from ontology_integration.shacl_review import check_shacl

def test_optional_shacl_dependency():
    data=Graph().parse(data='<urn:x> <urn:p> <urn:y> .',format='turtle')
    shapes=Graph().parse(data='''@prefix sh: <http://www.w3.org/ns/shacl#> .
        <urn:s> a sh:NodeShape ; sh:targetNode <urn:x> ;
        sh:property [ sh:path <urn:p> ; sh:minCount 2 ] .''',format='turtle')
    if importlib.util.find_spec('pyshacl') is None:
        with pytest.raises(RuntimeError,match='pip install pyshacl'):
            check_shacl(data,shapes)
    else:
        result=check_shacl(data,shapes)
        assert not result['conforms']
        assert 'Violation' in result['report']
