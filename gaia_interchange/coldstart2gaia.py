"""
Converts ColdStart++ knowledge bases to the GAIA interchange format.

See main method for a description of the parameters expected.
"""
import logging
import sys
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, MutableMapping, Optional, Union
from uuid import uuid4

from attr import attrs
from rdflib import Graph, URIRef, BNode, Literal, RDF
from rdflib.namespace import SKOS
from rdflib.term import Identifier

from flexnlp.parameters import YAMLParametersLoader, Parameters
from flexnlp.utils import logging_utils
from flexnlp.utils.attrutils import attrib_instance_of
from flexnlp.utils.io_utils import CharSource
from flexnlp.utils.preconditions import check_arg, check_not_none, check_isinstance
from flexnlp_sandbox.formats.tac.coldstart import ColdStartKB, ColdStartKBLoader, TypeAssertion, \
    Node, EntityNode, EventNode, StringNode, EntityMentionAssertion, CANONICAL_MENTION, LinkAssertion, \
    EventMentionAssertion, RelationAssertion, Provenance 
from gaia_interchange.aida_rdf_ontologies import AIDA_PROGRAM_ONTOLOGY, AIDA, AIDA_PROGRAM_ONTOLOGY_LUT

_log = logging.getLogger(__name__)


# Node generators


class NodeGenerator(metaclass=ABCMeta):
    """
    A strategy for generating RDF graph nodes.
    """

    @abstractmethod
    def next_node(self) -> Union[URIRef, BNode]:
        raise NotImplementedError()


class BlankNodeGenerator(NodeGenerator):
    """
    A node generation strategy which always returns blank nodes.

    This is useful for testing because we don't need to coordinate entity, event, etc.
    URIs in order to test isomorphism between graphs.  At runtime, it avoids
    generating URIs for nodes which only need to be referred to once as part of a
    large structure (e.g. confidences)
    """

    def next_node(self) -> Union[URIRef, BNode]:
        return BNode()


@attrs(frozen=True)
class UUIDNodeGenerator(NodeGenerator):
    """
    A node generation strategy which uses UUIDs appended to a base URI.

    We don't use this currently because UUID generation is very slow in Python.
    """
    base_uri: str = attrib_instance_of(str)

    def next_node(self) -> Union[URIRef, BNode]:
        return URIRef(self.base_uri + '/' + str(uuid4()))


class SequentialIDNodeGenerator(NodeGenerator):
    """
    A node generation strategy which uses sequential indices appended to a base URI.
    """

    def __init__(self, base_uri: str) -> None:
        self.next_id = 0
        self.base_uri = base_uri

    def next_node(self) -> Union[URIRef, BNode]:
        ret = URIRef(self.base_uri + '/' + str(self.next_id))
        self.next_id += 1
        return ret


