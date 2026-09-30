# TPC-C-derived speculative New-Order workload

This workload uses the TPC-C data model and New-Order access pattern as a
public, transaction-oriented anchor. It is **not** a compliant or audited TPC-C
run, and no result from this directory may be labelled tpmC or an official
TPC-C result.

## Candidate transformation

One logical purchase intent expands into `k` candidate fulfilment plans. All
candidates share reads of `warehouse`, `district`, and `customer`; each then
uses a different `(item, supplying warehouse)` alternative and writes a private
candidate-order record. `stock` is the controlled hot write set.

```text
New-Order intent
  ├─ shared: warehouse + district + customer + tax/discount rule
  ├─ candidate 1: local stock, requested item
  ├─ candidate 2: alternate supplying warehouse
  ├─ candidate 3: substitute item
  └─ candidate n: deterministic combination of both
```

The three protocols will be evaluated on exactly the same generated candidate
sets: 2PL, OCC, and Reuse-OCC. Reuse-OCC may share only the common discovery
result and must validate observed `w_version`, `d_version`, and `c_version`
before writing a candidate result.

## Planned measurements

* throughput, P50/P95 latency, completed candidates;
* 2PL lock wait, OCC abort/retry count, and Reuse-OCC cache hit/invalidation;
* final `stock.s_quantity >= 0` and exactly-once candidate-order insertion;
* shared discovery executions versus independent executions;
* candidate count 1/2/4/8/16, warehouse count 1/4/16, and hot-item count
  1/2/8/32.

The schema file is intentionally separated from the travel microbenchmark so
that both workloads can coexist in one PostgreSQL instance without state reuse.

## First runnable configuration

From WSL, after starting the PostgreSQL container and activating
`branchlab/.venv-wsl`:

```bash
python -m branchlab.tpcc_runner setup
python -m branchlab.tpcc_runner run --mode 2pl --workers 4 --tasks 20 --candidates 4 --hot-items 2 --discovery-ms 20 --think-ms 5 --seed 1
python -m branchlab.tpcc_runner setup
python -m branchlab.tpcc_runner run --mode occ --workers 4 --tasks 20 --candidates 4 --hot-items 2 --discovery-ms 20 --think-ms 5 --seed 1
python -m branchlab.tpcc_runner setup
python -m branchlab.tpcc_runner run --mode reuse --workers 4 --tasks 20 --candidates 4 --hot-items 2 --discovery-ms 20 --think-ms 5 --seed 1
```

`tpcc_runner.py` checks that no stock quantity is negative; each protocol
receives the same initialized data and seed. The initial dataset size is kept
small for fast functional validation and must be increased before reporting
final performance conclusions.
