# Section 1 – Q3: Triangle Counting in an Undirected Graph (MapReduce)

Counts the triangles of an undirected graph (`V ≤ 10^5`, `E ≤ 10^6`) with a chain of
four MapReduce jobs written as Hadoop-Streaming style Python programs (stdin → stdout,
`key<TAB>value` records). The same programs run:

* locally (`run_local.sh`, `sort` acts as the shuffle),
* distributed on the RCE **SLURM** cluster (`run_distributed.sbatch`, map and reduce
  tasks launched with `srun` on several nodes, hash-partitioned shuffle), and
* on Hadoop, if available (`run_hadoop.sh`, 4 chained streaming jobs).

## Input / output

```
4 5        <- V E  (header; stripped by the drivers before the edges are split)
0 1
1 2
2 0
2 3
3 0
```
Output: a single integer – the global triangle count (`2` for the sample).

## Algorithm (NodeIterator++ with degree ordering)

Every vertex gets a rank `rank(v) = (deg(v), v)` – a total order. A triangle
`{p,q,r}` with `rank(p) < rank(q) < rank(r)` is found **only at its lowest-ranked
vertex `p`**, as the wedge `q ← p → r` closed by the edge `(q,r)`. Since every triangle
has exactly one lowest vertex, it is counted exactly once – **no double counting and
no division by 3 / 6 is needed.** Orienting edges towards higher-degree vertices also
keeps every out-degree ≤ O(√E), so the number of wedges is O(E^1.5) even when the graph
has hubs (power-law graphs); ordering by id alone could produce O(V²) wedges at a hub.

| Job | Mapper | Intermediate key → value | Reducer | Output |
|---|---|---|---|---|
| 1 | `mapper1.py`: edge `u v` → emit both directions (drops self-loops) | `u → v`, `v → u` | `reducer1.py`: neighbour **set** of `x` (removes duplicate edges) → `deg(x)`; for each neighbour emit the edge id | `min,max → "x deg(x)"` |
| 2 | identity | edge id → both endpoints with degree | `reducer2.py`: orient low-rank → high-rank | `low → high` |
| 3 | identity | `low → high` (out-neighbours of each vertex) | `reducer3.py`: emit every **wedge** of out-neighbour pairs, plus an **edge marker** for each oriented edge | `a,b → 1` (wedge) / `a,b → $` (edge exists) |
| 4 | identity + **combiner** `combiner4.py` (sums wedge counts per key map-side) | edge id → `$` / counts | `reducer4.py`: if `$` present, all wedges on that key are triangles; emit partial sum | `triangles → n` |
| final | – | – | `sum_reducer.py` adds the partial sums of all reducers | global count |