@attrs(frozen=True)
class ColdStartToGaiaConverter:
    """
    Concert a ColdStart KB to an RDFLib graph in the proposed AIDA interchange format.
    """
    entity_node_generator: NodeGenerator = attrib_instance_of(NodeGenerator,
                                                              default=BlankNodeGenerator())
    event_node_generator: NodeGenerator = attrib_instance_of(NodeGenerator,
                                                             default=BlankNodeGenerator())
    string_node_generator: NodeGenerator = attrib_instance_of(NodeGenerator,
                                                              default=BlankNodeGenerator())
    assertion_node_generator: NodeGenerator = attrib_instance_of(NodeGenerator,
                                                                 default=BlankNodeGenerator())

    @staticmethod
    def from_parameters(params: Parameters) -> 'ColdStartToGaiaConverter':
        """
        Configure conversion process from parameters

        If 'base_uri' is present, then assertions, entities, and events will have assigned URIs
        instead of being blank nodes.
        """
        if 'base_uri' in params:
            base_uri = params.string('base_uri')
            return ColdStartToGaiaConverter(
                entity_node_generator=SequentialIDNodeGenerator(base_uri + "/entities"),
                event_node_generator=SequentialIDNodeGenerator(base_uri + "/events"),
                assertion_node_generator=SequentialIDNodeGenerator(base_uri + "/assertions"))
        else:
            return ColdStartToGaiaConverter()

    def convert_coldstart_to_gaia(self, system_uri: str, cs_kb: ColdStartKB) -> Graph:
        # stores a mapping of ColdStart objects to their URIs in the interchange format
        object_to_uri: Dict[Any, Union[BNode, URIRef]] = dict()

        # this is the URI for the generating system
        system_node = URIRef(system_uri)

        # utility methods. We define them here due to Python's unfortunate lack of
        # proper inner classes

        # mark a triple as having been generated by this system
        def associate_with_system(identifier: Identifier) -> None:
            check_isinstance(identifier, Identifier)
            g.add((identifier, AIDA.system, system_node))

        # mark an assertion with confidence from this system
        def mark_single_assertion_confidence(reified_assertion, confidence: float) -> None:
            confidence_blank_node = BNode()
            g.add((reified_assertion, AIDA.confidence, confidence_blank_node))
            g.add((confidence_blank_node, AIDA.confidenceValue, Literal(confidence)))
            g.add((confidence_blank_node, AIDA.system, system_node))

        # converts a ColdStart object to an RDF identifier (node in the RDF graph)
        # if this ColdStart node has been previously converted, we return the same RDF identifier
        def to_identifier(node: Node) -> Identifier:
            check_arg(isinstance(node, EntityNode) 
                      or isinstance(node, EventNode) 
                      or isinstance(node, StringNode))
            if node not in object_to_uri:
                if isinstance(node, EntityNode):
                    uri = self.entity_node_generator.next_node()
                elif isinstance(node, EventNode):
                    uri = self.event_node_generator.next_node()
                elif isinstance(node, StringNode):
                    uri = self.string_node_generator.next_node()
                else:
                    raise NotImplementedError("Cannot make a URI for {!s}".format(node))
                object_to_uri[node] = uri
            return object_to_uri[node]

        # convert a ColdStart justification to a RDF identifier
        def register_justifications(g: Graph,
                                    entity: Union[BNode, URIRef], 
                                    provenance: Provenance,
                                    string: Optional[str]=None,
                                    confidence: Optional[float]=None) -> None:
            for justification in provenance.predicate_justifications:
                justification_node = BNode()
                if confidence:
                    mark_single_assertion_confidence(justification_node, confidence)
                associate_with_system(justification_node)

                g.add((justification_node, RDF.type, AIDA.TextProvenance))
                g.add((justification_node, AIDA.source, Literal(provenance.doc_id)))
                g.add((justification_node, AIDA.startOffset, Literal(justification.start)))
                # +1 because Span end is exclusive but interchange format is inclusive
                g.add((justification_node, AIDA.endOffsetInclusive, Literal(justification.end + 1)))
                g.add((entity, AIDA.justifiedBy, justification_node))

                # put mention string as the prefLabel of the justification
                if string:
                    g.add((justification_node, SKOS.prefLabel, Literal(string)))

        # converts a ColdStart ontology type to a corresponding RDF identifier
        # TODO: This is temporarily hardcoded but will eventually need to be configurable
        # @xujun: you will need to extend this hardcoding
        def to_ontology_type(ontology_type: str) -> URIRef:
            if ":" in ontology_type:
                raise NotImplementedError("Not implemented yet")

            if ontology_type == "PER":
                return AIDA_PROGRAM_ONTOLOGY.Person
            elif ontology_type == "ORG":
                return AIDA_PROGRAM_ONTOLOGY.Organization
            elif ontology_type == "LOC":
                return AIDA_PROGRAM_ONTOLOGY.Location
            elif ontology_type == "FAC":
                return AIDA_PROGRAM_ONTOLOGY.Facility
            elif ontology_type == "GPE":
                return AIDA_PROGRAM_ONTOLOGY.GeopoliticalEntity
            elif ontology_type == "STRING" or ontology_type == "String":
                return AIDA_PROGRAM_ONTOLOGY.String
            elif ontology_type in AIDA_PROGRAM_ONTOLOGY_LUT: 
                return AIDA_PROGRAM_ONTOLOGY_LUT[ontology_type]
            else:
                raise NotImplementedError("Cannot interpret ontology type " + ontology_type)

        # below are the functions for translating each individual type of ColdStart assertion
        # into the appropriate RDF structures
        # each will return a boolean specifying whether or not the conversion was successful

        # translate ColdStart type assertions
        def translate_type(g: Graph, cs_assertion: TypeAssertion, confidence: Optional[float]) \
                -> bool:
            check_arg(confidence is None, "Type assertions should not have confidences in "
                                          "ColdStart")
            if isinstance(cs_assertion.sbj, EntityNode):
                rdf_assertion = self.assertion_node_generator.next_node()
                entity = to_identifier(cs_assertion.sbj)
                ontology_type = to_ontology_type(cs_assertion.obj)
                g.add((rdf_assertion, RDF.type, RDF.Statement))
                g.add((rdf_assertion, RDF.subject, entity))
                g.add((rdf_assertion, RDF.predicate, RDF.type))
                g.add((rdf_assertion, RDF.object, ontology_type))
                associate_with_system(rdf_assertion)
                return True
            else:
                # TODO: handle events, etc.
                return False

        # translate ColdStart relations:
        def translate_relation(g: Graph, cs_assertion: RelationAssertion,
                               confidence: Optional[float]) -> bool:
            check_not_none(confidence, "Relations must have confidences")

            if isinstance(cs_assertion.sbj, EntityNode):
                sbj = to_identifier(cs_assertion.sbj)
                obj = to_identifier(cs_assertion.obj)
                rdf_assertion = self.assertion_node_generator.next_node()
                g.add((rdf_assertion, RDF.type, to_ontology_type(cs_assertion.relation)))
                g.add((rdf_assertion, RDF.subject, sbj))
                g.add((rdf_assertion, RDF.object, obj))

                if confidence is not None:
                    confidence_node = BNode()
                    g.add((rdf_assertion, AIDA.confidence, confidence_node))
                    g.add((confidence_node, AIDA.confidenceValue, Literal(confidence)))

                register_justifications(g, rdf_assertion, cs_assertion.justifications)

            return True 

        def translate_event_argument(g: Graph, cs_assertion: EventMentionAssertion,
                                     confidence: Optional[float]) -> bool:
            check_not_none(confidence, "Relations must have confidences")

            if isinstance(cs_assertion.sbj, EventNode):
                sbj = to_identifier(cs_assertion.sbj)
                obj = to_identifier(cs_assertion.argument)
                rdf_assertion = self.assertion_node_generator.next_node()
                g.add((rdf_assertion, RDF.type, to_ontology_type(cs_assertion.argument_role)))
                g.add((rdf_assertion, RDF.subject, sbj))
                g.add((rdf_assertion, RDF.object, obj))

                if confidence is not None:
                    confidence_node = BNode()
                    g.add((rdf_assertion, AIDA.confidence, confidence_node))
                    g.add((confidence_node, AIDA.confidenceValue, Literal(confidence)))

                register_justifications(g, rdf_assertion, cs_assertion.justifications)

            return True

        # translate ColdStart entity mentions
        def translate_entity_mention(g: Graph, cs_assertion: EntityMentionAssertion,
                                     confidence: Optional[float]) -> bool:
            check_not_none(confidence, "Entity mentions must have confidences")
            entity_uri = to_identifier(assertion.sbj)
            associate_with_system(entity_uri)
            # if this is a canonical mention, then we need to make a skos:preferredLabel triple
            if cs_assertion.type == CANONICAL_MENTION:
                # TODO: because skos:preferredLabel isn't reified we can't attach info
                # on the generating system
                g.add((entity_uri, SKOS.prefLabel, Literal(cs_assertion.obj)))

            register_justifications(g, entity_uri, cs_assertion.justifications,
                                    cs_assertion.obj, confidence)

            # TODO: handle translation of value-typed mentions - #7
            return True

        # translate ColdStart link assertions
        def translate_link(g: Graph, cs_assertion: LinkAssertion,
                           confidence: Optional[float]) -> bool:
            entity_uri = to_identifier(cs_assertion.sbj)
            link_assertion = BNode()
            g.add((entity_uri, AIDA.link, link_assertion))
            # how do we want to handle links to external KBs? currently we just store
            # them as strings
            g.add((link_assertion, AIDA.linkTarget, Literal(cs_assertion.global_id)))
            if confidence is not None:
                confidence_node = BNode()
                g.add((link_assertion, AIDA.confidence, confidence_node))
                g.add((confidence_node, AIDA.confidenceValue, Literal(confidence)))

            return True

        # map each ColdStart assertion we know how to translate to its translation function
        assertions_to_translator = {TypeAssertion: translate_type,
                                    EntityMentionAssertion: translate_entity_mention,
                                    LinkAssertion: translate_link,
                                    RelationAssertion: translate_relation}

        # track which assertions we could not translate for later logging
        untranslatable_assertions: MutableMapping[str, int] = defaultdict(int)

        # this is what will be serialized as our final output
        g = Graph()

        for assertion in cs_kb.all_assertions:
            # note not all ColdStart assertions have confidences
            confidence = cs_kb.assertions_to_confidences.get(assertion, None)
            assertion_translator = assertions_to_translator.get(assertion.__class__, None)
            if not (assertion_translator and assertion_translator(g, assertion, confidence)):
                untranslatable_assertions[str(assertion.__class__)] += 1

        if untranslatable_assertions:
            _log.warning("The following ColdStart assertions could not be translated: {!s}".format(
                untranslatable_assertions))

        # binding these namespaces makes the output more human readable
        g.namespace_manager.bind('aida', AIDA)
        g.namespace_manager.bind('aidaProgramOntology', AIDA_PROGRAM_ONTOLOGY)
        g.namespace_manager.bind('skos', SKOS)

        return g


def main(params: Parameters) -> None:
    """
    A single YAML parameter file is expected as input.
    """
    logging_utils.configure_logging_from(params)
    # Coldstart KB is assumed to be gzip compressed
    coldstart_kb_file = params.existing_file('input_coldstart_gz_file')
    output_interchange_file = params.creatable_file('output_interchange_file')
    # the URI to be used to identify the system which generated this ColdStart KB
    system_uri = params.string('system_uri')
    converter = ColdStartToGaiaConverter.from_parameters(params)

    _log.info("Loading Coldstart KB from {!s}".format(coldstart_kb_file))
    coldstart_kb = ColdStartKBLoader().load(
        CharSource.from_gzipped_file(coldstart_kb_file, 'utf-8'))
    _log.info("Converting ColdStart KB to RDF graph")
    converted_graph = converter.convert_coldstart_to_gaia(system_uri, coldstart_kb)
    _log.info("Serializing RDF graph in Turtle format to {!s}".format(output_interchange_file))
    with open(output_interchange_file, 'wb') as out:
        converted_graph.serialize(destination=out, format='turtle')


if __name__ == '__main__':
    if len(sys.argv) == 2:
        main(YAMLParametersLoader().load(Path(sys.argv[1])))
