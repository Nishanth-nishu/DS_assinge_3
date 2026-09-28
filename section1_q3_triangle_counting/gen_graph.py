#!/usr/bin/env python3
"""
Reproducible undirected-graph generator in the assignment input format.

    gen_graph.py V E [--seed S] [--model er|powerlaw] > graph.txt

  er       : Erdos-Renyi style, E distinct edges chosen uniformly.
  powerlaw : preferential-attachment style (skewed degrees, many triangles
             around hubs) - a harder case for triangle counting.

Output: "V E" on the first line, then E lines "u v" (u != v, no duplicates).
"""
import argparse
import random
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("V", type=int)
    ap.add_argument("E", type=int)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--model", choices=["er", "powerlaw"], default="er")
    a = ap.parse_args()

    V, E = a.V, a.E
    max_e = V * (V - 1) // 2
    if E > max_e:
        sys.exit(f"E={E} exceeds maximum {max_e} for V={V}")
    rng = random.Random(a.seed)
    edges = set()
    if a.model == "er":
        while len(edges) < E:
            u, v = rng.randrange(V), rng.randrange(V)
            if u != v:
                edges.add((u, v) if u < v else (v, u))
    else:
        targets = [0, 1]  # endpoint list => sampling proportional to degree
        while len(edges) < E:
            u = rng.randrange(V)
            v = rng.choice(targets) if rng.random() < 0.8 else rng.randrange(V)
            if u == v:
                continue
            e = (u, v) if u < v else (v, u)
            if e not in edges:
                edges.add(e)
                targets.extend(e)
    out = sys.stdout
    out.write(f"{V} {E}\n")
    edges = list(edges)
    rng.shuffle(edges)
    for u, v in edges:
        # randomise direction so both orientations appear in the input
        if rng.random() < 0.5:
            u, v = v, u
        out.write(f"{u} {v}\n")


if __name__ == "__main__":
    main()
