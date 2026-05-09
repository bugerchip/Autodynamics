# Envelope diagnostics

**Status**: pre-registration. Locked at the start of the `v0.4.0a0`
cycle, before any of the implementation report below was written.

**Cycle**: `v0.4.0a0` (containment envelope primitives).

**Predecessor design documents**:
[`docs/TRAJECTORY_DIAGNOSTICS.md`](TRAJECTORY_DIAGNOSTICS.md)
(`v0.2.0a0`),
[`docs/COUPLING_DIAGNOSTICS.md`](COUPLING_DIAGNOSTICS.md)
(`v0.3.0a0`).
The discipline (locked decisions, named boundary regimes, falsifiable
predicted outcomes) is the same.

---

## Why this document exists

`v0.2.x` shipped a recording substrate plus algebra of trajectories.
`v0.3.x` shipped a directed Granger-causal coupling graph between
admitted axes. Both work *inside* the autonomy atlas: they describe
how a single trajectory (or pair of axes from a single trajectory)
moves and couples internally.

`v0.4.0a0` adds the smallest *region check* primitive: an
:class:`Envelope` is a per-axis box in profile space that answers a
single question — "is this profile inside an admissible region of
the atlas?" — with a trinary verdict
(:class:`ContainmentVerdict.INSIDE`, :class:`OUTSIDE`,
:class:`UNDEFINED`). The class itself is not a discovery. It is the
Shewhart (1931) control-limit recipe applied per axis, with a
mosaic-dropout-fielty trinary aggregation rule on top.

Because the toolbox composes a per-axis bound learner, a per-axis
containment check, and an aggregation rule, it is also easy to
misread its output. A caller who builds an envelope from a 200-row
reference trajectory and gets ``UNDEFINED`` on every subsequent
profile may not know whether the profiles are genuinely degraded,
the envelope was learned over the wrong axes, or the aggregation
rule is firing because exactly one of five axes happens to be
``None`` on the input.

This document fixes the **domain of applicability** of every
primitive *before* the implementation, so that future readers can
audit the implementation against a written specification rather
than against tribal knowledge.

---

## What this cycle is *not*

This cycle is deliberately conservative. It registers properties of
the **implementation**, not properties of the systems whose
trajectories the implementation analyses. It does *not*:

- claim that any particular envelope, learned from any particular
  reference trajectory, is the "correct" admissible region for
  any system;
- recommend a default value of ``width_multiplier`` for any
  applied use case;
- ship the composite gate that combines envelope containment with
  other checks; that composition is out of scope of the public
  library;
- predict transitions, anomalies or drifts from the verdict
  alone.

Empirical claims about real data live in their own
`docs/<COMPONENT>_VALIDATION.md` documents (see
[`docs/ENVELOPE_VALIDATION.md`](ENVELOPE_VALIDATION.md) for the
cycle's validation track against the public Autonometrics
benchmark).

---

## Locked decisions

### LD-1. Envelope shape and admissibility

An :class:`Envelope` is a finite mapping
``axis -> (lo, hi)`` with ``lo <= hi`` and both bounds finite. Axes
absent from the mapping are **unconstrained**: the envelope makes no
claim about their values, and a profile cannot be flagged on those
axes.

A profile (or any mapping ``axis -> value``) is checked
**axis by axis** against the bounded subset only. For every bounded
axis ``a``:

- if the profile reports a finite numeric value ``v``, the axis is
  ``INSIDE`` iff ``lo <= v <= hi`` (closed interval), else
  ``OUTSIDE``;
- if the profile reports ``None``, missing key, or a non-finite
  numeric value (``NaN`` or ±∞), the axis is ``UNDEFINED``.

The closed interval is intentional: callers who calibrate
``(lo, hi)`` from data already account for the boundary numerically;
forcing the inequality strict would silently create
left-out-by-one-floating-point-ulp false positives.

### LD-2. Default ``width_multiplier``

:meth:`Envelope.from_trajectory` learns per-axis bounds as
``(mean - width_multiplier * std, mean + width_multiplier * std)``
where ``mean`` and ``std`` are the per-axis sample mean and sample
standard deviation reported by
:meth:`autodynamics.ProfileTrajectory.summary`. The default
``width_multiplier`` is ``2.0``.

The default has **no theoretical claim**. It is the conservative,
atheoretical choice mirroring the standard Shewhart 2-sigma control
limit (Shewhart 1931, ch. 4). Under a Gaussian assumption it
captures roughly 95 % of the reference distribution; that
assumption is not enforced by the implementation. Callers with a
calibration target should override the default explicitly.

### LD-3. Aggregation rule

The global verdict is computed from the per-axis verdicts as:

1. if **any** bounded axis is ``OUTSIDE``, global verdict is
   ``OUTSIDE``;
