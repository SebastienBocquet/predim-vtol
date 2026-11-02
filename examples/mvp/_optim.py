"""Shared optimisation loop of the MVP examples: ``predimrc_wrapper.mdo.optimise`` with
the results printed and written to ``outputs/<tag>.json``."""

from __future__ import annotations

import json
from pathlib import Path

from predimrc_wrapper.mdo.optimise import optimise as run

OUT = Path(__file__).parent / "outputs"


def optimise(
    project,
    continuous,
    discrete: dict[str, list],
    tag: str,
    max_iter: int = 60,
    backend=None,
    algo: str = "SLSQP",
) -> dict:
    """Maximise the flight time at V1 for every combination of the discrete choices."""
    OUT.mkdir(exist_ok=True)
    summary = run(
        project, continuous, discrete, max_iter=max_iter, backend=backend, algo=algo
    )
    for r in summary.runs:
        if r.error:
            print(f"{r.choice}: failed ({r.error})")
        else:
            print(
                f"{r.choice}: flight time V1 {r.outputs['flight_time_v1'] / 60:.1f} min, feasible={r.feasible}, "
                f"x={ {k: round(v, 3) for k, v in r.x.items()} }"
            )
    data = summary.to_dict()
    (OUT / f"{tag}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    best = summary.best
    o = best.outputs
    print(f"\nOptimum {best.choice} {best.x}")
    print(
        f"  flight time V1 {o['flight_time_v1'] / 60:.1f} min, range V2 {o['range_v2'] / 1000:.1f} km, "
        f"V1 {o['v1']:.1f} m/s, V2 {o['v2']:.1f} m/s, mass {o['mass_total']:.2f} kg"
    )
    print(
        "  margins: "
        + ", ".join(f"{k[7:]} {o[k]:+.2f}" for k in o if k.startswith("margin_"))
    )
    print(f"  total time {summary.seconds:.0f} s; results in {OUT / (tag + '.json')}")
    return data
