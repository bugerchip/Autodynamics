# Test fixtures

This directory holds reproducible data fixtures used by the
Autodynamics test suite. Every file here is **either fully synthetic
or a verbatim subset of a public Autonometrics benchmark**. No
proprietary data, no calibrated thresholds, no private logs.

## `autonometrics_v0_8_sample.csv`

**Origin.** Reproducible subset of the public Autonometrics benchmark
`docs/benchmarks/v0.8.0a0.csv` from
[`bugerchip/Autonometrics`](https://github.com/bugerchip/Autonometrics).

**Selection rule.** Three groups, five seeds each (15 rows total):

| `class`           | `params`        | seeds |
|-------------------|-----------------|-------|
| `ECASystem`       | `rule=30`       | `0..4`|
| `KauffmanNetwork` | `coupling=0.5`  | `0..4`|
| `PeriodicCycle`   | `period=2`      | `0..4`|

The three groups were chosen because together they cover every
boundary regime of `ProfileTrajectory.summary()`:

- `ECASystem rule=30` exhibits two fully saturated axes
  (`closure = 1.0`, `constraint = 1.0`) and one variable axis
  (`memory`).
- `KauffmanNetwork coupling=0.5` includes one degenerate row
  (`seed = 1`, all axes `n/a`), exercising the mosaic-dropout
  contract on a trajectory with a real interior hole.
- `PeriodicCycle period=2` exhibits three axes saturated at extreme
  values (`closure = 1.0`, `constraint = 0.0`, `persistence = 0.0`)
  and one fully undefined axis (`coherence` empty for every seed).

**Reproducing this file.** From the root of `bugerchip/Autonometrics`
at the `v0.8.0a0` tag, run:

```python
import csv
keep = {
    ("PeriodicCycle", "period=2"),
    ("ECASystem", "rule=30"),
    ("KauffmanNetwork", "coupling=0.5"),
}
rows = list(csv.DictReader(open("docs/benchmarks/v0.8.0a0.csv")))
filtered = [r for r in rows if (r["class"], r["params"]) in keep
            and int(r["seed"]) < 5]
with open("autonometrics_v0_8_sample.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(filtered)
```

**License.** Inherits the license of the source repository
(Apache-2.0 on the Autonometrics side, Apache-2.0 here).
