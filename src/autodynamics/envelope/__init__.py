"""Containment envelope primitives for ``autodynamics``.

This subpackage ships the :class:`Envelope` region check and its
trinary verdict (:class:`ContainmentVerdict`,
:class:`ContainmentResult`).

An :class:`Envelope` is a per-axis box in profile space. Construct
it directly from explicit ``bounds``, or learn it from a reference
:class:`autodynamics.ProfileTrajectory` via
:meth:`Envelope.from_trajectory`. Then call :meth:`Envelope.evaluate`
on any :class:`autonometrics.AutonomyProfile` (or any mapping
``axis -> value``) to obtain a trinary verdict:

- :attr:`ContainmentVerdict.INSIDE` — all bounded axes are defined
  and inside their interval;
- :attr:`ContainmentVerdict.OUTSIDE` — at least one bounded axis is
  defined and outside its interval;
- :attr:`ContainmentVerdict.UNDEFINED` — no bounded axis is outside,
  but at least one is ``None`` on the input.

The class is mosaic-dropout-fielty: ``None`` propagates through to
:attr:`ContainmentVerdict.UNDEFINED`, never silently assumed to be
``INSIDE`` or ``OUTSIDE``. The recipe used by
:meth:`Envelope.from_trajectory` is the Shewhart (1931) control-limit
formula (``mean ± width_multiplier * std``) applied independently
per axis.

Pre-registered semantics live in
``docs/ENVELOPE_DIAGNOSTICS.md``.

References
----------
Shewhart, W. A. (1931). *Economic Control of Quality of Manufactured
Product*. Van Nostrand.
"""

from autodynamics.envelope.containment import (
    ContainmentResult,
    ContainmentVerdict,
)
from autodynamics.envelope.region import Envelope

__all__ = [
    "ContainmentResult",
    "ContainmentVerdict",
    "Envelope",
]
