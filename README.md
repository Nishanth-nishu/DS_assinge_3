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

# Section 1 Q3
cd section1_q3_triangle_counting && ./run_tests.sh && ./make_datasets.sh && sbatch run_distributed.sbatch

# Section 3 P2
cd ../section3_q2_food_ordering && ./setup.sh && python3 test_food_ordering.py && sbatch run_demo.sbatch
```
