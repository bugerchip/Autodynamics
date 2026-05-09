"""Envelope region for ``autodynamics.envelope``.

An :class:`Envelope` is a per-axis box in profile space: for every
axis the caller cares about, a closed interval ``(lo, hi)`` defines
the admissible region for that axis. Axes not present in the
``bounds`` mapping are unconstrained and are never checked. The
envelope is intentionally axis-agnostic: it accepts any string axis
name, not just the five canonical Autonometrics axes, so it composes
with arbitrary :class:`autodynamics.ProfileTrajectory` configurations
or with bare mappings of time series.

The class ships two construction paths:

- direct construction from explicit ``bounds`` (callers who already
  know the admissible region — for example, from a calibration
  step or a domain-specific specification), and
- :meth:`Envelope.from_trajectory` which learns per-axis bounds
  from a reference trajectory using a configurable multiplier of
  the per-axis sample standard deviation (Shewhart 1931 control
  limits, applied per axis independently).

Pre-registered semantics live in
``docs/ENVELOPE_DIAGNOSTICS.md``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from autonometrics import AutonomyProfile

from autodynamics.envelope.containment import (
    ContainmentResult,
    ContainmentVerdict,
)
from autodynamics.trajectory import ProfileTrajectory


@dataclass(frozen=True)
class Envelope:
    """A per-axis box in profile space defining an admissible region.

    Parameters
    ----------
    bounds:
        Mapping ``axis -> (lo, hi)`` with ``lo <= hi``. Axes absent
        from this mapping are unconstrained: a profile is *never*
        flagged as outside on those axes, even if the profile
        reports a value for them.

    Notes
    -----
    The class is frozen; ``bounds`` is normalised to an internal
    ``dict`` during construction and exposed as a read-only mapping
    through the :attr:`bounds` attribute. Callers should not rely on
    iteration order matching insertion order; the public guarantee
    is that :attr:`axes` returns axis names sorted lexicographically.
    """

    bounds: Mapping[str, tuple[float, float]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not isinstance(self.bounds, Mapping):
            raise TypeError(
                "bounds must be a Mapping[str, tuple[float, float]], "
                f"got {type(self.bounds).__name__}"
            )
        normalised: dict[str, tuple[float, float]] = {}
        for axis, interval in self.bounds.items():
            if not isinstance(axis, str):
                raise TypeError(
                    f"axis names must be str, got {type(axis).__name__}"
                )
            if not isinstance(interval, tuple) or len(interval) != 2:
                raise TypeError(
                    f"bounds[{axis!r}] must be a 2-tuple (lo, hi), "
                    f"got {interval!r}"
                )
            lo_raw, hi_raw = interval
            try:
                lo = float(lo_raw)
                hi = float(hi_raw)
            except (TypeError, ValueError) as exc:
                raise TypeError(
                    f"bounds[{axis!r}] must contain floats, got "
                    f"({lo_raw!r}, {hi_raw!r})"
                ) from exc
            if not (math.isfinite(lo) and math.isfinite(hi)):
                raise ValueError(
                    f"bounds[{axis!r}] must be finite, got ({lo}, {hi})"
                )
            if lo > hi:
                raise ValueError(
                    f"bounds[{axis!r}] has lo > hi: ({lo}, {hi})"
                )
            normalised[axis] = (lo, hi)
        object.__setattr__(self, "bounds", normalised)

    @property
    def axes(self) -> tuple[str, ...]:
        """Return the bounded axes in lexicographic order."""
        return tuple(sorted(self.bounds.keys()))

    def __len__(self) -> int:
        return len(self.bounds)

    def __contains__(self, axis: object) -> bool:
        return axis in self.bounds

    def evaluate(
        self,
        profile: AutonomyProfile | Mapping[str, float | None],
    ) -> ContainmentResult:
        """Apply the trinary containment check to ``profile``.

        Iterates over every bounded axis. For each axis:

        - if the profile value is ``None``, the axis verdict is
          ``UNDEFINED`` and the axis is recorded in
          ``undefined_axes``;
        - if the profile value is strictly outside the interval, the
          axis verdict is ``OUTSIDE`` and the axis is recorded in
          ``violated_axes``;
        - otherwise the axis verdict is ``INSIDE``.

        Aggregation (LD-3 of ``docs/ENVELOPE_DIAGNOSTICS.md``):

        - any axis ``OUTSIDE`` -> global ``OUTSIDE``;
        - else any axis ``UNDEFINED`` -> global ``UNDEFINED``;
        - else (all axes ``INSIDE``, including the trivial case of
          an envelope with no bounded axes) -> global ``INSIDE``.

        Parameters
        ----------
        profile:
            An :class:`autonometrics.AutonomyProfile`, or any
            mapping ``axis -> value`` accepting ``None`` and float
            values. The latter form lets callers reuse the envelope
            with raw axis values without having to construct a full
            profile.
        """
        per_axis: dict[str, ContainmentVerdict] = {}
        violated: list[str] = []
        undefined: list[str] = []
        reasons: list[str] = []

        for axis in sorted(self.bounds.keys()):
            lo, hi = self.bounds[axis]
            value = _read_axis(profile, axis)
            if value is None:
                per_axis[axis] = ContainmentVerdict.UNDEFINED
                undefined.append(axis)
                reasons.append(
                    f"{axis}=None (envelope bounds [{lo:.4f}, {hi:.4f}])"
                )
                continue
            if not math.isfinite(value):
                per_axis[axis] = ContainmentVerdict.UNDEFINED
                undefined.append(axis)
                reasons.append(
                    f"{axis}={value} non-finite (envelope bounds "
                    f"[{lo:.4f}, {hi:.4f}])"
                )
                continue
            if not (lo <= value <= hi):
                per_axis[axis] = ContainmentVerdict.OUTSIDE
                violated.append(axis)
                reasons.append(
                    f"{axis}={value:.4f} outside [{lo:.4f}, {hi:.4f}]"
                )
            else:
                per_axis[axis] = ContainmentVerdict.INSIDE

        if violated:
            verdict = ContainmentVerdict.OUTSIDE
        elif undefined:
            verdict = ContainmentVerdict.UNDEFINED
        else:
            verdict = ContainmentVerdict.INSIDE

        return ContainmentResult(
            verdict=verdict,
            per_axis=per_axis,
            violated_axes=tuple(violated),
            undefined_axes=tuple(undefined),
            reasons=tuple(reasons),
        )

    def contains(
        self,
        profile: AutonomyProfile | Mapping[str, float | None],
    ) -> bool:
        """Return ``True`` iff :meth:`evaluate` yields ``INSIDE``.

        Convenience shortcut for callers who do not need the
        per-axis breakdown. Returns ``False`` for both ``OUTSIDE``
        and ``UNDEFINED`` verdicts; consumers that need to
        distinguish those two cases should call :meth:`evaluate`
        directly.
        """
        return self.evaluate(profile).verdict == ContainmentVerdict.INSIDE

    @classmethod
    def from_trajectory(
        cls,
        trajectory: ProfileTrajectory,
        *,
        width_multiplier: float = 2.0,
        axes: Iterable[str] | None = None,
    ) -> "Envelope":
        """Learn per-axis bounds from a reference trajectory.

        For every axis configured on the trajectory (or for the
        explicit ``axes`` if provided), the bounds are
        ``(mean - width_multiplier * std, mean + width_multiplier * std)``
        where ``mean`` and ``std`` are the per-axis sample mean and
        sample standard deviation reported by
        :meth:`autodynamics.ProfileTrajectory.summary`. This is the
        Shewhart (1931) control-limit recipe applied independently
        per axis.

        Axes for which the trajectory has fewer than two defined
        values, or whose ``mean`` or ``std`` is ``None`` for any
        other reason, are silently dropped from the envelope: the
        sample standard deviation is undefined for ``n_defined < 2``
        and there is no honest way to construct a finite interval.
        Callers that want a strict, non-empty envelope should check
        :attr:`axes` on the result.

        Parameters
        ----------
        trajectory:
            The reference :class:`autodynamics.ProfileTrajectory`.
        width_multiplier:
            Non-negative float; the half-width of every interval
            in units of the per-axis sample standard deviation.
            Default ``2.0`` is a conservative, atheoretical choice
            (see LD-2 of ``docs/ENVELOPE_DIAGNOSTICS.md``); callers
            should override it whenever they have a calibration
            target.
        axes:
            Optional iterable restricting which axes are admitted
            to the envelope. Axes in ``axes`` that are not
            configured on the trajectory are silently ignored.
            Default ``None`` means "every axis configured on the
            trajectory".
        """
        if not isinstance(trajectory, ProfileTrajectory):
            raise TypeError(
                "trajectory must be a ProfileTrajectory, got "
                f"{type(trajectory).__name__}"
            )
        try:
            width = float(width_multiplier)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                "width_multiplier must be a non-negative float, got "
                f"{width_multiplier!r}"
            ) from exc
        if not math.isfinite(width) or width < 0.0:
            raise ValueError(
                "width_multiplier must be a non-negative finite float, "
                f"got {width}"
            )

        summary = trajectory.summary()
        if axes is None:
            requested = list(summary.keys())
        else:
            requested = [str(a) for a in axes]

        bounds: dict[str, tuple[float, float]] = {}
        for axis in requested:
            entry = summary.get(axis)
            if entry is None:
                continue
            mean_v = entry.get("mean")
            std_v = entry.get("std")
            if mean_v is None or std_v is None:
                continue
            mean_f = float(mean_v)
            std_f = float(std_v)
            half_width = width * std_f
            bounds[axis] = (mean_f - half_width, mean_f + half_width)
        return cls(bounds=bounds)


def _read_axis(
    profile: AutonomyProfile | Mapping[str, float | None],
    axis: str,
) -> float | None:
    """Read ``axis`` from a profile-shaped object, returning ``float | None``.

    Accepts both :class:`autonometrics.AutonomyProfile` (whose
    ``__getitem__`` already returns ``float | None``) and plain
    mappings. Mappings that do not contain ``axis`` are treated as
    if the axis were ``None`` for the profile, matching the
    mosaic-dropout convention.
    """
    if isinstance(profile, AutonomyProfile):
        return profile[axis]
    if isinstance(profile, Mapping):
        if axis not in profile:
            return None
        value = profile[axis]
        if value is None:
            return None
        return float(value)
    raise TypeError(
        "profile must be an AutonomyProfile or Mapping[str, float | None], "
        f"got {type(profile).__name__}"
    )


__all__ = [
    "Envelope",
]
