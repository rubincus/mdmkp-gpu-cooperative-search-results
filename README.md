# Cooperative GPU tabu search for the MDMKP: solutions, data and verification

This repository holds the solutions, the run records and the verification scripts of the computational study of
COTS-GPU, a cooperative tabu search on a GPU, on 120 benchmark instances of the multi-demand multidimensional
knapsack problem (MDMKP) with 100, 500 and 1000 items. Every solution can be checked with the scripts included here,
which use only the Python standard library.

## Results

COTS-GPU performed independent runs with seeds 1, 2, ... on every instance (900 runs):

| Items | Instances | Runs per instance | Time limit | Best value above the published best |
|---:|---:|---:|---:|---:|
| 100 | 30 | 10 | 60 s | 5 |
| 500 | 30 | 10 | 600 s | 25 |
| 1000 | 60 | 5 | 600 s | 41 |

The published best of an instance is the largest best value published for it by TSTS, CORE-LP-LS-TSTS, CP-LB-MS and
AF, together with the best-known values (BKV) published for the instances with 500 items
(`data/reference_values.csv`). The best value of COTS-GPU exceeds the published best on 71 instances, 61
of them among the 104 instances that took no part in the design pilots or in the selection of the configuration
(`data/campaign/summary.csv`, columns `new_best` and `development`).

## Verify the solutions

Python 3.8 or later is required.

```sh
python scripts/download_instances.py
python scripts/verify_solutions.py
```

`download_instances.py` obtains the instances with 100 and 500 items from the archive `benchmark.zip` distributed by
Lai, Hao and Yue (2019), which contains the instances of Gortázar et al. (2010), and the instances with 1000 items
from the repository [samehShihabi/MKMP-instances-1000](https://github.com/samehShihabi/MKMP-instances-1000) at commit
`a962b7b`. It checks the SHA-256 of the archive and of every instance file against `data/instances_source.json`
and `data/instances.csv` and writes the instances to `instances/`. Local copies can be given with `--archive` and
`--dir1000`. The instances are not redistributed here.

`verify_solutions.py` re-reads every instance, checks every capacity row and every demand row of every solution, and
recomputes its profit and its number of items. It then checks that the run tables, the traces, the per-instance
summary, the best-solution files, the reference values and the isolation table agree with the verified solutions.
With `--isolation` it also recounts the feasible neighbours of the best solution of every instance, which takes a few
minutes. The evaluator has unit tests:

```sh
python -m unittest discover -s scripts
```

## Contents

- `data/instances.csv`: group, instance label used in the manuscript, file, source, size, SHA-256 and dimensions of
  every instance; `data/instances_source.json`: the two sources.
- `data/development_instances.csv`: the 16 instances used in the design pilots or in the selection of the
  configuration, with the stages that used them. They are marked with a dagger in the tables of the manuscript and
  left out of its comparison on the remaining instances.
- `data/reference_values.csv`: the best value and the average published for each method, exactly as printed in the
  source tables, the published best and the methods that attain it; `data/reference_sources.csv` gives the source
  table of each column. 7 published values contradict the other values published for their instance; the column
  `inconsistent` lists them, and they are left out of the published best and of the comparisons of the manuscript.
- `data/campaign/`: `runs.csv` (one row per run: profit, number of items, time at which the run reaches its best
  value, wall time, iterations summed over the trajectories, number of trajectories and of intensifiers, time limit,
  and the SHA-256 of the kernel and host files), `traces.csv` (every improvement of the best value of each run, with
  the trajectory that found it and its role) and `summary.csv` (one row per instance).
- The mechanism experiments of the manuscript, on six instances with 1000 items, with `data/variants.csv` describing
  every variant and the runs it is paired with:
  - `data/ablation/`: 5 variants that each remove or restrict one component, on 6 instances with seeds 1 to 3 and runs of 600 s (90 runs).
  - `data/interaction/`: 2 variants that remove two components, on 6 instances with seeds 1 to 3 and runs of 600 s (36 runs).
  - `data/sensitivity/`: 8 variants that each change one parameter, on 6 instances with seeds 1 to 2 and runs of 600 s (96 runs).
  - `data/behaviour/`: the reference configuration on the same 6 instances with seed 1 and runs of 600 s, sampled every 5 s without altering the search (`samples.csv`; 6 runs).
  - `data/tuning/`: the two rounds of the selection of the configuration, each with a screening and a confirmation, on 13 instances with seeds 1 to 3 and runs of 120 s or 600 s (234 runs).
- `data/isolation.csv`: for the best solution of every instance, the size of its add/drop/swap neighbourhood, the
  number of feasible neighbours and the number of feasible neighbours with a higher profit.
- `data/code_digests.csv`: the SHA-256 digests of the kernel and host files used by each experiment.
- `solutions/`: the solution of every run, as selected items numbered from 0, in one file per experiment;
  `best/n<items>_<instance>.json` holds the best solution of each instance (the smallest seed attaining the best value
  of the campaign).
- `PUBLIC_EXPORT_MANIFEST.json`: export date, number of runs of each experiment and SHA-256 of every file.

The implementation of COTS-GPU is maintained separately; `data/code_digests.csv` identifies the kernel and host files
of every run.

## References

- Al-Shihabi, S., 2021. A novel core-based optimization framework for binary integer programs: the multidemand
  multidimensional knapsack problem as a test problem. Operations Research Perspectives 8, 100182.
  https://doi.org/10.1016/j.orp.2021.100182
- Al-Shihabi, S., 2025. An optimization framework for solving large scale multidemand multidimensional knapsack
  problem instances employing a novel core identification heuristic. European Journal of Operational Research 320,
  496-504. https://doi.org/10.1016/j.ejor.2024.08.025
- Cattarinich, I., Rojas-Vivanco, J., Minatogawa, V., Gornall, J., Garcia, J., 2026. An adaptive fuzzy-penalty swarm
  metaheuristic for the multi-demand multidimensional knapsack problem. Applied Soft Computing 202, 115946.
  https://doi.org/10.1016/j.asoc.2026.115946
- Gortázar, F., Duarte, A., Laguna, M., Martí, R., 2010. Black box scatter search for general classes of binary
  optimization problems. Computers & Operations Research 37, 1977-1986. https://doi.org/10.1016/j.cor.2010.01.013
- Lai, X., Hao, J.-K., Yue, D., 2019. Two-stage solution-based tabu search for the multidemand multidimensional
  knapsack problem. European Journal of Operational Research 274, 35-48. https://doi.org/10.1016/j.ejor.2018.10.001
