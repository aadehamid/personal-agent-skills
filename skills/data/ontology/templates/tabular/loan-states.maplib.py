"""The loan-state code list from loan-states.csv, as a maplib template (references/promotion.md,
"From a spreadsheet to triples"). The same rows and triples as loan-states.rml.ttl. Morph-KGC is the
engine to use for a spreadsheet; this template stays for comparison and to test the maplib route.

maplib maps each row into a staging graph under raw: predicates, then one SPARQL CONSTRUCT
writes the governed triples, adding the language tags with STRLANG: maplib 0.20.26 documents
no column type for a language-tagged literal.
"""
import os

import polars as pl
from maplib import IRI, Model, Parameter, RDFType, Template, Triple, Variable

LIB = "https://id.example.org/library/"
RAW = "https://id.example.org/library/raw#"
STAGING = "urn:x-staging:loan-states"
COLUMNS = ["notation", "label", "definition", "source"]


def build(folder):
    rows = pl.read_csv(os.path.join(folder, "loan-states.csv"), infer_schema=False)
    rows = rows.with_columns((pl.lit(LIB) + pl.col("slug")).alias("iri")).select(["iri"] + COLUMNS)
    var = {name: Variable(name) for name in ["iri"] + COLUMNS}
    row = Template(IRI(LIB + "template/LoanStateRow"),
                   [Parameter(var["iri"], rdf_type=RDFType.IRI)] + [Parameter(var[c]) for c in COLUMNS],
                   [Triple(var["iri"], IRI(RAW + c), var[c]) for c in COLUMNS])
    model = Model()
    model.map(row, rows, graph=STAGING)
    model.insert("""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX lib: <https://id.example.org/library/>
        PREFIX raw: <https://id.example.org/library/raw#>
        CONSTRUCT { ?c a skos:Concept ; skos:inScheme lib:loan-state ; skos:topConceptOf lib:loan-state ;
                      skos:notation ?n ; skos:prefLabel ?l ; skos:definition ?d ; dcterms:source ?s .
                    lib:loan-state a skos:ConceptScheme ; skos:hasTopConcept ?c ;
                      skos:prefLabel "Loan state"@en ;
                      skos:definition "The states a loan passes through; a loan is in exactly one at a time."@en }
        WHERE { ?c raw:notation ?n ; raw:label ?l0 ; raw:definition ?d0 ; raw:source ?s0 .
                BIND(STRLANG(?l0, "en") AS ?l) BIND(STRLANG(?d0, "en") AS ?d) BIND(STRLANG(?s0, "en") AS ?s) }
    """, source_graph=STAGING)
    return model
