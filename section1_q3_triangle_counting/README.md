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
One-shot, from the repo root on the login node (all work runs in SLURM jobs):
`bash rce_run_all.sh` submits prep (tests + datasets) followed by the 1/2/4/8-task
scaling runs, and `bash rce_run_all.sh collect` prints the results. Manual steps:
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

### RCE cluster (SLURM, `debug` partition)

`perf_results/rce_summary.csv`: jobs 99468–99471, submitted by `rce_run_all.sh` at commit
`1115be7`, run one after another, each over all 5 datasets. The configurations were
1 node × 1 task, 2 × 2, 4 × 4 and 4 × 8 (two tasks per node). Every phase is a real `srun`
step across the allocated nodes. Intermediate data goes through the shared `/home`, and
the shuffle is a crc32 hash partition. Times are wall-clock seconds for one run each.
Speed-up is relative to 1 × 1 for the same input. Every run matched
`verify_sequential.py` (`ok` column).

| input | E | nodes × tasks | J1 map | J1 red | J2 map | J2 red | J3 map | J3 red | J4 map | J4 red | total | speed-up | triangles | ok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sample | 5 | 1 × 1 | 0.09 | 0.07 | 1.05 | 0.07 | 0.08 | 0.07 | 0.10 | 0.06 | **1.64** | 1.00× | 2 | yes |
| sample | 5 | 2 × 2 | 0.22 | 0.18 | 0.21 | 0.18 | 0.21 | 0.17 | 0.22 | 0.17 | **1.61** | 1.02× | 2 | yes |
| sample | 5 | 4 × 4 | 0.25 | 0.21 | 0.25 | 0.19 | 0.24 | 0.21 | 0.27 | 0.19 | **1.87** | 0.88× | 2 | yes |
| sample | 5 | 4 × 8 | 0.26 | 0.22 | 0.25 | 0.21 | 0.24 | 0.20 | 0.28 | 0.20 | **1.92** | 0.85× | 2 | yes |
| tri_small | 5,000 | 1 × 1 | 0.08 | 0.09 | 0.08 | 0.08 | 0.08 | 0.09 | 0.11 | 0.07 | **0.72** | 1.00× | 175 | yes |
| tri_small | 5,000 | 2 × 2 | 0.22 | 0.20 | 0.22 | 0.21 | 0.21 | 0.20 | 0.25 | 0.18 | **1.72** | 0.42× | 175 | yes |
| tri_small | 5,000 | 4 × 4 | 0.26 | 0.21 | 0.26 | 0.21 | 0.24 | 0.20 | 0.28 | 0.21 | **1.93** | 0.38× | 175 | yes |
| tri_small | 5,000 | 4 × 8 | 0.26 | 0.23 | 0.24 | 0.22 | 0.25 | 0.21 | 0.29 | 0.21 | **1.97** | 0.37× | 175 | yes |
| tri_medium | 100,000 | 1 × 1 | 0.31 | 0.34 | 0.28 | 0.31 | 0.16 | 0.40 | 1.25 | 0.41 | **3.52** | 1.00× | 1341 | yes |
| tri_medium | 100,000 | 2 × 2 | 0.44 | 0.45 | 0.40 | 0.44 | 0.29 | 0.53 | 1.41 | 0.56 | **4.59** | 0.77× | 1341 | yes |
| tri_medium | 100,000 | 4 × 4 | 0.39 | 0.36 | 0.36 | 0.35 | 0.30 | 0.42 | 0.92 | 0.43 | **3.62** | 0.97× | 1341 | yes |
| tri_medium | 100,000 | 4 × 8 | 0.32 | 0.29 | 0.31 | 0.28 | 0.27 | 0.31 | 0.59 | 0.33 | **2.79** | 1.26× | 1341 | yes |
| tri_large | 1,000,000 | 1 × 1 | 2.50 | 3.09 | 2.04 | 2.73 | 0.96 | 3.63 | 12.14 | 3.54 | **30.89** | 1.00× | 1358 | yes |
| tri_large | 1,000,000 | 2 × 2 | 2.60 | 3.07 | 2.20 | 2.86 | 1.12 | 4.00 | 12.21 | 3.95 | **32.27** | 0.96× | 1358 | yes |
| tri_large | 1,000,000 | 4 × 4 | 1.61 | 1.84 | 1.36 | 1.72 | 0.76 | 2.33 | 6.93 | 2.34 | **19.39** | 1.59× | 1358 | yes |
| tri_large | 1,000,000 | 4 × 8 | 0.95 | 1.06 | 0.81 | 1.01 | 0.51 | 1.28 | 3.55 | 1.29 | **10.77** | 2.87× | 1358 | yes |
| tri_powerlaw | 500,000 | 1 × 1 | 1.27 | 1.50 | 1.05 | 1.37 | 0.52 | 1.76 | 5.73 | 1.67 | **15.03** | 1.00× | 2198 | yes |
| tri_powerlaw | 500,000 | 2 × 2 | 1.40 | 1.61 | 1.19 | 1.50 | 0.66 | 2.00 | 5.83 | 1.92 | **16.27** | 0.92× | 2198 | yes |
| tri_powerlaw | 500,000 | 4 × 4 | 0.94 | 1.04 | 0.81 | 0.96 | 0.51 | 1.24 | 3.43 | 1.20 | **10.35** | 1.45× | 2198 | yes |
| tri_powerlaw | 500,000 | 4 × 8 | 0.60 | 0.64 | 0.53 | 0.61 | 0.38 | 0.73 | 1.86 | 0.74 | **6.26** | 2.40× | 2198 | yes |

