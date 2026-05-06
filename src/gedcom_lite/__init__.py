# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""gedcom-lite — a lightweight, fidelity-preserving GEDCOM toolkit.

Top-level public API:

    parse(source) -> GedcomDocument
    GedcomDocument
    Structure

    DateValue, parse_date_value

    parents_of, children_of, ancestors_of, descendants_of
    ancestors_of_with_generation, descendants_of_with_generation
    ahnentafel, cousins_of_with_degree, siblings_of

    decode_ansel, encode_ansel

    document_to_dict, structure_to_dict, to_json
"""

from .ansel import decode_ansel, encode_ansel
from .core import (
    GedcomDocument,
    Structure,
    document_to_dict,
    parse,
    structure_to_dict,
    to_json,
)
from .dates import DateValue, parse_date_value
from .traversal import (
    ahnentafel,
    ancestors_of,
    ancestors_of_with_generation,
    children_of,
    cousins_of_with_degree,
    descendants_of,
    descendants_of_with_generation,
    parents_of,
    siblings_of,
)

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "GedcomDocument",
    "Structure",
    "parse",
    "DateValue",
    "parse_date_value",
    "ahnentafel",
    "ancestors_of",
    "ancestors_of_with_generation",
    "children_of",
    "cousins_of_with_degree",
    "descendants_of",
    "descendants_of_with_generation",
    "parents_of",
    "siblings_of",
    "decode_ansel",
    "encode_ansel",
    "document_to_dict",
    "structure_to_dict",
    "to_json",
]
