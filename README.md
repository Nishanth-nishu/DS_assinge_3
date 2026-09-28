# Distributed Systems – Homework 3

| Part | Folder | What |
|---|---|---|
| Section 1 – Q3 | [`section1_q3_triangle_counting/`](section1_q3_triangle_counting/) | Triangle counting with a 4-job MapReduce pipeline (local, SLURM multi-node, Hadoop Streaming) |
| Section 3 – Problem 2 | [`section3_q2_food_ordering/`](section3_q2_food_ordering/) | Food Ordering System using gRPC (server, customer & restaurant CLIs, streaming updates) |

Each folder has its own README with design, run instructions (local and RCE/SLURM),
correctness verification and results.

## Quick start on RCE
```bash
ssh <user>@rce.iiit.ac.in            # IIIT network or VPN
git clone https://github.com/Nishanth-nishu/DS_assinge_3.git && cd DS_assinge_3

bash rce_run_all.sh            # only submits SLURM jobs (nothing runs on the login node)
squeue -u $USER                # wait until empty
bash rce_run_all.sh collect    # print results
```
`rce_prep.sbatch` (installs gRPC if needed, generates stubs, runs the correctness tests,
builds the datasets) runs first on a compute node; the triangle-counting scaling runs
(1/2/4/8 tasks) and the 3-node gRPC demo + tests start only after it succeeds.