Scaling of the total time on the two large graphs:

| nodes × tasks | tri_large (1 M edges) | speed-up | efficiency | tri_powerlaw (500 k edges) | speed-up | efficiency |
|---|---|---|---|---|---|---|
| 1 × 1 | 30.89 s | 1.00× | 100 % | 15.03 s | 1.00× | 100 % |
| 2 × 2 | 32.27 s | 0.96× | 48 % | 16.27 s | 0.92× | 46 % |
| 4 × 4 | 19.39 s | 1.59× | 40 % | 10.35 s | 1.45× | 36 % |
| 4 × 8 | 10.77 s | 2.87× | 36 % | 6.26 s | 2.40× | 30 % |

#### Scaling analysis

* **Correctness is independent of parallelism.** All 20 runs return the sequential
  count (2 / 175 / 1341 / 1358 / 2198). The degree-ordered orientation assigns each
  triangle to exactly one key, however the keys are hash-partitioned.
* **Large inputs scale, but sub-linearly.** On `tri_large`, 8 tasks are 2.87× faster
  than 1 task (30.9 s → 10.8 s). Job 4's map phase alone goes from 12.14 s to 3.55 s
  (3.4×). Efficiency drops to about 36 % because each MapReduce job has two barriers
  (map, then reduce). The slowest task sets each phase's time, and every job step pays
  the `srun` launch cost plus shared-filesystem I/O. With 4 jobs that is 8 barriers per
  input. The split and the final sum are serial (Amdahl), but they take < 0.4 s.
* **Job 4 dominates.** It takes about 51 % of the 1-task time (12.1 s map + 3.5 s reduce
  on `tri_large`), because its input holds one record per wedge plus one per edge. It is
  also the phase that benefits most from more tasks. The map-side `sort | combiner4.py`
  collapses repeated wedge keys before the shuffle, so the reduce side stays small
  (3.5 s → 1.3 s).
* **The 2 × 2 run was not faster than 1 × 1** (30.9 s vs 32.3 s on `tri_large`). Every
  phase stayed flat, including the trivially parallel Job 1 map (2.50 → 2.60 s). This is
  not load imbalance in the algorithm:
  * crc32 mod 2 splits `tri_large` 499 191 / 500 809.
  * The same driver on a single 4-core machine scales almost linearly: `tri_large` takes
    49.0 s / 23.7 s / 12.4 s with 1 / 2 / 4 tasks, and the Job 4 map takes
    26.6 / 13.0 / 6.4 s.

  So on RCE one of the two tasks was a straggler: a node slower or busier than the one
  used by the 1 × 1 run (the `debug` nodes are shared), and/or cold cross-node reads
  from the shared `/home`. Each configuration ran once, so this point is noisy; re-running
  `sbatch --nodes=2 --ntasks=2 run_distributed.sbatch tri_large.txt tri_powerlaw.txt`
  would confirm it.
* **Small inputs get slower with more tasks.** With 1 task a phase costs about 0.08 s.
  With ≥ 2 nodes it costs about 0.20–0.26 s even for 5 edges: that is the fixed cost of a
  multi-node `srun` step plus Python start-up. For `tri_small` (5 k edges) the total goes
  from 0.72 s to about 1.9 s. For `tri_medium` (100 k edges), 8 tasks only just pay off
  (1.26×). This is the classic MapReduce start-up overhead: it only amortises once each
  task has enough data (here roughly ≥ 10⁵ edges per task). The 1.05 s Job 2 map on the
  very first `sample.txt` run is a one-off cold start (first job step on a fresh node).
* **Skew is handled.** The power-law graph has half the edges of `tri_large` and costs
  about half the time at every scale (15.0 vs 30.9 s, 6.3 vs 10.8 s). Orienting edges
  from low to high degree keeps hub out-degrees small, so the hubs do not blow up the
  wedge count.

### 2-core sandbox (pipeline sanity check)

`perf_results/local_sandbox_summary.csv`, produced by `run_distributed.sbatch` with the
local fallback (no `srun`) on a **2-core** cloud machine. Times in seconds.

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