2. else if **any** bounded axis is ``UNDEFINED``, global verdict
   is ``UNDEFINED``;
3. else (every bounded axis is ``INSIDE``, **including** the
   trivial case of an envelope with no bounded axes), global
   verdict is ``INSIDE``.

Step 1 strictly dominates step 2: ``OUTSIDE`` is a positive,
falsifiable observation about the profile (it actually crosses the
boundary), while ``UNDEFINED`` is the absence of evidence on a
specific axis. Reporting ``UNDEFINED`` instead of ``OUTSIDE`` when
the profile is *demonstrably* outside on at least one bounded axis
would silently hide the violation. The dual error — reporting
``OUTSIDE`` when only ``UNDEFINED`` axes exist — is forbidden by
step 2.

The trivial case in step 3 (envelope with no bounded axes) is
intentional: an unbounded envelope is the identity of the
containment check; it accepts every profile.

### LD-4. Mosaic-dropout fielty

The classification of ``None``, missing keys, ``NaN`` and ±∞ as
``UNDEFINED`` (rather than ``OUTSIDE``) is a hard contract.
Returning ``OUTSIDE`` for a missing value would silently equate
"the profile failed an axis check" with "the profile did not report
on that axis", which is the same error
``ProfileTrajectory.volatility`` and `granger_graph` already refuse
to make. The four cases are treated identically:

- ``profile[axis] is None``,
- ``axis not in profile`` (when profile is a mapping),
- ``math.isnan(profile[axis])``,
- ``math.isinf(profile[axis])``.

### LD-5. Envelope is frozen

:class:`Envelope` is constructed once and not mutated. The
``bounds`` mapping is normalised to an internal ``dict`` in
``__post_init__`` and exposed read-only through the dataclass. This
makes envelopes safely shareable across threads and callers, and
prevents the calibration-vs-evaluation phases from accidentally
contaminating each other.

### LD-6. ``from_trajectory`` admission policy

For every axis the caller asks about (or every axis configured on
the trajectory if ``axes is None``):

- if the axis is not configured on the trajectory, it is silently
  dropped;
- if the trajectory's per-axis ``summary`` reports
  ``mean is None`` or ``std is None``, the axis is silently dropped
  (this happens whenever ``n_defined < 2``: the sample standard
  deviation is undefined and we refuse to fabricate one);
- otherwise, bounds are
  ``(mean - width_multiplier * std, mean + width_multiplier * std)``.

A saturated axis (constant series, ``std == 0.0``) yields a
point interval ``(mean, mean)``. Subsequent
:meth:`Envelope.evaluate` calls will then flag any value strictly
different from ``mean`` as ``OUTSIDE``. This is the conservative
behaviour: a saturated axis admits exactly one value.

### LD-7. Boundary regimes (named)

| Regime                          | Definition                                                                | Expected behaviour                                                                                                                                  |
|---------------------------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| **Unbounded envelope**          | ``Envelope()`` or ``Envelope(bounds={})``                                 | ``axes == ()``, ``len(env) == 0``. Every profile yields ``INSIDE`` with empty ``per_axis``.                                                          |
| **Single-axis envelope**        | One bounded axis                                                          | Verdict depends only on that axis; other axes on the profile are ignored.                                                                            |
| **Saturated reference**         | Reference trajectory has ``std == 0`` on an axis                          | ``from_trajectory`` produces ``(mean, mean)`` for that axis. ``evaluate`` flags any deviation as ``OUTSIDE``; ``mean`` itself is ``INSIDE``.        |
| **Under-sampled reference**     | Reference axis has ``n_defined < 2``                                       | ``from_trajectory`` drops the axis silently. The resulting envelope has fewer admitted axes than requested.                                          |
| **Empty / single-snapshot**     | ``len(trajectory) <= 1``                                                   | ``from_trajectory`` admits no axis; ``axes == ()``.                                                                                                  |
| **Boundary value**              | ``profile[axis] == lo`` or ``profile[axis] == hi``                        | Per LD-1 closed interval, axis verdict is ``INSIDE``.                                                                                                |
| **Single ``None`` axis**        | Profile has one bounded axis ``None``, rest ``INSIDE``                    | Global verdict is ``UNDEFINED`` per LD-3 step 2.                                                                                                     |
| **Mixed ``None`` and outside**  | Profile has at least one ``OUTSIDE`` axis and at least one ``UNDEFINED`` | Global verdict is ``OUTSIDE`` per LD-3 step 1; both ``violated_axes`` and ``undefined_axes`` are non-empty in the result.                            |
| **Non-finite axis value**       | Profile has ``NaN`` or ±∞ on a bounded axis                                | Per LD-4, axis verdict is ``UNDEFINED`` (not ``OUTSIDE``).                                                                                            |

