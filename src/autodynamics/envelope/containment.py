"""Containment verdict and result types for ``autodynamics.envelope``.

This module ships the trinary verdict enumeration shared by every
public entry point of :mod:`autodynamics.envelope` and the result
dataclass produced by :meth:`autodynamics.envelope.Envelope.evaluate`.
The values are intentionally distinct from boolean: a :class:`bool`
collapses *outside-the-region* and *undefined-on-this-axis* into the
same ``False``, which silently destroys the mosaic-dropout fielty
preserved everywhere else in :mod:`autodynamics`.

Pre-registered semantics live in
``docs/ENVELOPE_DIAGNOSTICS.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ContainmentVerdict(str, Enum):
    """Trinary outcome of a containment check.

    The enum inherits from :class:`str` so members compare equal to
    their string name, which keeps existing ``status == "INSIDE"``
    style code paths working while still giving consumers a
    structured value.

    Members
    -------
    INSIDE:
        Every axis bounded by the envelope is defined on the input
        profile and lies inside its closed interval.
    OUTSIDE:
        At least one axis bounded by the envelope is defined on the
        input profile and lies *strictly* outside its closed
        interval. ``OUTSIDE`` strictly dominates ``UNDEFINED`` in
        the global aggregation (see locked decision LD-3 of
        ``docs/ENVELOPE_DIAGNOSTICS.md``).
    UNDEFINED:
        No axis is outside, but at least one axis bounded by the
        envelope is ``None`` on the input profile, and the verdict
        on that axis cannot be decided.
    """

    INSIDE = "INSIDE"
    OUTSIDE = "OUTSIDE"
    UNDEFINED = "UNDEFINED"


@dataclass(frozen=True)
class ContainmentResult:
    """Outcome of :meth:`autodynamics.envelope.Envelope.evaluate`.

    Attributes
    ----------
    verdict:
        Aggregated trinary outcome (LD-3 of
        ``docs/ENVELOPE_DIAGNOSTICS.md``).
    per_axis:
        Mapping ``axis -> ContainmentVerdict`` over the axes
        bounded by the envelope. Axes that the envelope does not
        bound are *not* included in this mapping (they cannot fail
        a check that does not exist).
    violated_axes:
        Tuple of bounded axes whose value is strictly outside their
        interval, in the order the envelope iterates them. Empty
        tuple unless ``verdict`` is :attr:`ContainmentVerdict.OUTSIDE`.
    undefined_axes:
        Tuple of bounded axes whose value is ``None`` on the input
        profile, in the order the envelope iterates them. May be
        non-empty alongside a non-empty ``violated_axes``: the
        verdict in that case is :attr:`ContainmentVerdict.OUTSIDE`,
        but the axes whose containment could not be decided are
        still reported for diagnostic purposes.
    reasons:
        Human-readable, frozen tuple of strings, one per
        non-``INSIDE`` axis, describing the reason. Format is
        deliberately stable: callers may assert against it in tests.
    """

    verdict: ContainmentVerdict
    per_axis: dict[str, ContainmentVerdict]
    violated_axes: tuple[str, ...]
    undefined_axes: tuple[str, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.verdict, ContainmentVerdict):
            raise TypeError(
                "verdict must be a ContainmentVerdict, got "
                f"{type(self.verdict).__name__}"
            )


__all__ = [
    "ContainmentResult",
    "ContainmentVerdict",
]
