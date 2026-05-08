"""Command-line entry point for the toy trajectory recorder demo.

Run via ``autodynamics-demo`` (after ``pip install autodynamics``) or
``python -m autodynamics.demo``.
"""

from __future__ import annotations

import argparse

import autonometrics as anm

from autodynamics.trajectory import ProfileTrajectory


def main() -> None:
    """Build a trajectory of profiles across a sweep of ``n_states`` and print it."""
    parser = argparse.ArgumentParser(
        prog="autodynamics-demo",
        description=(
            "Record a trajectory of autonomy profiles across a sweep of "
            "SimpleAutomaton configurations and print the resulting "
            "axis time series, deltas, and total path length."
        ),
    )
    parser.add_argument(
        "--n-states-list",
        type=int,
        nargs="+",
        default=[3, 4, 5, 6, 8],
        help="state alphabet sizes to sweep",
    )
    parser.add_argument(
        "--n-steps",
        type=int,
        default=600,
        help="trajectory length per system",
    )
    parser.add_argument("--seed", type=int, default=0, help="RNG seed")
    parser.add_argument(
        "--report",
        choices=("default", "summary"),
        default="default",
        help=(
            "output mode: 'default' prints per-pair deltas and total path "
            "length; 'summary' prints the per-axis ProfileTrajectory.summary() "
            "instead"
        ),
    )
    args = parser.parse_args()

    trajectory = ProfileTrajectory(axes=("closure", "memory"))

    print(
        f"Sweeping n_states in {args.n_states_list} with n_steps={args.n_steps}, "
        f"seed={args.seed}\n"
    )

    for n_states in args.n_states_list:
        sys = anm.SimpleAutomaton.demo(
            n_states=n_states,
            n_steps=args.n_steps,
            seed=args.seed,
        )
        sys.run()
        profile = anm.measure(sys, axes=["closure", "memory"])
        trajectory.append(profile)

    header = f"{'idx':>4} | {'n_states':>8} | {'closure':>10} | {'memory':>10}"
    print(header)
    print("-" * len(header))
    for snapshot, n_states in zip(trajectory, args.n_states_list, strict=True):
        cl = snapshot.profile.closure
        me = snapshot.profile.memory
        cl_s = f"{cl:.4f}" if cl is not None else "    None"
        me_s = f"{me:.4f}" if me is not None else "    None"
        print(
            f"{snapshot.index:>4} | {n_states:>8} | "
            f"{cl_s:>10} | {me_s:>10}"
        )

    print()
    print(f"Number of snapshots:    {len(trajectory)}")

    if args.report == "summary":
        summary = trajectory.summary()
        print()
        print("Per-axis summary:")
        print("-" * 56)
        for axis, metrics in summary.items():
            print(f"  {axis}:")
            for metric, value in metrics.items():
                if isinstance(value, bool):
                    value_s = str(value)
                elif isinstance(value, int):
                    value_s = str(value)
                elif isinstance(value, float):
                    value_s = f"{value:.4f}"
                else:
                    value_s = "None"
                print(f"    {metric:>12s} = {value_s}")
        return

    deltas = trajectory.deltas()
    print(f"Number of deltas:       {len(deltas)}")
    for delta in deltas:
        mag = delta.magnitude
        mag_s = f"{mag:.4f}" if mag is not None else "  None"
        print(
            f"  delta {delta.from_index}->{delta.to_index}: "
            f"magnitude={mag_s}"
        )

    total = trajectory.total_path_length()
    total_s = f"{total:.4f}" if total is not None else "None"
    print(f"\nTotal path length:      {total_s}")


if __name__ == "__main__":
    main()