---

## Predicted outcomes

The cycle ships a positive verdict iff all four predictions below
hold without deviation.

### PO-1. Determinism

For any fixed ``(reference_trajectory, width_multiplier, axes)``,
:meth:`Envelope.from_trajectory` produces a numerically identical
envelope on repeated calls. For any fixed ``(envelope, profile)``,
:meth:`Envelope.evaluate` produces a numerically identical
:class:`ContainmentResult` on repeated calls.

**Verification threshold**: bit-equality of ``bounds`` and of
every field of :class:`ContainmentResult`.

### PO-2. Round-trip identity at the mean profile

Let ``T`` be a reference trajectory of at least 3 snapshots with
strictly positive sample standard deviation on every configured
axis, and let ``E = Envelope.from_trajectory(T,
width_multiplier=w)`` for any ``w > 0``. Construct a synthetic
profile whose value on every axis equals the per-axis
``T.summary()[axis]["mean"]``. Then ``E.evaluate(synthetic_profile)``
yields ``ContainmentVerdict.INSIDE``.

**Verification threshold**: explicit assertion in the test suite.

### PO-3. Aggregation rule respects LD-3 precedence

For every combination of ``(any_outside, any_undefined,
any_inside_only)`` admitted by the rule, the implementation
respects the LD-3 precedence:

- ``OUTSIDE`` strictly dominates ``UNDEFINED``;
- ``UNDEFINED`` strictly dominates the trivial all-``INSIDE`` case;
- ``per_axis`` only contains entries for bounded axes.

**Verification threshold**: explicit assertion in the test suite,
with at least one test per combination listed in LD-7.

### PO-4. Mosaic-dropout fielty preserved

For a profile in which exactly one bounded axis is ``None``, ``NaN``
or ±∞, the four cases produce identical
:attr:`ContainmentResult.verdict` (``UNDEFINED``) and identical
:attr:`ContainmentResult.undefined_axes` (a tuple containing the
single axis name).

**Verification threshold**: explicit assertion in the test suite,
with at least one test per case listed in LD-4.

---

## Implementation report

The implementation lives in
[`src/autodynamics/envelope/`](../src/autodynamics/envelope/) as
three modules:

- [`region.py`](../src/autodynamics/envelope/region.py) — the
  :class:`Envelope` dataclass, its construction (direct + from
  trajectory), its containment check (:meth:`evaluate`), and the
  :meth:`contains` boolean shortcut. Implements LD-1, LD-2, LD-5,
  LD-6.
- [`containment.py`](../src/autodynamics/envelope/containment.py) —
  the :class:`ContainmentVerdict` enum and the
  :class:`ContainmentResult` dataclass. Implements LD-3, LD-4
  (data structure side).
- [`__init__.py`](../src/autodynamics/envelope/__init__.py) —
  public API surface; re-exported at the top level of
  :mod:`autodynamics`.

Tests are split across two files:

- [`tests/test_envelope_smoke.py`](../tests/test_envelope_smoke.py)
  — 13 smoke tests covering imports, return types, basic synthetic
  cases, ``None`` propagation, and the public API surface.
- [`tests/test_envelope.py`](../tests/test_envelope.py) — 51 tests
  exercising the locked decisions and predicted outcomes,
  organised by section: construction & validation, ``evaluate``
  semantics, input types, the ``contains`` shortcut,
  ``from_trajectory`` end-to-end, round-trip checks, and result
  invariants. PO-1 through PO-4 each map to at least one explicit
  test.

---

## Verdict

The verdict is recorded after the test suite goes green, before the
cycle is merged.

**v0.4.0a0**: positive. PO-1 through PO-4 all pass on the cycle's
test suite (`pytest tests/`). No deviations from this
pre-registration were required.

---

## Deviations from pre-registration

None recorded for `v0.4.0a0`.

---

## References

- Shewhart, W. A. (1931). *Economic Control of Quality of
  Manufactured Product*. Van Nostrand.
- Lyapunov, A. M. (1892). *The General Problem of the Stability of
  Motion*. (English translation: Taylor & Francis, 1992.)
- Kalman, R. E. (1960). "A New Approach to Linear Filtering and
  Prediction Problems." *Transactions of the ASME — Journal of
  Basic Engineering* 82 (Series D): 35-45.
- Schölkopf, B., Platt, J. C., Shawe-Taylor, J., Smola, A. J.,
  Williamson, R. C. (2001). "Estimating the Support of a
  High-Dimensional Distribution." *Neural Computation* 13 (7):
  1443-1471.

---

*End of pre-registration. Future cycles may extend this document
with new locked decisions and predictions; existing entries are
preserved and annotated with their cycle of origin.*
