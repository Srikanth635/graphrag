"""Optional SHACL assessment of asserted triples; never rewrites source claims."""
from __future__ import annotations
from rdflib import Graph

def check_shacl(data_graph: Graph, shapes_graph: Graph, *, ontology_graph: Graph | None = None):
    """Evaluate explicitly supplied SHACL shapes; do not fabricate constraints from OWL."""
    try:
        from pyshacl import validate
    except ImportError as exc:
        raise RuntimeError('SHACL checks require optional dependency: pip install pyshacl') from exc
    if not isinstance(data_graph, Graph) or not isinstance(shapes_graph, Graph):
        raise TypeError('Expected rdflib Graph inputs')
    conforms, results_graph, results_text = validate(
        data_graph=data_graph, shacl_graph=shapes_graph,
        ont_graph=ontology_graph, inference='none',
        do_owl_imports=False, advanced=False,
        allow_infos=True, allow_warnings=True)
    return {'conforms': bool(conforms), 'report': str(results_text),
            'report_graph_turtle': results_graph.serialize(format='turtle'),
            'scope': 'explicit_SHACL_shapes_not_OWL_DL'}
