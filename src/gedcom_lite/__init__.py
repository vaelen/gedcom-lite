# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""gedcom-lite — a lightweight, fidelity-preserving GEDCOM toolkit.

Top-level public API:

    parse(source) -> GedcomDocument
    GedcomDocument
    Structure

    DateValue, parse_date_value

    parents_of, children_of, ancestors_of, descendants_of

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
from .traversal import ancestors_of, children_of, descendants_of, parents_of

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "GedcomDocument",
    "Structure",
    "parse",
    "DateValue",
    "parse_date_value",
    "ancestors_of",
    "children_of",
    "descendants_of",
    "parents_of",
    "decode_ansel",
    "encode_ansel",
    "document_to_dict",
    "structure_to_dict",
    "to_json",
]
