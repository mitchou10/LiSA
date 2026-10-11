"""Relation types looked for when the input does not say.

The description gives the direction: the head is the first end, the tail the
second.
"""

from __future__ import annotations

from app.schemas import RelationRule

DEFAULT_RELATIONS = [
    RelationRule(
        name="works_for",
        description="Employment: the head is a person, the tail the organization "
        "they work for",
    ),
    RelationRule(
        name="lives_in",
        description="Residence: the head is a person, the tail the place they live in",
    ),
    RelationRule(
        name="located_in",
        description="Geographic containment: the head is a place or organization, "
        "the tail the place it is located in",
    ),
    RelationRule(
        name="married_to",
        description="Marriage or partnership between two people",
    ),
    RelationRule(
        name="parent_of",
        description="Parenthood: the head is the parent, the tail the child",
    ),
]
