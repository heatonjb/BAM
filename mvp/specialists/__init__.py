"""Specialist lenses available to every tenant.

A lens is condensed thinking, not an actor. ``get_specialist`` resolves one by
id; ``available_specialists`` lists what core ships.
"""

from __future__ import annotations

import pathlib
from typing import Optional

from .base import (
    RetrievedPrinciple,
    Specialist,
    Viewpoint,
    available_specialists,
)

__all__ = [
    "Specialist",
    "Viewpoint",
    "RetrievedPrinciple",
    "get_specialist",
    "available_specialists",
]


def get_specialist(specialist_id: str,
                   root: Optional[pathlib.Path] = None) -> Specialist:
    """Load a specialist lens by id."""
    return Specialist.load(specialist_id, root=root)