Data distribution: the edge list is split into `NT` line-aligned chunks (the "DFS
blocks"), one per mapper task. Mappers never talk to each other; everything they need is
delivered by the shuffle.

## Files

| File | Purpose |
|---|---|
| `mapper1.py`, `reducer1.py` … `reducer4.py`, `combiner4.py`, `identity_mapper.py`, `sum_reducer.py` | the MapReduce programs |
| `partition.py` | deterministic hash partitioner (crc32 mod R) for the SLURM shuffle |
| `run_local.sh [in] [out]` | single-machine pipeline (like `MapreduceForLocalTesting.sh`) |
| `run_distributed.sbatch [files…]` | multi-node SLURM driver with per-stage timing → `perf_results/triangles_dist_summary.csv` |
| `run_hadoop.sh graph [R]` | optional: same jobs on Hadoop Streaming |
| `gen_graph.py V E --seed S --model er\|powerlaw` | reproducible dataset generator |
| `make_datasets.sh` | builds the benchmark datasets (fixed seeds) in `test_data/` |
| `verify_sequential.py graph [--brute]` | independent sequential reference (and O(V³) brute force) |
| `run_tests.sh` | correctness test-suite |

## Running

### Local
```bash
./run_local.sh test_data/sample.txt          # -> 2
./run_tests.sh                               # 17 correctness tests
```

### RCE cluster (SLURM)
```bash
ssh cs3401.58@rce.iiit.ac.in                 # IIIT network / VPN only
git clone https://github.com/Nishanth-nishu/DS_assinge_3.git
cd DS_assinge_3/section1_q3_triangle_counting
./make_datasets.sh                           # ~18 MB of graphs, fixed seeds
sbatch run_distributed.sbatch                # 4 nodes x 1 task (default)
sbatch --nodes=2 --ntasks=2 run_distributed.sbatch          # scaling runs
sbatch --nodes=4 --ntasks=8 run_distributed.sbatch tri_large.txt
squeue -u $USER ; cat triangles_<jobid>.out
```
Each job has a **map phase** (`srun` over `NT` tasks: mapper → [sort → combiner] →
`partition.py` into `NT` buckets) and a **reduce phase** (`srun` over `NT` tasks: task
`r` gathers bucket `r` from every mapper → `sort` → reducer). Intermediate files live on
the shared home directory, which plays the role of the DFS. Every run also checks the
answer against `verify_sequential.py` (`correct` column in the CSV).

Interactive alternative:
```bash
salloc --nodes=4 --ntasks=4
bash run_distributed.sbatch tri_medium.txt   # srun picks up the allocation
```

## Correctness verification

`run_tests.sh` compares the MapReduce result with independent references:

* the assignment sample (2), single triangle, path (0), K4 (4), K30 (C(30,3) = 4060),
* duplicate / reversed edges and self-loops (must not change the count),
* 5 random Erdős–Rényi graphs checked against **brute force over all vertex triples**,
* 5 random power-law graphs checked against the sequential forward algorithm.

All 17 pass. The distributed driver additionally verifies every benchmark input.

## Benchmark

`perf_results/local_sandbox_summary.csv` – produced by `run_distributed.sbatch` with the
local fallback (no `srun`) on a **2-core** cloud sandbox, so it is only a sanity check of
the pipeline; re-run on RCE to get the multi-node numbers (they are appended to
`perf_results/triangles_dist_summary.csv`). Times in seconds.

| input | E | tasks | J1 map | J1 red | J2 map | J2 red | J3 map | J3 red | J4 map | J4 red | total | triangles | ok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tri_small | 5 000 | 1 | 0.03 | 0.03 | 0.03 | 0.04 | 0.03 | 0.04 | 0.09 | 0.02 | 0.38 | 175 | yes |
| tri_medium | 100 000 | 1 | 0.15 | 0.35 | 0.17 | 0.29 | 0.09 | 0.65 | 2.56 | 0.25 | 4.57 | 1341 | yes |
| tri_large | 1 000 000 | 1 | 1.32 | 3.69 | 1.54 | 2.88 | 0.83 | 6.06 | 25.45 | 3.26 | 45.13 | 1358 | yes |
| tri_powerlaw | 500 000 | 1 | 0.64 | 1.83 | 0.76 | 1.47 | 0.37 | 3.03 | 12.00 | 1.25 | 21.42 | 2198 | yes |
| tri_medium | 100 000 | 2 | 0.15 | 0.23 | 0.17 | 0.17 | 0.12 | 0.32 | 1.18 | 0.16 | 2.57 | 1341 | yes |
| tri_large | 1 000 000 | 2 | 1.12 | 1.91 | 1.31 | 1.38 | 0.62 | 3.26 | 11.91 | 1.51 | 23.11 | 1358 | yes |
| tri_powerlaw | 500 000 | 2 | 0.62 | 0.99 | 0.77 | 0.80 | 0.33 | 1.51 | 5.60 | 0.70 | 11.40 | 2198 | yes |
| tri_large | 1 000 000 | 4 | 0.92 | 1.82 | 1.05 | 1.51 | 0.61 | 3.28 | 9.85 | 1.50 | 20.63 | 1358 | yes |
| tri_powerlaw | 500 000 | 4 | 0.51 | 0.95 | 0.70 | 0.88 | 0.33 | 1.70 | 4.78 | 0.72 | 10.65 | 2198 | yes |

Observations

* **1 → 2 tasks gives ~2× speed-up** on the large inputs (45.1 s → 23.1 s); 4 tasks on
  2 cores gives little more, as expected – on RCE with 4 separate nodes the scaling
  should continue.
* **Job 4 dominates** (≈55 % of the time): it handles the largest intermediate data –
  one record per wedge plus one per edge – and its map side sorts before the combiner.
  Degree ordering keeps the wedge count bounded; with plain id ordering the power-law
  graph would generate far more wedges around its hubs.
* For tiny inputs the fixed cost of launching 9 phases dominates (0.4–0.6 s), and more
  tasks make it slower – the usual MapReduce start-up overhead.
* Degree-ordered orientation makes the skewed power-law graph (500 k edges) cost about
  half of the 1 M-edge uniform graph, i.e. hubs do not cause blow-up.
